import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../models/app_notification.dart';
import '../models/notification_channel.dart';
import '../services/local_profile_store.dart';
import '../services/notification_channel_store.dart';
import '../services/notification_channels.dart';
import '../services/notification_preferences.dart';
import '../services/notification_store.dart';
import '../services/profile_sync.dart';
import '../services/sarapp_api_client.dart';
import '../services/text_scale_store.dart';
import '../services/tracking_service.dart';
import '../widgets/app_drawer.dart';
import 'connections_screen.dart';
import 'notification_center_screen.dart';
import 'profile_screen.dart';

/// App settings: Account/profile, connection management, notification
/// preferences, text-size appearance, Location Tracking (GIS Phase 1 — see
/// tracking_plan.md), and Battery Saving Mode (Phase 3.5, a local UI toggle
/// only; it doesn't yet reduce GPS/sync frequency since neither exists in
/// this build yet).
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.args});

  final HomeNavArgs args;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _batterySavingMode = false;
  bool _trackingEnabled = false;
  bool _trackingBusy = false;
  bool _loadingTrackingState = true;
  bool _sendingPing = false;
  bool _syncingPending = false;
  bool _loadingDiagnostics = false;
  TrackingDiagnostics? _diagnostics;

  LocalProfile? _profile;
  bool _loadingProfile = true;
  Map<String, bool> _notificationPrefs = const {};
  Map<String, NotificationSoundOption> _channelSounds = const {};
  int _unreadNotifications = 0;
  double _textScale = TextScaleStore.standard;

  String get _personId =>
      '${widget.args.session['person_id'] ?? widget.args.session['username'] ?? widget.args.session['user_id'] ?? ''}';

  @override
  void initState() {
    super.initState();
    _loadTrackingState();
    _loadProfile();
    _loadNotificationPrefs();
    _loadChannelSounds();
    _loadUnreadCount();
    _loadTextScale();
  }

  Future<void> _loadChannelSounds() async {
    final sounds = await NotificationChannelStore.loadAll();
    if (!mounted) return;
    setState(() => _channelSounds = sounds);
  }

  Future<void> _onChannelSoundChanged(
    String channelId,
    NotificationSoundOption? sound,
  ) async {
    if (sound == null) return;
    await NotificationChannels.updateSound(channelId, sound);
    if (!mounted) return;
    setState(() => _channelSounds = {..._channelSounds, channelId: sound});
  }

  Future<void> _loadProfile() async {
    final profile = await LocalProfileStore.load();
    if (!mounted) return;
    setState(() {
      _profile = profile;
      _loadingProfile = false;
    });
  }

  Future<void> _loadNotificationPrefs() async {
    final prefs = await NotificationPreferences.loadAll();
    if (!mounted) return;
    setState(() => _notificationPrefs = prefs);
  }

  Future<void> _loadUnreadCount() async {
    final count = await NotificationStore.unreadCount();
    if (!mounted) return;
    setState(() => _unreadNotifications = count);
  }

  Future<void> _loadTextScale() async {
    final scale = await TextScaleStore.load();
    if (!mounted) return;
    setState(() => _textScale = scale);
  }

  Future<void> _openProfile() async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => ProfileScreen(existing: _profile)),
    );
    if (saved != true) return;
    await _loadProfile();
    final profile = _profile;
    if (profile == null) return;
    final client = SarAppApiClient();
    var synced = false;
    try {
      await ProfileSync(client).sync(profile);
      synced = true;
    } catch (_) {
      // Falls through to the "will update later" message below.
    } finally {
      client.dispose();
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

  Future<void> _openConnections() async {
    await Navigator.of(
      context,
    ).push(MaterialPageRoute(builder: (_) => const ConnectionsScreen()));
  }

  Future<void> _openNotificationCenter() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const NotificationCenterScreen()),
    );
    await _loadUnreadCount();
  }

  Future<void> _onNotificationPrefChanged(String category, bool value) async {
    await NotificationPreferences.setEnabled(category, value);
    if (!mounted) return;
    setState(
      () => _notificationPrefs = {..._notificationPrefs, category: value},
    );
  }

  Future<void> _onTextScaleChanged(double? scale) async {
    if (scale == null) return;
    await TextScaleStore.save(scale);
    if (!mounted) return;
    setState(() => _textScale = scale);
  }

  Future<void> _loadTrackingState() async {
    final enabled = await TrackingService.isEnabled();
    if (!mounted) return;
    setState(() {
      _trackingEnabled = enabled;
      _loadingTrackingState = false;
    });
  }

  Future<void> _refreshDiagnostics() async {
    setState(() => _loadingDiagnostics = true);
    final diagnostics = await TrackingService.diagnostics(
      widget.args.incidentId,
    );
    if (!mounted) return;
    setState(() {
      _diagnostics = diagnostics;
      _loadingDiagnostics = false;
    });
  }

  Future<void> _onTrackingChanged(bool value) async {
    setState(() => _trackingBusy = true);
    if (value) {
      final consented = await _confirmLocationTracking();
      if (consented != true) {
        setState(() => _trackingBusy = false);
        return;
      }
      // Tracelet/tracelet_sync throw (e.g. MissingPluginException on a stale
      // build that predates the plugin) if native setup isn't ready — must
      // not let that leave the switch permanently disabled.
      var started = false;
      String? errorMessage;
      try {
        started = await TrackingService.start(
          incidentId: widget.args.incidentId,
          teamId: widget.args.teamId,
          teamName: widget.args.teamName,
          personId: _personId,
          personRecord: _personRecord,
        );
      } catch (e) {
        errorMessage = '$e';
      }
      if (!mounted) return;
      if (!started) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              errorMessage != null
                  ? 'Could not enable tracking: $errorMessage'
                  : 'Location permission is required to enable tracking. Check your device settings.',
            ),
          ),
        );
      }
      setState(() {
        _trackingEnabled = started;
        _trackingBusy = false;
      });
    } else {
      try {
        await TrackingService.stop();
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error while stopping tracking: $e')),
          );
        }
      }
      if (!mounted) return;
      setState(() {
        _trackingEnabled = false;
        _trackingBusy = false;
      });
    }
  }

  /// Explains why the app wants background/"Always" location before
  /// triggering the real OS dialog — that dialog can't be re-prompted after
  /// a denial, so the explanation has to come first. Mirrors the FCM
  /// permission prompt's approach (see notification_permission_prompt.dart).
  Future<bool?> _confirmLocationTracking() {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Share your location?'),
        content: const Text(
          "Turning this on shares your team's position with incident "
          'command in the background, including while the app is closed. '
          "You can turn it off here at any time — it never starts on its "
          'own just from logging in.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Enable Tracking'),
          ),
        ],
      ),
    );
  }

  Future<void> _onSendTestPing() async {
    setState(() => _sendingPing = true);
    final result = await TrackingService.sendManualPing(
      incidentId: widget.args.incidentId,
      teamId: widget.args.teamId,
      teamName: widget.args.teamName,
      personId: _personId,
      personRecord: _personRecord,
    );
    if (!mounted) return;
    setState(() => _sendingPing = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result), duration: const Duration(seconds: 6)),
    );
    await _refreshDiagnostics();
  }

  Future<void> _onSyncPendingNow() async {
    setState(() => _syncingPending = true);
    final result = await TrackingService.syncPendingNow();
    if (!mounted) return;
    setState(() => _syncingPending = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result), duration: const Duration(seconds: 6)),
    );
    await _refreshDiagnostics();
  }

  String? get _personRecord {
    final value =
        widget.args.session['person_record'] ??
        widget.args.session['user']?['person_record'];
    return value == null ? null : '$value';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      drawer: AppDrawer(args: widget.args),
      body: ListView(
        children: [
          const _SectionHeader('Account'),
          ListTile(
            leading: const Icon(Icons.badge_outlined),
            title: Text(
              _loadingProfile
                  ? 'Loading…'
                  : (_profile?.fullName.isNotEmpty ?? false)
                  ? _profile!.fullName
                  : 'Set up your profile',
            ),
            subtitle: Text(
              _profile?.organization.isNotEmpty ?? false
                  ? _profile!.organization
                  : 'Personal info, organization, and radio ID',
            ),
            onTap: _loadingProfile ? null : _openProfile,
          ),
          const _SectionHeader('Connection'),
          ListTile(
            leading: const Icon(Icons.wifi_tethering),
            title: const Text('Manage Connections'),
            subtitle: const Text(
              'Saved connect codes and which server this device uses. '
              'Changes apply the next time you connect or switch incidents.',
            ),
            onTap: _openConnections,
          ),
          const _SectionHeader('Notifications'),
          ListTile(
            leading: Badge(
              isLabelVisible: _unreadNotifications > 0,
              label: Text('$_unreadNotifications'),
              child: const Icon(Icons.notifications_outlined),
            ),
            title: const Text('Notification History'),
            subtitle: const Text(
              'Task assignments, command broadcasts, and chat alerts received on this device.',
            ),
            onTap: _openNotificationCenter,
          ),
          for (final category in NotificationCategory.all)
            SwitchListTile(
              secondary: const Icon(Icons.notifications_active_outlined),
              title: Text(NotificationCategory.label(category)),
              value: _notificationPrefs[category] ?? true,
              onChanged: (value) =>
                  _onNotificationPrefChanged(category, value),
            ),
          const _SectionHeader('Alert Sounds'),
          for (final channelId in NotificationChannelId.all)
            ListTile(
              leading: const Icon(Icons.music_note_outlined),
              title: Text(NotificationChannelId.label(channelId)),
              trailing: DropdownButton<NotificationSoundOption>(
                value: _channelSounds[channelId] ?? NotificationSoundOption.defaultSound,
                onChanged: (sound) => _onChannelSoundChanged(channelId, sound),
                items: [
                  for (final sound in NotificationSoundOption.all)
                    DropdownMenuItem(value: sound, child: Text(sound.label)),
                ],
              ),
            ),
          const _SectionHeader('Appearance'),
          ListTile(
            leading: const Icon(Icons.text_fields),
            title: const Text('Text Size'),
            subtitle: Text(TextScaleStore.label(_textScale)),
            trailing: DropdownButton<double>(
              value: _textScale,
              onChanged: _onTextScaleChanged,
              items: [
                for (final scale in TextScaleStore.options)
                  DropdownMenuItem(
                    value: scale,
                    child: Text(TextScaleStore.label(scale)),
                  ),
              ],
            ),
          ),
          const _SectionHeader('Location & Tracking'),
          SwitchListTile(
            secondary: const Icon(Icons.location_on_outlined),
            title: const Text('Location Tracking'),
            subtitle: const Text(
              "Shares your team's position with incident command in the background.",
            ),
            value: _trackingEnabled,
            onChanged: (_loadingTrackingState || _trackingBusy)
                ? null
                : _onTrackingChanged,
          ),
          ListTile(
            leading: _sendingPing
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.my_location_outlined),
            title: const Text('Send Test Location Ping'),
            subtitle: const Text(
              'Dev tool: sends one location fix straight to the server now, '
              "bypassing the background scheduler — doesn't require the "
              'toggle above to be on.',
            ),
            enabled: !_sendingPing,
            onTap: _sendingPing ? null : _onSendTestPing,
          ),
          ListTile(
            leading: _syncingPending
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync_outlined),
            title: const Text('Sync Pending GPS Queue Now'),
            subtitle: const Text(
              'Diagnostic: forces Tracelet to upload any GPS fixes it has captured but not sent yet.',
            ),
            enabled: !_syncingPending,
            onTap: _syncingPending ? null : _onSyncPendingNow,
          ),
          ListTile(
            leading: _loadingDiagnostics
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.fact_check_outlined),
            title: const Text('Refresh Tracking Diagnostics'),
            subtitle: const Text(
              'Shows permission, native tracking state, queued fixes, last HTTP sync, and server map count.',
            ),
            enabled: !_loadingDiagnostics,
            onTap: _loadingDiagnostics ? null : _refreshDiagnostics,
          ),
          if (_diagnostics != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: _TrackingDiagnosticsPanel(diagnostics: _diagnostics!),
            ),
          SwitchListTile(
            secondary: const Icon(Icons.battery_saver_outlined),
            title: const Text('Battery Saving Mode'),
            subtitle: const Text(
              'Reduces GPS and sync frequency (not yet wired to those systems)',
            ),
            value: _batterySavingMode,
            onChanged: (value) => setState(() => _batterySavingMode = value),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
      child: Text(
        title,
        style: Theme.of(context).textTheme.labelLarge?.copyWith(
          color: Theme.of(context).colorScheme.primary,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

class _TrackingDiagnosticsPanel extends StatelessWidget {
  const _TrackingDiagnosticsPanel({required this.diagnostics});

  final TrackingDiagnostics diagnostics;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final rows = <(String, String)>[
      ('Toggle saved', diagnostics.toggleEnabled ? 'On' : 'Off'),
      ('Tracelet active', _yesNoUnknown(diagnostics.traceletEnabled)),
      ('Mode', diagnostics.trackingMode ?? '-'),
      ('Moving', _yesNoUnknown(diagnostics.isMoving)),
      ('Provider', _yesNoUnknown(diagnostics.providerEnabled)),
      ('Permission', diagnostics.authorizationStatus ?? '-'),
      ('GPS', _yesNoUnknown(diagnostics.gpsEnabled)),
      ('Network location', _yesNoUnknown(diagnostics.networkEnabled)),
      (
        'Connection token',
        diagnostics.connectionTokenPresent ? 'Present' : 'Missing',
      ),
      ('Queued fixes', '${diagnostics.pendingLocationCount ?? '-'}'),
      ('Server map rows', '${diagnostics.serverLocationCount ?? '-'}'),
      ('Last GPS fix', diagnostics.lastLocation ?? '-'),
      ('Last HTTP sync', diagnostics.lastHttp ?? '-'),
      ('Last test ping', diagnostics.lastManualPing ?? '-'),
      ('Last manual sync', diagnostics.lastManualSync ?? '-'),
      if (diagnostics.error != null) ('Errors', diagnostics.error!),
    ];

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: theme.colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
        color: theme.colorScheme.surfaceContainerLow,
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Tracking Diagnostics', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 128,
                      child: Text(
                        row.$1,
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                    Expanded(child: Text(row.$2)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  static String _yesNoUnknown(bool? value) {
    if (value == null) return '-';
    return value ? 'Yes' : 'No';
  }
}
