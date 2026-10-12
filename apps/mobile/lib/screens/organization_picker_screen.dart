import 'package:flutter/material.dart';

import '../models/organizations.dart';

/// Sentinel returned by [OrganizationPickerScreen] meaning "I don't see mine
/// in the list — let me type it in", distinct from any real organization
/// key. Shared with `profile_screen.dart`, which owns the free-text field
/// shown when this comes back.
const otherOrgKey = '__other__';

/// Drill-down + search picker over the (currently 196-entry) hardcoded
/// organization hierarchy. A single flat dropdown doesn't scale to that
/// many entries on a phone screen, so this instead:
/// - shows one tier at a time (tap a row with children to go in a level,
///   tap "Use this" to pick that tier itself without going further), and
/// - lets a search query jump straight to any entry at any depth, showing
///   its ancestor chain so the result is unambiguous.
///
/// Returns (via `Navigator.pop`) the selected [OrgEntry.key], [otherOrgKey]
/// if the user chose to type their own in, or `null` if they backed out
/// without choosing (caller should leave the existing selection alone).
class OrganizationPickerScreen extends StatefulWidget {
  const OrganizationPickerScreen({super.key, required this.entries});

  final List<OrgEntry> entries;

  @override
  State<OrganizationPickerScreen> createState() =>
      _OrganizationPickerScreenState();
}

class _OrganizationPickerScreenState extends State<OrganizationPickerScreen> {
  final _searchController = TextEditingController();
  String _query = '';

  // The path of organization keys drilled into so far; `null` means "at the
  // top-level roots". The last element (or null) is the current tier.
  final List<String?> _stack = [null];

  late final Map<String, OrgEntry> _byKey = {
    for (final entry in widget.entries) entry.key: entry,
  };
  late final Map<String?, List<OrgEntry>> _childrenByParent = () {
    final map = <String?, List<OrgEntry>>{};
    for (final entry in widget.entries) {
      map.putIfAbsent(entry.parentKey, () => []).add(entry);
    }
    for (final children in map.values) {
      children.sort((a, b) => a.name.compareTo(b.name));
    }
    return map;
  }();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  bool _hasChildren(String key) => _childrenByParent.containsKey(key);

  String _ancestorChain(OrgEntry entry) {
    final names = <String>[];
    var parentKey = entry.parentKey;
    while (parentKey != null) {
      final parent = _byKey[parentKey];
      if (parent == null) break;
      names.insert(0, parent.name);
      parentKey = parent.parentKey;
    }
    return names.join(' › ');
  }

  List<OrgEntry> _searchResults(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return const [];
    return widget.entries
        .where(
          (entry) =>
              entry.name.toLowerCase().contains(q) ||
              entry.shortName.toLowerCase().contains(q),
        )
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));
  }

  void _drillInto(String key) => setState(() => _stack.add(key));

  void _goBackOneLevel() => setState(() => _stack.removeLast());

  @override
  Widget build(BuildContext context) {
    final currentKey = _stack.last;
    final currentOrg = currentKey != null ? _byKey[currentKey] : null;
    final children = _childrenByParent[currentKey] ?? const [];
    final results = _searchResults(_query);
    final showingSearch = _query.trim().isNotEmpty;

    return PopScope(
      canPop: _stack.length == 1,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) _goBackOneLevel();
      },
      child: Scaffold(
        appBar: AppBar(title: Text(currentOrg?.name ?? 'Organization')),
        body: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                controller: _searchController,
                decoration: const InputDecoration(
                  labelText: 'Search',
                  prefixIcon: Icon(Icons.search),
                  border: OutlineInputBorder(),
                ),
                onChanged: (value) => setState(() => _query = value),
              ),
            ),
            Expanded(
              child: showingSearch
                  ? _buildSearchResults(results)
                  : _buildLevel(currentOrg, children),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchResults(List<OrgEntry> results) {
    if (results.isEmpty) {
      return const Center(child: Text('No matches.'));
    }
    return ListView.builder(
      itemCount: results.length,
      itemBuilder: (context, index) {
        final entry = results[index];
        final chain = _ancestorChain(entry);
        return ListTile(
          title: Text(entry.name),
          subtitle: Text([
            if (chain.isNotEmpty) chain,
            if (entry.location.isNotEmpty) entry.location,
          ].join(' · ')),
          onTap: () => Navigator.of(context).pop(entry.key),
        );
      },
    );
  }

  Widget _buildLevel(OrgEntry? currentOrg, List<OrgEntry> children) {
    return ListView(
      children: [
        if (currentOrg != null)
          ListTile(
            leading: const Icon(Icons.check_circle_outline),
            title: Text("Use '${currentOrg.name}'"),
            subtitle: const Text('No more specific unit'),
            onTap: () => Navigator.of(context).pop(currentOrg.key),
          ),
        for (final entry in children)
          ListTile(
            title: Text(entry.name),
            subtitle: entry.location.isNotEmpty ? Text(entry.location) : null,
            trailing: _hasChildren(entry.key)
                ? const Icon(Icons.chevron_right)
                : null,
            onTap: () => _hasChildren(entry.key)
                ? _drillInto(entry.key)
                : Navigator.of(context).pop(entry.key),
          ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.edit_outlined),
          title: const Text('Not listed — type it in'),
          onTap: () => Navigator.of(context).pop(otherOrgKey),
        ),
      ],
    );
  }
}
