import '../utils/json_parsing.dart';

/// Incident-level context shown in the dashboard header
/// (`GET .../incidents/{id}/header`, plus a best-effort operational period
/// from `GET .../incidents/{id}/op-periods`).
class IncidentContext {
  const IncidentContext({
    required this.id,
    required this.name,
    this.incidentNumber,
    this.status,
    this.icpLocation,
    this.startTime,
    this.currentOperationalPeriod,
  });

  final String id;
  final String name;
  final String? incidentNumber;
  final String? status;
  final String? icpLocation;
  final DateTime? startTime;
  final int? currentOperationalPeriod;

  factory IncidentContext.fromHeaderJson(
    Map<String, dynamic> json, {
    required String id,
    required String name,
    int? currentOperationalPeriod,
  }) {
    return IncidentContext(
      id: id,
      name: nullIfBlank(json['incident_name']) ?? name,
      incidentNumber: nullIfBlank(json['incident_number']),
      status: nullIfBlank(json['status']),
      icpLocation: nullIfBlank(json['icp_location']),
      startTime: parseDateTime(json['start_time']),
      currentOperationalPeriod: currentOperationalPeriod,
    );
  }
}
