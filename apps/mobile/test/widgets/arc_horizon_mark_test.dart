import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/widgets/arc_horizon_mark.dart';

void main() {
  testWidgets('brand widgets use the approved asset variants', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Column(
          children: [
            ArcHorizonMark(size: 48),
            ArcHorizonFullLogo(width: 240),
            ArcHorizonWordmark(width: 240),
          ],
        ),
      ),
    );

    final assets = tester
        .widgetList<Image>(find.byType(Image))
        .map((image) => (image.image as AssetImage).assetName);

    expect(
      assets,
      containsAll(<String>[
        'assets/branding/arc_horizon_mark.png',
        'assets/branding/arc_horizon_full_on_dark.png',
        'assets/branding/arc_horizon_wordmark_on_dark.png',
      ]),
    );
  });
}
