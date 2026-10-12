import 'package:flutter/material.dart';

import '../models/task.dart';
import 'section_card.dart';

/// Compact task metadata — deliberately minimal, just the task number and
/// name. The rest of the task's metadata (type, status, assignment info)
/// isn't something the field team cares about day-to-day, so it's omitted
/// to leave room for the location and narrative feed.
class TaskMetadataCard extends StatelessWidget {
  const TaskMetadataCard({
    super.key,
    required this.task,
    this.assignedTime,
    this.assignedBy,
  });

  final Task task;
  final DateTime? assignedTime;
  final String? assignedBy;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'TASK ${task.taskNumber}',
      trailing: _PriorityChip(priority: task.priorityLabel),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: task.title.isNotEmpty
          ? Text(
              task.title,
              style: Theme.of(context).textTheme.titleSmall,
            )
          : const SizedBox.shrink(),
    );
  }
}

class _PriorityChip extends StatelessWidget {
  const _PriorityChip({required this.priority});
  final String priority;

  Color _color(BuildContext context) {
    switch (priority) {
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _color(context),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        priority.toUpperCase(),
        style: const TextStyle(color: Color(0xFFf5f5f5), fontSize: 11, fontWeight: FontWeight.w700),
      ),
    );
  }
}
