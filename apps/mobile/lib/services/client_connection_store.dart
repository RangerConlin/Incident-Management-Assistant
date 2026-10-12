import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

class ClientConnectionStore {
  ClientConnectionStore._();

  static const _deviceIdKey = 'client_connection.device_id';
  static const _connectionTokenKey = 'client_connection.token';

  static Future<String> deviceId() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_deviceIdKey);
    if (existing != null && existing.isNotEmpty) return existing;

    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    final id = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    final deviceId = 'mobile-$id';
    await prefs.setString(_deviceIdKey, deviceId);
    return deviceId;
  }

  static Future<String?> connectionToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_connectionTokenKey);
  }

  static Future<void> setConnectionToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_connectionTokenKey, token);
  }

  static Future<void> clearConnectionToken() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_connectionTokenKey);
  }
}
