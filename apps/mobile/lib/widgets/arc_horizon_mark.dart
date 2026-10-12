import 'package:flutter/material.dart';

const _markAsset = 'assets/branding/arc_horizon_mark.png';
const _fullLogoOnDarkAsset =
    'assets/branding/arc_horizon_full_on_dark.png';
const _wordmarkOnDarkAsset =
    'assets/branding/arc_horizon_wordmark_on_dark.png';

/// The standalone Arc-Horizon mark for compact in-app placements.
class ArcHorizonMark extends StatelessWidget {
  const ArcHorizonMark({super.key, required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _markAsset,
      width: size,
      height: size,
      fit: BoxFit.contain,
      semanticLabel: 'Arc-Horizon',
    );
  }
}

/// The complete stacked lockup, including the product descriptor.
///
/// This light-text variant is intended for the app's dark surfaces.
class ArcHorizonFullLogo extends StatelessWidget {
  const ArcHorizonFullLogo({super.key, required this.width});

  final double width;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _fullLogoOnDarkAsset,
      width: width,
      fit: BoxFit.contain,
      semanticLabel: 'Arc-Horizon — Incident Command Assistant',
    );
  }
}

/// The horizontal lockup for short, wide headers on dark surfaces.
class ArcHorizonWordmark extends StatelessWidget {
  const ArcHorizonWordmark({super.key, required this.width});

  final double width;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      _wordmarkOnDarkAsset,
      width: width,
      fit: BoxFit.contain,
      semanticLabel: 'Arc-Horizon — Incident Command Assistant',
    );
  }
}
