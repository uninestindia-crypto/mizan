import 'package:flutter_test/flutter_test.dart';

class PurificationLogic {
  static double calculateRatio(double interestIncome, double prohibitedRevenue, double totalRevenue) {
    if (totalRevenue <= 0.0) {
      return (interestIncome + prohibitedRevenue) > 0.0 ? 1.0 : 0.0;
    }
    return double.parse(((interestIncome + prohibitedRevenue) / totalRevenue).toStringAsFixed(6));
  }

  static double calculatePayable(double grossDividend, double purificationRatio) {
    return double.parse((grossDividend * purificationRatio).toStringAsFixed(2));
  }
}

void main() {
  group('Dividend Purification Mathematical Precision', () {
    test('Calculates purification ratio accurately with 6 decimal places', () {
      final ratio = PurificationLogic.calculateRatio(120.0, 30.0, 25000.0);
      // 150 / 25000 = 0.006
      expect(ratio, 0.006);
    });

    test('Zero impermissible revenue produces exact 0.00 ratio and 0.00 payable', () {
      final ratio = PurificationLogic.calculateRatio(0.0, 0.0, 10000.0);
      final payable = PurificationLogic.calculatePayable(5000.0, ratio);
      expect(ratio, 0.0);
      expect(payable, 0.0);
    });

    test('Purification payable rounds half-up to 2 decimal places', () {
      // 1000 * 0.005555 = 5.555 -> 5.56
      final payable = PurificationLogic.calculatePayable(1000.0, 0.005555);
      expect(payable, 5.56);
    });

    test('Zero declared dividend produces zero payable regardless of ratio', () {
      final payable = PurificationLogic.calculatePayable(0.0, 0.05);
      expect(payable, 0.0);
    });
  });
}
