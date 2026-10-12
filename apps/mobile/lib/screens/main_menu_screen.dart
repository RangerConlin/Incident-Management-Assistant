import 'package:flutter/material.dart';

import '../config/build_info.dart';
import '../services/local_profile_store.dart';
import '../services/organizations_sync.dart';
import '../services/profile_sync.dart';
import '../services/sarapp_api_client.dart';
import '../services/server_connection_store.dart';
import '../widgets/arc_horizon_mark.dart';
import 'check_in_qr_screen.dart';
import 'connections_screen.dart';
import 'incident_picker_screen.dart';
import 'profile_screen.dart';

enum _ServerStatus { none, checking, connected, unreachable }

/// The app's home when no incident is loaded. Everything here works with no
/// server: the profile lives on the device and connections are just saved
/// codes. Only "Load incident" needs a reachable server.
class MainMenuScreen extends StatefulWidget {
  const MainMenuScreen({super.key, this.clientFactory = SarAppApiClient.new});

  /// Builds an API client for the *current* connection. A new one is needed
  /// per use because a client's base URL is fixed when it is created.
  final SarAppApiClient Function() clientFactory;

  @override
  State<MainMenuScreen> createState() => _MainMenuScreenState();
}

class _MainMenuScreenState extends State<MainMenuScreen> {
  LocalProfile? _profile;
  _ServerStatus _status = _ServerStatus.none;
  int _checkGeneration = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final profile = await LocalProfileStore.load();
    if (!mounted) return;
    setState(() => _profile = profile);
    await _checkConnection();
  }

  Future<void> _checkConnection() async {
    final generation = ++_checkGeneration;
    if (ServerConnectionStore.active == null) {
      setState(() => _status = _ServerStatus.none);
      return;
    }
    setState(() => _status = _ServerStatus.checking);

    final client = widget.clientFactory();
    final healthy = await client.checkHealth();
    if (healthy) {
      // Opportunistic — keeps the organization picker's roster current.
      // Awaited before dispose() below, since dispose() closes the
      // underlying HTTP client this call still needs.
      await OrganizationsSync.syncFromServer(client);
    }
    client.dispose();

    // A newer check (e.g. after switching connection) supersedes this one.
    if (!mounted || generation != _checkGeneration) return;
    setState(
      () => _status = healthy
          ? _ServerStatus.connected
          : _ServerStatus.unreachable,
    );
  }

  Future<void> _openProfile() async {
    final saved = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => ProfileScreen(existing: _profile)));
    if (saved != true) return;
    await _load();
    await _syncProfile();
  }

  /// Pushes the just-saved profile to the server's master record when it can
  /// be reached; otherwise it goes up the next time an incident is loaded.
  Future<void> _syncProfile() async {
    final profile = _profile;
    if (profile == null) return;

    var synced = false;
    if (_status == _ServerStatus.connected) {
      final client = widget.clientFactory();
      try {
        await ProfileSync(client).sync(profile);
        synced = true;
      } catch (_) {
        // Falls through to the "will update later" message below.
      } finally {
        client.dispose();
      }
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          synced
              ? 'Profile updated on the server.'
              : 'Saved on this device. The server will be updated when you load an incident.',
        ),
      ),
    );
  }

  void _openCheckInQr() {
    final profile = _profile;
    if (profile == null) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => CheckInQrScreen(profile: profile)),
    );
  }

  Future<void> _openConnections() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const ConnectionsScreen()),
    );
    if (mounted) _checkConnection();
  }

  void _openIncidentPicker() {
    final profile = _profile;
    if (profile == null) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => IncidentPickerScreen(
          profile: profile,
          clientFactory: widget.clientFactory,
        ),
      ),
    );
  }

  /// Why "Load incident" is unavailable, or null when it can be used.
  String? get _loadBlocker {
    if (_profile == null) return 'Create your profile first.';
    return switch (_status) {
      _ServerStatus.none => 'Add a connection code to load incidents.',
      _ServerStatus.checking => 'Checking the server…',
      _ServerStatus.unreachable => 'The server can\'t be reached right now.',
      _ServerStatus.connected => null,
    };
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final blocker = _loadBlocker;

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const SizedBox(height: 16),
            Align(
              alignment: Alignment.centerLeft,
              child: ArcHorizonWordmark(
                width: (MediaQuery.sizeOf(context).width - 32).clamp(
                  0.0,
                  360.0,
                ).toDouble(),
              ),
            ),
            const SizedBox(height: 24),
            _buildProfileCard(theme),
            const SizedBox(height: 12),
            _buildConnectionCard(theme),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: blocker == null ? _openIncidentPicker : null,
              icon: const Icon(Icons.login),
              label: const Text('Load incident'),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
              ),
            ),
            if (blocker != null) ...[
              const SizedBox(height: 8),
              Text(
                blocker,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _profile == null ? null : _openCheckInQr,
              icon: const Icon(Icons.qr_code_2),
              label: const Text('My check-in QR'),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
              ),
            ),
            const SizedBox(height: 32),
            Text(
              BuildInfo.displayVersion,
              textAlign: TextAlign.center,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileCard(ThemeData theme) {
    final profile = _profile;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: profile == null
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Your profile', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  const Text(
                    'Create a profile once and it is used for every incident. '
                    'It is saved on this device, so this works offline.',
                  ),
                  const SizedBox(height: 12),
                  FilledButton.tonal(
                    onPressed: _openProfile,
                    child: const Text('Create profile'),
                  ),
                ],
              )
            : Row(
                children: [
                  const Icon(Icons.person_outline, size: 32),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          profile.fullName,
                          style: theme.textTheme.titleMedium,
                        ),
                        Text(
                          [
                            'ID ${profile.personId}',
                            if (profile.organization.isNotEmpty)
                              profile.organization,
                          ].join(' · '),
                          style: theme.textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  TextButton(onPressed: _openProfile, child: const Text('Edit')),
                ],
              ),
      ),
    );
  }

  Widget _buildConnectionCard(ThemeData theme) {
    final active = ServerConnectionStore.active;
    final (IconData icon, Color color, String label) = switch (_status) {
      _ServerStatus.none => (
        Icons.link_off,
        theme.colorScheme.onSurfaceVariant,
        'No connection set',
      ),
      _ServerStatus.checking => (
        Icons.sync,
        theme.colorScheme.onSurfaceVariant,
        'Checking…',
      ),
      _ServerStatus.connected => (
        Icons.cloud_done_outlined,
        Colors.green,
        'Connected',
      ),
      _ServerStatus.unreachable => (
        Icons.cloud_off_outlined,
        theme.colorScheme.error,
        'Unreachable',
      ),
    };

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: 8),
                Text('Server connection', style: theme.textTheme.titleMedium),
                const Spacer(),
                Text(label, style: TextStyle(color: color)),
              ],
            ),
            if (active != null) ...[
              const SizedBox(height: 8),
              Text('Connect code ${active.code}'),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                FilledButton.tonal(
                  onPressed: _openConnections,
                  child: Text(active == null ? 'Add connection' : 'Manage'),
                ),
                const SizedBox(width: 8),
                if (active != null)
                  TextButton.icon(
                    onPressed: _status == _ServerStatus.checking
                        ? null
                        : _checkConnection,
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('Retry'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
