import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';
import '../widgets/preview_banner.dart';

class _ReferenceDoc {
  const _ReferenceDoc({required this.title, required this.category});
  final String title;
  final String category;
}

/// Field resources reference library viewer (Phase 5): SOPs, training
/// guides, maps. Not yet wired to `GET /api/master/reference-library` —
/// shows sample documents.
class ReferenceLibraryScreen extends StatelessWidget {
  const ReferenceLibraryScreen({super.key, required this.args});

  final HomeNavArgs args;

  static const _sampleDocs = [
    _ReferenceDoc(title: 'SAR Field Operations Guide', category: 'SOP'),
    _ReferenceDoc(title: 'Radio Communications Protocol', category: 'SOP'),
    _ReferenceDoc(title: 'Incident Area Overview Map', category: 'Map'),
    _ReferenceDoc(title: 'Hazard Recognition Training', category: 'Training'),
  ];

  void _notReady(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Opening reference documents is not available yet in this build.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reference Library')),
      drawer: AppDrawer(args: args),
      body: Column(
        children: [
          const PreviewBanner(
            message: 'Preview data — not yet connected to the reference library.',
          ),
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _sampleDocs.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final doc = _sampleDocs[index];
                return ListTile(
                  leading: const Icon(Icons.description_outlined),
                  title: Text(doc.title),
                  subtitle: Text(doc.category),
                  onTap: () => _notReady(context),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
