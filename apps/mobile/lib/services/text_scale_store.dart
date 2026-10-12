import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// On-device text-size preference. The app's color theme is deliberately
/// fixed to a single always-dark field-ops look (see `AppTheme`), so
/// "Appearance" settings are scoped to legibility (text scale) rather than
/// a light/dark switch.
class TextScaleStore {
  TextScaleStore._();

  static const _key = 'text_scale.factor';

  static const double standard = 1.0;
  static const double large = 1.15;
  static const double extraLarge = 1.3;

  static const options = [standard, large, extraLarge];

  /// Live value the root `MaterialApp` listens to, so a change in Settings
  /// applies immediately without an app restart. Seeded from storage by
  /// `load()` at startup.
  static final ValueNotifier<double> current = ValueNotifier<double>(
    standard,
  );

  static String label(double scale) {
    if (scale >= extraLarge) return 'Extra Large';
    if (scale >= large) return 'Large';
    return 'Standard';
  }

  static Future<double> load() async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getDouble(_key) ?? standard;
    current.value = value;
    return value;
  }

  static Future<void> save(double scale) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_key, scale);
    current.value = scale;
  }
}
