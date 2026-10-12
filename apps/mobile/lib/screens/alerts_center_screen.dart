import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/incident_alert.dart';
import '../services/sarapp_api_client.dart';
import '../utils/date_format.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';

/// Alerts Center: priority/broadcast alerts from command (evacuation
/// orders, radio silence, weather advisories), distinct from the regular
/// team Messages inbox. The current backend exposes live operational team
/// alerts, so mobile filters that incident-wide feed down to the signed-in
/// team's relevant items only.
class AlertsCenterScreen extends StatefulWidget {
  const AlertsCenterScreen({super.key, required this.args, SarAppApiClient? apiClient})
    : _injectedApiClient = apiClient;

  final HomeNavArgs args;
  final SarAppApiClient? _injectedApiClient;

  @override
  State<AlertsCenterScreen> createState() => _AlertsCenterScreenState();
}

class _AlertsCenterScreenState extends State<AlertsCenterScreen> {
  late final SarAppApiClient _apiClient =
      widget._injectedApiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget._injectedApiClient == null;

  bool _loading = true;
  String? _errorMessage;
  List<IncidentAlert> _alerts = const [];

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
      _errorMessage = null;
    });

    try {
      final alerts = await _apiClient.fetchAlerts(widget.args.incidentId);
      final filtered = alerts.where((alert) {
        return alert.matchesTeam(
          teamId: widget.args.teamId,
          teamName: widget.args.teamName,
        );
      }).toList();
      if (!mounted) return;
      setState(() {
        _alerts = filtered;
        _loading = false;
      });
    } on SarAppApiException {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to load alerts.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Alerts')),
      drawer: AppDrawer(args: widget.args),
      body: _buildBody(context),
      bottomNavigationBar: AppBottomNav(current: AppTab.alerts, args: widget.args),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage!, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (_alerts.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text('No active alerts for your team.'),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: _alerts.length,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (context, index) => _AlertCard(alert: _alerts[index]),
      ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.alert});

  final IncidentAlert alert;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = alert.isCritical
        ? theme.colorScheme.errorContainer
        : theme.colorScheme.surfaceContainerHigh;
    final onColor =
        alert.isCritical ? theme.colorScheme.onErrorContainer : theme.colorScheme.onSurface;
    return Card(
      margin: EdgeInsets.zero,
      color: color,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  alert.isCritical ? Icons.warning_amber : Icons.notifications_active_outlined,
                  color: onColor,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    alert.title,
                    style: theme.textTheme.titleSmall?.copyWith(color: onColor),
                  ),
                ),
                Text(
                  formatTimeOnly(alert.lastCheckinAt),
                  style: TextStyle(color: onColor, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(alert.body, style: TextStyle(color: onColor)),
            if (alert.status.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Current status: ${alert.status}',
                style: theme.textTheme.bodySmall?.copyWith(color: onColor),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
