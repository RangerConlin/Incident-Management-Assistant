import '../utils/json_parsing.dart';

String _text(dynamic value) => value == null ? '' : '$value'.trim();

String _joinParts(Iterable<String> values, String separator) =>
    values.where((value) => value.trim().isNotEmpty).join(separator);

class Ics205Plan {
  const Ics205Plan({
    required this.channels,
    this.opPeriodId,
    this.specialInstructions = '',
    this.phoneNumbers = const [],
    this.notes = '',
  });

  final List<Ics205Channel> channels;
  final String? opPeriodId;
  final String specialInstructions;
  final List<Ics205PhoneNumber> phoneNumbers;
  final String notes;

  bool get isEmpty =>
      channels.isEmpty &&
      specialInstructions.isEmpty &&
      phoneNumbers.isEmpty &&
      notes.isEmpty;

  factory Ics205Plan.fromJson({
    required List<dynamic> channelRows,
    required Map<String, dynamic> planJson,
  }) {
    final opPeriodId = _text(planJson['op_period_id']);
    return Ics205Plan(
      channels: channelRows
          .whereType<Map<String, dynamic>>()
          .map(Ics205Channel.fromJson)
          .where((channel) => channel.includeOn205)
          .toList(),
      opPeriodId: opPeriodId.isEmpty ? null : opPeriodId,
      specialInstructions: _text(planJson['special_instructions']),
      phoneNumbers: (planJson['phone_numbers'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(Ics205PhoneNumber.fromJson)
          .where((phone) => !phone.isEmpty)
          .toList(),
      notes: _text(planJson['notes']),
    );
  }
}

class Ics205Channel {
  const Ics205Channel({
    required this.name,
    required this.function,
    required this.mode,
    required this.includeOn205,
    this.system = '',
    this.band = '',
    this.rxFreq = '',
    this.txFreq = '',
    this.rxTone = '',
    this.txTone = '',
    this.encryption = '',
    this.assignmentDivision = '',
    this.assignmentTeam = '',
    this.priority = '',
    this.remarks = '',
  });

  final String name;
  final String function;
  final String mode;
  final bool includeOn205;
  final String system;
  final String band;
  final String rxFreq;
  final String txFreq;
  final String rxTone;
  final String txTone;
  final String encryption;
  final String assignmentDivision;
  final String assignmentTeam;
  final String priority;
  final String remarks;

  String get displayTitle => name.isNotEmpty ? name : 'Unnamed channel';

  String get assignment =>
      _joinParts([assignmentDivision, assignmentTeam], ' / ');

  String get receive =>
      _joinParts([rxFreq, if (rxTone.isNotEmpty) 'Tone $rxTone'], ' · ');

  String get transmit =>
      _joinParts([txFreq, if (txTone.isNotEmpty) 'Tone $txTone'], ' · ');

  factory Ics205Channel.fromJson(Map<String, dynamic> json) {
    return Ics205Channel(
      name: _text(json['channel']),
      function: _text(json['function']),
      mode: _text(json['mode']),
      includeOn205: parseIntBool(json['include_on_205'] ?? true),
      system: _text(json['system']),
      band: _text(json['band']),
      rxFreq: _text(json['rx_freq']),
      txFreq: _text(json['tx_freq']),
      rxTone: _text(json['rx_tone']),
      txTone: _text(json['tx_tone']),
      encryption: _text(json['encryption']),
      assignmentDivision: _text(json['assignment_division']),
      assignmentTeam: _text(json['assignment_team']),
      priority: _text(json['priority']),
      remarks: _text(json['remarks']),
    );
  }
}

class Ics205PhoneNumber {
  const Ics205PhoneNumber({
    this.label = '',
    this.number = '',
    this.note = '',
  });

  final String label;
  final String number;
  final String note;

  bool get isEmpty => label.isEmpty && number.isEmpty && note.isEmpty;

  String get displayTitle => label.isNotEmpty ? label : number;

  String get detail => _joinParts([number, note], ' · ');

  factory Ics205PhoneNumber.fromJson(Map<String, dynamic> json) {
    return Ics205PhoneNumber(
      label: _text(json['label']),
      number: _text(json['number']),
      note: _text(json['note']),
    );
  }
}
