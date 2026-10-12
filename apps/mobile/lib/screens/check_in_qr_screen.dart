import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../services/local_profile_store.dart';
import '../utils/check_in_qr.dart';

/// Shows the person's check-in QR for a check-in desk to scan. Built from the
/// on-device profile alone, so it works with no connection.
class CheckInQrScreen extends StatelessWidget {
  const CheckInQrScreen({super.key, required this.profile});

  final LocalProfile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Check-in QR')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  profile.fullName,
                  style: theme.textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 4),
                Text('ID ${profile.personId}', style: theme.textTheme.bodyLarge),
                const SizedBox(height: 24),
                // Always dark-on-white, whatever the app theme: scanners need
                // the contrast, and a white quiet zone around the code.
                Container(
                  color: Colors.white,
                  padding: const EdgeInsets.all(16),
                  child: QrImageView(
                    data: CheckInQr.payload(profile.personId),
                    size: 260,
                    backgroundColor: Colors.white,
                    eyeStyle: const QrEyeStyle(
                      eyeShape: QrEyeShape.square,
                      color: Colors.black,
                    ),
                    dataModuleStyle: const QrDataModuleStyle(
                      dataModuleShape: QrDataModuleShape.square,
                      color: Colors.black,
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Show this to the check-in desk. Turn your screen brightness up if it is hard to scan.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
