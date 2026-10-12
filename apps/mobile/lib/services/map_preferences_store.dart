import 'package:shared_preferences/shared_preferences.dart';

class MapPreferencesStore {
  MapPreferencesStore._();

  static const _basemapKey = 'map.basemap_id';
  static const _showTeamsKey = 'map.layers.teams';

  static Future<String?> selectedBasemapId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_basemapKey);
  }

  static Future<void> setSelectedBasemapId(String id) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_basemapKey, id);
  }

  static Future<bool> showTeams() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_showTeamsKey) ?? true;
  }

  static Future<void> setShowTeams(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_showTeamsKey, value);
  }
}
