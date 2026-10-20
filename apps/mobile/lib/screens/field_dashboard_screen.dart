import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/incident_context.dart';
import '../models/narrative_entry.dart';
import '../models/task.dart';
import '../models/team.dart';
import '../services/app_presence_service.dart';
import '../services/chat_presence_service.dart';
import '../services/push_notification_service.dart';
import '../services/sarapp_api_client.dart';
import '../services/tracking_service.dart';
import '../theme/app_theme.dart';
import '../utils/session_identity.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';
import '../widgets/assignment_reference_panel.dart';
import '../widgets/field_action_grid.dart';
import '../widgets/incident_header_bar.dart';
import '../widgets/narrative_feed.dart';
import '../widgets/section_card.dart';
import '../widgets/task_location_tile.dart';
import '../widgets/task_metadata_card.dart';
import '../widgets/team_status_grid.dart';
import 'add_narrative_sheet.dart';
import 'coming_soon_screen.dart';
import 'notification_permission_prompt.dart';
import 'report_hazard_screen.dart';

/// The field team's MDT-style home screen: current-task narrative, compact
/// task metadata, free-text location, team-status controls, and field
/// action buttons. Replaces the previous roster-focused `DashboardScreen` —
/// a team roster/member-status view is deliberately not shown here; see
/// Team management in the drawer (`TeamManagementScreen`).
class FieldDashboardScreen extends StatefulWidget {
  const FieldDashboardScreen({
    super.key,
    required this.incidentId,
    required this.incidentName,
    this.incidentType,
    required this.teamId,
    required this.teamName,
    required this.session,
    SarAppApiClient? apiClient,
  }) : _injectedApiClient = apiClient;

  final String incidentId;
  final String incidentName;
  final String? incidentType;
  final String teamId;
  final String teamName;
  final Map<String, dynamic> session;
  final SarAppApiClient? _injectedApiClient;

  static const double wideLayoutBreakpoint = 720;

  @override
  State<FieldDashboardScreen> createState() => _FieldDashboardScreenState();
}

class _FieldDashboardScreenState extends State<FieldDashboardScreen> {
  late final SarAppApiClient _apiClient =
      widget._injectedApiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget._injectedApiClient == null;

  IncidentContext? _incidentContext;
  Team? _team;
  Task? _task;
  List<NarrativeEntry> _narratives = const [];
  DateTime? _assignedTime;
  String? _assignedBy;

  bool _loading = true;
  bool _statusUpdateInFlight = false;
  String? _errorMessage;
  String? _teamErrorMessage;

  /// Raw login id — identifies the operator to the server.
  String get _displayName => SessionIdentity.personId(widget.session);

  /// Human-readable name for attribution shown to other users.
  String get _operatorName => SessionIdentity.displayName(widget.session);

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
        teamId: widget.teamId,
        teamName: widget.teamName,
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
      await maybeShowNotificationPermissionPrompt(
        context,
        session: widget.session,
        incidentId: widget.incidentId,
      );
      if (!mounted) return;
      // Resumes tracking after an app kill+relaunch, but only if the user
      // had previously left it on via the Settings toggle — never starts it
      // fresh from here. See TrackingService.resumeIfEnabled.
      await TrackingService.resumeIfEnabled(
        incidentId: widget.incidentId,
        teamId: widget.teamId,
        teamName: widget.teamName,
        personId: _displayName,
        personRecord: personRecord == null ? null : '$personRecord',
      );
    });
  }

  @override
  void dispose() {
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);

    IncidentContext? incidentContext;
    Team? team;
    Task? task;
    List<NarrativeEntry> narratives = const [];
    DateTime? assignedTime;
    String? assignedBy;
    String? errorMessage;
    String? teamErrorMessage;

    try {
      final header = await _apiClient.fetchIncidentHeader(widget.incidentId);
      int? currentOp;
      try {
        final opPeriods = await _apiClient.fetchOpPeriods(widget.incidentId);
        final numbers = opPeriods
            .map((e) => e is int ? e : int.tryParse('$e'))
            .whereType<int>()
            .toList();
        if (numbers.isNotEmpty) {
          currentOp = numbers.reduce((a, b) => a > b ? a : b);
        }
      } catch (_) {
        // Operational-period lookup is best-effort only.
      }
      incidentContext = IncidentContext.fromHeaderJson(
        header,
        id: widget.incidentId,
        name: widget.incidentName,
        currentOperationalPeriod: currentOp,
      );
    } on SarAppApiException catch (e) {
      errorMessage = 'Failed to load incident: ${e.message}';
    }

    if (widget.teamId.isNotEmpty) {
      try {
        final teamsRaw = await _apiClient.fetchTeams(widget.incidentId);
        final teamNameLower = widget.teamName.trim().toLowerCase();
        Map<String, dynamic>? match;
        for (final raw in teamsRaw) {
          final entry = Map<String, dynamic>.from(raw as Map);
          if ('${entry['name'] ?? ''}'.trim().toLowerCase() == teamNameLower) {
            match = entry;
            break;
          }
        }
        if (match == null) {
          teamErrorMessage =
              'Team "${widget.teamName}" was not found in operations records.';
        } else {
          final teamJson = await _apiClient.fetchTeam(
            widget.incidentId,
            '${match['int_id']}',
          );
          team = Team.fromJson(teamJson);
          if (team.currentTaskId != null) {
            try {
              final taskJson = await _apiClient.fetchTask(
                widget.incidentId,
                '${team.currentTaskId}',
              );
              task = Task.fromJson(taskJson);
              final narrativesRaw = await _apiClient.fetchNarratives(
                widget.incidentId,
                taskId: task.intId,
              );
              narratives =
                  narrativesRaw
                      .map(
                        (e) => NarrativeEntry.fromJson(
                          Map<String, dynamic>.from(e as Map),
                        ),
                      )
                      .toList()
                    ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
              assignedTime = task.assignmentFor(team.intId)?.timeAssigned;
              if (narratives.isNotEmpty) {
                final earliest = narratives.reduce(
                  (a, b) => a.timestamp.isBefore(b.timestamp) ? a : b,
                );
                assignedBy = earliest.enteredBy.isEmpty
                    ? null
                    : earliest.enteredBy;
              }
            } on SarAppApiException catch (e) {
              errorMessage = 'Failed to load task: ${e.message}';
            }
          }
        }
      } on SarAppApiException catch (e) {
        teamErrorMessage = 'Failed to load team: ${e.message}';
      }
    }

    if (!mounted) return;
    setState(() {
      _incidentContext = incidentContext;
      _team = team;
      _task = task;
      _narratives = narratives;
      _assignedTime = assignedTime;
      _assignedBy = assignedBy;
      _errorMessage = errorMessage;
      _teamErrorMessage = teamErrorMessage;
      _loading = false;
    });
  }

  Future<void> _onStatusSelected(TeamStatusOption option) async {
    final team = _team;
    if (team == null) return;
    setState(() => _statusUpdateInFlight = true);
    try {
      final updated = await _apiClient.patchTeamStatus(
        incidentId: widget.incidentId,
        teamIntId: '${team.intId}',
        statusKey: option.key,
        changedBy: _operatorName,
      );
      if (!mounted) return;
      final newTeam = Team.fromJson(updated);
      setState(() => _team = newTeam);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Status updated to ${option.label}')),
      );
      if (newTeam.currentTaskId != team.currentTaskId) {
        await _load();
      }
    } on SarAppApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update status: ${e.message}')),
      );
    } finally {
      if (mounted) setState(() => _statusUpdateInFlight = false);
    }
  }

  Future<void> _onAddNarrative() async {
    final task = _task;
    if (task == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Select an active task first.')),
      );
      return;
    }
    final posted = await showAddNarrativeSheet(
      context,
      apiClient: _apiClient,
      incidentId: widget.incidentId,
      task: task,
      enteredBy: _operatorName,
      teamNum: widget.teamName,
    );
    if (posted == true) await _load();
  }

  void _openComingSoon(String title) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ComingSoonScreen(title: title, args: _navArgs),
      ),
    );
  }

  HomeNavArgs get _navArgs => HomeNavArgs(
    incidentId: widget.incidentId,
    incidentName: widget.incidentName,
    incidentType: widget.incidentType,
    teamId: widget.teamId,
    teamName: widget.teamName,
    session: widget.session,
  );

  List<FieldActionItem> _fieldActions() {
    return [
      FieldActionItem(
        icon: Icons.description_outlined,
        label: 'Intel Report',
        onTap: () => _openComingSoon('Intel Report'),
      ),
      FieldActionItem(
        icon: Icons.edit_note_outlined,
        label: 'Add Narrative',
        onTap: _onAddNarrative,
      ),
      FieldActionItem(
        icon: Icons.chat_bubble_outline,
        label: 'Messages',
        onTap: () =>
            AppBottomNav.navigateTo(context, AppTab.messages, _navArgs),
      ),
      FieldActionItem(
        icon: Icons.warning_amber_outlined,
        label: 'Report Hazard',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ReportHazardScreen(args: _navArgs)),
        ),
      ),
      FieldActionItem(
        icon: Icons.assignment_outlined,
        label: 'Forms',
        onTap: () => _openComingSoon('Forms'),
      ),
      FieldActionItem(
        icon: Icons.more_horiz,
        label: 'More Actions',
        onTap: () => _openComingSoon('More Actions'),
      ),
    ];
  }

  String? get _currentStatusKey {
    final status = _team?.status;
    if (status == null) return null;
    return TeamStatuses.keyForDisplayLabel(status) ?? status.toLowerCase();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: IncidentHeaderBar(
        incident: _incidentContext,
        teamName: widget.teamName,
        teamStatus: _team?.status,
        onMessagesPressed: () =>
            AppBottomNav.navigateTo(context, AppTab.messages, _navArgs),
      ),
      drawer: AppDrawer(args: _navArgs),
      body: SafeArea(
        top: false,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : LayoutBuilder(
                builder: (context, constraints) {
                  final wide =
                      constraints.maxWidth >=
                      FieldDashboardScreen.wideLayoutBreakpoint;
                  return wide
                      ? _buildWideLayout(context)
                      : _buildPhoneLayout(context);
                },
              ),
      ),
      bottomNavigationBar: AppBottomNav(
        current: AppTab.dashboard,
        args: _navArgs,
      ),
    );
  }

  Widget? _errorBanner(BuildContext context) {
    final messages = [
      _errorMessage,
      _teamErrorMessage,
    ].whereType<String>().toList();
    if (messages.isEmpty) return null;
    return Container(
      width: double.infinity,
      color: Theme.of(context).colorScheme.errorContainer,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        messages.join('\n'),
        style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
      ),
    );
  }

  Widget _taskSection(BuildContext context) {
    if (widget.teamId.isEmpty) {
      return const SectionCard(
        title: 'TEAM',
        child: Text('You are not assigned to a team for this incident.'),
      );
    }
    if (_task == null) {
      return SectionCard(
        title: 'TASK',
        child: Text(
          _teamErrorMessage != null
              ? 'Task status unavailable.'
              : 'Your team has no active task assigned.',
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TaskMetadataCard(
          task: _task!,
          assignedTime: _assignedTime,
          assignedBy: _assignedBy,
        ),
        TaskLocationTile(location: _task!.location),
      ],
    );
  }

  Widget _narrativePanel(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      key: const Key('dashboard_narrative_panel'),
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        border: Border.all(color: colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(12),
      ),
      clipBehavior: Clip.antiAlias,
      child: NarrativeFeed(entries: _narratives, onRefresh: _load),
    );
  }

  Widget _buildPhoneLayout(BuildContext context) {
    final banner = _errorBanner(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ?banner,
                _taskSection(context),
                const SizedBox(height: 4),
                // Fixed-height (not Expanded) so this is the one region that
                // scrolls independently of the rest of the page — everything
                // else scrolls together as a single page via the
                // SingleChildScrollView above.
                SizedBox(
                  height: constraints.maxHeight * 0.55,
                  child: _narrativePanel(context),
                ),
                TeamStatusGrid(
                  currentStatusKey: _currentStatusKey,
                  busy: _statusUpdateInFlight || _team == null,
                  onSelect: _onStatusSelected,
                ),
                FieldActionGrid(items: _fieldActions()),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildWideLayout(BuildContext context) {
    final banner = _errorBanner(context);
    return Column(
      children: [
        ?banner,
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 3,
                child: Column(
                  children: [
                    _taskSection(context),
                    const SizedBox(height: 4),
                    Expanded(
                      child: _narrativePanel(context),
                    ),
                  ],
                ),
              ),
              Expanded(
                flex: 2,
                child: ListView(
                  children: [
                    TeamStatusGrid(
                      currentStatusKey: _currentStatusKey,
                      busy: _statusUpdateInFlight || _team == null,
                      onSelect: _onStatusSelected,
                    ),
                    FieldActionGrid(items: _fieldActions()),
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12),
                      child: AssignmentReferencePanel(),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
