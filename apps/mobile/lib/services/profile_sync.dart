import 'local_profile_store.dart';
import 'sarapp_api_client.dart';

/// Pushes the on-device profile to the connected server's master personnel
/// record. The device is the source of truth: an existing record for the
/// profile's Person ID is updated from it, and one is created when there is
/// none. Throws [SarAppApiException] if the ID is shared by several records.
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
        throw SarAppApiException(
          'More than one personnel record uses Person ID ${profile.personId}. '
          'Ask an administrator to fix the roster.',
        );
    }
  }
}
