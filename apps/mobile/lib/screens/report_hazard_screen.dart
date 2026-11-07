import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../services/sarapp_api_client.dart';
import '../widgets/app_drawer.dart';

/// Field safety report submission backed by the shared incident safety API.
class ReportHazardScreen extends StatefulWidget {
  const ReportHazardScreen({super.key, required this.args, this.apiClient});

  final HomeNavArgs args;
  final SarAppApiClient? apiClient;

  @override
  State<ReportHazardScreen> createState() => _ReportHazardScreenState();
}

class _ReportHazardScreenState extends State<ReportHazardScreen> {
  final _formKey = GlobalKey<FormState>();
  final _descriptionController = TextEditingController();
  final _locationController = TextEditingController();
  late final SarAppApiClient _apiClient = widget.apiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget.apiClient == null;
  String _severity = 'Routine';
  bool _submitting = false;

  static const _severityOptions = ['Routine', 'Priority', 'High', 'Emergency'];

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false) || _submitting) return;
    setState(() => _submitting = true);
    try {
      await _apiClient.createSafetyReport(
        incidentId: widget.args.incidentId,
        notes: _descriptionController.text.trim(),
        severity: _severity,
        location: _locationController.text.trim().isEmpty
            ? null
            : _locationController.text.trim(),
        reportedBy: '${widget.args.session['person_id'] ?? ''}'.trim(),
        teamId: int.tryParse(widget.args.teamId),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Safety report submitted.')));
      Navigator.of(context).pop(true);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Unable to submit the safety report. Try again.'),
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    _locationController.dispose();
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Report Hazard')),
      drawer: AppDrawer(args: widget.args),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            DropdownButtonFormField<String>(
              initialValue: _severity,
              decoration: const InputDecoration(
                labelText: 'Severity',
                border: OutlineInputBorder(),
              ),
              items: _severityOptions
                  .map(
                    (value) =>
                        DropdownMenuItem(value: value, child: Text(value)),
                  )
                  .toList(),
              onChanged: _submitting
                  ? null
                  : (value) => setState(() => _severity = value ?? 'Routine'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _locationController,
              enabled: !_submitting,
              decoration: const InputDecoration(
                labelText: 'Location',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _descriptionController,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Safety concern or hazard',
                border: OutlineInputBorder(),
              ),
              enabled: !_submitting,
              validator: (value) => (value ?? '').trim().isEmpty
                  ? 'Describe the safety concern or hazard.'
                  : null,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _submitting ? null : _submit,
              icon: _submitting
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send_outlined),
              label: Text(_submitting ? 'Submitting…' : 'Submit Report'),
            ),
          ],
        ),
      ),
    );
  }
}
