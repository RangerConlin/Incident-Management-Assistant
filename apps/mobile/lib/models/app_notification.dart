import 'dart:convert';

/// Notification severity, ported from the desktop repo's
/// `notifications/models/notification.py` (`Severity`/`SEVERITY_RANK`) so
/// both clients agree on what "urgent" means. Ordered lowest to highest.
class NotificationSeverity {
  NotificationSeverity._();

  static const informational = 'informational';
  static const routine = 'routine';
  static const priority = 'priority';
  static const emergency = 'emergency';

  static const all = [informational, routine, priority, emergency];

  static const _rank = {informational: 0, routine: 1, priority: 2, emergency: 3};

  static int rank(String severity) => _rank[severity] ?? _rank[routine]!;

  static String normalize(String? raw) {
    final lower = raw?.trim().toLowerCase();
    return all.contains(lower) ? lower! : routine;
  }

  /// Hex accent/background colors, ported from the desktop toast/feed
  /// widgets (`notifications/widgets/toast_manager.py`,
  /// `notifications/panels/notifications_panel.py`'s `_SEVERITY_ACCENT`/
  /// `_SEVERITY_BG`) so a given severity looks the same on both clients.
  static const _accentHex = {
    informational: 0xFF444444,
    routine: 0xFF888888,
    priority: 0xFFD9A938,
    emergency: 0xFFD93838,
  };

  static int accentColorValue(String severity) =>
      _accentHex[severity] ?? _accentHex[routine]!;
}

/// Notification category, ported from the desktop repo's
/// `notifications/models/notification.py` (`Category`) and
/// `notifications/panels/notifications_panel.py`'s `_CATEGORY_LABEL`.
class NotificationCategory {
  NotificationCategory._();

  static const operations = 'operations';
  static const communications = 'communications';
  static const safety = 'safety';
  static const logistics = 'logistics';
  static const planning = 'planning';
  static const administrative = 'administrative';
  static const system = 'system';

  static const all = [
    operations,
    communications,
    safety,
    logistics,
    planning,
    administrative,
    system,
  ];

  static const _shortLabel = {
    operations: 'OPS',
    communications: 'COMMS',
    safety: 'SAFETY',
    logistics: 'LOG',
    planning: 'PLAN',
    administrative: 'ADMIN',
    system: 'SYS',
  };

  static const _accentHex = {
    operations: 0xFF3879D9,
    communications: 0xFF38A8D9,
    safety: 0xFFD9A938,
    logistics: 0xFF8A38D9,
    planning: 0xFF38D978,
    administrative: 0xFF888888,
    system: 0xFF888888,
  };

  static const _label = {
    operations: 'Operations',
    communications: 'Communications',
    safety: 'Safety',
    logistics: 'Logistics',
    planning: 'Planning',
    administrative: 'Administrative',
    system: 'System',
  };

  static String label(String category) => _label[category] ?? category;

  static String shortLabel(String category) => _shortLabel[category] ?? '';

  static int accentColorValue(String category) =>
      _accentHex[category] ?? _accentHex[system]!;

  static String normalize(String? raw) {
    final lower = raw?.trim().toLowerCase();
    return all.contains(lower) ? lower! : operations;
  }
}

/// Per-category toast defaults, ported from the desktop repo's
/// `notifications/models/notification.py` (`CATEGORY_DEFAULTS`). Drives how
/// long an in-app banner stays up and whether it plays a sound, before any
/// [NotificationSeverity]-driven override is applied.
class CategoryToastDefaults {
  const CategoryToastDefaults({required this.durationMs, required this.sound});

  final int durationMs;
  final bool sound;

  static const _byCategory = {
    NotificationCategory.operations: CategoryToastDefaults(
      durationMs: 5000,
      sound: true,
    ),
    NotificationCategory.communications: CategoryToastDefaults(
      durationMs: 5000,
      sound: true,
    ),
    NotificationCategory.safety: CategoryToastDefaults(
      durationMs: 6000,
      sound: true,
    ),
    NotificationCategory.logistics: CategoryToastDefaults(
      durationMs: 4000,
      sound: true,
    ),
    NotificationCategory.planning: CategoryToastDefaults(
      durationMs: 4000,
      sound: true,
    ),
    NotificationCategory.administrative: CategoryToastDefaults(
      durationMs: 3000,
      sound: false,
    ),
    NotificationCategory.system: CategoryToastDefaults(
      durationMs: 3000,
      sound: false,
    ),
  };

  static CategoryToastDefaults forCategory(String category) =>
      _byCategory[category] ?? _byCategory[NotificationCategory.system]!;
}

/// How a notification should present itself in-app, resolved from category
/// defaults plus a severity override — mirrors the desktop repo's
/// `CATEGORY_TOAST_THRESHOLDS` + `SEVERITY_OVERRIDES` resolution in
/// `notification.py`.
class ToastPlan {
  const ToastPlan({
    required this.show,
    required this.sticky,
    required this.durationMs,
    required this.sound,
  });

  final bool show;

  /// An emergency notification is sticky: it blocks with a dialog the user
  /// must explicitly act on, instead of auto-dismissing like a routine
  /// banner.
  final bool sticky;
  final int durationMs;
  final bool sound;

  static const _toastThresholdRank = {
    NotificationCategory.operations: 1,
    NotificationCategory.communications: 1,
    NotificationCategory.safety: 0,
    NotificationCategory.logistics: 1,
    NotificationCategory.planning: 1,
    NotificationCategory.administrative: 2,
    NotificationCategory.system: 2,
  };

  static ToastPlan resolve({required String severity, required String category}) {
    final defaults = CategoryToastDefaults.forCategory(category);
    final threshold =
        _toastThresholdRank[category] ?? NotificationSeverity.rank(NotificationSeverity.routine);
    var show = NotificationSeverity.rank(severity) >= threshold;
    var sticky = false;
    var durationMs = defaults.durationMs;
    var sound = defaults.sound;

    switch (severity) {
      case NotificationSeverity.informational:
        show = false;
        sound = false;
      case NotificationSeverity.priority:
        durationMs = 7000;
      case NotificationSeverity.emergency:
        sticky = true;
    }

    return ToastPlan(show: show, sticky: sticky, durationMs: durationMs, sound: sound);
  }
}

/// One entry in the device-local notification history. Captured from
/// incoming FCM messages (see `PushNotificationService`) — this is an
/// in-app inbox only, not a server-synced record, though its fields mirror
/// the server's `notifications` collection shape (see the desktop repo's
/// `data/db/sarapp_db/schemas/notification_schema.py`) so a captured entry
/// carries everything needed to re-render or act on it (acknowledge,
/// dismiss, deep-link) later.
class AppNotification {
  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.severity,
    required this.category,
    required this.receivedAt,
    this.notificationId,
    this.incidentId,
    this.sourceType,
    this.sourceId,
    this.requiresAcknowledgement = false,
    this.acknowledged = false,
    this.data = const {},
    this.read = false,
  });

  final String id;
  final String title;
  final String body;
  final String severity;
  final String category;
  final DateTime receivedAt;

  /// The server's own integer id for this notification
  /// (`notification_id` in `data/db/sarapp_db/schemas/notification_schema.py`),
  /// needed to call the acknowledge/dismiss endpoints. Null for a
  /// locally-originated entry that never carried one.
  final int? notificationId;
  final String? incidentId;

  /// What this notification is about, e.g. `"task"`/`"team"` — used to
  /// deep-link a tap to the relevant mobile screen instead of always
  /// opening the Notification Center.
  final String? sourceType;
  final String? sourceId;
  final bool requiresAcknowledgement;
  final bool acknowledged;
  final Map<String, dynamic> data;
  final bool read;

  AppNotification copyWith({bool? read, bool? acknowledged}) => AppNotification(
    id: id,
    title: title,
    body: body,
    severity: severity,
    category: category,
    receivedAt: receivedAt,
    notificationId: notificationId,
    incidentId: incidentId,
    sourceType: sourceType,
    sourceId: sourceId,
    requiresAcknowledgement: requiresAcknowledgement,
    acknowledged: acknowledged ?? this.acknowledged,
    data: data,
    read: read ?? this.read,
  );

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    return AppNotification(
      id: '${json['id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      body: '${json['body'] ?? ''}',
      severity: NotificationSeverity.normalize(json['severity'] as String?),
      category: NotificationCategory.normalize(json['category'] as String?),
      receivedAt:
          DateTime.tryParse('${json['received_at'] ?? ''}') ?? DateTime.now(),
      notificationId: json['notification_id'] == null
          ? null
          : int.tryParse('${json['notification_id']}'),
      incidentId: (json['incident_id'] as String?)?.isEmpty ?? true
          ? null
          : json['incident_id'] as String,
      sourceType: (json['source_type'] as String?)?.isEmpty ?? true
          ? null
          : json['source_type'] as String,
      sourceId: (json['source_id'] as String?)?.isEmpty ?? true
          ? null
          : json['source_id'] as String,
      requiresAcknowledgement: json['requires_acknowledgement'] == true,
      acknowledged: json['acknowledged'] == true,
      data: (json['data'] is Map)
          ? Map<String, dynamic>.from(json['data'] as Map)
          : const {},
      read: json['read'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'body': body,
    'severity': severity,
    'category': category,
    'received_at': receivedAt.toIso8601String(),
    'notification_id': notificationId,
    'incident_id': incidentId,
    'source_type': sourceType,
    'source_id': sourceId,
    'requires_acknowledgement': requiresAcknowledgement,
    'acknowledged': acknowledged,
    'data': data,
    'read': read,
  };

  static String encodeList(List<AppNotification> items) =>
      jsonEncode(items.map((e) => e.toJson()).toList());

  static List<AppNotification> decodeList(String raw) {
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return [];
      return decoded
          .whereType<Map>()
          .map((e) => AppNotification.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    } catch (_) {
      return [];
    }
  }
}
