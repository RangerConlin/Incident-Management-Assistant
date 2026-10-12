import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';

/// One incident command post's server, reached through the cloud router at
/// `<routerUrl>/r/<code>` (see `AppConfig`).
class ServerConnection {
  const ServerConnection({required this.code, required this.routerUrl});

  factory ServerConnection.fromJson(Map<String, dynamic> json) =>
      ServerConnection(
        code: '${json['code']}',
        routerUrl: '${json['router_url'] ?? AppConfig.cloudRouterBaseUrl}',
      );

  final String code;
  final String routerUrl;

  String get baseUrl => '$routerUrl/r/$code';

  Map<String, dynamic> toJson() => {'code': code, 'router_url': routerUrl};

  static final _codePattern = RegExp(r'^[A-Z0-9][A-Z0-9-]{2,31}$');

  /// Upper-cases and trims [input]; null if it isn't a plausible connect code.
  static String? normalizeCode(String input) {
    final code = input.trim().toUpperCase();
    return _codePattern.hasMatch(code) ? code : null;
  }

  /// Trims [input] and drops trailing slashes; null unless it is an http(s)
  /// URL. Blank input means "use the built-in router".
  static String? normalizeRouterUrl(String input) {
    final url = input.trim().replaceAll(RegExp(r'/+$'), '');
    if (url.isEmpty) return AppConfig.cloudRouterBaseUrl;
    final uri = Uri.tryParse(url);
    final valid =
        uri != null &&
        (uri.scheme == 'http' || uri.scheme == 'https') &&
        uri.host.isNotEmpty;
    return valid ? url : null;
  }

  @override
  bool operator ==(Object other) =>
      other is ServerConnection &&
      other.code == code &&
      other.routerUrl == routerUrl;

  @override
  int get hashCode => Object.hash(code, routerUrl);
}

/// The connect codes this device knows about, and which one is in use.
///
/// The active connection is mirrored in memory so `AppConfig.sarAppBaseUrl`
/// (read synchronously by the API clients) always reflects it; call
/// [initialize] once at startup.
class ServerConnectionStore {
  ServerConnectionStore._();

  static const _listKey = 'server_connections.list';
  static const _activeKey = 'server_connections.active';

  static ServerConnection? _active;

  static ServerConnection? get active => _active;

  /// Loads the active connection into memory.
  static Future<void> initialize() async {
    final all = await loadAll();
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_activeKey);
    _active = all.where((c) => c.code == code).firstOrNull;
  }

  static Future<List<ServerConnection>> loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_listKey);
    if (raw == null) return const [];
    try {
      return (jsonDecode(raw) as List)
          .map((e) => ServerConnection.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
    } catch (_) {
      return const [];
    }
  }

  static Future<void> _saveAll(List<ServerConnection> all) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _listKey,
      jsonEncode(all.map((c) => c.toJson()).toList()),
    );
  }

  /// Saves [connection] (replacing any with the same code) and makes it the
  /// active one.
  static Future<void> addAndActivate(ServerConnection connection) async {
    final all = await loadAll();
    await _saveAll([
      ...all.where((c) => c.code != connection.code),
      connection,
    ]);
    await setActive(connection.code);
  }

  static Future<void> setActive(String code) async {
    final all = await loadAll();
    final prefs = await SharedPreferences.getInstance();
    _active = all.where((c) => c.code == code).firstOrNull;
    if (_active == null) {
      await prefs.remove(_activeKey);
    } else {
      await prefs.setString(_activeKey, code);
    }
  }

  static Future<void> remove(String code) async {
    final all = await loadAll();
    await _saveAll(all.where((c) => c.code != code).toList());
    if (_active?.code == code) {
      _active = null;
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_activeKey);
    }
  }
}
