import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/team_type_definition.dart';

void main() {
  test('parses the canonical team type catalog shape', () {
    final definition = TeamTypeDefinition.fromJson({
      'type_short': 'gt', 'name': 'Ground Team', 'category': 'Search & Rescue',
      'background_color': '#228b22', 'text_color': '#ffffff', 'icon_key': 'team',
      'capability_ids': ['1', '2'], 'is_aviation': false, 'is_drone': 1,
    });

    expect(definition.code, 'GT');
    expect(definition.backgroundColor.toARGB32(), 0xff228b22);
    expect(definition.textColor.toARGB32(), 0xffffffff);
    expect(definition.capabilityIds, ['1', '2']);
    expect(definition.isDrone, isTrue);
  });
}
