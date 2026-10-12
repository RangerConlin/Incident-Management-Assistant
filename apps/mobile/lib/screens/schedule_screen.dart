import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';
import '../widgets/preview_banner.dart';

class _ScheduleItem {
  const _ScheduleItem({required this.time, required this.activity});
  final String time;
  final String activity;
}

/// Event-day schedule, shown under More only for Planned Event incidents
/// (see `IncidentTabConfig`). Not yet wired to a server schedule endpoint —
/// shows sample content.
class ScheduleScreen extends StatelessWidget {
  const ScheduleScreen({super.key, required this.args});

  final HomeNavArgs args;

  static const _sampleSchedule = [
    _ScheduleItem(time: '07:00', activity: 'Gates open / vendor setup'),
    _ScheduleItem(time: '09:00', activity: 'Event start'),
    _ScheduleItem(time: '12:00', activity: 'Shift change briefing'),
    _ScheduleItem(time: '17:00', activity: 'Event end / teardown begins'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Schedule')),
      drawer: AppDrawer(args: args),
      body: Column(
        children: [
          const PreviewBanner(
            message: 'Preview data — not yet connected to the incident schedule.',
          ),
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _sampleSchedule.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = _sampleSchedule[index];
                return ListTile(
                  leading: const Icon(Icons.schedule_outlined),
                  title: Text(item.activity),
                  trailing: Text(item.time),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
