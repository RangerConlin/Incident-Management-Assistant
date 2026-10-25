import 'package:flutter/material.dart';

import '../services/incident_session_starter.dart';
import '../services/local_profile_store.dart';
import '../services/sarapp_api_client.dart';
import '../utils/natural_sort.dart';
import 'field_dashboard_screen.dart';
import 'incident_staff_dashboard_screen.dart';

/// Choose an incident and team on the connected server, then join as the
/// saved profile. There is no sign-in here: the profile already identifies
/// the user, and the server is told about it automatically.
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
  List<Map<String, dynamic>> _teams = const [];
  Map<String, dynamic>? _selectedTeam;
  bool _loadingIncidents = false;
  bool _loadingTeams = false;
  bool _joining = false;
  String? _errorMessage;
  String? _incidentsErrorMessage;
  String? _teamsErrorMessage;

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
    await _loadTeams();
  }

  Future<void> _loadTeams() async {
    final incident = _selectedIncident;
    if (incident == null) {
      setState(() {
        _teams = const [];
        _selectedTeam = null;
      });
      return;
    }

    setState(() {
      _loadingTeams = true;
      _teamsErrorMessage = null;
    });
    try {
      final teams = await _apiClient.fetchCheckinTeams(_incidentId(incident));
      if (!mounted) return;
      setState(() {
        _teams =
            teams
                .map(
                  (e) => Map<String, dynamic>.from(e as Map<dynamic, dynamic>),
                )
                .toList()
              ..sort((a, b) => naturalCompare(_teamName(a), _teamName(b)));
        if (!_teams.contains(_selectedTeam)) _selectedTeam = null;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _teams = const [];
          _selectedTeam = null;
          _teamsErrorMessage = 'Failed to load teams: ${_describe(e)}';
        });
      }
    } finally {
      if (mounted) setState(() => _loadingTeams = false);
    }
  }

  String _incidentId(Map<String, dynamic> incident) =>
      '${incident['id'] ?? incident['_id'] ?? incident['incident_id']}';

  String _incidentName(Map<String, dynamic> incident) =>
      '${incident['name'] ?? incident['title'] ?? incident['incident_name'] ?? 'Unnamed incident'}';

  String _incidentNumber(Map<String, dynamic> incident) =>
      '${incident['number'] ?? incident['incident_number'] ?? _incidentId(incident)}';

  String _teamId(Map<String, dynamic> team) => '${team['team_id']}';

  String _teamName(Map<String, dynamic> team) =>
      '${team['team_name'] ?? _teamId(team)}';

  Future<void> _join({bool withoutTeam = false}) async {
    final incident = _selectedIncident;
    final team = withoutTeam ? null : _selectedTeam;
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
        teamId: team == null ? null : _teamId(team),
        teamName: team == null ? null : _teamName(team),
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Load incident')),
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
                _loadTeams();
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
          const SizedBox(height: 16),
          Text('Team', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_loadingTeams)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: LinearProgressIndicator(),
            )
          else if (_teamsErrorMessage != null)
            _errorText(_teamsErrorMessage!)
          else if (_teams.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('No teams found for this incident.'),
            )
          else
            DropdownButtonFormField<Map<String, dynamic>>(
              initialValue: _selectedTeam,
              isExpanded: true,
              items: _teams
                  .map(
                    (team) => DropdownMenuItem(
                      value: team,
                      child: Text(_teamName(team)),
                    ),
                  )
                  .toList(),
              onChanged: (value) => setState(() => _selectedTeam = value),
            ),
          const SizedBox(height: 16),
          if (_errorMessage != null) _errorText(_errorMessage!),
          FilledButton(
            onPressed:
                (_joining || _selectedIncident == null || _selectedTeam == null)
                ? null
                : () => _join(),
            child: _joining
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Load incident'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: (_joining || _selectedIncident == null)
                ? null
                : () => _join(withoutTeam: true),
            child: const Text('Enter without a field team'),
          ),
        ],
      ),
    );
  }
}
