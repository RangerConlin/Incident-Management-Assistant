import 'dart:async';

import 'package:flutter/material.dart';

import '../config/incident_tab_config.dart';
import '../models/home_nav_args.dart';
import '../models/incident_category.dart';
import '../screens/comms_plan_screen.dart';
import '../screens/field_dashboard_screen.dart';
import '../screens/incident_staff_dashboard_screen.dart';
import '../screens/main_menu_screen.dart';
import '../screens/logbook_screen.dart';
import '../screens/med_plan_screen.dart';
import '../screens/navigation_tools_screen.dart';
import '../screens/notification_center_screen.dart';
import '../screens/qr_scanner_screen.dart';
import '../screens/reference_library_screen.dart';
import '../screens/safety_screen.dart';
import '../screens/settings_screen.dart';
import '../screens/team_management_screen.dart';
import '../services/app_presence_service.dart';
import '../services/chat_presence_service.dart';
import '../services/notification_store.dart';
import '../services/push_notification_service.dart';
import '../services/session_store.dart';
import '../services/tracking_service.dart';
import 'arc_horizon_mark.dart';

/// Side navigation drawer for secondary destinations that don't warrant a
/// bottom-nav tab slot (Team, Comms/Med Plan, Logbook, Navigation Tools, QR
/// Scanner, Reference Library, Settings), plus incident-category-specific
/// extras (see `IncidentTabConfig`) and log out. Replaces the old "More"
/// tab. Map is a primary bottom-nav tab because it is a frequent field
/// workflow.
class AppDrawer extends StatelessWidget {
  const AppDrawer({super.key, required this.args});

  final HomeNavArgs args;

  Future<void> _leaveIncident(
    BuildContext context, {
    required bool unregisterPushToken,
  }) async {
    // Keep the NavigatorState before closing the drawer. The ListTile's
    // context can be unmounted by pop(), so using/checking that context after
    // the asynchronous cleanup would silently skip the route transition.
    final navigator = Navigator.of(context);
    navigator.pop();
    if (unregisterPushToken) {
      // Best-effort and never awaited: fetching an FCM token can hang for a
      // long time on devices/emulators without full Play Services, which
      // would otherwise block logout on something the user can't see or fix.
      unawaited(PushNotificationService.unregisterCurrentToken());
    }
    AppPresenceService.stop();
    ChatPresenceService.stop();
    // Native tracking shutdown can be slow or unavailable. Start it, but do
    // not make navigation depend on the plugin responding.
    unawaited(_stopTracking());
    try {
      await SessionStore.clear();
    } catch (error) {
      // Do not strand the operator on the dashboard because local storage
      // failed. A later successful clear will remove the stale session.
      debugPrint('AppDrawer: failed to clear session: $error');
    }
    if (!navigator.mounted) return;
    navigator.pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const MainMenuScreen()),
      (route) => false,
    );
  }

  Future<void> _stopTracking() async {
    try {
      await TrackingService.stop();
    } catch (error) {
      debugPrint('AppDrawer: failed to stop tracking: $error');
    }
  }

  Future<void> _logout(BuildContext context) =>
      _leaveIncident(context, unregisterPushToken: true);

  /// Returns to the main menu without unregistering the push
  /// token — `PushNotificationService.syncRegistration` upserts by token,
  /// so it'll simply re-associate with whichever incident is loaded next
  /// (see its doc comment) rather than needing a fresh registration. The
  /// profile and connection stay, so loading another incident needs no
  /// sign-in.
  Future<void> _switchIncident(BuildContext context) =>
      _leaveIncident(context, unregisterPushToken: false);

  void _openScreen(BuildContext context, WidgetBuilder builder) {
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute(builder: builder));
  }

  /// Returns to the Dashboard tab from anywhere, clearing the rest of the
  /// navigation stack — a consistent "go home" regardless of how deep the
  /// current screen is nested.
  void _goHome(BuildContext context) {
    Navigator.of(context).pop();
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => args.teamId.isEmpty
            ? IncidentStaffDashboardScreen(
                incidentId: args.incidentId,
                incidentName: args.incidentName,
                incidentType: args.incidentType,
                session: args.session,
              )
            : FieldDashboardScreen(
                incidentId: args.incidentId,
                incidentName: args.incidentName,
                incidentType: args.incidentType,
                teamId: args.teamId,
                teamName: args.teamName,
                session: args.session,
              ),
      ),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final category = categoryForIncidentType(args.incidentType);
    final extraEntries = configFor(category).extraMoreEntries;

    return Drawer(
      child: SafeArea(
        top: false,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            DrawerHeader(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  const ArcHorizonWordmark(width: 240),
                  const SizedBox(height: 16),
                  Text(
                    args.incidentName,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(
                    args.teamName,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            ListTile(
              leading: const Icon(Icons.home_outlined),
              title: const Text('Home'),
              onTap: () => _goHome(context),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.groups_outlined),
              title: const Text('Team'),
              onTap: () =>
                  _openScreen(context, (_) => TeamManagementScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.radio_outlined),
              title: const Text('Comms Plan'),
              subtitle: const Text('ICS 205'),
              onTap: () =>
                  _openScreen(context, (_) => CommsPlanScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.medical_services_outlined),
              title: const Text('Med Plan'),
              subtitle: const Text('ICS 206'),
              onTap: () =>
                  _openScreen(context, (_) => MedPlanScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.health_and_safety_outlined),
              title: const Text('Safety'),
              subtitle: const Text('GAR'),
              onTap: () =>
                  _openScreen(context, (_) => SafetyScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.menu_book_outlined),
              title: const Text('Logbook'),
              subtitle: const Text('ICS 214'),
              onTap: () =>
                  _openScreen(context, (_) => LogbookScreen(args: args)),
            ),
            for (final entry in extraEntries)
              ListTile(
                leading: Icon(entry.icon),
                title: Text(entry.title),
                subtitle: entry.subtitle == null ? null : Text(entry.subtitle!),
                onTap: () => _openScreen(context, (_) => entry.builder(args)),
              ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.near_me_outlined),
              title: const Text('Navigation Tools'),
              onTap: () => _openScreen(
                context,
                (_) => NavigationToolsScreen(args: args),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.qr_code_scanner_outlined),
              title: const Text('QR Scanner'),
              onTap: () =>
                  _openScreen(context, (_) => QrScannerScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.library_books_outlined),
              title: const Text('Reference Library'),
              onTap: () => _openScreen(
                context,
                (_) => ReferenceLibraryScreen(args: args),
              ),
            ),
            const Divider(height: 1),
            FutureBuilder<int>(
              future: NotificationStore.unreadCount(),
              builder: (context, snapshot) {
                final unread = snapshot.data ?? 0;
                return ListTile(
                  leading: Badge(
                    isLabelVisible: unread > 0,
                    label: Text('$unread'),
                    child: const Icon(Icons.notifications_outlined),
                  ),
                  title: const Text('Notifications'),
                  onTap: () => _openScreen(
                    context,
                    (_) => const NotificationCenterScreen(),
                  ),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.settings_outlined),
              title: const Text('Settings'),
              onTap: () =>
                  _openScreen(context, (_) => SettingsScreen(args: args)),
            ),
            ListTile(
              leading: const Icon(Icons.swap_horiz_outlined),
              title: const Text('Switch Incident'),
              onTap: () => _switchIncident(context),
            ),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Log Out'),
              onTap: () => _logout(context),
            ),
          ],
        ),
      ),
    );
  }
}
