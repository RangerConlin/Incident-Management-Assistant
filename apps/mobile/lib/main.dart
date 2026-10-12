import 'dart:async';

import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';
import 'screens/splash_screen.dart';
import 'services/app_navigation.dart';
import 'services/notification_channels.dart';
import 'services/server_connection_store.dart';
import 'services/push_notification_service.dart';
import 'services/text_scale_store.dart';
import 'services/tracking_service.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Read synchronously by the API clients and tracking config, so it must be
  // loaded before anything that could make a request.
  await ServerConnectionStore.initialize();
  await TextScaleStore.load();
  runApp(const ArcHorizonApp());
  unawaited(_initializeAppServices());
}

Future<void> _initializeAppServices() async {
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    ).timeout(const Duration(seconds: 8));
  } catch (e, stackTrace) {
    debugPrint('Startup: Firebase initialization failed: $e');
    debugPrintStack(stackTrace: stackTrace);
    return;
  }

  try {
    await PushNotificationService.registerHandlers()
        .timeout(const Duration(seconds: 5));
  } catch (e, stackTrace) {
    debugPrint('Startup: push handler registration failed: $e');
    debugPrintStack(stackTrace: stackTrace);
  }

  try {
    await NotificationChannels.registerAll().timeout(
      const Duration(seconds: 5),
    );
  } catch (e, stackTrace) {
    debugPrint('Startup: notification channel registration failed: $e');
    debugPrintStack(stackTrace: stackTrace);
  }

  try {
    await registerLocationHeadlessTask().timeout(const Duration(seconds: 5));
  } catch (e, stackTrace) {
    debugPrint('Startup: location headless task registration failed: $e');
    debugPrintStack(stackTrace: stackTrace);
  }

  try {
    await TrackingService.initialize().timeout(const Duration(seconds: 12));
  } catch (e, stackTrace) {
    debugPrint('Startup: tracking initialization failed: $e');
    debugPrintStack(stackTrace: stackTrace);
  }
}

class ArcHorizonApp extends StatelessWidget {
  const ArcHorizonApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<double>(
      valueListenable: TextScaleStore.current,
      builder: (context, textScale, _) {
        return MaterialApp(
          navigatorKey: AppNavigation.navigatorKey,
          title: 'Arc-Horizon',
          theme: AppTheme.dark,
          darkTheme: AppTheme.dark,
          themeMode: ThemeMode.dark,
          builder: (context, child) {
            return MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: TextScaler.linear(textScale)),
              child: child!,
            );
          },
          home: const SplashScreen(),
        );
      },
    );
  }
}
