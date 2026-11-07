import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/log_entry.dart';
import '../services/sarapp_api_client.dart';
import '../utils/date_format.dart';
import '../utils/json_parsing.dart';
import '../widgets/app_drawer.dart';
import 'add_log_entry_sheet.dart';

enum LogStream { personal, team, incident }

/// Selectable views over the canonical incident ICS-214 activity stream.
class LogbookScreen extends StatefulWidget {
  const LogbookScreen({super.key, required this.args, this.apiClient});

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<LogbookScreen> createState() => _LogbookScreenState();
}

class _LogbookScreenState extends State<LogbookScreen> {
  late final SarAppApiClient _apiClient;
  late final bool _ownsApiClient;

  List<LogEntry> _entries = const [];
  bool _loading = true;
  String? _error;
  LogStream _stream = LogStream.personal;

  int? get _teamIntId => int.tryParse(widget.args.teamId);
  int? get _personRecord => parseInt(
    widget.args.session['person_record'] ??
        widget.args.session['user']?['person_record'],
  );

  @override
  void initState() {
    super.initState();
    _apiClient = widget.apiClient ?? SarAppApiClient();
    _ownsApiClient = widget.apiClient == null;
    _load();
  }

  @override
  void dispose() {
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_stream == LogStream.personal && _personRecord == null) {
      setState(() {
        _loading = false;
        _error =
            'Your personnel record is unavailable, so the personal log cannot be loaded.';
      });
      return;
    }
    if (_stream == LogStream.team && _teamIntId == null) {
      setState(() {
        _loading = false;
        _error = 'No team is selected, so the team log cannot be loaded.';
      });
      return;
    }
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final rows = await _apiClient.fetchIcs214Entries(
        widget.args.incidentId,
        personRecord: _stream == LogStream.personal ? _personRecord : null,
        teamIntId: _stream == LogStream.team ? _teamIntId : null,
      );
      final entries =
          rows
              .whereType<Map>()
              .map((row) => LogEntry.fromJson(Map<String, dynamic>.from(row)))
              .where((entry) => entry.source != 'internal')
              .toList()
            ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
      if (!mounted) return;
      setState(() {
        _entries = entries;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Unable to load the logbook.';
        _loading = false;
      });
    }
  }

  Future<void> _addEntry() async {
    final personRecord = _personRecord;
    final teamIntId = _teamIntId;
    final posted = await showAddLogEntrySheet(
      context,
      apiClient: _apiClient,
      incidentId: widget.args.incidentId,
      session: widget.args.session,
      personIds: _stream == LogStream.personal && personRecord != null
          ? [personRecord]
          : const [],
      teamIds: _stream == LogStream.team && teamIntId != null
          ? [teamIntId]
          : const [],
      incidentWide: _stream == LogStream.incident,
      expandTeamMembers: _stream == LogStream.team,
    );
    if (posted == true) await _load();
  }

  Widget _buildBody() {
    if (_loading && _entries.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _entries.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!),
            const SizedBox(height: 12),
            FilledButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      );
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
          child: SizedBox(
            width: double.infinity,
            child: SegmentedButton<LogStream>(
              segments: [
                const ButtonSegment(
                  value: LogStream.personal,
                  label: Text('Personal'),
                  icon: Icon(Icons.person_outline),
                ),
                ButtonSegment(
                  value: LogStream.team,
                  label: const Text('Team'),
                  icon: const Icon(Icons.groups_outlined),
                  enabled: _teamIntId != null,
                ),
                const ButtonSegment(
                  value: LogStream.incident,
                  label: Text('Incident'),
                  icon: Icon(Icons.assignment_outlined),
                ),
              ],
              selected: {_stream},
              showSelectedIcon: false,
              onSelectionChanged: (selection) {
                setState(() => _stream = selection.first);
                _load();
              },
            ),
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: _entries.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Text(
                          'No ${_stream.label.toLowerCase()} log entries yet.',
                        ),
                      ),
                    ],
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(12),
                    itemCount: _entries.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final entry = _entries[index];
                      final note = entry.note;
                      return ListTile(
                        leading: Icon(
                          entry.critical
                              ? Icons.priority_high
                              : Icons.notes_outlined,
                          color: entry.critical
                              ? Theme.of(context).colorScheme.error
                              : null,
                        ),
                        title: Text(entry.activity),
                        subtitle: note == null ? null : Text(note),
                        trailing: Text(formatTimestamp(entry.timestamp)),
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Logbook · ICS 214')),
      drawer: AppDrawer(args: widget.args),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton(
        onPressed:
            (_stream == LogStream.personal && _personRecord == null) ||
                (_stream == LogStream.team && _teamIntId == null)
            ? null
            : _addEntry,
        tooltip: 'Add Log Entry',
        child: const Icon(Icons.add),
      ),
    );
  }
}

extension on LogStream {
  String get label => switch (this) {
    LogStream.personal => 'Personal',
    LogStream.team => 'Team',
    LogStream.incident => 'Incident',
  };
}
