import 'package:flutter/material.dart';

/// Root navigator key, set on the app's `MaterialApp`. Lets code with no
/// `BuildContext` of its own — notably `PushNotificationService`, which
/// reacts to FCM messages that can arrive at any time, on any screen —
/// present a banner/dialog or push a route without needing one threaded
/// through.
class AppNavigation {
  AppNavigation._();

  static final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>();

  static BuildContext? get currentContext =>
      navigatorKey.currentState?.overlay?.context;
}
