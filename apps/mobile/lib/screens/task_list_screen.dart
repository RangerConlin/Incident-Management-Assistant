import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/task.dart';
import '../services/sarapp_api_client.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';
import 'task_detail_screen.dart';

/// Field task list (ICS 204-style tasking, Active911-inspired per the
/// Phase 2 design doc). Loads live operations tasks from the current
/// incident and preserves explicit empty/error states when the server has no
/// tasking to show.
class TaskListScreen extends StatefulWidget {
  const TaskListScreen({super.key, required this.args, this.apiClient});

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<TaskListScreen> createState() => _TaskListScreenState();
}

enum _TaskFilter { all, myTeam, open, complete }

class _TaskListScreenState extends State<TaskListScreen> {
  late final SarAppApiClient _apiClient;
  late final bool _ownsApiClient;
  var _loading = true;
  String? _error;
  List<Task> _tasks = const [];
  _TaskFilter _filter = _TaskFilter.all;

  int? get _teamIntId => int.tryParse(widget.args.teamId);

  @override
  void initState() {
    super.initState();
    _apiClient = widget.apiClient ?? SarAppApiClient();
    _ownsApiClient = widget.apiClient == null;
    _loadTasks();
  }

  @override
  void dispose() {
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _loadTasks() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final rows = await _apiClient.fetchTasks(widget.args.incidentId);
      final tasks =
          rows
              .whereType<Map>()
              .map((row) => Task.fromJson(Map<String, dynamic>.from(row)))
              .toList()
            ..sort(_compareTasks);
      if (!mounted) return;
      setState(() {
        _tasks = tasks;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Unable to load tasks.';
        _loading = false;
      });
    }
  }

  int _compareTasks(Task a, Task b) {
    final statusCompare = _isComplete(
      a,
    ).toString().compareTo(_isComplete(b).toString());
    if (statusCompare != 0) return statusCompare;
    final priorityCompare = b.priority.compareTo(a.priority);
    if (priorityCompare != 0) return priorityCompare;
    return a.taskNumber.compareTo(b.taskNumber);
  }

  bool _isComplete(Task task) {
    final status = task.status.toLowerCase();
    return status == 'complete' || status == 'completed' || status == 'cleared';
  }

  bool _isMyTeamTask(Task task) {
    final teamIntId = _teamIntId;
    if (teamIntId == null) return false;
    if (task.activeTeamIds.contains(teamIntId)) return true;
    return task.taskTeams.any((assignment) => assignment.teamId == teamIntId);
  }

  List<Task> get _filteredTasks {
    switch (_filter) {
      case _TaskFilter.all:
        return _tasks;
      case _TaskFilter.myTeam:
        return _tasks.where(_isMyTeamTask).toList();
      case _TaskFilter.open:
        return _tasks.where((task) => !_isComplete(task)).toList();
      case _TaskFilter.complete:
        return _tasks.where(_isComplete).toList();
    }
  }

  String get _emptyMessage {
    switch (_filter) {
      case _TaskFilter.myTeam:
        return 'No tasks are assigned to your team.';
      case _TaskFilter.open:
        return 'No open tasks for this incident.';
      case _TaskFilter.complete:
        return 'No completed tasks for this incident.';
      case _TaskFilter.all:
        return 'No tasks have been published for this incident.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final filteredTasks = _filteredTasks;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Tasks'),
        actions: [
          IconButton(
            tooltip: 'Refresh tasks',
            onPressed: _loading ? null : _loadTasks,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      drawer: AppDrawer(args: widget.args),
      body: RefreshIndicator(
        onRefresh: _loadTasks,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: _TaskFilterBar(
                selected: _filter,
                onSelected: (filter) => setState(() => _filter = filter),
              ),
            ),
            if (_loading)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              SliverFillRemaining(
                hasScrollBody: false,
                child: _TaskStateMessage(
                  icon: Icons.cloud_off_outlined,
                  title: _error!,
                  message: 'Check the server connection, then refresh tasks.',
                  action: FilledButton.icon(
                    onPressed: _loadTasks,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                  ),
                ),
              )
            else if (filteredTasks.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: _TaskStateMessage(
                  icon: Icons.assignment_outlined,
                  title: _emptyMessage,
                  message:
                      'When operations publishes tasking, it will appear here.',
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                sliver: SliverList.builder(
                  itemCount: filteredTasks.length * 2 - 1,
                  itemBuilder: (context, index) {
                    if (index.isOdd) return const SizedBox(height: 8);
                    final taskIndex = index ~/ 2;
                    final task = filteredTasks[taskIndex];
                    return _TaskCard(
                      task: task,
                      isAssignedToCurrentTeam: _isMyTeamTask(task),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) =>
                              TaskDetailScreen(task: task, args: widget.args),
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        current: AppTab.tasks,
        args: widget.args,
      ),
    );
  }
}

class _TaskFilterBar extends StatelessWidget {
  const _TaskFilterBar({required this.selected, required this.onSelected});

  final _TaskFilter selected;
  final ValueChanged<_TaskFilter> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: SegmentedButton<_TaskFilter>(
        selected: {selected},
        onSelectionChanged: (selection) => onSelected(selection.single),
        segments: const [
          ButtonSegment(
            value: _TaskFilter.all,
            icon: Icon(Icons.list_alt),
            label: Text('All'),
          ),
          ButtonSegment(
            value: _TaskFilter.myTeam,
            icon: Icon(Icons.group_outlined),
            label: Text('My Team'),
          ),
          ButtonSegment(
            value: _TaskFilter.open,
            icon: Icon(Icons.radio_button_checked),
            label: Text('Open'),
          ),
          ButtonSegment(
            value: _TaskFilter.complete,
            icon: Icon(Icons.check_circle_outline),
            label: Text('Done'),
          ),
        ],
      ),
    );
  }
}

class _TaskStateMessage extends StatelessWidget {
  const _TaskStateMessage({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 40, color: colorScheme.onSurfaceVariant),
          const SizedBox(height: 12),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          if (action != null) ...[
            const SizedBox(height: 16),
            Center(child: action),
          ],
        ],
      ),
    );
  }
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.task,
    required this.isAssignedToCurrentTeam,
    required this.onTap,
  });

  final Task task;
  final bool isAssignedToCurrentTeam;
  final VoidCallback onTap;

  Color _priorityColor() {
    switch (task.priorityLabel) {
      case 'Critical':
        return const Color(0xFF8c2f2f);
      case 'High':
        return const Color(0xFFa88f1a);
      case 'Medium':
        return const Color(0xFF1f6088);
      default:
        return const Color(0xFF2f6d34);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final subtitleParts = [
      task.typeLabel,
      if (task.status.isNotEmpty) task.status,
      if (task.location != null) task.location!,
    ];

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      '${task.taskNumber} · ${task.title.isEmpty ? 'Untitled task' : task.title}',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  _TaskChip(
                    label: task.priorityLabel.toUpperCase(),
                    background: _priorityColor(),
                    foreground: const Color(0xFFf5f5f5),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                subtitleParts.join('  ·  '),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
              if (isAssignedToCurrentTeam) ...[
                const SizedBox(height: 10),
                const _TaskChip(
                  label: 'MY TEAM',
                  background: Color(0xFF1f6088),
                  foreground: Color(0xFFf0f0f0),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _TaskChip extends StatelessWidget {
  const _TaskChip({
    required this.label,
    required this.background,
    required this.foreground,
  });

  final String label;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: foreground,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
