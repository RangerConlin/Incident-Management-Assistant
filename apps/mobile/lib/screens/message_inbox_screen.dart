import 'dart:async';

import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../services/chat_presence_service.dart';
import '../services/chat_service.dart';
import '../theme/app_theme.dart';
import '../utils/date_format.dart';
import '../utils/session_identity.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';

// How often to re-poll who's online. Presence is a staleness computation
// the server can only do at request time (see PRESENCE_STALE_AFTER_SECONDS
// in chat.py) — there's no live "went offline" event to listen for instead.
// Mirrors the desktop client's ChatWindow poll interval.
const _presencePollInterval = Duration(seconds: 15);

/// Mobile incident chat wired to the same chat collections and incident
/// WebSocket the desktop client uses.
class MessageInboxScreen extends StatefulWidget {
  const MessageInboxScreen({super.key, required this.args, ChatService? chatService})
    : _injectedChatService = chatService;

  final HomeNavArgs args;
  final ChatService? _injectedChatService;

  @override
  State<MessageInboxScreen> createState() => _MessageInboxScreenState();
}

class _MessageInboxScreenState extends State<MessageInboxScreen> {
  static const double _wideLayoutBreakpoint = 720;

  late final ChatService _chatService =
      widget._injectedChatService ?? ChatService();
  late final bool _ownsChatService = widget._injectedChatService == null;
  final TextEditingController _messageController = TextEditingController();

  StreamSubscription<ChatMessage>? _liveSubscription;
  Timer? _presenceTimer;
  List<ChatChannel> _channels = const [];
  List<ChatMessage> _messages = const [];
  Map<String, String> _displayNames = const {};
  Map<String, String> _presenceByUser = const {};
  String? _activeChannelId;
  bool _loadingChannels = true;
  bool _loadingMessages = false;
  bool _sending = false;
  String? _errorMessage;

  String get _currentUserId =>
      SessionIdentity.personId(widget.args.session);

  String get _currentUserDisplayName =>
      SessionIdentity.displayName(widget.args.session);

  ChatChannel? get _activeChannel {
    final activeChannelId = _activeChannelId;
    if (activeChannelId == null) return null;
    for (final channel in _channels) {
      if (channel.id == activeChannelId) {
        return channel;
      }
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _loadChannels();
    _loadDisplayNames();
    _refreshPresence();
    _presenceTimer = Timer.periodic(
      _presencePollInterval,
      (_) => _refreshPresence(),
    );
  }

  @override
  void dispose() {
    _liveSubscription?.cancel();
    _presenceTimer?.cancel();
    _messageController.dispose();
    if (_ownsChatService) {
      _chatService.dispose();
    } else {
      _chatService.disconnect();
    }
    super.dispose();
  }

  Future<void> _loadChannels() async {
    if (_currentUserId.isEmpty) {
      setState(() {
        _loadingChannels = false;
        _errorMessage = 'Chat is unavailable until you are signed in.';
      });
      return;
    }

    setState(() {
      _loadingChannels = true;
      _errorMessage = null;
    });

    try {
      final channels = await _chatService.listChannels(
        widget.args.incidentId,
        userId: _currentUserId,
      );
      if (!mounted) return;

      final nextActiveChannelId = _chooseActiveChannelId(channels);
      setState(() {
        _channels = channels;
        _activeChannelId = nextActiveChannelId;
        _loadingChannels = false;
      });

      if (nextActiveChannelId != null) {
        await _loadMessagesForChannel(nextActiveChannelId);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingChannels = false;
        _errorMessage = 'Unable to load chat channels.';
      });
    }
  }

  String? _chooseActiveChannelId(List<ChatChannel> channels) {
    if (channels.isEmpty) return null;
    final existing = _activeChannelId;
    if (existing != null) {
      for (final channel in channels) {
        if (channel.id == existing) return existing;
      }
    }
    for (final channel in channels) {
      if ((channel.name ?? '').trim().toLowerCase() == 'general') {
        return channel.id;
      }
    }
    return channels.first.id;
  }

  Future<void> _loadMessagesForChannel(String channelId) async {
    setState(() {
      _loadingMessages = true;
      _errorMessage = null;
    });

    try {
      final messages = await _chatService.fetchHistory(
        widget.args.incidentId,
        channelId: channelId,
      );
      if (!mounted) return;
      setState(() {
        _messages = _dedupeMessages(messages);
        _loadingMessages = false;
      });
      _connectLive(channelId);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages = const [];
        _loadingMessages = false;
        _errorMessage = 'Unable to load messages for this channel.';
      });
    }
  }

  void _connectLive(String channelId) {
    _liveSubscription?.cancel();
    _liveSubscription = _chatService
        .connect(widget.args.incidentId, channelId: channelId)
        .listen(
          (message) {
            if (!mounted) return;
            setState(() {
              _messages = _dedupeMessages([..._messages, message]);
            });
          },
        );
  }

  List<ChatMessage> _dedupeMessages(List<ChatMessage> messages) {
    final byId = <String, ChatMessage>{};
    for (final message in messages) {
      byId[message.id] = message;
    }
    final deduped = byId.values.toList()
      ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return deduped;
  }

  Future<void> _selectChannel(String channelId) async {
    if (_activeChannelId == channelId) return;
    setState(() {
      _activeChannelId = channelId;
      _messages = const [];
    });
    await _loadMessagesForChannel(channelId);
  }

  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    final activeChannelId = _activeChannelId;
    if (text.isEmpty || activeChannelId == null || _currentUserId.isEmpty) {
      return;
    }

    setState(() => _sending = true);
    try {
      await _chatService.sendMessage(
        widget.args.incidentId,
        channelId: activeChannelId,
        senderId: _currentUserId,
        senderName: _currentUserDisplayName.isEmpty
            ? null
            : _currentUserDisplayName,
        text: text,
      );
      if (!mounted) return;
      _messageController.clear();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to send message.')),
      );
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  Future<void> _loadDisplayNames() async {
    try {
      final names = await _chatService.fetchDisplayNames(
        widget.args.incidentId,
      );
      if (!mounted) return;
      setState(() => _displayNames = names);
    } catch (_) {
      // Best-effort — DM titles/roster entries fall back to raw ids.
    }
  }

  Future<void> _refreshPresence() async {
    try {
      final entries = await _chatService.listPresence(widget.args.incidentId);
      if (!mounted) return;
      setState(() {
        _presenceByUser = {
          for (final entry in entries)
            if (entry.userId != _currentUserId) entry.userId: entry.status,
        };
      });
    } catch (_) {
      // Best-effort — keep the last known roster rather than clearing it on
      // a transient network error.
    }
  }

  /// Display title for a channel, resolving a DM's other participant id to
  /// their real name via `_displayNames` when available (falls back to the
  /// raw id, same as `ChatChannel.displayTitleFor`).
  String _channelTitle(ChatChannel channel) {
    if (!channel.isDirectMessage) {
      return channel.displayTitleFor(_currentUserId);
    }
    final otherId = channel.participantIds.firstWhere(
      (participant) => participant != _currentUserId,
      orElse: () => '',
    );
    if (otherId.isEmpty) return 'Direct Message';
    return _displayNames[otherId] ?? otherId;
  }

  String? _presenceStatusFor(ChatChannel channel) {
    if (!channel.isDirectMessage) return null;
    final otherId = channel.participantIds.firstWhere(
      (participant) => participant != _currentUserId,
      orElse: () => '',
    );
    if (otherId.isEmpty) return null;
    return _presenceByUser[otherId];
  }

  Future<void> _showNewChannelDialog() async {
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('New Channel'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Channel name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty || _currentUserId.isEmpty) return;

    try {
      final channel = await _chatService.createChannel(
        widget.args.incidentId,
        name: name,
        createdBy: _currentUserId,
      );
      if (!mounted) return;
      setState(() => _channels = [..._channels, channel]);
      await _selectChannel(channel.id);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Failed to create channel.')));
    }
  }

  Future<void> _showNewDirectMessageSheet() async {
    if (_displayNames.isEmpty) {
      await _loadDisplayNames();
    }
    if (!mounted) return;

    final candidates = _displayNames.entries
        .where((entry) => entry.key != _currentUserId)
        .toList()
      ..sort((a, b) => a.value.toLowerCase().compareTo(b.value.toLowerCase()));

    final selected = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) {
        if (candidates.isEmpty) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Text('No one else is checked in to this incident yet.'),
          );
        }
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              for (final entry in candidates)
                ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(entry.value),
                  onTap: () => Navigator.pop(sheetContext, entry.key),
                ),
            ],
          ),
        );
      },
    );
    if (selected != null) {
      await _startDirectMessage(selected);
    }
  }

  Future<void> _startDirectMessage(String otherUserId) async {
    if (_currentUserId.isEmpty) return;
    try {
      final channel = await _chatService.findOrCreateDm(
        widget.args.incidentId,
        userA: _currentUserId,
        userB: otherUserId,
      );
      if (!mounted) return;
      setState(() {
        if (!_channels.any((existing) => existing.id == channel.id)) {
          _channels = [..._channels, channel];
        }
      });
      await _selectChannel(channel.id);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to start direct message.')),
      );
    }
  }

  String _statusLabel(String status) => switch (status) {
    'away' => 'Away',
    'unavailable' => 'Unavailable',
    _ => 'Online',
  };

  Future<void> _showPeopleSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Your status',
                  style: Theme.of(sheetContext).textTheme.labelLarge,
                ),
                const SizedBox(height: 8),
                ValueListenableBuilder<String>(
                  valueListenable: ChatPresenceService.status,
                  builder: (context, status, _) => SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'online', label: Text('Online')),
                      ButtonSegment(value: 'away', label: Text('Away')),
                      ButtonSegment(
                        value: 'unavailable',
                        label: Text('Unavailable'),
                      ),
                    ],
                    selected: {status},
                    onSelectionChanged: (selection) =>
                        ChatPresenceService.setStatus(selection.first),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'Online',
                  style: Theme.of(sheetContext).textTheme.labelLarge,
                ),
                const SizedBox(height: 4),
                if (_presenceByUser.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('No one else is online right now.'),
                  )
                else
                  ..._presenceByUser.entries.map(
                    (entry) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        Icons.circle,
                        size: 12,
                        color: PresenceStatusColors.forStatus(entry.value),
                      ),
                      title: Text(_displayNames[entry.key] ?? entry.key),
                      subtitle: Text(_statusLabel(entry.value)),
                      onTap: () {
                        Navigator.pop(sheetContext);
                        _startDirectMessage(entry.key);
                      },
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Messages'),
        actions: [
          IconButton(
            icon: const Icon(Icons.people_outline),
            tooltip: 'People',
            onPressed: _showPeopleSheet,
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.add),
            tooltip: 'New',
            onSelected: (value) {
              if (value == 'channel') _showNewChannelDialog();
              if (value == 'dm') _showNewDirectMessageSheet();
            },
            itemBuilder: (context) => const [
              PopupMenuItem(value: 'channel', child: Text('New Channel')),
              PopupMenuItem(value: 'dm', child: Text('New Direct Message')),
            ],
          ),
        ],
      ),
      drawer: AppDrawer(args: widget.args),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= _wideLayoutBreakpoint;
          if (wide) {
            return _buildWideLayout(context);
          }
          return _buildPhoneLayout(context);
        },
      ),
      bottomNavigationBar: AppBottomNav(current: AppTab.messages, args: widget.args),
    );
  }

  Widget _buildPhoneLayout(BuildContext context) {
    return Column(
      children: [
        _buildBanner(context),
        _buildChannelChips(context),
        const Divider(height: 1),
        Expanded(child: _buildThread(context)),
        _buildComposer(context),
      ],
    );
  }

  Widget _buildWideLayout(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 280,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildBanner(context),
              Expanded(child: _buildChannelList(context)),
            ],
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: Column(
            children: [
              _buildThreadHeader(context),
              const Divider(height: 1),
              Expanded(child: _buildThread(context)),
              _buildComposer(context),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildBanner(BuildContext context) {
    final theme = Theme.of(context);
    if (_errorMessage != null) {
      return Material(
        color: theme.colorScheme.errorContainer,
        child: ListTile(
          leading: Icon(Icons.warning_amber, color: theme.colorScheme.onErrorContainer),
          title: Text(
            _errorMessage!,
            style: TextStyle(color: theme.colorScheme.onErrorContainer),
          ),
          trailing: TextButton(
            onPressed: _loadChannels,
            child: const Text('Retry'),
          ),
        ),
      );
    }
    return Material(
      color: theme.colorScheme.surfaceContainerHigh,
      child: ListTile(
        dense: true,
        leading: const Icon(Icons.chat_bubble_outline),
        title: Text(
          _activeChannel != null
              ? _channelTitle(_activeChannel!)
              : 'Incident chat',
        ),
        subtitle: Text(widget.args.incidentName),
      ),
    );
  }

  Widget _buildChannelChips(BuildContext context) {
    if (_loadingChannels) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: LinearProgressIndicator(),
      );
    }
    if (_channels.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('No chat channels are available for this incident.'),
      );
    }
    return SizedBox(
      height: 56,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        itemCount: _channels.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final channel = _channels[index];
          final status = _presenceStatusFor(channel);
          return ChoiceChip(
            avatar: status != null
                ? CircleAvatar(
                    backgroundColor: PresenceStatusColors.forStatus(status),
                    radius: 6,
                  )
                : null,
            label: Text(_channelTitle(channel)),
            selected: channel.id == _activeChannelId,
            onSelected: (_) => _selectChannel(channel.id),
          );
        },
      ),
    );
  }

  Widget _buildChannelList(BuildContext context) {
    if (_loadingChannels) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_channels.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('No chat channels are available for this incident.'),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: _channels.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final channel = _channels[index];
        final selected = channel.id == _activeChannelId;
        final status = _presenceStatusFor(channel);
        return ListTile(
          selected: selected,
          leading: Icon(
            channel.isDirectMessage ? Icons.person_outline : Icons.forum_outlined,
            color: status != null ? PresenceStatusColors.forStatus(status) : null,
          ),
          title: Text(_channelTitle(channel)),
          onTap: () => _selectChannel(channel.id),
        );
      },
    );
  }

  Widget _buildThreadHeader(BuildContext context) {
    final channel = _activeChannel;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Text(
        channel != null ? _channelTitle(channel) : 'Select a channel',
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );
  }

  Widget _buildThread(BuildContext context) {
    if (_loadingChannels) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_activeChannelId == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('Select a channel to view incident chat.'),
        ),
      );
    }
    if (_loadingMessages) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_messages.isEmpty) {
      return RefreshIndicator(
        onRefresh: () => _loadMessagesForChannel(_activeChannelId!),
        child: ListView(
          children: const [
            SizedBox(height: 140),
            Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text('No messages yet in this channel.'),
              ),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: () => _loadMessagesForChannel(_activeChannelId!),
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: _messages.length,
        itemBuilder: (context, index) {
          final message = _messages[index];
          return _ChatMessageCard(
            message: message,
            isOwnMessage: message.senderId == _currentUserId,
          );
        },
      ),
    );
  }

  Widget _buildComposer(BuildContext context) {
    final disabled = _activeChannelId == null || _sending || _currentUserId.isEmpty;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _messageController,
                enabled: !disabled,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendMessage(),
                decoration: const InputDecoration(
                  labelText: 'Message',
                  hintText: 'Send an incident update',
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
              onPressed: disabled ? null : _sendMessage,
              icon: _sending
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send),
              label: const Text('Send'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatMessageCard extends StatelessWidget {
  const _ChatMessageCard({required this.message, required this.isOwnMessage});

  final ChatMessage message;
  final bool isOwnMessage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final backgroundColor = isOwnMessage
        ? theme.colorScheme.primaryContainer
        : theme.colorScheme.surfaceContainerHigh;
    final foregroundColor = isOwnMessage
        ? theme.colorScheme.onPrimaryContainer
        : theme.colorScheme.onSurface;

    return Align(
      alignment: isOwnMessage ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Card(
          margin: const EdgeInsets.symmetric(vertical: 4),
          color: backgroundColor,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  message.senderName?.trim().isNotEmpty == true
                      ? message.senderName!
                      : message.senderId,
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: foregroundColor,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  message.text,
                  style: theme.textTheme.bodyMedium?.copyWith(color: foregroundColor),
                ),
                const SizedBox(height: 8),
                Text(
                  formatTimeOnly(message.createdAt.toLocal()),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: foregroundColor.withValues(alpha: 0.75),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
