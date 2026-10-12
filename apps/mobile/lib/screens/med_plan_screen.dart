import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/ics206_plan.dart';
import '../services/sarapp_api_client.dart';
import '../widgets/app_drawer.dart';
import '../widgets/section_card.dart';

/// Med Plan Viewer (ICS 206), read-only per the Phase 2 design doc.
/// Reachable from the More menu. Loads the live incident medical plan from
/// the sectioned ICS 206 API.
class MedPlanScreen extends StatefulWidget {
  const MedPlanScreen({
    super.key,
    required this.args,
    this.apiClient,
  });

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<MedPlanScreen> createState() => _MedPlanScreenState();
}

class _MedPlanScreenState extends State<MedPlanScreen> {
  late final SarAppApiClient _apiClient = widget.apiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget.apiClient == null;

  Ics206Plan? _plan;
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
      final plan = await _apiClient.fetchIcs206Plan(
        widget.args.incidentId,
        opPeriod: opPeriod,
      );
      if (!mounted) return;
      setState(() {
        _opPeriod =
            opPeriod ?? plan.procedures.opPeriod ?? plan.signatures.opPeriod;
        _plan = plan;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Unable to load the medical plan.';
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
        title: const Text('Med Plan · ICS 206'),
        actions: [
          IconButton(
            tooltip: 'Refresh medical plan',
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
        message: 'Check the server connection, then refresh ICS 206.',
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
        icon: Icons.medical_services_outlined,
        title: 'No ICS 206 has been published for this incident.',
        message: 'When the medical unit fills out the plan, it will appear here.',
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
        if (plan.procedures.content.isNotEmpty)
          SectionCard(
            title: 'MEDICAL EMERGENCY PROCEDURES',
            child: Text(plan.procedures.content),
          ),
        _RecordSection(
          title: 'AID STATIONS',
          records: plan.aidStations,
          rows: const [
            _FieldRow('Type', 'type'),
            _FieldRow('Level', 'level'),
            _FieldRow('Location', 'location_text'),
            _FieldRow('Manager', 'manager_name'),
            _FieldRow('24/7', 'is_24_7', boolField: true),
            _FieldRow('Notes', 'notes'),
          ],
        ),
        _RecordSection(
          title: 'AMBULANCE SERVICES',
          records: plan.ambulanceServices,
          rows: const [
            _FieldRow('Type', 'type'),
            _FieldRow('Phone', 'phone'),
            _FieldRow('Location', 'location'),
            _FieldRow('Notes', 'notes'),
          ],
        ),
        _RecordSection(
          title: 'HOSPITALS',
          records: plan.hospitals,
          rows: const [
            _FieldRow('Address', 'address'),
            _FieldRow('Phone', 'phone'),
            _FieldRow('Helipad', 'helipad', boolField: true),
            _FieldRow('Burn Center', 'burn_center', boolField: true),
            _FieldRow('Trauma Level', 'level'),
            _FieldRow('Notes', 'notes'),
          ],
        ),
        _RecordSection(
          title: 'AIR AMBULANCE / MEDEVAC',
          records: plan.airAmbulance,
          rows: const [
            _FieldRow('Phone', 'phone'),
            _FieldRow('Base', 'base'),
            _FieldRow('Contact', 'contact'),
            _FieldRow('Notes', 'notes'),
          ],
        ),
        _RecordSection(
          title: 'MEDICAL COMMUNICATIONS',
          records: plan.medicalComms,
          rows: const [
            _FieldRow('Function', 'function'),
            _FieldRow('Frequency', 'frequency'),
            _FieldRow('Mode', 'mode'),
            _FieldRow('Notes', 'notes'),
          ],
        ),
        if (!plan.signatures.isEmpty)
          SectionCard(
            title: 'PREPARED / APPROVED',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (plan.signatures.preparedBy.isNotEmpty)
                  LabeledRow(
                    label: 'Prepared By',
                    value: plan.signatures.preparedBy,
                  ),
                if (plan.signatures.position.isNotEmpty)
                  LabeledRow(label: 'Position', value: plan.signatures.position),
                if (plan.signatures.approvedBy.isNotEmpty)
                  LabeledRow(
                    label: 'Approved By',
                    value: plan.signatures.approvedBy,
                  ),
                if (plan.signatures.date.isNotEmpty)
                  LabeledRow(label: 'Date', value: plan.signatures.date),
              ],
            ),
          ),
      ],
    );
  }
}

class _FieldRow {
  const _FieldRow(this.label, this.key, {this.boolField = false});

  final String label;
  final String key;
  final bool boolField;
}

class _RecordSection extends StatelessWidget {
  const _RecordSection({
    required this.title,
    required this.records,
    required this.rows,
  });

  final String title;
  final List<Ics206Record> records;
  final List<_FieldRow> rows;

  @override
  Widget build(BuildContext context) {
    if (records.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
          child: Text(
            title,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ),
        ...records.map((record) {
          final visibleRows = rows.where((row) {
            if (row.boolField) return record.data.containsKey(row.key);
            return record.text(row.key).isNotEmpty;
          }).toList();

          return SectionCard(
            title: record.displayTitle,
            trailing: _OpChip(opPeriod: record.opPeriod),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final row in visibleRows)
                  LabeledRow(
                    label: row.label,
                    value: row.boolField
                        ? (record.flag(row.key) ? 'Yes' : 'No')
                        : record.text(row.key),
                  ),
              ],
            ),
          );
        }),
      ],
    );
  }
}

class _OpChip extends StatelessWidget {
  const _OpChip({required this.opPeriod});

  final int? opPeriod;

  @override
  Widget build(BuildContext context) {
    if (opPeriod == null) return const SizedBox.shrink();
    return Text(
      'OP $opPeriod',
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
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
