import 'package:flutter/material.dart';

import '../config/incident_tab_config.dart';
import '../models/home_nav_args.dart';
import '../models/incident_category.dart';
import '../screens/alerts_center_screen.dart';
import '../screens/field_dashboard_screen.dart';
import '../screens/incident_staff_dashboard_screen.dart';
import '../screens/map_screen.dart';
import '../screens/message_inbox_screen.dart';

/// The five primary tab destinations, in bottom-nav order. Team management
/// and the former "More" menu live in `AppDrawer` instead — five is about
/// the practical limit for a `NavigationBar` before icons/labels get
/// cramped.
enum AppTab { dashboard, tasks, map, alerts, messages }

/// Shared bottom tab bar for the five primary destinations. Switches tabs
/// with `pushReplacement` — exactly one tab screen stays on the navigation
/// stack at a time — instead of pushing a new route per tap, so repeated
/// tab taps don't grow the stack and `selectedIndex` always matches the
/// screen actually on screen.
class AppBottomNav extends StatelessWidget {
  const AppBottomNav({super.key, required this.current, required this.args});

  final AppTab current;
  final HomeNavArgs args;

  static Widget _screenFor(AppTab tab, HomeNavArgs args) {
    switch (tab) {
      case AppTab.dashboard:
        return args.teamId.isEmpty
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
              );
      case AppTab.tasks:
        final category = categoryForIncidentType(args.incidentType);
        return configFor(category).taskTabBuilder(args);
      case AppTab.map:
        return MapScreen(args: args);
      case AppTab.alerts:
        return AlertsCenterScreen(args: args);
      case AppTab.messages:
        return MessageInboxScreen(args: args);
    }
  }

  /// Switches the current top-level tab screen. Exposed so app-bar shortcut
  /// buttons (e.g. the dashboard's messages icon) can jump to a tab using
  /// the same stack-replacing behavior as tapping it in the nav bar.
  static void navigateTo(BuildContext context, AppTab tab, HomeNavArgs args) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => _screenFor(tab, args)),
    );
  }

  void _onDestinationSelected(BuildContext context, int index) {
    final tab = AppTab.values[index];
    if (tab == current) return;
    navigateTo(context, tab, args);
  }

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: current.index,
      onDestinationSelected: (index) => _onDestinationSelected(context, index),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
        NavigationDestination(icon: Icon(Icons.checklist_outlined), label: 'Tasks'),
        NavigationDestination(icon: Icon(Icons.map_outlined), label: 'Map'),
        NavigationDestination(icon: Icon(Icons.warning_amber_outlined), label: 'Alerts'),
        NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'Messages'),
      ],
    );
  }
}
