import 'package:flutter/material.dart';

import '../models/task.dart';
import '../services/sarapp_api_client.dart';

/// Bottom sheet for posting a new narrative entry against the current task.
/// Returns `true` if an entry was successfully posted, so the caller can
/// refetch the narrative feed.
Future<bool?> showAddNarrativeSheet(
  BuildContext context, {
  required SarAppApiClient apiClient,
  required String incidentId,
  required Task task,
  required String enteredBy,
  String? teamNum,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (context) => _AddNarrativeSheetContent(
      apiClient: apiClient,
      incidentId: incidentId,
      task: task,
      enteredBy: enteredBy,
      teamNum: teamNum,
    ),
  );
}

class _AddNarrativeSheetContent extends StatefulWidget {
  const _AddNarrativeSheetContent({
    required this.apiClient,
    required this.incidentId,
    required this.task,
    required this.enteredBy,
    this.teamNum,
  });

  final SarAppApiClient apiClient;
  final String incidentId;
  final Task task;
  final String enteredBy;
  final String? teamNum;

  @override
  State<_AddNarrativeSheetContent> createState() => _AddNarrativeSheetContentState();
}

class _AddNarrativeSheetContentState extends State<_AddNarrativeSheetContent> {
  final _controller = TextEditingController();
  bool _critical = false;
  bool _submitting = false;
  String? _errorMessage;

  Future<void> _submit() async {
    final text = _controller.text.trim();
    if (text.isEmpty) {
      setState(() => _errorMessage = 'Enter a narrative entry.');
      return;
    }
    final taskIntId = widget.task.intId;
    if (taskIntId == null) {
      setState(() => _errorMessage = 'This task has no valid id — cannot post a narrative.');
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await widget.apiClient.postNarrative(
        incidentId: widget.incidentId,
        taskId: taskIntId,
        narrative: text,
        enteredBy: widget.enteredBy,
        teamNum: widget.teamNum ?? '',
        critical: _critical,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on SarAppApiException catch (e) {
      if (mounted) setState(() => _errorMessage = 'Failed to post narrative: ${e.message}');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
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
          Text('Add Narrative', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          TextField(
            controller: _controller,
            maxLines: 4,
            autofocus: true,
            decoration: const InputDecoration(
              hintText: 'Narrative entry…',
              border: OutlineInputBorder(),
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Mark as Safety / Critical'),
            value: _critical,
            onChanged: (value) => setState(() => _critical = value),
          ),
          if (_errorMessage != null) ...[
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            const SizedBox(height: 8),
          ],
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Post Entry'),
          ),
        ],
      ),
    );
  }
}
