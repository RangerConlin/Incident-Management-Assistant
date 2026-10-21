import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../services/sarapp_api_client.dart';
import '../utils/json_parsing.dart';
import '../utils/session_identity.dart';
import '../widgets/app_drawer.dart';

/// Team management for mobile: assign people to the team, manage team-linked
/// resources, and edit/remove those assignments from the drawer menu.
class TeamManagementScreen extends StatefulWidget {
  const TeamManagementScreen({
    super.key,
    required this.args,
    SarAppApiClient? apiClient,
  }) : _injectedApiClient = apiClient;

  final HomeNavArgs args;
  final SarAppApiClient? _injectedApiClient;

  @override
  State<TeamManagementScreen> createState() => _TeamManagementScreenState();
}

class _TeamManagementScreenState extends State<TeamManagementScreen>
    with SingleTickerProviderStateMixin {
  late final SarAppApiClient _apiClient =
      widget._injectedApiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget._injectedApiClient == null;
  late final TabController _tabController =
      TabController(length: 3, vsync: this)..addListener(() {
        if (!_tabController.indexIsChanging && mounted) {
          setState(() {});
        }
      });

  Map<String, dynamic>? _team;
  List<Map<String, dynamic>> _personnel = const [];
  List<Map<String, dynamic>> _resources = const [];
  bool _loading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _load();
  }

  int? get _teamIntId =>
      parseInt(_team?['int_id']) ?? parseInt(widget.args.teamId);

  String get _teamName =>
      '${_team?['name'] ?? widget.args.teamName}'.trim().isEmpty
      ? widget.args.teamName
      : '${_team?['name'] ?? widget.args.teamName}';

  String get _changedBy {
    return SessionIdentity.displayName(
      widget.args.session,
      fallback: 'Mobile Team Menu',
    );
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final team = await _loadTeam();
      final roster = await _apiClient.fetchCheckinRoster(
        widget.args.incidentId,
      );
      final resources = await _apiClient.fetchResourceStatuses(
        widget.args.incidentId,
      );
      if (!mounted) return;
      setState(() {
        _team = team;
        _personnel =
            roster
                .whereType<Map>()
                .map((e) => Map<String, dynamic>.from(e))
                .where(_belongsToCurrentTeam)
                .toList()
              ..sort((a, b) => _personName(a).compareTo(_personName(b)));
        _resources =
            resources
                .whereType<Map>()
                .map((e) => Map<String, dynamic>.from(e))
                .where(_isTeamResource)
                .where(
                  (row) =>
                      '${row['entity_type'] ?? ''}'.toLowerCase() !=
                      'personnel',
                )
                .toList()
              ..sort((a, b) => _resourceName(a).compareTo(_resourceName(b)));
      });
    } on SarAppApiException catch (e) {
      if (mounted) {
        setState(() => _errorMessage = e.message);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _errorMessage = '$e');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<Map<String, dynamic>> _loadTeam() async {
    final directTeamId = parseInt(widget.args.teamId);
    if (directTeamId != null) {
      return _apiClient.fetchTeam(widget.args.incidentId, '$directTeamId');
    }
    final teams = await _apiClient.fetchTeams(widget.args.incidentId);
    final match = teams
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .cast<Map<String, dynamic>?>()
        .firstWhere(
          (row) =>
              '${row?['name'] ?? ''}'.trim().toLowerCase() ==
              widget.args.teamName.trim().toLowerCase(),
          orElse: () => null,
        );
    if (match == null) {
      throw SarAppApiException(
        'Unable to find team "${widget.args.teamName}".',
      );
    }
    final intId = parseInt(match['int_id']);
    if (intId == null) {
      throw SarAppApiException(
        'The selected team does not have a valid team id.',
      );
    }
    return _apiClient.fetchTeam(widget.args.incidentId, '$intId');
  }

  bool _belongsToCurrentTeam(Map<String, dynamic> entry) {
    final teamId = '${entry['team_id'] ?? ''}'.trim();
    final assignmentRef = '${entry['assignment_reference'] ?? ''}'.trim();
    final teamName = '${entry['team'] ?? entry['assigned_to'] ?? ''}'
        .trim()
        .toLowerCase();
    final currentId = '${_teamIntId ?? ''}';
    return (teamId.isNotEmpty && teamId == currentId) ||
        (assignmentRef.isNotEmpty && assignmentRef == currentId) ||
        (teamName.isNotEmpty && teamName == _teamName.trim().toLowerCase());
  }

  bool _isTeamResource(Map<String, dynamic> row) {
    final assignmentRef = '${row['assignment_reference'] ?? ''}'.trim();
    final assignedTo = '${row['assigned_to'] ?? ''}'.trim().toLowerCase();
    final currentId = '${_teamIntId ?? ''}';
    return (assignmentRef.isNotEmpty && assignmentRef == currentId) ||
        (assignedTo.isNotEmpty && assignedTo == _teamName.trim().toLowerCase());
  }

  String _personName(Map<String, dynamic> row) {
    final name = '${row['name'] ?? row['resource_name'] ?? ''}'.trim();
    return name.isNotEmpty
        ? name
        : 'Person ${row['person_record'] ?? row['person_id'] ?? ''}';
  }

  String _personRole(Map<String, dynamic> row) {
    return '${row['role'] ?? row['primary_role'] ?? row['role_on_team'] ?? ''}'
        .trim();
  }

  String _resourceName(Map<String, dynamic> row) {
    final name = '${row['resource_name'] ?? row['name'] ?? ''}'.trim();
    return name.isNotEmpty
        ? name
        : 'Resource ${row['record_id'] ?? row['resource_id'] ?? ''}';
  }

  String _resourceTypeLabel(Map<String, dynamic> row) {
    final raw = '${row['resource_type'] ?? row['entity_type'] ?? 'Resource'}'
        .trim();
    return raw.isEmpty ? 'Resource' : raw;
  }

  Set<String> _currentTeamAssetIds(String entityType) {
    final fields = switch (entityType) {
      'vehicle' => ['vehicles_json', 'vehicle_ids'],
      'equipment' => ['equipment_json', 'equipment_ids'],
      'aircraft' => ['aircraft_json', 'aircraft_ids'],
      _ => const <String>[],
    };
    if (fields.isEmpty) return <String>{};
    for (final field in fields) {
      final value = _team?[field];
      if (value is List) {
        final ids = value
            .map((e) => '$e'.trim())
            .where((e) => e.isNotEmpty)
            .toSet();
        if (ids.isNotEmpty) return ids;
      }
      final raw = '${value ?? ''}'.trim();
      if (raw.isEmpty) continue;
      try {
        final decoded = jsonDecode(raw);
        if (decoded is List) {
          final ids = decoded
              .map((e) => '$e'.trim())
              .where((e) => e.isNotEmpty)
              .toSet();
          if (ids.isNotEmpty) return ids;
        }
      } catch (_) {}
      if (raw.isNotEmpty && !raw.startsWith('[')) {
        return {raw};
      }
    }
    return <String>{};
  }

  Future<void> _syncTeamAssetIds(
    String entityType,
    String recordId, {
    required bool add,
  }) async {
    final teamIntId = _teamIntId;
    if (teamIntId == null) {
      throw SarAppApiException('This team is missing a valid id.');
    }
    final ids = _currentTeamAssetIds(entityType);
    if (add) {
      ids.add(recordId);
    } else {
      ids.remove(recordId);
    }
    final sorted = ids.toList()..sort();
    final body = switch (entityType) {
      'vehicle' => {'vehicles_json': jsonEncode(sorted), 'vehicle_ids': sorted},
      'equipment' => {'equipment_json': jsonEncode(sorted)},
      'aircraft' => {
        'aircraft_json': jsonEncode(sorted),
        'aircraft_ids': sorted,
      },
      _ => <String, dynamic>{},
    };
    if (body.isEmpty) return;
    await _apiClient.updateTeam(
      incidentId: widget.args.incidentId,
      teamIntId: '$teamIntId',
      body: body,
    );
  }

  Future<void> _showError(Object error) async {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('$error')));
  }

  Future<void> _showSaved(String message) async {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _syncTeamMemberIds(Set<int> memberIds) async {
    final teamIntId = _teamIntId;
    if (teamIntId == null) {
      throw SarAppApiException('This team is missing a valid id.');
    }
    await _apiClient.updateTeam(
      incidentId: widget.args.incidentId,
      teamIntId: '$teamIntId',
      body: {'member_person_records': memberIds.toList()..sort()},
    );
  }

  Set<int> _currentMemberIds() {
    final values = _team?['member_person_records'];
    if (values is List) {
      return values.map(parseInt).whereType<int>().toSet();
    }
    return <int>{};
  }

  Future<void> _addMember() async {
    final person = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _PersonSearchDialog(
        apiClient: _apiClient,
        incidentId: widget.args.incidentId,
      ),
    );
    if (person == null) return;
    final personRecord = parseInt(person['person_record']);
    if (personRecord == null) {
      await _showError('The selected person is missing a valid person record.');
      return;
    }
    try {
      Map<String, dynamic> existing = <String, dynamic>{};
      try {
        existing = await _apiClient.fetchCheckin(
          widget.args.incidentId,
          '$personRecord',
        );
      } on SarAppApiException catch (e) {
        if (e.statusCode != 404) rethrow;
      }
      await _apiClient.submitCheckin(
        incidentId: widget.args.incidentId,
        personId: '$personRecord',
        checkinPayload: {
          ...existing,
          'status': existing['status'] ?? 'Checked In',
          'team_id': '${_teamIntId ?? widget.args.teamId}',
          'location': existing['location'] ?? 'ICP',
          'notes': existing['notes'],
          'arrival_time':
              existing['arrival_time'] ??
              DateTime.now().toUtc().toIso8601String(),
        },
      );
      final memberIds = _currentMemberIds()..add(personRecord);
      await _syncTeamMemberIds(memberIds);
      await _load();
      await _showSaved('Added ${_personName(person)} to $_teamName.');
    } catch (e) {
      await _showError(e);
    }
  }

  Future<void> _editMember(Map<String, dynamic> row) async {
    final updated = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _PersonEditDialog(
        personName: _personName(row),
        initialStatus: '${row['status'] ?? row['ci_status'] ?? 'Checked In'}',
        initialLocation: '${row['location'] ?? ''}',
        initialNotes: '${row['notes'] ?? ''}',
      ),
    );
    if (updated == null) return;
    final personRecord = parseInt(row['person_record']);
    if (personRecord == null) {
      await _showError('This roster entry is missing a person record.');
      return;
    }
    try {
      await _apiClient.patchCheckin(
        incidentId: widget.args.incidentId,
        personId: '$personRecord',
        checkinPayload: {
          'status': updated['status'],
          'location': updated['location'],
          'notes': updated['notes'],
          'team_id': '${_teamIntId ?? widget.args.teamId}',
        },
      );
      await _load();
      await _showSaved('Updated ${_personName(row)}.');
    } catch (e) {
      await _showError(e);
    }
  }

  Future<void> _removeMember(Map<String, dynamic> row) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Team Member'),
        content: Text('Remove ${_personName(row)} from $_teamName?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final personRecord = parseInt(row['person_record']);
    if (personRecord == null) {
      await _showError('This roster entry is missing a person record.');
      return;
    }
    try {
      await _apiClient.patchCheckin(
        incidentId: widget.args.incidentId,
        personId: '$personRecord',
        checkinPayload: {'team_id': null},
      );
      final memberIds = _currentMemberIds()..remove(personRecord);
      await _syncTeamMemberIds(memberIds);
      await _load();
      await _showSaved('Removed ${_personName(row)} from $_teamName.');
    } catch (e) {
      await _showError(e);
    }
  }

  Future<void> _addResource() async {
    final resource = await showDialog<_ResourceCandidate>(
      context: context,
      builder: (context) => _ResourcePickerDialog(
        apiClient: _apiClient,
        incidentId: widget.args.incidentId,
        currentTeamId: '${_teamIntId ?? widget.args.teamId}',
        currentTeamName: _teamName,
      ),
    );
    if (resource == null || !mounted) return;
    final details = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _ResourceEditDialog(
        initialResourceType: resource.entityType,
        initialResourceId: resource.recordId,
        initialStatus: resource.currentStatus ?? 'Assigned',
        initialLocation: resource.currentLocation ?? '',
        initialNotes: resource.currentNotes ?? '',
        readOnlyIdentity: true,
        identityLabel: resource.displayName,
      ),
    );
    if (details == null) return;
    try {
      await _apiClient.upsertIncidentResourceStatus(
        incidentId: widget.args.incidentId,
        body: {
          'entity_type': resource.entityType,
          'record_id': resource.recordId,
          'resource_id': resource.recordId,
          'resource_name': resource.displayName,
          'resource_type': resource.typeLabel,
          'status': details['status'],
          'assigned_to': _teamName,
          'assignment_reference': '${_teamIntId ?? widget.args.teamId}',
          'location': details['location'],
          'notes': details['notes'],
          'changed_by': _changedBy,
        },
      );
      await _syncTeamAssetIds(
        resource.entityType,
        resource.recordId,
        add: true,
      );
      await _load();
      await _showSaved('Assigned ${resource.displayName} to $_teamName.');
    } catch (e) {
      await _showError(e);
    }
  }

  Future<void> _editResource(Map<String, dynamic> row) async {
    final updated = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _ResourceEditDialog(
        initialResourceType: '${row['entity_type'] ?? 'vehicle'}',
        initialResourceId: '${row['record_id'] ?? row['resource_id'] ?? ''}'
            .trim(),
        initialStatus: '${row['status'] ?? 'Assigned'}',
        initialLocation: '${row['location'] ?? ''}',
        initialNotes: '${row['notes'] ?? ''}',
        readOnlyIdentity: true,
      ),
    );
    if (updated == null) return;
    final itemId = '${row['id'] ?? row['_id'] ?? ''}'.trim();
    if (itemId.isEmpty) {
      await _showError(
        'This resource cannot be edited because its record id is missing.',
      );
      return;
    }
    try {
      await _apiClient.patchIncidentResource(
        incidentId: widget.args.incidentId,
        itemId: itemId,
        body: {
          'assigned_to': _teamName,
          'assignment_reference': '${_teamIntId ?? widget.args.teamId}',
          'location': updated['location'],
          'notes': updated['notes'],
          'resource_name': row['resource_name'],
        },
      );
      await _apiClient.patchIncidentResourceStatus(
        incidentId: widget.args.incidentId,
        itemId: itemId,
        body: {'status': updated['status'], 'changed_by': _changedBy},
      );
      await _syncTeamAssetIds(
        '${row['entity_type'] ?? ''}'.toLowerCase(),
        '${row['record_id'] ?? row['resource_id'] ?? ''}'.trim(),
        add: true,
      );
      await _load();
      await _showSaved('Updated ${_resourceName(row)}.');
    } catch (e) {
      await _showError(e);
    }
  }

  Future<void> _removeResource(Map<String, dynamic> row) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Team Resource'),
        content: Text('Remove ${_resourceName(row)} from $_teamName?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final itemId = '${row['id'] ?? row['_id'] ?? ''}'.trim();
    if (itemId.isEmpty) {
      await _showError(
        'This resource cannot be updated because its record id is missing.',
      );
      return;
    }
    try {
      await _apiClient.patchIncidentResource(
        incidentId: widget.args.incidentId,
        itemId: itemId,
        body: {'assigned_to': null, 'assignment_reference': null},
      );
      await _syncTeamAssetIds(
        '${row['entity_type'] ?? ''}'.toLowerCase(),
        '${row['record_id'] ?? row['resource_id'] ?? ''}'.trim(),
        add: false,
      );
      await _load();
      await _showSaved('Removed ${_resourceName(row)} from $_teamName.');
    } catch (e) {
      await _showError(e);
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_teamName),
        actions: [
          IconButton(
            onPressed: _loading
                ? null
                : () {
                    switch (_tabController.index) {
                      case 0:
                        _addMember();
                        break;
                      case 1:
                        _addResource();
                        break;
                      default:
                        _load();
                        break;
                    }
                  },
            icon: Icon(_tabController.index == 2 ? Icons.refresh : Icons.add),
            tooltip: _tabController.index == 0
                ? 'Add team member'
                : _tabController.index == 1
                ? 'Add team resource'
                : 'Refresh',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Members'),
            Tab(text: 'Resources'),
            Tab(text: 'Check-In'),
          ],
        ),
      ),
      drawer: AppDrawer(args: widget.args),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildMembersTab(context),
                  _buildResourcesTab(context),
                  _buildCheckinTab(context),
                ],
              ),
            ),
    );
  }

  Widget _buildMembersTab(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_errorMessage != null)
          _MessageCard(
            message: _errorMessage!,
            color: Theme.of(context).colorScheme.errorContainer,
          ),
        _SectionHeader(
          title: 'Team Members',
          subtitle: 'Add, update, or remove people assigned to this team.',
          actionLabel: 'Add member',
          onAction: _addMember,
        ),
        if (_personnel.isEmpty)
          const _EmptyCard(
            message:
                'No team members are currently assigned in the mobile roster.',
          )
        else
          ..._personnel.map(
            (entry) => Card(
              child: ListTile(
                leading: const CircleAvatar(child: Icon(Icons.person_outline)),
                title: Text(_personName(entry)),
                subtitle: Text(
                  [
                    if (_personRole(entry).isNotEmpty) _personRole(entry),
                    if ('${entry['location'] ?? ''}'.trim().isNotEmpty)
                      '${entry['location']}',
                  ].join(' • '),
                ),
                trailing: PopupMenuButton<String>(
                  onSelected: (value) {
                    switch (value) {
                      case 'edit':
                        _editMember(entry);
                        break;
                      case 'remove':
                        _removeMember(entry);
                        break;
                    }
                  },
                  itemBuilder: (context) => const [
                    PopupMenuItem(value: 'edit', child: Text('Edit')),
                    PopupMenuItem(value: 'remove', child: Text('Remove')),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildResourcesTab(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_errorMessage != null)
          _MessageCard(
            message: _errorMessage!,
            color: Theme.of(context).colorScheme.errorContainer,
          ),
        const _MessageCard(
          message:
              'Pick from live vehicle, aircraft, and equipment catalogs. Assets already assigned to another team are shown but locked.',
        ),
        _SectionHeader(
          title: 'Team Resources',
          subtitle:
              'Manage vehicles, aircraft, and equipment assigned to this team.',
          actionLabel: 'Add resource',
          onAction: _addResource,
        ),
        if (_resources.isEmpty)
          const _EmptyCard(
            message: 'No resources are currently assigned to this team.',
          )
        else
          ..._resources.map(
            (resource) => Card(
              child: ListTile(
                leading: Icon(_resourceIcon(resource)),
                title: Text(_resourceName(resource)),
                subtitle: Text(_resourceTypeLabel(resource)),
                trailing: PopupMenuButton<String>(
                  onSelected: (value) {
                    switch (value) {
                      case 'edit':
                        _editResource(resource);
                        break;
                      case 'remove':
                        _removeResource(resource);
                        break;
                    }
                  },
                  itemBuilder: (context) => const [
                    PopupMenuItem(value: 'edit', child: Text('Edit')),
                    PopupMenuItem(value: 'remove', child: Text('Remove')),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildCheckinTab(BuildContext context) {
    final checkedIn = _personnel.where((row) {
      final status = '${row['status'] ?? row['ci_status'] ?? ''}'.toLowerCase();
      return status.contains('checked') ||
          status == 'available' ||
          status == 'assigned';
    }).toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const _MessageCard(
          message:
              'Member check-in details are editable from the Members tab. This view highlights who is currently checked in under the team.',
        ),
        _SectionHeader(
          title: 'Checked-In Members',
          subtitle: '${checkedIn.length} currently checked in',
        ),
        if (checkedIn.isEmpty)
          const _EmptyCard(
            message: 'No assigned team members are checked in yet.',
          )
        else
          ...checkedIn.map(
            (entry) => Card(
              child: ListTile(
                leading: const Icon(Icons.badge_outlined),
                title: Text(_personName(entry)),
                subtitle: Text(_personRole(entry)),
                trailing: Text(
                  '${entry['status'] ?? entry['ci_status'] ?? ''}',
                ),
                onTap: () => _editMember(entry),
              ),
            ),
          ),
      ],
    );
  }

  IconData _resourceIcon(Map<String, dynamic> row) {
    switch ('${row['entity_type'] ?? ''}'.toLowerCase()) {
      case 'aircraft':
        return Icons.flight_outlined;
      case 'equipment':
        return Icons.build_outlined;
      case 'vehicle':
      default:
        return Icons.local_shipping_outlined;
    }
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  final String title;
  final String subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
          if (actionLabel != null && onAction != null)
            TextButton.icon(
              onPressed: onAction,
              icon: const Icon(Icons.add),
              label: Text(actionLabel!),
            ),
        ],
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.message, this.color});

  final String message;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: color,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(padding: const EdgeInsets.all(12), child: Text(message)),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(padding: const EdgeInsets.all(16), child: Text(message)),
    );
  }
}

class _PersonSearchDialog extends StatefulWidget {
  const _PersonSearchDialog({
    required this.apiClient,
    required this.incidentId,
  });

  final SarAppApiClient apiClient;
  final String incidentId;

  @override
  State<_PersonSearchDialog> createState() => _PersonSearchDialogState();
}

class _PersonSearchDialogState extends State<_PersonSearchDialog> {
  final TextEditingController _queryController = TextEditingController();
  List<Map<String, dynamic>> _results = const [];
  bool _loading = false;
  String? _error;

  Future<void> _search() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await widget.apiClient.searchPersonnel(
        widget.incidentId,
        query: _queryController.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _results = results
            .whereType<Map>()
            .map((row) => Map<String, dynamic>.from(row))
            .toList();
      });
    } on SarAppApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Team Member'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _queryController,
              textInputAction: TextInputAction.search,
              decoration: const InputDecoration(
                labelText: 'Search personnel',
                hintText: 'Name, callsign, or person id',
              ),
              onSubmitted: (_) => _search(),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _loading ? null : _search,
                icon: const Icon(Icons.search),
                label: const Text('Search'),
              ),
            ),
            const SizedBox(height: 12),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(12),
                child: CircularProgressIndicator(),
              )
            else if (_results.isEmpty)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Text('Search to find incident personnel to assign.'),
              )
            else
              SizedBox(
                height: 280,
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _results.length,
                  itemBuilder: (context, index) {
                    final person = _results[index];
                    return ListTile(
                      title: Text('${person['name'] ?? 'Unknown'}'),
                      subtitle: Text(
                        [
                          if ('${person['primary_role'] ?? ''}'
                              .trim()
                              .isNotEmpty)
                            '${person['primary_role']}',
                          if ('${person['person_record'] ?? ''}'
                              .trim()
                              .isNotEmpty)
                            'ID ${person['person_record']}',
                        ].join(' • '),
                      ),
                      onTap: () => Navigator.of(context).pop(person),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}

class _PersonEditDialog extends StatefulWidget {
  const _PersonEditDialog({
    required this.personName,
    required this.initialStatus,
    required this.initialLocation,
    required this.initialNotes,
  });

  final String personName;
  final String initialStatus;
  final String initialLocation;
  final String initialNotes;

  @override
  State<_PersonEditDialog> createState() => _PersonEditDialogState();
}

class _PersonEditDialogState extends State<_PersonEditDialog> {
  static const _statusOptions = [
    'Checked In',
    'Assigned',
    'Available',
    'Enroute',
    'Pending',
    'Out of Service',
  ];

  late String _status = _statusOptions.contains(widget.initialStatus)
      ? widget.initialStatus
      : _statusOptions.first;
  late final TextEditingController _locationController = TextEditingController(
    text: widget.initialLocation,
  );
  late final TextEditingController _notesController = TextEditingController(
    text: widget.initialNotes,
  );

  @override
  void dispose() {
    _locationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Edit ${widget.personName}'),
      content: SizedBox(
        width: 380,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              initialValue: _status,
              decoration: const InputDecoration(labelText: 'Status'),
              items: _statusOptions
                  .map(
                    (status) =>
                        DropdownMenuItem(value: status, child: Text(status)),
                  )
                  .toList(),
              onChanged: (value) => setState(() => _status = value ?? _status),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _locationController,
              decoration: const InputDecoration(labelText: 'Location'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _notesController,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Notes'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(context).pop({
              'status': _status,
              'location': _locationController.text.trim(),
              'notes': _notesController.text.trim(),
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _ResourceCandidate {
  const _ResourceCandidate({
    required this.entityType,
    required this.recordId,
    required this.displayName,
    required this.typeLabel,
    required this.subtitle,
    required this.searchText,
    this.statusId,
    this.assignedTo,
    this.assignmentReference,
    this.currentStatus,
    this.currentLocation,
    this.currentNotes,
  });

  final String entityType;
  final String recordId;
  final String displayName;
  final String typeLabel;
  final String subtitle;
  final String searchText;
  final String? statusId;
  final String? assignedTo;
  final String? assignmentReference;
  final String? currentStatus;
  final String? currentLocation;
  final String? currentNotes;

  bool isAssignedToTeam(String teamId, String teamName) {
    final normalizedTeamId = teamId.trim();
    final normalizedTeamName = teamName.trim().toLowerCase();
    return (assignmentReference ?? '').trim() == normalizedTeamId ||
        (assignedTo ?? '').trim().toLowerCase() == normalizedTeamName;
  }

  bool get isAssignedElsewhere {
    return (assignmentReference ?? '').trim().isNotEmpty ||
        (assignedTo ?? '').trim().isNotEmpty;
  }
}

class _ResourcePickerDialog extends StatefulWidget {
  const _ResourcePickerDialog({
    required this.apiClient,
    required this.incidentId,
    required this.currentTeamId,
    required this.currentTeamName,
  });

  final SarAppApiClient apiClient;
  final String incidentId;
  final String currentTeamId;
  final String currentTeamName;

  @override
  State<_ResourcePickerDialog> createState() => _ResourcePickerDialogState();
}

class _ResourcePickerDialogState extends State<_ResourcePickerDialog> {
  final TextEditingController _searchController = TextEditingController();
  List<_ResourceCandidate> _all = const [];
  bool _loading = true;
  String? _error;
  String _typeFilter = 'all';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<dynamic>([
        widget.apiClient.fetchMasterVehicles(),
        widget.apiClient.fetchMasterAircraft(),
        widget.apiClient.fetchMasterEquipment(limit: 400),
        widget.apiClient.fetchResourceStatuses(widget.incidentId),
      ]);
      final statusRows = (results[3] as List<dynamic>)
          .whereType<Map>()
          .map((row) => Map<String, dynamic>.from(row))
          .toList();
      final statusByKey = <String, Map<String, dynamic>>{};
      for (final row in statusRows) {
        final key =
            '${row['entity_type'] ?? ''}:${row['record_id'] ?? row['resource_id'] ?? ''}';
        statusByKey[key] = row;
      }
      final candidates =
          <_ResourceCandidate>[
            ..._buildVehicleCandidates(
              results[0] as List<dynamic>,
              statusByKey,
            ),
            ..._buildAircraftCandidates(
              results[1] as List<dynamic>,
              statusByKey,
            ),
            ..._buildEquipmentCandidates(
              results[2] as List<dynamic>,
              statusByKey,
            ),
          ]..sort(
            (a, b) => a.displayName.toLowerCase().compareTo(
              b.displayName.toLowerCase(),
            ),
          );
      if (!mounted) return;
      setState(() => _all = candidates);
    } on SarAppApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<_ResourceCandidate> _buildVehicleCandidates(
    List<dynamic> rows,
    Map<String, Map<String, dynamic>> statusByKey,
  ) {
    return rows.whereType<Map>().map((raw) {
      final row = Map<String, dynamic>.from(raw);
      final recordId = '${row['vehicle_record'] ?? row['vehicle_id'] ?? ''}'
          .trim();
      final vehicleId = '${row['vehicle_id'] ?? ''}'.trim();
      final plate = '${row['license_plate'] ?? ''}'.trim();
      final type = '${row['type'] ?? row['type_id'] ?? 'Vehicle'}'.trim();
      final display =
          [
            if (vehicleId.isNotEmpty) vehicleId,
            if (plate.isNotEmpty && plate != vehicleId) plate,
          ].isEmpty
          ? 'Vehicle $recordId'
          : [
              if (vehicleId.isNotEmpty) vehicleId,
              if (plate.isNotEmpty && plate != vehicleId) plate,
            ].join(' • ');
      return _candidateFromStatus(
        entityType: 'vehicle',
        recordId: recordId,
        displayName: display,
        typeLabel: 'Vehicle',
        subtitle: type,
        searchParts: [
          display,
          vehicleId,
          plate,
          type,
          '${row['organization'] ?? ''}',
        ],
        statusByKey: statusByKey,
      );
    }).toList();
  }

  List<_ResourceCandidate> _buildAircraftCandidates(
    List<dynamic> rows,
    Map<String, Map<String, dynamic>> statusByKey,
  ) {
    return rows.whereType<Map>().map((raw) {
      final row = Map<String, dynamic>.from(raw);
      final recordId = '${row['aircraft_record'] ?? row['aircraft_id'] ?? ''}'
          .trim();
      final aircraftId = '${row['aircraft_id'] ?? ''}'.trim();
      final callsign = '${row['callsign'] ?? ''}'.trim();
      final tail = '${row['tail_number'] ?? ''}'.trim();
      final type = '${row['type'] ?? 'Aircraft'}'.trim();
      final display =
          [
            if (callsign.isNotEmpty) callsign,
            if (aircraftId.isNotEmpty && aircraftId != callsign) aircraftId,
            if (tail.isNotEmpty && tail != aircraftId) tail,
          ].isEmpty
          ? 'Aircraft $recordId'
          : [
              if (callsign.isNotEmpty) callsign,
              if (aircraftId.isNotEmpty && aircraftId != callsign) aircraftId,
              if (tail.isNotEmpty && tail != aircraftId) tail,
            ].join(' • ');
      return _candidateFromStatus(
        entityType: 'aircraft',
        recordId: recordId,
        displayName: display,
        typeLabel: 'Aircraft',
        subtitle: type,
        searchParts: [
          display,
          aircraftId,
          callsign,
          tail,
          type,
          '${row['organization'] ?? ''}',
        ],
        statusByKey: statusByKey,
      );
    }).toList();
  }

  List<_ResourceCandidate> _buildEquipmentCandidates(
    List<dynamic> rows,
    Map<String, Map<String, dynamic>> statusByKey,
  ) {
    return rows.whereType<Map>().map((raw) {
      final row = Map<String, dynamic>.from(raw);
      final recordId = '${row['equipment_record'] ?? row['equipment_id'] ?? ''}'
          .trim();
      final equipmentId = '${row['equipment_id'] ?? ''}'.trim();
      final name = '${row['name'] ?? ''}'.trim();
      final serial = '${row['serial_number'] ?? ''}'.trim();
      final type = '${row['type'] ?? 'Equipment'}'.trim();
      final display =
          [
            if (name.isNotEmpty) name,
            if (equipmentId.isNotEmpty && equipmentId != name) equipmentId,
            if (serial.isNotEmpty && serial != equipmentId) serial,
          ].isEmpty
          ? 'Equipment $recordId'
          : [
              if (name.isNotEmpty) name,
              if (equipmentId.isNotEmpty && equipmentId != name) equipmentId,
              if (serial.isNotEmpty && serial != equipmentId) serial,
            ].join(' • ');
      return _candidateFromStatus(
        entityType: 'equipment',
        recordId: recordId,
        displayName: display,
        typeLabel: 'Equipment',
        subtitle: type,
        searchParts: [display, name, equipmentId, serial, type],
        statusByKey: statusByKey,
      );
    }).toList();
  }

  _ResourceCandidate _candidateFromStatus({
    required String entityType,
    required String recordId,
    required String displayName,
    required String typeLabel,
    required String subtitle,
    required List<String> searchParts,
    required Map<String, Map<String, dynamic>> statusByKey,
  }) {
    final status = statusByKey['$entityType:$recordId'];
    return _ResourceCandidate(
      entityType: entityType,
      recordId: recordId,
      displayName: displayName,
      typeLabel: typeLabel,
      subtitle: subtitle,
      searchText: searchParts.join(' ').toLowerCase(),
      statusId: '${status?['id'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['id']}',
      assignedTo: '${status?['assigned_to'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['assigned_to']}',
      assignmentReference:
          '${status?['assignment_reference'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['assignment_reference']}',
      currentStatus: '${status?['status'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['status']}',
      currentLocation: '${status?['location'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['location']}',
      currentNotes: '${status?['notes'] ?? ''}'.trim().isEmpty
          ? null
          : '${status?['notes']}',
    );
  }

  List<_ResourceCandidate> get _filtered {
    final query = _searchController.text.trim().toLowerCase();
    return _all.where((candidate) {
      if (_typeFilter != 'all' && candidate.entityType != _typeFilter) {
        return false;
      }
      if (query.isNotEmpty && !candidate.searchText.contains(query)) {
        return false;
      }
      return true;
    }).toList();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final results = _filtered;
    return AlertDialog(
      title: const Text('Pick Team Resource'),
      content: SizedBox(
        width: 640,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                labelText: 'Search resources',
                hintText: 'Name, callsign, unit id, plate, serial',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                for (final filter in const [
                  'all',
                  'vehicle',
                  'aircraft',
                  'equipment',
                ])
                  ChoiceChip(
                    label: Text(
                      filter == 'all'
                          ? 'All'
                          : filter[0].toUpperCase() + filter.substring(1),
                    ),
                    selected: _typeFilter == filter,
                    onSelected: (_) => setState(() => _typeFilter = filter),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              )
            else if (_loading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: CircularProgressIndicator(),
              )
            else if (results.isEmpty)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Text('No matching resources found.'),
              )
            else
              SizedBox(
                height: 420,
                child: ListView.builder(
                  itemCount: results.length,
                  itemBuilder: (context, index) {
                    final candidate = results[index];
                    final assignedToThisTeam = candidate.isAssignedToTeam(
                      widget.currentTeamId,
                      widget.currentTeamName,
                    );
                    return Card(
                      child: ListTile(
                        leading: Icon(
                          _resourceIconForType(candidate.entityType),
                        ),
                        title: Text(candidate.displayName),
                        subtitle: Text(candidate.subtitle),
                        trailing: _AssignmentBadge(
                          assignedToThisTeam: assignedToThisTeam,
                          assignedTo: candidate.assignedTo,
                          hasIncidentStatus: candidate.statusId != null,
                        ),
                        onTap: () => Navigator.of(context).pop(candidate),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
      ],
    );
  }

  IconData _resourceIconForType(String entityType) {
    switch (entityType) {
      case 'aircraft':
        return Icons.flight_outlined;
      case 'equipment':
        return Icons.build_outlined;
      case 'vehicle':
      default:
        return Icons.local_shipping_outlined;
    }
  }
}

class _AssignmentBadge extends StatelessWidget {
  const _AssignmentBadge({
    required this.assignedToThisTeam,
    required this.assignedTo,
    required this.hasIncidentStatus,
  });

  final bool assignedToThisTeam;
  final String? assignedTo;
  final bool hasIncidentStatus;

  @override
  Widget build(BuildContext context) {
    final label = assignedToThisTeam
        ? 'On this team'
        : !hasIncidentStatus
        ? 'Not checked in'
        : (assignedTo == null || assignedTo!.trim().isEmpty)
        ? 'Unassigned'
        : assignedTo!;
    final bg = assignedToThisTeam
        ? Theme.of(context).colorScheme.primaryContainer
        : !hasIncidentStatus
        ? Theme.of(context).colorScheme.tertiaryContainer
        : (assignedTo == null || assignedTo!.trim().isEmpty)
        ? Theme.of(context).colorScheme.surfaceContainerHighest
        : Theme.of(context).colorScheme.secondaryContainer;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label, style: Theme.of(context).textTheme.labelSmall),
    );
  }
}

class _ResourceEditDialog extends StatefulWidget {
  const _ResourceEditDialog({
    this.initialResourceType = 'vehicle',
    this.initialResourceId = '',
    this.initialStatus = 'Assigned',
    this.initialLocation = '',
    this.initialNotes = '',
    this.readOnlyIdentity = false,
    this.identityLabel,
  });

  final String initialResourceType;
  final String initialResourceId;
  final String initialStatus;
  final String initialLocation;
  final String initialNotes;
  final bool readOnlyIdentity;
  final String? identityLabel;

  @override
  State<_ResourceEditDialog> createState() => _ResourceEditDialogState();
}

class _ResourceEditDialogState extends State<_ResourceEditDialog> {
  static const _types = ['vehicle', 'equipment', 'aircraft'];
  static const _statuses = [
    'Assigned',
    'Checked In',
    'Available',
    'Enroute',
    'Out of Service',
  ];

  late String _resourceType =
      _types.contains(widget.initialResourceType.toLowerCase())
      ? widget.initialResourceType.toLowerCase()
      : _types.first;
  late String _status = _statuses.contains(widget.initialStatus)
      ? widget.initialStatus
      : _statuses.first;
  late final TextEditingController _resourceIdController =
      TextEditingController(text: widget.initialResourceId);
  late final TextEditingController _locationController = TextEditingController(
    text: widget.initialLocation,
  );
  late final TextEditingController _notesController = TextEditingController(
    text: widget.initialNotes,
  );

  @override
  void dispose() {
    _resourceIdController.dispose();
    _locationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        widget.readOnlyIdentity ? 'Edit Team Resource' : 'Add Team Resource',
      ),
      content: SizedBox(
        width: 380,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.identityLabel != null) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  widget.identityLabel!,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              const SizedBox(height: 12),
            ],
            DropdownButtonFormField<String>(
              initialValue: _resourceType,
              decoration: const InputDecoration(labelText: 'Resource type'),
              items: _types
                  .map(
                    (type) => DropdownMenuItem(
                      value: type,
                      child: Text(type[0].toUpperCase() + type.substring(1)),
                    ),
                  )
                  .toList(),
              onChanged: widget.readOnlyIdentity
                  ? null
                  : (value) =>
                        setState(() => _resourceType = value ?? _resourceType),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _resourceIdController,
              readOnly: widget.readOnlyIdentity,
              decoration: const InputDecoration(
                labelText: 'Resource record id',
                hintText: 'Example: 7',
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _status,
              decoration: const InputDecoration(labelText: 'Status'),
              items: _statuses
                  .map(
                    (status) =>
                        DropdownMenuItem(value: status, child: Text(status)),
                  )
                  .toList(),
              onChanged: (value) => setState(() => _status = value ?? _status),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _locationController,
              decoration: const InputDecoration(labelText: 'Location'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _notesController,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Notes'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            if (!widget.readOnlyIdentity &&
                _resourceIdController.text.trim().isEmpty) {
              return;
            }
            Navigator.of(context).pop({
              'resourceType': _resourceType,
              'resourceId': _resourceIdController.text.trim(),
              'status': _status,
              'location': _locationController.text.trim(),
              'notes': _notesController.text.trim(),
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
