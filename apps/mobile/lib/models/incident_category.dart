/// Coarse incident category used to decide which tab content and extra
/// "More" screens apply for the current incident.
///
/// Incident `type` itself is a free-text, admin-editable lookup value
/// (`GET /api/lookup/incident-types` on the server — ~24 default values
/// such as "Missing Person", "Wildfire Response", "Marathon / Race Event",
/// and agencies can add their own), not a fixed enum. This maps the known
/// default values into three broader buckets and falls back to
/// [IncidentCategory.allHazard] — the most feature-complete bucket — for
/// any custom type an agency adds later, so a new lookup value never
/// silently hides tabs/content.
enum IncidentCategory { sar, plannedEvent, allHazard }

IncidentCategory categoryForIncidentType(String? incidentType) {
  final type = (incidentType ?? '').trim();
  if (_sarTypes.contains(type)) return IncidentCategory.sar;
  if (_plannedEventTypes.contains(type)) return IncidentCategory.plannedEvent;
  return IncidentCategory.allHazard;
}

// Mirrors the default seed list in
// Incident-Management-Assistant/data/db/sarapp_db/api/routers/lookup_types.py
// (`_DEFAULT_INCIDENT_TYPES`). Any type not listed here — including custom
// agency-added lookup values — falls through to allHazard.
const _sarTypes = {
  'ELT Reports',
  'Missing Aircraft',
  'Missing Person',
};

const _plannedEventTypes = {
  'Agricultural Event',
  'Air Show / Fly-In',
  'Community Preparedness Fair',
  'Concert / Outdoor Entertainment',
  'County / State Fair',
  'Disaster Drill / ICS Exercise',
  'Festival / Fair',
  'Marathon / Race Event',
  'Parade / March',
  'Public Demonstration / Rally',
  'Public Health Event (e.g., vaccine clinic)',
  'Sporting Event',
};
