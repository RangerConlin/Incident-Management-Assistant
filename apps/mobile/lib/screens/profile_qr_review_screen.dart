import 'package:flutter/material.dart';

import '../services/sarapp_api_client.dart';
import '../utils/check_in_qr.dart';

class ProfileQrReviewScreen extends StatefulWidget {
  const ProfileQrReviewScreen({
    super.key,
    required this.incidentId,
    required this.payload,
    this.teamId,
    this.checkIn = true,
    this.approvedByPersonRecord,
    this.apiClient,
  });

  final String incidentId;
  final String payload;
  final int? teamId;
  final bool checkIn;
  final int? approvedByPersonRecord;
  final SarAppApiClient? apiClient;

  @override
  State<ProfileQrReviewScreen> createState() => _ProfileQrReviewScreenState();
}

class _ProfileQrReviewScreenState extends State<ProfileQrReviewScreen> {
  late final SarAppApiClient _api = widget.apiClient ?? SarAppApiClient();
  late final bool _ownsApi = widget.apiClient == null;
  Map<String, dynamic>? _profile;
  Map<String, dynamic>? _preview;
  String? _error;
  bool _loading = true;
  bool _applying = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    if (_ownsApi) _api.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final profile = CheckInQr.decode(widget.payload);
    if (profile == null) {
      setState(() {
        _error = 'This is not a supported SARApp personnel profile QR.';
        _loading = false;
      });
      return;
    }
    try {
      final preview = await _api.previewResourceQr(
        incidentId: widget.incidentId,
        profile: profile,
      );
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _preview = preview;
        _loading = false;
      });
    } on SarAppApiException catch (error) {
      if (mounted) {
        setState(() {
          _error = error.message;
          _loading = false;
        });
      }
    }
  }

  Future<void> _approve() async {
    final profile = _profile;
    if (profile == null) return;
    setState(() => _applying = true);
    try {
      final result = await _api.applyResourceQr(
        incidentId: widget.incidentId,
        profile: profile,
        teamId: widget.teamId,
        checkIn: widget.checkIn,
        approvedByPersonRecord: widget.approvedByPersonRecord,
      );
      if (mounted) Navigator.of(context).pop(result);
    } on SarAppApiException catch (error) {
      if (mounted) {
        setState(() {
          _error = error.message;
          _applying = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final preview = _preview;
    final ambiguous = preview?['match_status'] == 'ambiguous';
    return Scaffold(
      appBar: AppBar(title: const Text('Review scanned profile')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null)
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(_error!),
                    ),
                  ),
                if (preview != null) ...[
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      preview['match_status'] == 'new'
                          ? Icons.person_add_outlined
                          : Icons.person_search_outlined,
                    ),
                    title: Text('${_profile?['name'] ?? ''}'),
                    subtitle: Text(
                      preview['match_status'] == 'new'
                          ? 'A new master personnel record will be created.'
                          : ambiguous
                          ? 'Several records share this Person ID. Resolve the duplicate before check-in.'
                          : 'Matched an existing master personnel record.',
                    ),
                  ),
                  const Divider(),
                  for (final entry in _profile!.entries)
                    ListTile(
                      dense: true,
                      title: Text(entry.key.replaceAll('_', ' ')),
                      subtitle: Text(_displayValue(entry.value)),
                    ),
                  if ((preview['differences'] as List? ?? const []).isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(
                        'Incident copy fields that differ: ${(preview['differences'] as List).join(', ')}',
                      ),
                    ),
                  FilledButton.icon(
                    onPressed: ambiguous || _applying ? null : _approve,
                    icon: _applying
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.how_to_reg_outlined),
                    label: Text(
                      widget.teamId == null
                          ? 'Approve and check in'
                          : 'Approve, check in, and add to team',
                    ),
                  ),
                ],
              ],
            ),
    );
  }

  String _displayValue(Object? value) {
    if (value is Map) {
      if (value.isEmpty) return 'None';
      return value.entries
          .map(
            (entry) =>
                '${entry.key.toString().replaceAll('_', ' ')}: ${entry.value}',
          )
          .join('\n');
    }
    if (value is List) {
      if (value.isEmpty) return 'None';
      return value.map(_displayValue).join('\n');
    }
    return '$value';
  }
}
