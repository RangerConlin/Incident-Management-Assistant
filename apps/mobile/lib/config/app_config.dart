import '../services/server_connection_store.dart';

class AppConfig {
  AppConfig._();

  /// Default base URL of the SARApp cloud router (reverse-tunnel proxy), not a
  /// direct LAN server address. Field/mobile traffic must go through
  /// `/r/<connect_code>/...` to reach a specific registered LAN server —
  /// see `build_cloud_url` in the desktop client's
  /// `core/networking/connection_manager.py`.
  static const String cloudRouterBaseUrl = 'https://sarapp.arcadiacommandsolutions.com';

  /// Connect code of the dev LAN server. Only used to carry a session saved
  /// before connections were user-configurable over to the new connection
  /// list (see `SplashScreen`); it is never selected for a fresh install.
  static const String devConnectCode = 'OURS-9165';

  /// Base URL for all API traffic: the router plus the active connect code,
  /// combined the same way the desktop client does. With no connection
  /// chosen yet this is just the router root, so requests fail cleanly
  /// rather than reaching some other server.
  static String get sarAppBaseUrl =>
      ServerConnectionStore.active?.baseUrl ?? cloudRouterBaseUrl;
}
