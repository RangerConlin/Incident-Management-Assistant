import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Large, touch-friendly team-status buttons. The currently-selected status
/// is confirmed by the server (not a local guess) — see
/// `FieldDashboardScreen._onStatusSelected` for why status updates are
/// confirm-then-update rather than optimistic.
class TeamStatusGrid extends StatelessWidget {
  const TeamStatusGrid({
    super.key,
    required this.currentStatusKey,
    required this.busy,
    required this.onSelect,
  });

  final String? currentStatusKey;
  final bool busy;
  final void Function(TeamStatusOption option) onSelect;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 6),
            child: Text(
              'STATUS',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    letterSpacing: 0.5,
                  ),
            ),
          ),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 6,
            crossAxisSpacing: 6,
            childAspectRatio: 2.5,
            children: [
              for (final option in TeamStatuses.primary)
                _StatusButton(
                  option: option,
                  selected: option.key == currentStatusKey,
                  enabled: !busy,
                  onTap: () => onSelect(option),
                ),
              _MoreStatusButton(
                currentStatusKey: currentStatusKey,
                enabled: !busy,
                onSelect: onSelect,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatusButton extends StatelessWidget {
  const _StatusButton({
    required this.option,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final TeamStatusOption option;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = TeamStatusColors.forKey(option.key);
    return Material(
      color: enabled ? color.background : color.background.withValues(alpha: 0.45),
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: enabled ? onTap : null,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: selected ? Border.all(color: Colors.white, width: 2) : null,
          ),
          alignment: Alignment.center,
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Text(
            option.label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: enabled ? color.foreground : color.foreground.withValues(alpha: 0.85),
              fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }
}

class _MoreStatusButton extends StatelessWidget {
  const _MoreStatusButton({
    required this.currentStatusKey,
    required this.enabled,
    required this.onSelect,
  });

  final String? currentStatusKey;
  final bool enabled;
  final void Function(TeamStatusOption option) onSelect;

  Future<void> _openSheet(BuildContext context) async {
    final chosen = await showModalBottomSheet<TeamStatusOption>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final option in TeamStatuses.overflow)
              ListTile(
                title: Text(option.label),
                onTap: () => Navigator.of(sheetContext).pop(option),
              ),
          ],
        ),
      ),
    );
    if (chosen != null) onSelect(chosen);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final selectedOverflowKey = currentStatusKey != null &&
            TeamStatuses.overflow.any((o) => o.key == currentStatusKey)
        ? currentStatusKey
        : null;
    final selected = selectedOverflowKey != null;
    final selectedColor = selected
        ? TeamStatusColors.forKey(selectedOverflowKey)
        : null;
    return Material(
      color: selected
          ? (enabled
              ? selectedColor!.background
              : selectedColor!.background.withValues(alpha: 0.45))
          : theme.colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: enabled ? () => _openSheet(context) : null,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: selected ? Border.all(color: Colors.white, width: 2) : null,
          ),
          alignment: Alignment.center,
          child: Text(
            'More',
            style: TextStyle(
              color: selected
                  ? (enabled
                      ? selectedColor!.foreground
                      : selectedColor!.foreground.withValues(alpha: 0.85))
                  : theme.colorScheme.onSurface,
              fontWeight: FontWeight.w600,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }
}
