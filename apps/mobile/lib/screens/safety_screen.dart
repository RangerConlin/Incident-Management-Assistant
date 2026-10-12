import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';
import '../widgets/preview_banner.dart';
import '../widgets/section_card.dart';

/// Safety workspace scaffold. The SPE/GAR calculation system is not wired
/// into mobile yet; this screen gives teams a stable drawer destination for
/// the future GAR workflow without presenting placeholder values as live
/// safety data.
class SafetyScreen extends StatelessWidget {
  const SafetyScreen({super.key, required this.args});

  final HomeNavArgs args;

  void _notReady(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('GAR calculations are not available yet in this build.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final subduedStyle = theme.textTheme.bodyMedium?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Safety')),
      drawer: AppDrawer(args: args),
      body: Column(
        children: [
          const PreviewBanner(
            message:
                'Scaffold only - GAR calculations will be added after the SPE/GAR system is complete.',
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(0, 10, 0, 16),
              children: [
                SectionCard(
                  title: 'GAR CALCULATOR',
                  trailing: const _StatusChip(label: 'Pending'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Teams will use this workspace to calculate and review GAR scores before or during field assignments.',
                        style: subduedStyle,
                      ),
                      const SizedBox(height: 12),
                      FilledButton.icon(
                        onPressed: () => _notReady(context),
                        icon: const Icon(Icons.calculate_outlined),
                        label: const Text('Start GAR Calculation'),
                      ),
                    ],
                  ),
                ),
                const SectionCard(
                  title: 'SPE / GAR INPUTS',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _PlaceholderRow(
                        icon: Icons.groups_outlined,
                        label: 'Team factors',
                        value: 'Scaffold',
                      ),
                      _PlaceholderRow(
                        icon: Icons.terrain_outlined,
                        label: 'Environment and hazards',
                        value: 'Scaffold',
                      ),
                      _PlaceholderRow(
                        icon: Icons.assignment_outlined,
                        label: 'Mission complexity',
                        value: 'Scaffold',
                      ),
                    ],
                  ),
                ),
                SectionCard(
                  title: 'CURRENT STATUS',
                  child: Text(
                    'No GAR score has been calculated in the mobile app. Once the safety module is connected, the active score and mitigation notes will appear here.',
                    style: subduedStyle,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Chip(
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.compact,
      label: Text(label),
      backgroundColor: colorScheme.surface,
      labelStyle: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
    );
  }
}

class _PlaceholderRow extends StatelessWidget {
  const _PlaceholderRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 20, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 12),
          Expanded(child: Text(label)),
          Text(
            value,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}
