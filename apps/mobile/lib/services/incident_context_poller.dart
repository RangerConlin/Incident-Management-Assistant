import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/mobile_incident_context.dart';
import 'sarapp_api_client.dart';

/// Whether the viewer's team assignment changed between two polls.
enum TeamTransition { none, gained, lost }

/// Pure and unit-testable on its own: compares the previous and current
/// "do I have a team" flag from two `/mobile/context` polls. [previouslyHadTeam]
/// is null on the very first poll (nothing to compare against yet).
TeamTransition detectTeamTransition({
  required bool? previouslyHadTeam,
  required bool hasTeamNow,
}) {
  if (previouslyHadTeam == null) return TeamTransition.none;
  if (!previouslyHadTeam && hasTeamNow) return TeamTransition.gained;
  if (previouslyHadTeam && !hasTeamNow) return TeamTransition.lost;
  return TeamTransition.none;
}

/// Periodically refreshes `/mobile/context` while a dashboard screen
/// (`FieldDashboardScreen` or `IncidentStaffDashboardScreen`) is open, so a
/// team assignment added or removed server-side is noticed without the user
/// relaunching the app. Static start/stop lifecycle, same shape as
/// `AppPresenceService`/`ChatPresenceService` — only one dashboard screen is
/// ever the active one at a time.
class IncidentContextPoller {
  IncidentContextPoller._();

  static const _interval = Duration(seconds: 45);

  static Timer? _timer;
  static SarAppApiClient? _client;
  static bool? _lastHadTeam;

  static void start({
    required String incidentId,
    required int personRecord,
    required void Function(MobileIncidentContext context, TeamTransition transition) onUpdate,
    bool? initialHasTeam,
  }) {
    stop();
    _lastHadTeam = initialHasTeam;
    _client = SarAppApiClient();
    _timer = Timer.periodic(_interval, (_) async {
      final client = _client;
      if (client == null) return;
      try {
        final context = await client.fetchMobileIncidentContext(
          incidentId: incidentId,
          personRecord: personRecord,
        );
        final transition = detectTeamTransition(
          previouslyHadTeam: _lastHadTeam,
          hasTeamNow: context.hasTeam,
        );
        _lastHadTeam = context.hasTeam;
        onUpdate(context, transition);
      } catch (e) {
        debugPrint('IncidentContextPoller: poll failed: $e');
      }
    });
  }

  static void stop() {
    _timer?.cancel();
    _timer = null;
    _client?.dispose();
    _client = null;
    _lastHadTeam = null;
  }
}
