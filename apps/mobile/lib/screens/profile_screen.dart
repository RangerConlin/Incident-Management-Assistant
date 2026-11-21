import 'package:flutter/material.dart';

import '../models/organizations.dart';
import '../services/local_profile_store.dart';
import '../services/organizations_sync.dart';
import '../services/sarapp_api_client.dart';
import 'organization_picker_screen.dart';

/// Create or edit the on-device profile. The fields match the identifying
/// fields of the desktop's master personnel record. Saving only writes to the
/// device; the main menu and incident loading push it to the server.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, this.existing, this.clientFactory});

  final LocalProfile? existing;

  /// Builds a client for the active server connection, used to look up an
  /// existing catalog record for [_personId] and pre-fill a new profile from
  /// it. Null when there is no reachable connection yet — the operator just
  /// fills the form in by hand in that case, same as before this existed.
  final SarAppApiClient Function()? clientFactory;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final _personId = TextEditingController(text: widget.existing?.personId);
  late final _firstName = TextEditingController(
    text: widget.existing?.firstName,
  );
  late final _lastName = TextEditingController(text: widget.existing?.lastName);
  late final _primaryRole = TextEditingController(
    text: widget.existing?.primaryRole,
  );
  late final _homeUnit = TextEditingController(text: widget.existing?.homeUnit);
  late final _rank = TextEditingController(text: widget.existing?.rank);
  late final _callsign = TextEditingController(text: widget.existing?.callsign);
  late final _title = TextEditingController(text: widget.existing?.title);
  late final _phone = TextEditingController(text: widget.existing?.phone);
  late final _email = TextEditingController(text: widget.existing?.email);
  late final _radioId = TextEditingController(text: widget.existing?.radioId);
  late final _status = TextEditingController(text: widget.existing?.status);
  late final _notes = TextEditingController(text: widget.existing?.notes);
  late final _photoUrl = TextEditingController(text: widget.existing?.photoUrl);
  late final _certifications = TextEditingController(
    text: _formatCertifications(widget.existing?.certifications ?? const []),
  );
  late final Map<String, TextEditingController> _emergency = {
    for (final key in _emergencyFields.keys)
      key: TextEditingController(text: widget.existing?.emergencyInfo[key]),
  };
  late final Map<String, TextEditingController> _contact = {
    for (final key in _contactFields.keys)
      key: TextEditingController(text: widget.existing?.contactInfo[key]),
  };
  late bool _isMedic = widget.existing?.isMedic ?? false;

  // Organization picker: a hardcoded hierarchy (see lib/models/organizations.dart)
  // with a manual "Other" fallback for anything not in the list, since the
  // hierarchy only covers CAP and State-of-Michigan agencies so far.
  List<OrgEntry> _orgEntries = Organizations.bundled;
  String _selectedOrgKey = otherOrgKey;
  late final _customOrganization = TextEditingController();

  // Looks up the server's catalog record for a new Person ID and pre-fills
  // the rest of the form from it, so the operator isn't retyping a record
  // that already exists (e.g. after signing out, or on a new device).
  late final _personIdFocus = FocusNode()..addListener(_onPersonIdFocusChange);
  bool _lookingUpPersonId = false;

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

  void _onPersonIdFocusChange() {
    if (!_personIdFocus.hasFocus) _lookupPersonId();
  }

  /// Fetches the catalog record for the just-entered Person ID and fills the
  /// rest of the form from it. Only runs for a brand-new profile (not while
  /// editing one) and only while the name fields are still blank, so it
  /// can't silently overwrite something the operator already typed.
  Future<void> _lookupPersonId() async {
    final clientFactory = widget.clientFactory;
    if (widget.existing != null || clientFactory == null) return;
    final personId = _personId.text.trim();
    if (personId.isEmpty) return;
    if (_firstName.text.trim().isNotEmpty || _lastName.text.trim().isNotEmpty) {
      return;
    }

    setState(() => _lookingUpPersonId = true);
    final client = clientFactory();
    try {
      final lookup = await client.lookupPerson(personId);
      if (!mounted) return;
      final profile = lookup.profile;
      if (lookup.status == PersonLookupStatus.found && profile != null) {
        _applyLookedUpProfile(profile);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Loaded your existing profile from the server.'),
          ),
        );
      } else if (lookup.status == PersonLookupStatus.ambiguous) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Several personnel records share this ID; enter your details below.',
            ),
          ),
        );
      }
    } catch (_) {
      // Offline or unreachable - fall back to filling the form in by hand.
    } finally {
      client.dispose();
      if (mounted) setState(() => _lookingUpPersonId = false);
    }
  }

  /// Fills the form from a catalog record. Emergency contacts, additional
  /// contact info and notes are left alone — the lookup response doesn't
  /// carry those (see auth_sessions.py's `_login_person`), so there is
  /// nothing from the server to apply to them here.
  void _applyLookedUpProfile(LocalProfile profile) {
    setState(() {
      _firstName.text = profile.firstName;
      _lastName.text = profile.lastName;
      _homeUnit.text = profile.homeUnit;
      _primaryRole.text = profile.primaryRole;
      _rank.text = profile.rank;
      _callsign.text = profile.callsign;
      _title.text = profile.title;
      _phone.text = profile.phone;
      _email.text = profile.email;
      _radioId.text = profile.radioId;
      _status.text = profile.status;
      _isMedic = profile.isMedic;
      _certifications.text = _formatCertifications(profile.certifications);
      _applyOrganization(_orgEntries, profile.organization);
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
      _primaryRole,
      _homeUnit,
      _rank,
      _callsign,
      _title,
      _phone,
      _email,
      _radioId,
      _status,
      _notes,
      _photoUrl,
      _certifications,
      ..._emergency.values,
      ..._contact.values,
    ]) {
      c.dispose();
    }
    _personIdFocus.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final profile = LocalProfile(
      personId: _personId.text.trim(),
      firstName: _firstName.text.trim(),
      lastName: _lastName.text.trim(),
      organization: _organizationValue,
      homeUnit: _homeUnit.text.trim(),
      primaryRole: _primaryRole.text.trim(),
      rank: _rank.text.trim(),
      callsign: _callsign.text.trim(),
      title: _title.text.trim(),
      phone: _phone.text.trim(),
      email: _email.text.trim(),
      radioId: _radioId.text.trim(),
      isMedic: _isMedic,
      status: _status.text.trim().isEmpty ? 'available' : _status.text.trim(),
      notes: _notes.text.trim(),
      photoUrl: _photoUrl.text.trim(),
      emergencyInfo: _controllerValues(_emergency),
      contactInfo: _controllerValues(_contact),
      certifications: _parseCertifications(_certifications.text),
    );
    if (!profile.isComplete) {
      setState(
        () =>
            _errorMessage = 'Person ID, first name and last name are required.',
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
    FocusNode? focusNode,
    bool loading = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        focusNode: focusNode,
        enabled: enabled,
        keyboardType: keyboardType,
        textCapitalization: capitalization,
        decoration: InputDecoration(
          labelText: label,
          helperText: helper,
          suffixIcon: loading
              ? const Padding(
                  padding: EdgeInsets.all(14),
                  child: SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : null,
        ),
      ),
    );
  }

  static const _emergencyFields = {
    'primary_name': 'Primary contact name',
    'primary_relationship': 'Primary relationship',
    'primary_phone': 'Primary contact phone',
    'secondary_name': 'Secondary contact name',
    'secondary_relationship': 'Secondary relationship',
    'secondary_phone': 'Secondary contact phone',
    'medical': 'Medical information',
  };

  static const _contactFields = {
    'address1': 'Address line 1',
    'address2': 'Address line 2',
    'city': 'City',
    'state': 'State / Province',
    'zip': 'ZIP / Postal code',
    'work_phone': 'Work phone',
    'secondary_phone': 'Secondary phone',
    'pager_id': 'Pager / alternate radio ID',
    'notes': 'Contact notes',
  };

  static Map<String, String> _controllerValues(
    Map<String, TextEditingController> controllers,
  ) => {
    for (final entry in controllers.entries) entry.key: entry.value.text.trim(),
  };

  static String _formatCertifications(List<Map<String, int>> rows) => rows
      .map((row) => '${row['cert_type_id']}:${row['level'] ?? 0}')
      .join('; ');

  static List<Map<String, int>> _parseCertifications(String value) {
    final result = <Map<String, int>>[];
    for (final token in value.split(RegExp(r'[;\n,]+'))) {
      final parts = token.trim().split(':');
      final typeId = int.tryParse(parts.first.trim());
      if (typeId == null) continue;
      final level = parts.length > 1 ? int.tryParse(parts[1].trim()) ?? 0 : 0;
      result.add({'cert_type_id': typeId, 'level': level.clamp(0, 3)});
    }
    return result;
  }

  Widget _section({
    required String title,
    required IconData icon,
    required List<Widget> children,
    String? subtitle,
    bool initiallyExpanded = false,
  }) {
    return Card(
      clipBehavior: Clip.antiAlias,
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        initiallyExpanded: initiallyExpanded,
        leading: Icon(icon),
        title: Text(title),
        subtitle: subtitle == null ? null : Text(subtitle),
        childrenPadding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 600 ? 2 : 1;
              final spacing = 12.0;
              final width = columns == 2
                  ? (constraints.maxWidth - spacing) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: spacing,
                runSpacing: 0,
                children: [
                  for (final child in children)
                    SizedBox(width: width, child: child),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Future<void> _pickOrganization() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (context) => OrganizationPickerScreen(entries: _orgEntries),
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
      appBar: AppBar(
        title: Text(editing ? 'Edit profile' : 'Create profile'),
        actions: [
          TextButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.save_outlined),
            label: const Text('Save'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Saved on this device and used for every incident. Loading an '
              'incident, or saving while connected, updates your personnel '
              'record on the server to match.',
            ),
            const SizedBox(height: 12),
            if (_errorMessage != null) ...[
              Text(
                _errorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
              const SizedBox(height: 12),
            ],
            _section(
              title: 'Identity',
              icon: Icons.badge_outlined,
              subtitle: 'Required identification and organization',
              initiallyExpanded: true,
              children: [
                _field(
                  _personId,
                  'Person ID *',
                  enabled: !editing,
                  focusNode: editing ? null : _personIdFocus,
                  loading: _lookingUpPersonId,
                  helper: editing
                      ? 'Identifies your personnel record and cannot be changed.'
                      : widget.clientFactory == null
                      ? 'Your badge or member number'
                      : 'Loads your existing server record when available.',
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
                _field(
                  _homeUnit,
                  'Home unit',
                  capitalization: TextCapitalization.words,
                ),
              ],
            ),
            _section(
              title: 'Operational details',
              icon: Icons.assignment_ind_outlined,
              subtitle: 'Role, rank, callsign, radio, and availability',
              children: [
                _field(
                  _primaryRole,
                  'Primary role',
                  capitalization: TextCapitalization.words,
                ),
                _field(_rank, 'Rank', capitalization: TextCapitalization.words),
                _field(_callsign, 'Callsign'),
                _field(
                  _title,
                  'Title',
                  capitalization: TextCapitalization.words,
                ),
                _field(_radioId, 'Radio ID'),
                _field(_status, 'Status'),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Medical responder'),
                  subtitle: const Text('Available for medical roles'),
                  value: _isMedic,
                  onChanged: (value) => setState(() => _isMedic = value),
                ),
              ],
            ),
            _section(
              title: 'Contact',
              icon: Icons.contact_phone_outlined,
              subtitle: 'Primary ways to reach you',
              children: [
                _field(_phone, 'Phone', keyboardType: TextInputType.phone),
                _field(
                  _email,
                  'Email',
                  keyboardType: TextInputType.emailAddress,
                ),
                _field(_photoUrl, 'Photo URL', keyboardType: TextInputType.url),
                _field(
                  _notes,
                  'Personnel notes',
                  capitalization: TextCapitalization.sentences,
                ),
              ],
            ),
            _section(
              title: 'Emergency information',
              icon: Icons.emergency_outlined,
              subtitle: 'Contacts and medical information',
              children: [
                for (final entry in _emergencyFields.entries)
                  _field(
                    _emergency[entry.key]!,
                    entry.value,
                    keyboardType: entry.key.endsWith('phone')
                        ? TextInputType.phone
                        : null,
                    capitalization: TextCapitalization.sentences,
                  ),
              ],
            ),
            _section(
              title: 'Address and alternate contact',
              icon: Icons.home_outlined,
              subtitle: 'Mailing address and secondary contact methods',
              children: [
                for (final entry in _contactFields.entries)
                  _field(
                    _contact[entry.key]!,
                    entry.value,
                    keyboardType: entry.key.contains('phone')
                        ? TextInputType.phone
                        : null,
                    capitalization: TextCapitalization.sentences,
                  ),
              ],
            ),
            _section(
              title: 'Certifications',
              icon: Icons.workspace_premium_outlined,
              subtitle: 'Qualification type IDs and levels',
              children: [
                _field(
                  _certifications,
                  'Certification type IDs and levels',
                  helper:
                      'Use cert_type_id:level entries separated by semicolons. Levels are 0–3.',
                ),
              ],
            ),
            if (editing) ...[
              TextButton(
                onPressed: _remove,
                child: const Text('Remove profile from this device'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
