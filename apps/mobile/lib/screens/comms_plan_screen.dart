import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/ics205_plan.dart';
import '../services/sarapp_api_client.dart';
import '../widgets/app_drawer.dart';
import '../widgets/section_card.dart';

/// Comms Plan Viewer (ICS 205), read-only per the Phase 2 design doc.
/// Reachable from the More menu. Loads the live incident communications plan
/// and channel assignments from the sectioned ICS 205 API.
class CommsPlanScreen extends StatefulWidget {
  const CommsPlanScreen({
    super.key,
    required this.args,
    this.apiClient,
  });

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<CommsPlanScreen> createState() => _CommsPlanScreenState();
}

class _CommsPlanScreenState extends State<CommsPlanScreen> {
  late final SarAppApiClient _apiClient = widget.apiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget.apiClient == null;

  Ics205Plan? _plan;
  int? _opPeriod;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPlan();
  }

  @override
  void dispose() {
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _loadPlan() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final opPeriod = await _bestEffortCurrentOpPeriod();
      final plan = await _apiClient.fetchIcs205Plan(
        widget.args.incidentId,
        opPeriod: opPeriod,
      );
      if (!mounted) return;
      setState(() {
        _opPeriod = opPeriod ?? int.tryParse(plan.opPeriodId ?? '');
        _plan = plan;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Unable to load the communications plan.';
        _loading = false;
      });
    }
  }

  Future<int?> _bestEffortCurrentOpPeriod() async {
    try {
      final rows = await _apiClient.fetchOpPeriods(widget.args.incidentId);
      final periods = rows
          .map((value) => int.tryParse('$value'))
          .whereType<int>()
          .where((value) => value > 0)
          .toList();
      if (periods.isEmpty) return null;
      periods.sort();
      return periods.last;
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Comms Plan · ICS 205'),
        actions: [
          IconButton(
            tooltip: 'Refresh communications plan',
            onPressed: _loading ? null : _loadPlan,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      drawer: AppDrawer(args: widget.args),
      body: RefreshIndicator(
        onRefresh: _loadPlan,
        child: _body(context),
      ),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return _StateMessage(
        icon: Icons.cloud_off_outlined,
        title: _error!,
        message: 'Check the server connection, then refresh ICS 205.',
        action: FilledButton.icon(
          onPressed: _loadPlan,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      );
    }

    final plan = _plan;
    if (plan == null || plan.isEmpty) {
      return const _StateMessage(
        icon: Icons.settings_input_antenna_outlined,
        title: 'No ICS 205 has been published for this incident.',
        message: 'When the communications unit fills out the plan, it will appear here.',
      );
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(0, 10, 0, 16),
      children: [
        if (_opPeriod != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 6),
            child: Text(
              'Operational period $_opPeriod',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
        if (plan.specialInstructions.isNotEmpty)
          SectionCard(
            title: 'Special Instructions',
            child: Text(plan.specialInstructions),
          ),
        if (plan.channels.isNotEmpty) ...[
          ...plan.channels.map((channel) => _ChannelCard(channel: channel)),
        ],
      ],
    );
  }
}

class _ChannelCard extends StatelessWidget {
  const _ChannelCard({required this.channel});

  final Ics205Channel channel;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: channel.displayTitle,
      trailing: channel.mode.isEmpty
          ? null
          : Text(
              channel.mode,
              style: Theme.of(context).textTheme.labelMedium,
            ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (channel.function.isNotEmpty)
            LabeledRow(label: 'Function', value: channel.function),
          if (channel.remarks.isNotEmpty)
            LabeledRow(label: 'Notes', value: channel.remarks),
        ],
      ),
    );
  }
}

class _StateMessage extends StatelessWidget {
  const _StateMessage({
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
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 96),
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
    );
  }
}
