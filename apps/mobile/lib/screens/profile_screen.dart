import 'package:flutter/material.dart';

import '../models/organizations.dart';
import '../services/local_profile_store.dart';
import '../services/organizations_sync.dart';
import 'organization_picker_screen.dart';

/// Create or edit the on-device profile. The fields match the identifying
/// fields of the desktop's master personnel record. Saving only writes to the
/// device; the main menu and incident loading push it to the server.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, this.existing});

  final LocalProfile? existing;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final _personId = TextEditingController(text: widget.existing?.personId);
  late final _firstName = TextEditingController(text: widget.existing?.firstName);
  late final _lastName = TextEditingController(text: widget.existing?.lastName);
  late final _title = TextEditingController(text: widget.existing?.title);
  late final _phone = TextEditingController(text: widget.existing?.phone);
  late final _email = TextEditingController(text: widget.existing?.email);
  late final _radioId = TextEditingController(text: widget.existing?.radioId);

  // Organization picker: a hardcoded hierarchy (see lib/models/organizations.dart)
  // with a manual "Other" fallback for anything not in the list, since the
  // hierarchy only covers CAP and State-of-Michigan agencies so far.
  List<OrgEntry> _orgEntries = Organizations.bundled;
  String _selectedOrgKey = otherOrgKey;
  late final _customOrganization = TextEditingController();

  String? _errorMessage;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _applyOrganization(_orgEntries, widget.existing?.organization ?? '');
    // Upgrade from the bundled fallback to the synced server copy, if any.
    OrganizationsSync.loadOrganizations().then((entries) {
      if (!mounted) return;
      setState(() {
        _orgEntries = entries;
        _applyOrganization(entries, widget.existing?.organization ?? '');
      });
    });
  }

  /// Selects the dropdown entry matching [organizationName] by name, or
  /// falls back to "Other" with the raw text preserved in the free-text
  /// field (covers a pre-existing value entered before this picker existed,
  /// or one from outside the hardcoded hierarchy).
  void _applyOrganization(List<OrgEntry> entries, String organizationName) {
    final trimmed = organizationName.trim();
    final match = trimmed.isEmpty ? null : _findByName(entries, trimmed);
    if (match != null) {
      _selectedOrgKey = match.key;
      _customOrganization.text = '';
    } else {
      _selectedOrgKey = otherOrgKey;
      _customOrganization.text = trimmed;
    }
  }

  String get _organizationValue {
    if (_selectedOrgKey == otherOrgKey) return _customOrganization.text.trim();
    return _findByKey(_orgEntries, _selectedOrgKey)?.name ?? '';
  }

  static OrgEntry? _findByName(List<OrgEntry> entries, String name) {
    for (final entry in entries) {
      if (entry.name == name) return entry;
    }
    return null;
  }

  static OrgEntry? _findByKey(List<OrgEntry> entries, String key) {
    for (final entry in entries) {
      if (entry.key == key) return entry;
    }
    return null;
  }

  @override
  void dispose() {
    for (final c in [
      _personId,
      _firstName,
      _lastName,
      _customOrganization,
      _title,
      _phone,
      _email,
      _radioId,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final profile = LocalProfile(
      personId: _personId.text.trim(),
      firstName: _firstName.text.trim(),
      lastName: _lastName.text.trim(),
      organization: _organizationValue,
      title: _title.text.trim(),
      phone: _phone.text.trim(),
      email: _email.text.trim(),
      radioId: _radioId.text.trim(),
    );
    if (!profile.isComplete) {
      setState(
        () => _errorMessage = 'Person ID, first name and last name are required.',
      );
      return;
    }

    setState(() {
      _saving = true;
      _errorMessage = null;
    });
    await LocalProfileStore.save(profile);
    if (mounted) Navigator.of(context).pop(true);
  }

  Future<void> _remove() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove profile?'),
        content: const Text(
          'This removes the profile from this device only. Your personnel '
          'record on the server is not deleted. You can then create a profile '
          'with a different Person ID.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await LocalProfileStore.clear();
    if (mounted) Navigator.of(context).pop(true);
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    TextInputType? keyboardType,
    TextCapitalization capitalization = TextCapitalization.none,
    String? helper,
    bool enabled = true,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        enabled: enabled,
        keyboardType: keyboardType,
        textCapitalization: capitalization,
        decoration: InputDecoration(labelText: label, helperText: helper),
      ),
    );
  }

  Future<void> _pickOrganization() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (context) =>
            OrganizationPickerScreen(entries: _orgEntries),
      ),
    );
    if (result != null) setState(() => _selectedOrgKey = result);
  }

  Widget _organizationField() {
    // The hierarchy is too large (196+ entries) for a single dropdown, so
    // this opens a dedicated drill-down + search picker instead (see
    // organization_picker_screen.dart).
    final selected = _selectedOrgKey == otherOrgKey
        ? null
        : _findByKey(_orgEntries, _selectedOrgKey);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: _pickOrganization,
            child: InputDecorator(
              decoration: const InputDecoration(
                labelText: 'Organization',
                suffixIcon: Icon(Icons.chevron_right),
              ),
              child: Text(
                selected?.name ??
                    (_selectedOrgKey == otherOrgKey
                        ? 'Other / Not Listed'
                        : 'Tap to select'),
              ),
            ),
          ),
          if (_selectedOrgKey == otherOrgKey)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: TextField(
                controller: _customOrganization,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  labelText: 'Organization (not listed above)',
                ),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.existing != null;
    return Scaffold(
      appBar: AppBar(title: Text(editing ? 'Edit profile' : 'Create profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Saved on this device and used for every incident. Loading an '
            'incident, or saving while connected, updates your personnel '
            'record on the server to match.',
          ),
          const SizedBox(height: 16),
          _field(
            _personId,
            'Person ID *',
            enabled: !editing,
            helper: editing
                ? 'Identifies your personnel record, so it can\'t be changed. '
                      'Remove the profile to use a different ID.'
                : 'Your badge or member number',
          ),
          _field(
            _firstName,
            'First name *',
            capitalization: TextCapitalization.words,
          ),
          _field(
            _lastName,
            'Last name *',
            capitalization: TextCapitalization.words,
          ),
          _organizationField(),
          _field(_title, 'Title', capitalization: TextCapitalization.words),
          _field(_phone, 'Phone', keyboardType: TextInputType.phone),
          _field(_email, 'Email', keyboardType: TextInputType.emailAddress),
          _field(_radioId, 'Radio ID'),
          if (_errorMessage != null) ...[
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            const SizedBox(height: 12),
          ],
          FilledButton(
            onPressed: _saving ? null : _save,
            child: const Text('Save profile'),
          ),
          if (editing) ...[
            const SizedBox(height: 8),
            TextButton(
              onPressed: _remove,
              child: const Text('Remove profile from this device'),
            ),
          ],
        ],
      ),
    );
  }
}
