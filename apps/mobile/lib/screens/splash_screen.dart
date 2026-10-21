import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../config/build_info.dart';
import '../services/server_connection_store.dart';
import '../services/session_store.dart';
import '../widgets/arc_horizon_mark.dart';
import 'field_dashboard_screen.dart';
import 'incident_staff_dashboard_screen.dart';
import 'main_menu_screen.dart';

/// First screen on launch. Loads what's stored on the device — no network —
/// then goes straight into the last incident if one is still loaded, or to
/// the main menu otherwise. Being offline never blocks either path.
class SplashScreen extends StatefulWidget {
  const SplashScreen({
    super.key,
    this.minDisplay = const Duration(milliseconds: 1400),
  });

  /// Shortest time the splash stays up, so it reads as a splash rather than
  /// a flicker when the stored data loads instantly.
  final Duration minDisplay;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  bool _visible = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _visible = true);
    });
    _boot();
  }

  Future<void> _boot() async {
    final results = await Future.wait<Object?>([
      _loadStoredState(),
      Future<void>.delayed(widget.minDisplay),
    ]);
    if (!mounted) return;
    final saved = results.first as StoredSession?;

    final Widget next = saved == null
        ? const MainMenuScreen()
        : saved.teamId.isEmpty
        ? IncidentStaffDashboardScreen(
            incidentId: saved.incidentId,
            incidentName: saved.incidentName,
            session: saved.session,
          )
        : FieldDashboardScreen(
            incidentId: saved.incidentId,
            incidentName: saved.incidentName,
            incidentType: saved.incidentType,
            teamId: saved.teamId,
            teamName: saved.teamName,
            session: saved.session,
          );
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => next));
  }

  Future<StoredSession?> _loadStoredState() async {
    await ServerConnectionStore.initialize();
    final saved = await SessionStore.load();

    // A session saved before connections were configurable was made against
    // the dev server; adopt it so that user isn't dropped into an incident
    // with nowhere to send requests.
    if (saved != null && ServerConnectionStore.active == null) {
      await ServerConnectionStore.addAndActivate(
        const ServerConnection(
          code: AppConfig.devConnectCode,
          routerUrl: AppConfig.cloudRouterBaseUrl,
        ),
      );
    }
    return saved;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final logoWidth = (MediaQuery.sizeOf(context).width - 48)
        .clamp(0.0, 320.0)
        .toDouble();
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Center(
                child: AnimatedOpacity(
                  opacity: _visible ? 1 : 0,
                  duration: const Duration(milliseconds: 600),
                  curve: Curves.easeOut,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ArcHorizonFullLogo(width: logoWidth),
                      const SizedBox(height: 32),
                      const SizedBox(
                        width: 28,
                        height: 28,
                        child: CircularProgressIndicator(strokeWidth: 3),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                BuildInfo.displayVersion,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
