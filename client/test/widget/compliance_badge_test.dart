import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:halal_investment_client/models/stock_model.dart';
import 'package:halal_investment_client/widgets/compliance_badge.dart';

void main() {
  group('ComplianceBadge Widget Rendering', () {
    testWidgets('Renders COMPLIANT status with check icon and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ComplianceBadge(status: ComplianceStatus.compliant),
          ),
        ),
      );

      expect(find.text('COMPLIANT'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
    });

    testWidgets('Renders QUESTIONABLE status with warning icon and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ComplianceBadge(status: ComplianceStatus.questionable),
          ),
        ),
      );

      expect(find.text('QUESTIONABLE'), findsOneWidget);
      expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    });

    testWidgets('Renders NON-COMPLIANT status with cancel icon and label', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ComplianceBadge(status: ComplianceStatus.nonCompliant),
          ),
        ),
      );

      expect(find.text('NON-COMPLIANT'), findsOneWidget);
      expect(find.byIcon(Icons.cancel_rounded), findsOneWidget);
    });

    testWidgets('Renders with prefix standard label when provided', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ComplianceBadge(
              status: ComplianceStatus.compliant,
              standardLabel: 'AAOIFI',
            ),
          ),
        ),
      );

      expect(find.text('AAOIFI: COMPLIANT'), findsOneWidget);
    });
  });
}
