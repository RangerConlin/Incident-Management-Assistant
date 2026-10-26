import 'dart:async';

import 'package:flutter/material.dart';

import '../models/app_notification.dart';
import '../models/home_nav_args.dart';
import '../models/task.dart';
import '../screens/notification_center_screen.dart';
import '../screens/task_detail_screen.dart';
import '../screens/team_management_screen.dart';
import '../widgets/notification_banner.dart';
import 'app_navigation.dart';
import 'notification_sound.dart';
import 'sarapp_api_client.dart';
import 'session_store.dart';

/// Decides how an incoming notification should actually appear on screen —
/// the part `PushNotificationService` doesn't own. Severity drives the
/// presentation (ported from the desktop repo's toast-mode resolution, see
/// `ToastPlan` in `app_notification.dart`): routine/priority show a
/// transient top-of-screen banner; `emergency` shows a blocking dialog the
/// user must acknowledge or dismiss, since that's the broadcast-alert case
/// (evacuate, radio silence) the Phase 5 design doc calls for an
/// unmissable response to.
class NotificationPresenter {
  NotificationPresenter._();

  static OverlayEntry? _bannerEntry;

  /// Shows [notification] in-app if its [ToastPlan] calls for it. Safe to
  /// call for any notification — one below its category's toast threshold
  /// (e.g. a routine administrative notice) simply does nothing visible,
  /// matching the desktop repo's "still reaches the feed, never pops"
  /// behavior.
  static void present(AppNotification notification) {
    final plan = ToastPlan.resolve(
      severity: notification.severity,
      category: notification.category,
    );
    if (!plan.show) return;

    if (plan.sound) unawaited(NotificationSound.play(notification.severity));

    if (plan.sticky) {
      _showEmergencyDialog(notification);
    } else {
      _showBanner(notification, plan);
    }
  }

  static void _showBanner(AppNotification notification, ToastPlan plan) {
    final context = AppNavigation.currentContext;
    if (context == null) return;
    final overlay = Overlay.of(context, rootOverlay: true);

    _bannerEntry?.remove();
    late OverlayEntry entry;
    void dismiss() {
      entry.remove();
      if (identical(_bannerEntry, entry)) _bannerEntry = null;
    }

    entry = OverlayEntry(
      builder: (context) => Positioned(
        top: MediaQuery.of(context).padding.top + 8,
        left: 12,
        right: 12,
        child: _BannerWithAutoDismiss(
          notification: notification,
          durationMs: plan.durationMs,
          onDismiss: dismiss,
          onTap: () {
            dismiss();
            openNotification(notification);
          },
        ),
      ),
    );
    _bannerEntry = entry;
    overlay.insert(entry);
  }

  static void _showEmergencyDialog(AppNotification notification) {
    final context = AppNavigation.currentContext;
    if (context == null) return;

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return AlertDialog(
          icon: const Icon(Icons.warning_amber_rounded, color: Colors.red),
          title: Text(notification.title),
          content: Text(notification.body),
          actions: [
            TextButton(
              onPressed: () async {
                Navigator.of(dialogContext).pop();
                await _dismiss(notification);
              },
              child: const Text('Dismiss'),
            ),
            FilledButton(
              onPressed: () async {
                Navigator.of(dialogContext).pop();
                if (notification.requiresAcknowledgement) {
                  await _acknowledge(notification);
                } else {
                  await _dismiss(notification);
                }
                openNotification(notification);
              },
              child: Text(
                notification.requiresAcknowledgement ? 'Acknowledge' : 'View',
              ),
            ),
          ],
        );
      },
    );
  }

  static Future<void> _acknowledge(AppNotification notification) =>
      _sendResponse(notification, acknowledge: true);

  static Future<void> _dismiss(AppNotification notification) =>
      _sendResponse(notification, acknowledge: false);

  /// Best-effort — a failed acknowledge/dismiss call must never block the
  /// user from moving on; the notification already reached the device, and
  /// the server-side record (source of truth) can be reconciled later.
  static Future<void> _sendResponse(
    AppNotification notification, {
    required bool acknowledge,
  }) async {
    final notificationId = notification.notificationId;
    final incidentId = notification.incidentId;
    if (notificationId == null || incidentId == null) return;

    final saved = await SessionStore.load();
    final rawPersonRecord = saved?.session['person_record'];
    final personRecord = rawPersonRecord is int
        ? rawPersonRecord
        : int.tryParse('$rawPersonRecord');
    if (personRecord == null) return;

    final client = SarAppApiClient();
    try {
      if (acknowledge) {
        await client.acknowledgeNotification(
          incidentId: incidentId,
          notificationId: notificationId,
          personRecord: personRecord,
        );
      } else {
        await client.dismissNotification(
          incidentId: incidentId,
          notificationId: notificationId,
          personRecord: personRecord,
        );
      }
    } catch (e) {
      debugPrint(
        'NotificationPresenter: ${acknowledge ? 'acknowledge' : 'dismiss'} failed: $e',
      );
    } finally {
      client.dispose();
    }
  }

  /// Deep-links to the screen [notification] is about when possible,
  /// falling back to the Notification Center. Only resolves a deep link
  /// when the device's active session matches the notification's incident
  /// — a push can arrive for an incident the user isn't currently in (or
  /// isn't signed into at all), in which case there's nothing sensible to
  /// open besides the history list.
  static Future<void> openNotification(AppNotification notification) async {
    final navigator = AppNavigation.navigatorKey.currentState;
    if (navigator == null) return;

    final saved = await SessionStore.load();
    final sameIncident =
        saved != null &&
        (notification.incidentId == null ||
            saved.incidentId == notification.incidentId);

    if (saved != null && sameIncident && notification.sourceType != null) {
      final args = HomeNavArgs(
        incidentId: saved.incidentId,
        incidentName: saved.incidentName,
        teamId: saved.teamId,
        teamName: saved.teamName,
        session: saved.session,
        incidentType: saved.incidentType,
      );
      final opened = await _openDeepLink(navigator, notification, args);
      if (opened) return;
    }

    navigator.push(
      MaterialPageRoute(builder: (_) => const NotificationCenterScreen()),
    );
  }

  /// Returns true if a specific screen for [notification.sourceType] was
  /// opened; false means the caller should fall back to the Notification
  /// Center (unrecognized source type, or the referenced record no longer
  /// fetches).
  static Future<bool> _openDeepLink(
    NavigatorState navigator,
    AppNotification notification,
    HomeNavArgs args,
  ) async {
    final sourceId = notification.sourceId;
    if (sourceId == null) return false;

    switch (notification.sourceType) {
      case 'task':
        final client = SarAppApiClient();
        try {
          final raw = await client.fetchTask(args.incidentId, sourceId);
          final task = Task.fromJson(raw);
          navigator.push(
            MaterialPageRoute(
              builder: (_) => TaskDetailScreen(task: task, args: args),
            ),
          );
          return true;
        } catch (e) {
          debugPrint('NotificationPresenter: task deep link failed: $e');
          return false;
        } finally {
          client.dispose();
        }
      case 'team':
        navigator.push(
          MaterialPageRoute(builder: (_) => TeamManagementScreen(args: args)),
        );
        return true;
      default:
        return false;
    }
  }
}

/// Wraps [NotificationBannerCard] with its own auto-dismiss timer so each
/// banner's lifetime is independent of whatever replaces it in the overlay.
class _BannerWithAutoDismiss extends StatefulWidget {
  const _BannerWithAutoDismiss({
    required this.notification,
    required this.durationMs,
    required this.onDismiss,
    required this.onTap,
  });

  final AppNotification notification;
  final int durationMs;
  final VoidCallback onDismiss;
  final VoidCallback onTap;

  @override
  State<_BannerWithAutoDismiss> createState() => _BannerWithAutoDismissState();
}

class _BannerWithAutoDismissState extends State<_BannerWithAutoDismiss> {
  @override
  void initState() {
    super.initState();
    Future.delayed(Duration(milliseconds: widget.durationMs), () {
      if (mounted) widget.onDismiss();
    });
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: NotificationBannerCard(
        notification: widget.notification,
        onTap: widget.onTap,
        onDismiss: widget.onDismiss,
      ),
    );
  }
}
