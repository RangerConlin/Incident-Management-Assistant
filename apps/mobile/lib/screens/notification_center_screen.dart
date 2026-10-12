import 'package:flutter/material.dart';

import '../models/app_notification.dart';
import '../services/notification_presenter.dart';
import '../services/notification_store.dart';
import '../utils/date_format.dart';

/// In-app notification history. This is a device-local inbox populated as
/// FCM messages arrive (see `PushNotificationService._captureMessage`) —
/// there is no server-side notification feed to page through yet, so this
/// shows only what this device has actually received since its last clear.
/// Severity/category coloring mirrors the desktop repo's notification feed
/// panel so the same notification looks the same on both clients.
class NotificationCenterScreen extends StatefulWidget {
  const NotificationCenterScreen({super.key});

  @override
  State<NotificationCenterScreen> createState() =>
      _NotificationCenterScreenState();
}

class _NotificationCenterScreenState extends State<NotificationCenterScreen> {
  List<AppNotification> _items = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final items = await NotificationStore.load();
    if (!mounted) return;
    setState(() {
      _items = items;
      _loading = false;
    });
  }

  Future<void> _markAllRead() async {
    await NotificationStore.markAllRead();
    await _load();
  }

  Future<void> _clearAll() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear all notifications?'),
        content: const Text(
          'This removes every notification from this device. It cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await NotificationStore.clear();
    await _load();
  }

  Future<void> _onTap(AppNotification item) async {
    if (!item.read) {
      await NotificationStore.markRead(item.id);
      await _load();
    }
    await NotificationPresenter.openNotification(item);
  }

  Future<void> _onDismiss(AppNotification item) async {
    await NotificationStore.remove(item.id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final hasUnread = _items.any((e) => !e.read);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (hasUnread)
            IconButton(
              tooltip: 'Mark all read',
              icon: const Icon(Icons.done_all),
              onPressed: _markAllRead,
            ),
          if (_items.isNotEmpty)
            IconButton(
              tooltip: 'Clear all',
              icon: const Icon(Icons.delete_sweep_outlined),
              onPressed: _clearAll,
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
          ? const _EmptyState()
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.separated(
                itemCount: _items.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final item = _items[index];
                  final accent = Color(
                    NotificationSeverity.accentColorValue(item.severity),
                  );
                  final categoryColor = Color(
                    NotificationCategory.accentColorValue(item.category),
                  );
                  final categoryShort = NotificationCategory.shortLabel(
                    item.category,
                  );
                  return Dismissible(
                    key: ValueKey(item.id),
                    direction: DismissDirection.endToStart,
                    background: Container(
                      color: Theme.of(context).colorScheme.errorContainer,
                      alignment: Alignment.centerRight,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Icon(
                        Icons.delete_outline,
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                    ),
                    onDismissed: (_) => _onDismiss(item),
                    child: Container(
                      decoration: BoxDecoration(
                        border: Border(left: BorderSide(color: accent, width: 3)),
                      ),
                      child: ListTile(
                        leading: Icon(
                          item.read
                              ? Icons.notifications_none
                              : Icons.notifications_active,
                          color: item.read ? null : accent,
                        ),
                        title: Row(
                          children: [
                            if (categoryShort.isNotEmpty) ...[
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 4,
                                  vertical: 1,
                                ),
                                decoration: BoxDecoration(
                                  border: Border.all(color: categoryColor),
                                  borderRadius: BorderRadius.circular(3),
                                ),
                                child: Text(
                                  categoryShort,
                                  style: TextStyle(
                                    color: categoryColor,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 6),
                            ],
                            Expanded(
                              child: Text(
                                item.title,
                                style: item.read
                                    ? null
                                    : const TextStyle(
                                        fontWeight: FontWeight.bold,
                                      ),
                              ),
                            ),
                          ],
                        ),
                        subtitle: Text(
                          item.body.isEmpty
                              ? NotificationCategory.label(item.category)
                              : item.body,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing: Text(
                          relativeTime(item.receivedAt),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        onTap: () => _onTap(item),
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.notifications_off_outlined,
              size: 48,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 12),
            const Text(
              'No notifications yet',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              'Task assignments, command broadcasts, and chat alerts will show up here.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
