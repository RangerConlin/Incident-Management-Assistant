import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';
import '../widgets/preview_banner.dart';

class _NavTarget {
  const _NavTarget({required this.label, required this.coordinates});
  final String label;
  final String coordinates;
}

/// Quick GPS coordinate access for team members, assigned sectors, and
/// task destinations, with a placeholder to launch an external map app
/// (Phase 3.5). No location-targets endpoint exists yet — see
/// `Current Mobile API Contract.txt` — so this shows sample coordinates.
class NavigationToolsScreen extends StatelessWidget {
  const NavigationToolsScreen({super.key, required this.args});

  final HomeNavArgs args;

  static const _sampleTargets = [
    _NavTarget(label: 'My Team (GT-4 Alpha)', coordinates: '38.8951° N, 106.7621° W'),
    _NavTarget(label: 'Assigned Sector (Charlie-7)', coordinates: '38.9012° N, 106.7550° W'),
    _NavTarget(label: 'Task Destination', coordinates: '38.8890° N, 106.7703° W'),
  ];

  void _notReady(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Opening an external map app is not available yet in this build.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Navigation Tools')),
      drawer: AppDrawer(args: args),
      body: Column(
        children: [
          const PreviewBanner(
            message: 'Preview data — not yet connected to live location targets.',
          ),
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _sampleTargets.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final target = _sampleTargets[index];
                return ListTile(
                  leading: const Icon(Icons.near_me_outlined),
                  title: Text(target.label),
                  subtitle: Text(target.coordinates),
                  trailing: IconButton(
                    icon: const Icon(Icons.map_outlined),
                    tooltip: 'Open in map app',
                    onPressed: () => _notReady(context),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
