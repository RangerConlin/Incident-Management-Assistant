import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../services/sarapp_api_client.dart';
import '../widgets/app_drawer.dart';
import '../widgets/section_card.dart';
import 'report_hazard_screen.dart';

/// Live incident safety workspace for field and command users.
class SafetyScreen extends StatefulWidget {
  const SafetyScreen({super.key, required this.args, this.apiClient});

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<SafetyScreen> createState() => _SafetyScreenState();
}

class _SafetyScreenState extends State<SafetyScreen> {
  late final SarAppApiClient _apiClient = widget.apiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget.apiClient == null;
  List<Map<String, dynamic>> _hazards = const [];
  List<Map<String, dynamic>> _reports = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _apiClient.fetchHazards(widget.args.incidentId),
        _apiClient.fetchSafetyReports(widget.args.incidentId),
      ]);
      if (!mounted) return;
      setState(() {
        _hazards = _maps(results[0]);
        _reports = _maps(results[1]).reversed.toList();
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Unable to load incident safety data.';
        _loading = false;
      });
    }
  }

  static List<Map<String, dynamic>> _maps(List<dynamic> rows) => rows
      .whereType<Map>()
      .map((row) => Map<String, dynamic>.from(row))
      .toList();

  Future<void> _report() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) =>
            ReportHazardScreen(args: widget.args, apiClient: _apiClient),
      ),
    );
    if (created == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Safety'),
        actions: [
          IconButton(
            tooltip: 'Refresh safety data',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      drawer: AppDrawer(args: widget.args),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _report,
        icon: const Icon(Icons.report_outlined),
        label: const Text('Report'),
      ),
      body: RefreshIndicator(onRefresh: _load, child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const SizedBox(height: 96),
          Icon(
            Icons.cloud_off_outlined,
            size: 48,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(height: 12),
          Center(child: Text(_error!)),
          const SizedBox(height: 12),
          Center(
            child: FilledButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ),
        ],
      );
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(0, 10, 0, 88),
      children: [
        SectionCard(
          title: 'INCIDENT SAFETY',
          child: Row(
            children: [
              Expanded(
                child: _Count(label: 'Active hazards', value: _hazards.length),
              ),
              Expanded(
                child: _Count(label: 'Field reports', value: _reports.length),
              ),
              Expanded(
                child: _Count(
                  label: 'Flagged',
                  value: _reports.where((row) => row['flagged'] == true).length,
                ),
              ),
            ],
          ),
        ),
        SectionCard(
          title: 'ACTIVE HAZARDS',
          child: _hazards.isEmpty
              ? const Text('No active hazards are recorded for this incident.')
              : Column(children: _hazards.map(_hazardTile).toList()),
        ),
        SectionCard(
          title: 'RECENT FIELD REPORTS',
          child: _reports.isEmpty
              ? const Text('No field safety reports have been submitted.')
              : Column(children: _reports.take(10).map(_reportTile).toList()),
        ),
      ],
    );
  }

  Widget _hazardTile(Map<String, dynamic> row) {
    final spe = row['spe_residual'] is Map
        ? Map<String, dynamic>.from(row['spe_residual'] as Map)
        : row['default_spe'] is Map
        ? Map<String, dynamic>.from(row['default_spe'] as Map)
        : const <String, dynamic>{};
    final subtitle = [row['location_text'], spe['band']]
        .map((value) => '$value'.trim())
        .where((value) => value.isNotEmpty && value != 'null')
        .join(' · ');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.warning_amber_outlined),
      title: Text('${row['title'] ?? 'Untitled hazard'}'),
      subtitle: subtitle.isEmpty ? null : Text(subtitle),
    );
  }

  Widget _reportTile(Map<String, dynamic> row) {
    final details =
        [row['severity'], row['location'], _displayTime(row['time'])]
            .map((value) => '$value'.trim())
            .where((value) => value.isNotEmpty && value != 'null')
            .join(' · ');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        row['flagged'] == true
            ? Icons.priority_high
            : Icons.health_and_safety_outlined,
      ),
      title: Text('${row['notes'] ?? 'Safety report'}'),
      subtitle: details.isEmpty ? null : Text(details),
    );
  }

  static String _displayTime(dynamic value) {
    final parsed = DateTime.tryParse('$value');
    if (parsed == null) return '';
    final local = parsed.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} '
        '${two(local.hour)}:${two(local.minute)}:${two(local.second)}';
  }
}

class _Count extends StatelessWidget {
  const _Count({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Text('$value', style: Theme.of(context).textTheme.headlineMedium),
      Text(label, textAlign: TextAlign.center),
    ],
  );
}
