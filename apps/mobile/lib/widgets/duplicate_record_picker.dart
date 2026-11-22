import 'package:flutter/material.dart';

import '../services/sarapp_api_client.dart';

/// Lets the operator pick which personnel record is theirs when a Person ID
/// matches more than one (see `AmbiguousPersonException`), instead of being
/// blocked until an administrator deduplicates the roster. Mirrors the
/// desktop client's `DuplicateRecordPickerDialog`.
///
/// Returns the chosen record's `person_record`, or null if the operator
/// dismissed the dialog.
Future<int?> showDuplicateRecordPicker(
  BuildContext context,
  String personId,
  List<PersonCandidate> candidates,
) {
  return showDialog<int>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Multiple Matching Records'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'More than one personnel record uses ID "$personId". Pick the '
              'one that is you, or ask an administrator to merge/delete the '
              'rest later.',
            ),
            const SizedBox(height: 12),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: candidates.length,
                itemBuilder: (context, index) {
                  final candidate = candidates[index];
                  return ListTile(
                    title: Text('#${candidate.personRecord} — ${candidate.name}'),
                    subtitle: candidate.details.isEmpty
                        ? null
                        : Text(candidate.details),
                    onTap: () =>
                        Navigator.of(context).pop(candidate.personRecord),
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
      ],
    ),
  );
}
