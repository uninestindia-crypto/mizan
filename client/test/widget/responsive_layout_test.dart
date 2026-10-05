import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:halal_investment_client/widgets/adaptive_scaffold.dart';

void main() {
  group('AdaptiveScaffold Breakpoint Switching', () {
    testWidgets('Displays BottomNavigationBar on mobile viewports (<600dp)', (tester) async {
      // Set viewport width to 412 (Android Phone)
      tester.view.physicalSize = const Size(412, 915);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveScaffold(
            themeMode: ThemeMode.dark,
            onToggleTheme: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Mobile: BottomNavigationBar must be present, NavigationRail must NOT be present
      expect(find.byType(BottomNavigationBar), findsOneWidget);
      expect(find.byType(NavigationRail), findsNothing);
    });

    testWidgets('Displays NavigationRail on desktop/tablet viewports (>=600dp)', (tester) async {
      // Set viewport width to 1200 (Desktop/Web)
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveScaffold(
            themeMode: ThemeMode.dark,
            onToggleTheme: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Desktop: NavigationRail must be present, BottomNavigationBar must NOT be present
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsNothing);
    });
  });
}
