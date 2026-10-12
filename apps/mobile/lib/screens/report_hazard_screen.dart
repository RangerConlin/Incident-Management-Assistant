import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';

/// Field hazard/safety report submission (Phase 3.5). No
/// `POST /api/safety/report`-equivalent mobile endpoint exists yet — the
/// form is a placeholder; submitting shows a not-ready message instead of
/// silently pretending to succeed.
class ReportHazardScreen extends StatefulWidget {
  const ReportHazardScreen({super.key, required this.args});

  final HomeNavArgs args;

  @override
  State<ReportHazardScreen> createState() => _ReportHazardScreenState();
}

class _ReportHazardScreenState extends State<ReportHazardScreen> {
  final _descriptionController = TextEditingController();
  final _locationController = TextEditingController();
  String? _hazardType;

  static const _hazardTypes = [
    'Terrain / Fall Hazard',
    'Wildlife',
    'Weather',
    'Structural',
    'Medical',
    'Other',
  ];

  void _submit() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Hazard reporting is not available yet in this build.')),
    );
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    _locationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Report Hazard')),
      drawer: AppDrawer(args: widget.args),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<String>(
            initialValue: _hazardType,
            decoration: const InputDecoration(labelText: 'Hazard Type'),
            items: _hazardTypes
                .map((type) => DropdownMenuItem(value: type, child: Text(type)))
                .toList(),
            onChanged: (value) => setState(() => _hazardType = value),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _locationController,
            decoration: const InputDecoration(
              labelText: 'Location',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _descriptionController,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'Description',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _submit,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Attach Photo'),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _submit, child: const Text('Submit Report')),
        ],
      ),
    );
  }
}
