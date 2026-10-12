class Ics206Plan {
  const Ics206Plan({
    required this.aidStations,
    required this.ambulanceServices,
    required this.hospitals,
    required this.airAmbulance,
    required this.medicalComms,
    required this.procedures,
    required this.signatures,
    this.opPeriod,
  });

  final List<Ics206Record> aidStations;
  final List<Ics206Record> ambulanceServices;
  final List<Ics206Record> hospitals;
  final List<Ics206Record> airAmbulance;
  final List<Ics206Record> medicalComms;
  final Ics206Procedures procedures;
  final Ics206Signatures signatures;
  final int? opPeriod;

  bool get isEmpty =>
      aidStations.isEmpty &&
      ambulanceServices.isEmpty &&
      hospitals.isEmpty &&
      airAmbulance.isEmpty &&
      medicalComms.isEmpty &&
      procedures.content.isEmpty &&
      signatures.isEmpty;

  static List<Ics206Record> recordsFromJsonList(List<dynamic> rows) {
    return rows
        .whereType<Map>()
        .map((row) => Ics206Record(Map<String, dynamic>.from(row)))
        .toList();
  }
}

class Ics206Record {
  const Ics206Record(this.data);

  final Map<String, dynamic> data;

  String text(String key) => _asText(data[key]);

  bool flag(String key) => _asBool(data[key]);

  int? get opPeriod => _asInt(data['op_period']);

  String get displayTitle {
    for (final key in ['name', 'channel', 'function', 'type']) {
      final value = text(key);
      if (value.isNotEmpty) return value;
    }
    return 'Untitled';
  }
}

class Ics206Procedures {
  const Ics206Procedures({required this.content, this.opPeriod});

  final String content;
  final int? opPeriod;

  factory Ics206Procedures.fromJson(Map<String, dynamic> json) {
    return Ics206Procedures(
      content: _asText(json['content']),
      opPeriod: _asInt(json['op_period']),
    );
  }
}

class Ics206Signatures {
  const Ics206Signatures({
    required this.preparedBy,
    required this.position,
    required this.approvedBy,
    required this.date,
    this.opPeriod,
  });

  final String preparedBy;
  final String position;
  final String approvedBy;
  final String date;
  final int? opPeriod;

  bool get isEmpty =>
      preparedBy.isEmpty &&
      position.isEmpty &&
      approvedBy.isEmpty &&
      date.isEmpty;

  factory Ics206Signatures.fromJson(Map<String, dynamic> json) {
    return Ics206Signatures(
      preparedBy: _asText(json['prepared_by']),
      position: _asText(json['position']),
      approvedBy: _asText(json['approved_by']),
      date: _asText(json['date']),
      opPeriod: _asInt(json['op_period']),
    );
  }
}

String _asText(Object? value) => value == null ? '' : '$value'.trim();

bool _asBool(Object? value) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  final text = _asText(value).toLowerCase();
  return text == 'true' || text == 'yes' || text == '1';
}

int? _asInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(_asText(value));
}
