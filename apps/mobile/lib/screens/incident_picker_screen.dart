import 'package:flutter/material.dart';

import '../models/mobile_incident_context.dart';
import '../services/incident_session_starter.dart';
import '../services/local_profile_store.dart';
import '../services/profile_sync.dart';
import '../services/sarapp_api_client.dart';
import 'field_dashboard_screen.dart';
import 'incident_staff_dashboard_screen.dart';

/// Choose an incident on the connected server, then join as the saved
/// profile. There is no sign-in here: the profile already identifies the
/// user, and the server is told about it automatically. Team assignment is
/// never chosen here — it's whatever the server already has for this person
/// on this incident (shown read-only once an incident is picked), and it
/// alone decides whether entry lands on Team View or Staff View.
class IncidentPickerScreen extends StatefulWidget {
  const IncidentPickerScreen({
    super.key,
    required this.profile,
    this.clientFactory = SarAppApiClient.new,
  });

  final LocalProfile profile;
  final SarAppApiClient Function() clientFactory;

  @override
  State<IncidentPickerScreen> createState() => _IncidentPickerScreenState();
}

class _IncidentPickerScreenState extends State<IncidentPickerScreen> {
  late final SarAppApiClient _apiClient = widget.clientFactory();

  List<Map<String, dynamic>> _incidents = const [];
  Map<String, dynamic>? _selectedIncident;
  bool _loadingIncidents = false;
  bool _joining = false;
  String? _errorMessage;
  String? _incidentsErrorMessage;

  bool _loadingPreview = false;
  MobileIncidentContext? _previewContext;
  String? _previewErrorMessage;

  @override
  void initState() {
    super.initState();
    _loadIncidents();
  }

  @override
  void dispose() {
    _apiClient.dispose();
    super.dispose();
  }

  /// A user-facing reason for a failed request. Non-API errors are network
  /// failures (offline, timeout, DNS), which carry nothing worth showing.
  String _describe(Object error) => error is SarAppApiException
      ? error.message
      : 'Could not reach the server. Check your connection and try again.';

  Future<void> _loadIncidents() async {
    setState(() {
      _loadingIncidents = true;
      _incidentsErrorMessage = null;
    });
    try {
      final incidents = await _apiClient.fetchIncidents();
      if (!mounted) return;
      setState(() {
        _incidents = incidents
            .map((e) => Map<String, dynamic>.from(e as Map<dynamic, dynamic>))
            .toList();
        if (!_incidents.contains(_selectedIncident)) {
          _selectedIncident = _incidents.isNotEmpty ? _incidents.first : null;
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _incidents = const [];
          _selectedIncident = null;
          _incidentsErrorMessage = 'Failed to load incidents: ${_describe(e)}';
        });
      }
    } finally {
      if (mounted) setState(() => _loadingIncidents = false);
    }
    await _loadPreview();
  }

  /// Best-effort, read-only look at what the server already has for this
  /// person on the selected incident — their team (if any) or staff
  /// position(s) — shown before they commit by tapping Enter Incident.
  /// Never blocks entry: a failure here just leaves the preview blank.
  Future<void> _loadPreview() async {
    final incident = _selectedIncident;
    if (incident == null) {
      setState(() {
        _previewContext = null;
        _previewErrorMessage = null;
      });
      return;
    }

    setState(() {
      _loadingPreview = true;
      _previewErrorMessage = null;
      _previewContext = null;
    });
    try {
      await ProfileSync(_apiClient).sync(widget.profile);
      final session = await _apiClient.startSession(
        personId: widget.profile.personId,
        incidentId: _incidentId(incident),
      );
      final personRecord = session['person_record'];
      if (personRecord == null) {
        throw SarAppApiException(
          'The server session did not identify a personnel record.',
        );
      }
      final context = await _apiClient.fetchMobileIncidentContext(
        incidentId: _incidentId(incident),
        personRecord: int.parse('$personRecord'),
      );
      if (!mounted) return;
      setState(() => _previewContext = context);
    } catch (e) {
      if (mounted) setState(() => _previewErrorMessage = _describe(e));
    } finally {
      if (mounted) setState(() => _loadingPreview = false);
    }
  }

  String _incidentId(Map<String, dynamic> incident) =>
      '${incident['id'] ?? incident['_id'] ?? incident['incident_id']}';

  String _incidentName(Map<String, dynamic> incident) =>
      '${incident['name'] ?? incident['title'] ?? incident['incident_name'] ?? 'Unnamed incident'}';

  String _incidentNumber(Map<String, dynamic> incident) =>
      '${incident['number'] ?? incident['incident_number'] ?? _incidentId(incident)}';

  Future<void> _join() async {
    final incident = _selectedIncident;
    if (incident == null) {
      setState(() => _errorMessage = 'Select an incident.');
      return;
    }
    setState(() {
      _joining = true;
      _errorMessage = null;
    });
    try {
      final started = await IncidentSessionStarter(_apiClient).start(
        profile: widget.profile,
        incidentId: _incidentId(incident),
        incidentName: _incidentName(incident),
      );
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(
          builder: (_) => started.teamId.isEmpty
              ? IncidentStaffDashboardScreen(
                  incidentId: started.incidentId,
                  incidentName: started.incidentName,
                  incidentType: started.incidentType,
                  session: started.session,
                )
              : FieldDashboardScreen(
                  incidentId: started.incidentId,
                  incidentName: started.incidentName,
                  incidentType: started.incidentType,
                  teamId: started.teamId,
                  teamName: started.teamName,
                  session: started.session,
                ),
        ),
        (route) => false,
      );
    } catch (e) {
      if (mounted) {
        setState(
          () => _errorMessage = 'Could not load incident: ${_describe(e)}',
        );
      }
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  Widget _errorText(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Text(
      message,
      style: TextStyle(color: Theme.of(context).colorScheme.error),
    ),
  );

  Widget _previewRow(BuildContext context) {
    final theme = Theme.of(context);
    final preview = _previewContext;
    IconData icon;
    String text;
    if (preview == null) {
      return const SizedBox.shrink();
    } else if (preview.hasTeam) {
      icon = Icons.groups_outlined;
      text = 'Team: ${preview.teamName}';
    } else if (preview.staffAssignments.isNotEmpty) {
      icon = Icons.badge_outlined;
      text = 'Position: ${preview.staffAssignments.first['title'] ?? ''}';
    } else {
      icon = Icons.person_outline;
      text = 'No assignment yet';
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Enter Incident')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              const Icon(Icons.person_outline),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Joining as ${widget.profile.fullName} (${widget.profile.personId})',
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text('Incident', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_loadingIncidents)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: LinearProgressIndicator(),
            )
          else if (_incidentsErrorMessage != null)
            _errorText(_incidentsErrorMessage!)
          else if (_incidents.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('No active incidents found.'),
            )
          else
            DropdownButtonFormField<Map<String, dynamic>>(
              initialValue: _selectedIncident,
              isExpanded: true,
              items: _incidents
                  .map(
                    (incident) => DropdownMenuItem(
                      value: incident,
                      child: Text(
                        '${_incidentName(incident)} (#${_incidentNumber(incident)})',
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                setState(() => _selectedIncident = value);
                _loadPreview();
              },
            ),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: _loadingIncidents ? null : _loadIncidents,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Refresh'),
            ),
          ),
          if (_loadingPreview)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: LinearProgressIndicator(),
            )
          else if (_previewErrorMessage == null)
            _previewRow(context),
          const SizedBox(height: 8),
          if (_errorMessage != null) _errorText(_errorMessage!),
          FilledButton(
            onPressed: (_joining || _selectedIncident == null)
                ? null
                : () => _join(),
            child: _joining
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Enter Incident'),
          ),
        ],
      ),
    );
  }
}
