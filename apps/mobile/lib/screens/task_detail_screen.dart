import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/task.dart';
import '../widgets/app_drawer.dart';
import '../widgets/section_card.dart';

/// Task detail / status-advance screen (ICS 204-style, Active911-inspired).
/// Status-advance actions are UI-only placeholders until the mobile
/// tasking write endpoints exist.
class TaskDetailScreen extends StatelessWidget {
  const TaskDetailScreen({super.key, required this.task, required this.args});

  final Task task;
  final HomeNavArgs args;

  void _notReady(BuildContext context, String action) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$action is not available yet in this build.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Task ${task.taskNumber}')),
      drawer: AppDrawer(args: args),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          SectionCard(
            title: task.title.isEmpty ? 'TASK DETAILS' : task.title,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                LabeledRow(label: 'Type', value: task.typeLabel),
                LabeledRow(label: 'Priority', value: task.priorityLabel),
                LabeledRow(label: 'Status', value: task.status.isEmpty ? '—' : task.status),
                LabeledRow(label: 'Location', value: task.location ?? '—'),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.tonal(
                  onPressed: () => _notReady(context, 'Acknowledge'),
                  child: const Text('Acknowledge'),
                ),
                FilledButton.tonal(
                  onPressed: () => _notReady(context, 'En Route'),
                  child: const Text('En Route'),
                ),
                FilledButton.tonal(
                  onPressed: () => _notReady(context, 'On Scene'),
                  child: const Text('On Scene'),
                ),
                FilledButton.tonal(
                  onPressed: () => _notReady(context, 'Complete'),
                  child: const Text('Complete'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SectionCard(
            title: 'NOTES',
            child: TextField(
              maxLines: 3,
              enabled: false,
              decoration: const InputDecoration(
                hintText: 'Task notes are read-only in this preview.',
                border: OutlineInputBorder(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
