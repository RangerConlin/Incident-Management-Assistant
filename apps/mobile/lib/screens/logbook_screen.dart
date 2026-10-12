import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/log_entry.dart';
import '../services/sarapp_api_client.dart';
import '../utils/date_format.dart';
import '../widgets/app_drawer.dart';
import 'add_log_entry_sheet.dart';

/// The team's ICS 214 activity log, backed by the server's mobile team-log
/// endpoints. Entries posted here land on the team's 214 stream and are
/// visible to desktop clients (source `mobile`).
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

  int? get _teamIntId => int.tryParse(widget.args.teamId);

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
    if (_teamIntId == null) {
      setState(() {
        _loading = false;
        _error = 'No team is selected, so there is no logbook to load.';
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
      final rows = await _apiClient.fetchTeamLog(
        widget.args.incidentId,
        widget.args.teamId,
      );
      final entries = rows
          .whereType<Map>()
          .map((row) => LogEntry.fromJson(Map<String, dynamic>.from(row)))
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
    final posted = await showAddLogEntrySheet(
      context,
      apiClient: _apiClient,
      incidentId: widget.args.incidentId,
      teamId: widget.args.teamId,
      session: widget.args.session,
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
    return RefreshIndicator(
      onRefresh: _load,
      child: _entries.isEmpty
          ? ListView(
              children: const [
                SizedBox(height: 120),
                Center(child: Text('No log entries yet.')),
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
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Logbook · ICS 214')),
      drawer: AppDrawer(args: widget.args),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton(
        onPressed: _teamIntId == null ? null : _addEntry,
        tooltip: 'Add Log Entry',
        child: const Icon(Icons.add),
      ),
    );
  }
}
