import 'local_profile_store.dart';
import 'sarapp_api_client.dart';

/// Thrown when a Person ID matches more than one personnel record. Carries
/// the [candidates] so the caller can let the operator pick which one is
/// theirs (see `showDuplicateRecordPicker`) instead of being blocked until
/// an administrator deduplicates the roster.
class AmbiguousPersonException extends SarAppApiException {
  AmbiguousPersonException(this.personId, this.candidates)
    : super(
        'More than one personnel record uses Person ID $personId. '
        'Pick the one that is you, or ask an administrator to fix the roster '
        'later.',
      );

  final String personId;
  final List<PersonCandidate> candidates;
}

/// Pushes the on-device profile to the connected server's master personnel
/// record. The device is the source of truth: an existing record for the
/// profile's Person ID is updated from it, and one is created when there is
/// none. Throws [AmbiguousPersonException] if the ID is shared by several
/// records.
class ProfileSync {
  ProfileSync(this._api);

  final SarAppApiClient _api;

  Future<void> sync(LocalProfile profile) async {
    final lookup = await _api.lookupPerson(profile.personId);
    switch (lookup.status) {
      case PersonLookupStatus.found:
        await _api.updateProfile(profile);
      case PersonLookupStatus.notFound:
        await _api.registerPerson(profile);
      case PersonLookupStatus.ambiguous:
        throw AmbiguousPersonException(profile.personId, lookup.candidates);
    }
  }
}
