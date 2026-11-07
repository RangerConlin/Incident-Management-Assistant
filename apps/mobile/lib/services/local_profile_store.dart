import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// The operator's own profile, kept on this device so it can be created and
/// edited with no server connection. It mirrors the identifying fields of the
/// desktop's master personnel record and is shared with an incident server
/// the first time the user loads an incident there (see
/// `IncidentSessionStarter`).
class LocalProfile {
  const LocalProfile({
    required this.personId,
    required this.firstName,
    required this.lastName,
    this.organization = '',
    this.homeUnit = '',
    this.primaryRole = '',
    this.rank = '',
    this.callsign = '',
    this.title = '',
    this.phone = '',
    this.email = '',
    this.radioId = '',
    this.isMedic = false,
    this.status = 'available',
    this.notes = '',
    this.photoUrl = '',
    this.emergencyInfo = const {},
    this.contactInfo = const {},
    this.certifications = const [],
  });

  factory LocalProfile.fromJson(Map<String, dynamic> json) {
    String text(String key) => '${json[key] ?? ''}'.trim();
    return LocalProfile(
      personId: text('person_id'),
      firstName: text('first_name'),
      lastName: text('last_name'),
      organization: text('organization'),
      homeUnit: text('home_unit'),
      primaryRole: text('primary_role'),
      rank: text('rank'),
      callsign: text('callsign'),
      title: text('title'),
      phone: text('phone'),
      email: text('email'),
      radioId: text('radio_id'),
      isMedic: json['is_medic'] == true,
      status: text('status').isEmpty ? 'available' : text('status'),
      notes: text('notes'),
      photoUrl: text('photo_url'),
      emergencyInfo: _textMap(json['emergency_info']),
      contactInfo: _textMap(json['contact_info']),
      certifications: _certificationList(json['certifications']),
    );
  }

  /// The visible ID (badge / member number) that identifies this person on
  /// the server. Not the server's internal record key.
  final String personId;
  final String firstName;
  final String lastName;
  final String organization;
  final String homeUnit;
  final String primaryRole;
  final String rank;
  final String callsign;
  final String title;
  final String phone;
  final String email;
  final String radioId;
  final bool isMedic;
  final String status;
  final String notes;
  final String photoUrl;
  final Map<String, String> emergencyInfo;
  final Map<String, String> contactInfo;
  final List<Map<String, int>> certifications;

  String get fullName => '$firstName $lastName'.trim();

  /// True when the fields the server requires are present.
  bool get isComplete =>
      personId.isNotEmpty && firstName.isNotEmpty && lastName.isNotEmpty;

  /// Canonical identity fields shared with master and incident personnel.
  Map<String, dynamic> toPersonnelJson() => {
    'person_id': personId,
    'name': fullName,
    'first_name': firstName,
    'last_name': lastName,
    'organization': organization,
    'home_unit': homeUnit,
    'primary_role': primaryRole,
    'rank': rank,
    'callsign': callsign,
    'title': title,
    'phone': phone,
    'email': email,
    'radio_id': radioId,
    'is_medic': isMedic,
    'status': status,
    'notes': notes,
    'photo_url': photoUrl,
    'emergency_info': {
      for (final key in _emergencyFieldNames)
        if (emergencyInfo.containsKey(key)) key: emergencyInfo[key]!,
    },
    'contact_info': contactInfo,
    'certifications': certifications,
  };

  Map<String, dynamic> toJson() => toPersonnelJson();

  static Map<String, String> _textMap(Object? value) {
    if (value is! Map) return const {};
    return {
      for (final entry in value.entries)
        '${entry.key}': '${entry.value ?? ''}'.trim(),
    };
  }

  static const _emergencyFieldNames = {
    'primary_name',
    'primary_relationship',
    'primary_phone',
    'secondary_name',
    'secondary_relationship',
    'secondary_phone',
    'medical',
  };

  static List<Map<String, int>> _certificationList(Object? value) {
    if (value is! List) return const [];
    final result = <Map<String, int>>[];
    for (final item in value) {
      if (item is! Map) continue;
      final typeId = int.tryParse('${item['cert_type_id'] ?? ''}');
      final level = int.tryParse('${item['level'] ?? 0}');
      if (typeId != null) {
        result.add({'cert_type_id': typeId, 'level': (level ?? 0).clamp(0, 3)});
      }
    }
    return result;
  }
}

class LocalProfileStore {
  LocalProfileStore._();

  static const _key = 'local_profile.json';

  static Future<LocalProfile?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return null;
    try {
      final profile = LocalProfile.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
      return profile.isComplete ? profile : null;
    } catch (_) {
      return null;
    }
  }

  static Future<void> save(LocalProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(profile.toJson()));
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
