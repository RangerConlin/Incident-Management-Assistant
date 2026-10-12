import 'dart:async';

import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../services/chat_service.dart';
import '../utils/date_format.dart';
import '../utils/session_identity.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';

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
  List<ChatChannel> _channels = const [];
  List<ChatMessage> _messages = const [];
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
  }

  @override
  void dispose() {
    _liveSubscription?.cancel();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Messages')),
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
          _activeChannel?.displayTitleFor(_currentUserId) ?? 'Incident chat',
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
          return ChoiceChip(
            label: Text(channel.displayTitleFor(_currentUserId)),
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
        return ListTile(
          selected: selected,
          leading: Icon(
            channel.isDirectMessage ? Icons.person_outline : Icons.forum_outlined,
          ),
          title: Text(channel.displayTitleFor(_currentUserId)),
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
        channel?.displayTitleFor(_currentUserId) ?? 'Select a channel',
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
