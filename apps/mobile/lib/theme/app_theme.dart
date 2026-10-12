import 'package:flutter/material.dart';

/// Dark operational theme for the field dashboard — a deliberate,
/// always-dark look for a single-purpose field ops tool (glare/battery
/// friendly), rather than following the device's light/dark setting.
class AppTheme {
  AppTheme._();

  static const primaryDarkBlue = Color(0xFF17324D);
  static const primaryLightBlue = Color(0xFF397A9A);
  static const horizonAccent = Color(0xFF74365A);
  static const neutralGray = Color(0xFF6B7280);

  static ThemeData get dark {
    final colorScheme =
        ColorScheme.fromSeed(
          seedColor: primaryLightBlue,
          brightness: Brightness.dark,
        ).copyWith(
          primary: primaryLightBlue,
          secondary: horizonAccent,
          tertiary: horizonAccent,
          outline: neutralGray,
        );
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: colorScheme,
    );
    return base.copyWith(
      scaffoldBackgroundColor: const Color(0xFF0D1822),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        backgroundColor: primaryDarkBlue,
        foregroundColor: Colors.white,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primaryLightBlue,
      ),
    );
  }
}

/// bg/fg pair for a team-status chip or button.
class StatusColor {
  const StatusColor(this.background, this.foreground);
  final Color background;
  final Color foreground;
}

/// Team-status color lookup, ported from the desktop app's
/// `styles/profiles/dark.py` `TEAM_STATUS` dict so the mobile UI matches the
/// existing design system's real values instead of a new palette.
class TeamStatusColors {
  TeamStatusColors._();

  static const Map<String, StatusColor> byKey = {
    'available': StatusColor(Color(0xFF2f6d34), Color(0xFFf5f5f5)),
    'assigned': StatusColor(Color(0xFFa88f1a), Color(0xFFf5f5f5)),
    'briefed': StatusColor(Color(0xFFa88f1a), Color(0xFFf5f5f5)),
    'enroute': StatusColor(Color(0xFF1aa8a8), Color(0xFFf5f5f5)),
    'arrival': StatusColor(Color(0xFF1f6088), Color(0xFFf0f0f0)),
    'find': StatusColor(Color(0xFFb2700d), Color(0xFFf5f5f5)),
    'complete': StatusColor(Color(0xFF2f6d34), Color(0xFFf5f5f5)),
    'break': StatusColor(Color(0xFF6e2b75), Color(0xFFf5f5f5)),
    'returning': StatusColor(Color(0xFF1f6088), Color(0xFFf5f5f5)),
    'oos': StatusColor(Color(0xFF8c2f2f), Color(0xFFf5f5f5)),
  };

  static const StatusColor fallback = StatusColor(
    Color(0xFF3a3a3a),
    Color(0xFFf5f5f5),
  );

  static StatusColor forKey(String statusKey) =>
      byKey[statusKey.toLowerCase()] ?? fallback;
}

/// A team-status option shown in the status grid: the canonical lowercase
/// `status_key` the PATCH endpoint expects, plus its display label.
class TeamStatusOption {
  const TeamStatusOption(this.key, this.label);
  final String key;
  final String label;
}

/// The real SARApp team-status vocabulary (see
/// `data/db/sarapp_db/api/routers/operations.py`'s `TEAM_STATUS_DISPLAY` in
/// the desktop repo, which is what the PATCH .../status endpoint actually
/// persists as `team.status`). Labels here match that endpoint's output
/// exactly — not the mockup's "Searching"/"At Clue" wording, and not the
/// "Discovery"/"RTB" abbreviations used only for ICS-214 log text — so the
/// status text mobile displays (e.g. in `IncidentHeaderBar`) always matches
/// what the desktop status board shows and colors for the same team.
class TeamStatuses {
  TeamStatuses._();

  static const primary = [
    TeamStatusOption('available', 'Available'),
    TeamStatusOption('enroute', 'En Route'),
    TeamStatusOption('arrival', 'On Scene'),
    TeamStatusOption('find', 'Find'),
    TeamStatusOption('break', 'Break'),
    TeamStatusOption('returning', 'Returning'),
    TeamStatusOption('complete', 'Complete'),
  ];

  static const overflow = [
    TeamStatusOption('assigned', 'Assigned'),
    TeamStatusOption('briefed', 'Briefed'),
    TeamStatusOption('oos', 'Out of Service'),
  ];

  static const all = [...primary, ...overflow];

  /// Best-effort reverse lookup from the team's server-reported display
  /// status string (e.g. "On Scene") back to a status_key, for highlighting
  /// the currently-selected button. Falls back to a lowercase slug match.
  static String? keyForDisplayLabel(String label) {
    for (final option in all) {
      if (option.label.toLowerCase() == label.toLowerCase()) return option.key;
    }
    return null;
  }
}
