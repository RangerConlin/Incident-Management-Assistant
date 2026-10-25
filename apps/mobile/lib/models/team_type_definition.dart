import 'package:flutter/material.dart';

import '../utils/json_parsing.dart';

class TeamTypeDefinition {
  const TeamTypeDefinition({
    required this.code,
    required this.name,
    required this.category,
    required this.backgroundColor,
    required this.textColor,
    required this.iconKey,
    required this.capabilityIds,
    required this.isAviation,
    required this.isDrone,
  });

  final String code;
  final String name;
  final String category;
  final Color backgroundColor;
  final Color textColor;
  final String iconKey;
  final List<String> capabilityIds;
  final bool isAviation;
  final bool isDrone;

  factory TeamTypeDefinition.fromJson(Map<String, dynamic> json) {
    return TeamTypeDefinition(
      code: '${json['type_short'] ?? ''}'.trim().toUpperCase(),
      name: '${json['name'] ?? ''}'.trim(),
      category: '${json['category'] ?? 'General'}'.trim(),
      backgroundColor: _hexColor('${json['background_color'] ?? '#7a7a7a'}'),
      textColor: _hexColor('${json['text_color'] ?? '#ffffff'}'),
      iconKey: '${json['icon_key'] ?? 'team'}'.trim(),
      capabilityIds: (json['capability_ids'] as List<dynamic>? ?? const [])
          .map((value) => '$value')
          .toList(growable: false),
      isAviation: parseIntBool(json['is_aviation']),
      isDrone: parseIntBool(json['is_drone']),
    );
  }

  static Color _hexColor(String value) {
    final normalized = value.replaceFirst('#', '');
    final rgb = int.tryParse(normalized, radix: 16) ?? 0x7a7a7a;
    return Color(0xff000000 | rgb);
  }
}
