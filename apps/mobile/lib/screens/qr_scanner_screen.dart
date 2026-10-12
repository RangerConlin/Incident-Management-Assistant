import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';

/// Field QR scan utility placeholder (equipment/location/team QR codes,
/// Phase 3.5). No camera scanning is wired up yet — this is a placeholder
/// consistent with the rest of the app's unwired-feature convention.
class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen({super.key, required this.args});

  final HomeNavArgs args;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('QR Scanner')),
      drawer: AppDrawer(args: args),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.qr_code_scanner_outlined, size: 64, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(height: 16),
              Text(
                'QR scanning is not available yet in this build.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
