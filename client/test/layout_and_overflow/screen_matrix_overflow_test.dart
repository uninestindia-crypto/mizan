import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:halal_investment_client/screens/dashboard_screen.dart';
import 'package:halal_investment_client/screens/screener_screen.dart';
import 'package:halal_investment_client/screens/baskets_screen.dart';
import 'package:halal_investment_client/screens/purification_screen.dart';
import 'package:halal_investment_client/screens/academy_zakat_screen.dart';

void main() {
  final viewports = [
    {'name': 'iPhone SE (375x667)', 'size': const Size(375, 667)},
    {'name': 'Android Flagship (412x915)', 'size': const Size(412, 915)},
    {'name': 'Tablet / iPad Air (820x1180)', 'size': const Size(820, 1180)},
    {'name': 'Desktop / Web 1080p (1920x1080)', 'size': const Size(1920, 1080)},
  ];

  final screens = [
    {'name': 'DashboardScreen', 'widget': const DashboardScreen()},
    {'name': 'ScreenerScreen', 'widget': const ScreenerScreen()},
    {'name': 'BasketsScreen', 'widget': const BasketsScreen()},
    {'name': 'PurificationScreen', 'widget': const PurificationScreen()},
    {'name': 'AcademyZakatScreen', 'widget': const AcademyZakatScreen()},
  ];

  group('Screen Matrix Zero-RenderFlex-Overflow Verification', () {
    for (final vp in viewports) {
      for (final scr in screens) {
        testWidgets(
          'Zero overflow on ${scr['name']} at ${vp['name']}',
          (tester) async {
            tester.view.physicalSize = vp['size'] as Size;
            tester.view.devicePixelRatio = 1.0;
            addTearDown(tester.view.resetPhysicalSize);

            await tester.pumpWidget(
              MaterialApp(
                theme: ThemeData.dark(),
                home: Scaffold(body: scr['widget'] as Widget),
              ),
            );
            await tester.pumpAndSettle();

            // Assert that no Flutter framework overflow exception occurred
            expect(tester.takeException(), isNull);
          },
        );
      }
    }
  });
}
