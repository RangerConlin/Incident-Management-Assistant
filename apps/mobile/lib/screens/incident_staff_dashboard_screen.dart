import 'package:flutter/material.dart';

import '../services/app_presence_service.dart';
import '../services/chat_presence_service.dart';
import '../services/push_notification_service.dart';
import '../services/session_store.dart';
import '../utils/session_identity.dart';
import 'main_menu_screen.dart';

/// Temporary landing page for incident participants without a field team.
class IncidentStaffDashboardScreen extends StatefulWidget {
  const IncidentStaffDashboardScreen({
    super.key,
    required this.incidentId,
    required this.incidentName,
    required this.session,
  });

  final String incidentId;
  final String incidentName;
  final Map<String, dynamic> session;

  @override
  State<IncidentStaffDashboardScreen> createState() =>
      _IncidentStaffDashboardScreenState();
}

class _IncidentStaffDashboardScreenState
    extends State<IncidentStaffDashboardScreen> {
  @override
  void initState() {
    super.initState();
    _startServices();
  }

  Future<void> _startServices() async {
    final personRecord =
        widget.session['person_record'] ??
        widget.session['user']?['person_record'];
    final personId = SessionIdentity.personId(widget.session);
    await AppPresenceService.start(
      incidentId: widget.incidentId,
      teamId: '',
      teamName: '',
      personId: personId,
      personRecord: personRecord == null ? null : '$personRecord',
    );
    ChatPresenceService.start(incidentId: widget.incidentId, userId: personId);
    await PushNotificationService.syncRegistration(
      personRecord: personRecord == null ? null : '$personRecord',
      personId: personId.isEmpty ? null : personId,
      incidentId: widget.incidentId,
    );
  }

  Future<void> _switchIncident() async {
    AppPresenceService.stop();
    ChatPresenceService.stop();
    await SessionStore.clear();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const MainMenuScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.incidentName),
        actions: [
          IconButton(
            tooltip: 'Switch incident',
            onPressed: _switchIncident,
            icon: const Icon(Icons.swap_horiz),
          ),
        ],
      ),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.account_tree_outlined, size: 64),
              SizedBox(height: 16),
              Text(
                'Incident Staff',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w600),
              ),
              SizedBox(height: 8),
              Text(
                'Dashboard content will be added with the final mobile design.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
