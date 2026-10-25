import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/mobile_incident_context.dart';
import '../models/narrative_entry.dart';
import '../models/task.dart';
import '../models/team.dart';
import '../models/team_type_definition.dart';
import '../services/app_presence_service.dart';
import '../services/chat_presence_service.dart';
import '../services/incident_context_poller.dart';
import '../services/push_notification_service.dart';
import '../services/sarapp_api_client.dart';
import '../services/session_store.dart';
import '../theme/app_theme.dart';
import '../utils/session_identity.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';
import '../widgets/field_action_grid.dart';
import '../widgets/incident_stat_tiles.dart';
import '../widgets/narrative_feed.dart';
import '../widgets/section_card.dart';
import '../widgets/staff_assignment_card.dart';
import '../widgets/team_overview_list.dart';
import 'coming_soon_screen.dart';
import 'field_dashboard_screen.dart';
import 'reference_library_screen.dart';
import 'safety_screen.dart';
import 'team_management_screen.dart';

/// Landing screen for any incident participant with no field team — "Staff
/// View". Shows the viewer's staff assignment(s) (if any), an incident-wide
/// status overview, and quick actions. See
/// apps/mobile/docs/incident_staff_ui_handoff.md for the backend contract
/// this is built against.
class IncidentStaffDashboardScreen extends StatefulWidget {
  const IncidentStaffDashboardScreen({
    super.key,
    required this.incidentId,
    required this.incidentName,
    required this.session,
    this.incidentType,
    SarAppApiClient? apiClient,
  }) : _injectedApiClient = apiClient;

  final String incidentId;
  final String incidentName;
  final String? incidentType;
  final Map<String, dynamic> session;
  final SarAppApiClient? _injectedApiClient;

  @override
  State<IncidentStaffDashboardScreen> createState() =>
      _IncidentStaffDashboardScreenState();
}

class _IncidentStaffDashboardScreenState
    extends State<IncidentStaffDashboardScreen> {
  late final SarAppApiClient _apiClient =
      widget._injectedApiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget._injectedApiClient == null;

  bool _loading = true;
  bool _offline = false;

  MobileIncidentContext? _mobileContext;
  List<Team> _teams = const [];
  Map<String, TeamTypeDefinition> _teamTypes = const {};
  Map<int, String> _taskTitleById = const {};
  List<Map<String, dynamic>> _objectives = const [];
  List<NarrativeEntry> _narratives = const [];
  int _openTasks = 0;
  int _personnelOnIncident = 0;
  int _openSafetyIssues = 0;
  int? _currentOpPeriod;

  String get _displayName => SessionIdentity.personId(widget.session);

  int? get _personRecord {
    final raw =
        widget.session['person_record'] ??
        widget.session['user']?['person_record'];
    return raw == null ? null : int.tryParse('$raw');
  }

  @override
  void initState() {
    super.initState();
    _load().then((_) async {
      if (!mounted) return;
      final personRecord =
          widget.session['person_record'] ??
          widget.session['user']?['person_record'];
      await AppPresenceService.start(
        incidentId: widget.incidentId,
        personId: _displayName,
        personRecord: personRecord == null ? null : '$personRecord',
      );
      ChatPresenceService.start(
        incidentId: widget.incidentId,
        userId: _displayName,
      );
      if (!mounted) return;
      await PushNotificationService.syncRegistration(
        personRecord: personRecord == null ? null : '$personRecord',
        personId: _displayName.isEmpty ? null : _displayName,
        incidentId: widget.incidentId,
      );
      if (!mounted) return;
      final record = _personRecord;
      if (record != null) {
        IncidentContextPoller.start(
          incidentId: widget.incidentId,
          personRecord: record,
          initialHasTeam: _mobileContext?.hasTeam ?? false,
          onUpdate: _onPollUpdate,
        );
      }
    });
  }

  @override
  void dispose() {
    IncidentContextPoller.stop();
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  bool _isTeamActive(Team team) {
    final key =
        TeamStatuses.keyForDisplayLabel(team.status) ??
        team.status.toLowerCase();
    return !const {'available', 'oos', 'complete'}.contains(key);
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _offline = false;
    });

    final record = _personRecord;
    if (record == null) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _offline = true;
      });
      return;
    }

    try {
      int? opPeriod;
      try {
        final periods = await _apiClient.fetchOpPeriods(widget.incidentId);
        final numbers = periods
            .map((e) => e is int ? e : int.tryParse('$e'))
            .whereType<int>()
            .toList();
        if (numbers.isNotEmpty) {
          opPeriod = numbers.reduce((a, b) => a > b ? a : b);
        }
      } catch (_) {
        // Operational-period lookup is best-effort only.
      }

      final results = await Future.wait<Object?>([
        _apiClient.fetchMobileIncidentContext(
          incidentId: widget.incidentId,
          personRecord: record,
        ),
        _apiClient.fetchTeams(widget.incidentId),
        _apiClient.fetchTasks(widget.incidentId),
        _apiClient.fetchCheckinRoster(widget.incidentId),
        _apiClient.fetchHazards(widget.incidentId, opPeriod: opPeriod),
        _apiClient.fetchObjectives(widget.incidentId),
        _apiClient.fetchNarratives(widget.incidentId),
        _apiClient.fetchTeamTypes(),
      ]);

      final mobileContext = results[0] as MobileIncidentContext;
      final teams = (results[1] as List)
          .whereType<Map>()
          .map((e) => Team.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      final tasks = (results[2] as List)
          .whereType<Map>()
          .map((e) => Task.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      final roster = results[3] as List;
      final hazards = results[4] as List;
      final objectives =
          (results[5] as List)
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
              .toList()
            ..sort(
              (a, b) => ((a['display_order'] as int?) ?? 0).compareTo(
                (b['display_order'] as int?) ?? 0,
              ),
            );
      final narratives =
          (results[6] as List)
              .whereType<Map>()
              .map((e) => NarrativeEntry.fromJson(Map<String, dynamic>.from(e)))
              .toList()
            ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
      final teamTypes = <String, TeamTypeDefinition>{};
      for (final raw in (results[7] as List).whereType<Map>()) {
        final definition = TeamTypeDefinition.fromJson(Map<String, dynamic>.from(raw));
        if (definition.code.isNotEmpty) teamTypes[definition.code] = definition;
      }

      final taskTitleById = <int, String>{
        for (final task in tasks)
          if (task.intId != null) task.intId!: task.title,
      };
      final openTasks = tasks
          .where((t) => t.status == 'Planned' || t.status == 'In Progress')
          .length;

      if (!mounted) return;
      setState(() {
        _mobileContext = mobileContext;
        _teams = teams;
        _teamTypes = teamTypes;
        _taskTitleById = taskTitleById;
        _objectives = objectives;
        _narratives = narratives;
        _openTasks = openTasks;
        _personnelOnIncident = roster.length;
        _openSafetyIssues = hazards.length;
        _currentOpPeriod = opPeriod;
        _loading = false;
        _offline = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _offline = true;
      });
    }
  }

  Future<void> _persistTeam(String teamId, String teamName) =>
      SessionStore.save(
        incidentId: widget.incidentId,
        incidentName: widget.incidentName,
        incidentType: widget.incidentType,
        teamId: teamId,
        teamName: teamName,
        session: widget.session,
      );

  void _switchToTeamView() {
    final mobileContext = _mobileContext;
    if (mobileContext == null || !mobileContext.hasTeam) return;
    _persistTeam(mobileContext.teamId, mobileContext.teamName);
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => FieldDashboardScreen(
          incidentId: widget.incidentId,
          incidentName: widget.incidentName,
          incidentType: widget.incidentType,
          teamId: mobileContext.teamId,
          teamName: mobileContext.teamName,
          session: widget.session,
        ),
      ),
      (route) => false,
    );
  }

  void _onPollUpdate(
    MobileIncidentContext mobileContext,
    TeamTransition transition,
  ) {
    if (!mounted) return;
    setState(() => _mobileContext = mobileContext);
    if (transition == TeamTransition.gained) {
      _persistTeam(mobileContext.teamId, mobileContext.teamName);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Added to ${mobileContext.teamName}'),
          action: SnackBarAction(
            label: 'Switch to Team View',
            onPressed: _switchToTeamView,
          ),
          duration: const Duration(seconds: 6),
        ),
      );
    }
  }

  HomeNavArgs get _navArgs => HomeNavArgs(
    incidentId: widget.incidentId,
    incidentName: widget.incidentName,
    incidentType: widget.incidentType,
    teamId: _mobileContext?.hasTeam == true ? _mobileContext!.teamId : '',
    teamName: _mobileContext?.hasTeam == true ? _mobileContext!.teamName : '',
    session: widget.session,
  );

  List<FieldActionItem> _quickActions() => [
    FieldActionItem(
      icon: Icons.chat_bubble_outline,
      label: 'Messages',
      onTap: () => AppBottomNav.navigateTo(context, AppTab.messages, _navArgs),
    ),
    FieldActionItem(
      icon: Icons.assignment_outlined,
      label: 'Forms',
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ComingSoonScreen(title: 'Forms', args: _navArgs),
        ),
      ),
    ),
    FieldActionItem(
      icon: Icons.health_and_safety_outlined,
      label: 'Safety / GAR',
      onTap: () => Navigator.of(
        context,
      ).push(MaterialPageRoute(builder: (_) => SafetyScreen(args: _navArgs))),
    ),
    FieldActionItem(
      icon: Icons.library_books_outlined,
      label: 'Reference Library',
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ReferenceLibraryScreen(args: _navArgs),
        ),
      ),
    ),
    FieldActionItem(
      icon: Icons.map_outlined,
      label: 'Map',
      onTap: () => AppBottomNav.navigateTo(context, AppTab.map, _navArgs),
    ),
  ];

  String get _headerSubtitle {
    if (_offline) return 'Offline';
    final opPrefix = _currentOpPeriod != null ? 'OP $_currentOpPeriod' : '';
    final assignments = _mobileContext?.staffAssignments ?? const [];
    final title = assignments.isNotEmpty
        ? '${assignments.first['title'] ?? ''}'
        : 'Incident Staff';
    return opPrefix.isEmpty ? title : '$opPrefix · $title';
  }

  @override
  Widget build(BuildContext context) {
    final hasTeamNow = _mobileContext?.hasTeam ?? false;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 96,
        leading: Builder(
          builder: (context) => IconButton(
            icon: const Icon(Icons.menu),
            tooltip: 'Menu',
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                widget.incidentName,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                _headerSubtitle,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        actions: [
          if (hasTeamNow)
            IconButton(
              icon: const Icon(Icons.swap_horiz),
              tooltip: 'Switch to Team View',
              onPressed: _switchToTeamView,
            ),
          IconButton(
            icon: const Icon(Icons.message_outlined),
            tooltip: 'Messages',
            onPressed: () =>
                AppBottomNav.navigateTo(context, AppTab.messages, _navArgs),
          ),
        ],
      ),
      drawer: AppDrawer(args: _navArgs),
      body: SafeArea(
        top: false,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _offline
            ? _offlineBody(context)
            : _loadedBody(context),
      ),
      bottomNavigationBar: AppBottomNav(
        current: AppTab.dashboard,
        args: _navArgs,
      ),
    );
  }

  Widget _offlineBody(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.wifi_off,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 12),
            Text("You're offline", style: theme.textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(
              "Incident data can't be refreshed right now. Reconnect to see current status.",
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _loadedBody(BuildContext context) {
    final theme = Theme.of(context);
    final mobileContext = _mobileContext;
    final assignments = mobileContext?.staffAssignments ?? const [];
    final ownTeamId = mobileContext?.hasTeam == true
        ? int.tryParse(mobileContext!.teamId)
        : null;

    return SingleChildScrollView(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (assignments.isNotEmpty)
            StaffAssignmentCard(
              assignments: assignments,
              teamName: mobileContext?.hasTeam == true
                  ? mobileContext!.teamName
                  : null,
              onSwitchToTeamView: _switchToTeamView,
            ),
          IncidentStatTiles(
            teamsActive: _teams.where(_isTeamActive).length,
            teamsTotal: _teams.length,
            openTasks: _openTasks,
            personnelOnIncident: _personnelOnIncident,
            openSafetyIssues: _openSafetyIssues,
          ),
          SectionCard(
            title: _currentOpPeriod != null
                ? 'INCIDENT OBJECTIVES · OP $_currentOpPeriod'
                : 'INCIDENT OBJECTIVES',
            child: _objectives.isEmpty
                ? Text(
                    'No objectives recorded yet.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final objective in _objectives)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 3),
                          child: Text('${objective['text'] ?? ''}'),
                        ),
                    ],
                  ),
          ),
          TeamOverviewList(
            teams: _teams,
            teamTypes: _teamTypes,
            taskTitleById: _taskTitleById,
            ownTeamId: ownTeamId,
            onViewAll: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => TeamManagementScreen(args: _navArgs),
              ),
            ),
          ),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            height: 320,
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerLow,
              border: Border.all(color: theme.colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(12),
            ),
            clipBehavior: Clip.antiAlias,
            child: NarrativeFeed(entries: _narratives, onRefresh: _load),
          ),
          FieldActionGrid(items: _quickActions()),
        ],
      ),
    );
  }
}
