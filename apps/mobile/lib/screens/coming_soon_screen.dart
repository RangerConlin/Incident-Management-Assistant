import 'package:flutter/material.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';

/// Shared placeholder for destinations that don't have a backend/screen
/// implementation yet (Map, Intel Report, Forms, additional field
/// actions). One stub convention used consistently instead of a bespoke
/// fake screen per feature.
class ComingSoonScreen extends StatelessWidget {
  const ComingSoonScreen({super.key, required this.title, required this.args, this.message});

  final String title;
  final HomeNavArgs args;
  final String? message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      drawer: AppDrawer(args: args),
      body: ComingSoonBody(title: title, message: message),
    );
  }
}

/// The placeholder body content alone, for screens that need their own
/// `Scaffold` around it instead of the default `AppBar` this widget builds.
class ComingSoonBody extends StatelessWidget {
  const ComingSoonBody({super.key, required this.title, this.message});

  final String title;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.construction_outlined, size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: 16),
            Text(
              message ?? '$title is not available yet in this build.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
