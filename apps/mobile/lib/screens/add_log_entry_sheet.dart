import 'package:flutter/material.dart';

import '../models/log_entry.dart';
import '../services/sarapp_api_client.dart';
import '../utils/session_identity.dart';

/// Bottom sheet for adding an ICS 214 log entry to the team's stream. Posts
/// to the server and returns true on success, or null if cancelled. Mirrors
/// `add_narrative_sheet.dart`'s layout convention.
Future<bool?> showAddLogEntrySheet(
  BuildContext context, {
  required SarAppApiClient apiClient,
  required String incidentId,
  required String teamId,
  required Map<String, dynamic> session,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (context) => _AddLogEntrySheetContent(
      apiClient: apiClient,
      incidentId: incidentId,
      teamId: teamId,
      actorUserId: SessionIdentity.personId(session),
    ),
  );
}

class _AddLogEntrySheetContent extends StatefulWidget {
  const _AddLogEntrySheetContent({
    required this.apiClient,
    required this.incidentId,
    required this.teamId,
    required this.actorUserId,
  });

  final SarAppApiClient apiClient;
  final String incidentId;
  final String teamId;
  final String actorUserId;

  @override
  State<_AddLogEntrySheetContent> createState() => _AddLogEntrySheetContentState();
}

class _AddLogEntrySheetContentState extends State<_AddLogEntrySheetContent> {
  final _activityController = TextEditingController();
  final _noteController = TextEditingController();
  String? _errorMessage;
  bool _submitting = false;

  Future<void> _submit() async {
    final activity = _activityController.text.trim();
    if (activity.isEmpty) {
      setState(() => _errorMessage = 'Enter what happened.');
      return;
    }
    final note = _noteController.text.trim();
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await widget.apiClient.postTeamLogEntry(
        incidentId: widget.incidentId,
        teamIntId: widget.teamId,
        text: LogEntry.composeText(activity, note),
        actorUserId: widget.actorUserId,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on SarAppApiException catch (e) {
      if (mounted) setState(() => _errorMessage = 'Failed to save log entry: ${e.message}');
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Failed to save log entry.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _activityController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Add Log Entry', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          TextField(
            controller: _activityController,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Activity',
              hintText: 'e.g. Departed staging area',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _noteController,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Note (optional)',
              border: OutlineInputBorder(),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 8),
            Text(_errorMessage!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: Text(_submitting ? 'Saving…' : 'Add Entry'),
          ),
        ],
      ),
    );
  }
}
