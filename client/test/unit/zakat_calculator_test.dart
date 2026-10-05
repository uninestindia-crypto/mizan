import 'package:flutter_test/flutter_test.dart';

class ZakatCalculatorLogic {
  static const double silverNisabInr = 53550.0;
  static const double lunarRate = 0.025000; // 2.500%
  static const double solarRate = 0.025770; // 2.577%

  static Map<String, dynamic> calculateActiveTrader({
    required double portfolioValue,
    required double cashBalance,
    String calendar = 'lunar',
  }) {
    final rate = calendar.toLowerCase() == 'solar' ? solarRate : lunarRate;
    final zakatableBase = double.parse((portfolioValue + cashBalance).toStringAsFixed(2));
    final isObligatory = zakatableBase >= silverNisabInr;
    final zakatDue = isObligatory ? double.parse((zakatableBase * rate).toStringAsFixed(2)) : 0.0;

    return {
      'zakatable_base': zakatableBase,
      'is_obligatory': isObligatory,
      'rate': rate,
      'zakat_due': zakatDue,
    };
  }

  static Map<String, dynamic> calculateLongTermInvestor({
    required List<Map<String, dynamic>> holdings,
    required double cashBalance,
    String calendar = 'lunar',
  }) {
    final rate = calendar.toLowerCase() == 'solar' ? solarRate : lunarRate;
    double holdingsBase = 0.0;

    for (final h in holdings) {
      final znwaPerShare = (h['znwa_per_share'] as num?)?.toDouble() ?? 0.0;
      final clampedZnwa = znwaPerShare < 0.0 ? 0.0 : znwaPerShare;
      final shares = (h['shares'] as num?)?.toInt() ?? 0;
      holdingsBase += double.parse((clampedZnwa * shares).toStringAsFixed(2));
    }

    final zakatableBase = double.parse((holdingsBase + cashBalance).toStringAsFixed(2));
    final isObligatory = zakatableBase >= silverNisabInr;
    final zakatDue = isObligatory ? double.parse((zakatableBase * rate).toStringAsFixed(2)) : 0.0;

    return {
      'zakatable_base': zakatableBase,
      'is_obligatory': isObligatory,
      'rate': rate,
      'zakat_due': zakatDue,
    };
  }
}

void main() {
  group('Equity Zakat Calculator Mathematical Rigor', () {
    test('Active Trader Lunar rate is strictly 2.500% on 100% NLV', () {
      final result = ZakatCalculatorLogic.calculateActiveTrader(
        portfolioValue: 1000000.0,
        cashBalance: 200000.0,
        calendar: 'lunar',
      );
      expect(result['zakatable_base'], 1200000.0);
      expect(result['is_obligatory'], isTrue);
      expect(result['rate'], 0.025);
      expect(result['zakat_due'], 30000.00);
    });

    test('Active Trader Solar rate is strictly 2.577% on 100% NLV', () {
      final result = ZakatCalculatorLogic.calculateActiveTrader(
        portfolioValue: 1000000.0,
        cashBalance: 0.0,
        calendar: 'solar',
      );
      expect(result['zakatable_base'], 1000000.0);
      expect(result['zakat_due'], 25770.00);
    });

    test('Long-Term Investor computes Zakat only on Net Working Assets (ZNWA)', () {
      final holdings = [
        {'ticker': 'TCS.NS', 'shares': 500, 'znwa_per_share': 88.14},
        {'ticker': 'INFY.NS', 'shares': 1000, 'znwa_per_share': 68.59},
      ];
      final result = ZakatCalculatorLogic.calculateLongTermInvestor(
        holdings: holdings,
        cashBalance: 20000.0,
        calendar: 'lunar',
      );
      // TCS: 500 * 88.14 = 44,070.0; INFY: 1000 * 68.59 = 68,590.0; Total = 112,660 + 20,000 = 132,660.0
      expect(result['zakatable_base'], 132660.00);
      expect(result['zakat_due'], 3316.50);
    });

    test('Negative working capital is clamped to 0.0 and never reduces Zakat base', () {
      final holdings = [
        {'ticker': 'DISTRESSED.NS', 'shares': 1000, 'znwa_per_share': -45.50},
      ];
      final result = ZakatCalculatorLogic.calculateLongTermInvestor(
        holdings: holdings,
        cashBalance: 60000.0,
        calendar: 'lunar',
      );
      expect(result['zakatable_base'], 60000.0);
      expect(result['zakat_due'], 1500.0);
    });

    test('Silver Nisab Boundary: 1 cent below (₹53,549.99) is strictly EXEMPT', () {
      final result = ZakatCalculatorLogic.calculateActiveTrader(
        portfolioValue: 50000.0,
        cashBalance: 3549.99,
      );
      expect(result['zakatable_base'], 53549.99);
      expect(result['is_obligatory'], isFalse);
      expect(result['zakat_due'], 0.0);
    });

    test('Silver Nisab Boundary: Exactly threshold (₹53,550.00) is strictly OBLIGATORY', () {
      final result = ZakatCalculatorLogic.calculateActiveTrader(
        portfolioValue: 50000.0,
        cashBalance: 3550.00,
      );
      expect(result['zakatable_base'], 53550.00);
      expect(result['is_obligatory'], isTrue);
      expect(result['zakat_due'], 1338.75);
    });

    test('Silver Nisab Boundary: 1 cent above (₹53,550.01) is strictly OBLIGATORY', () {
      final result = ZakatCalculatorLogic.calculateActiveTrader(
        portfolioValue: 50000.0,
        cashBalance: 3550.01,
      );
      expect(result['zakatable_base'], 53550.01);
      expect(result['is_obligatory'], isTrue);
      expect(result['zakat_due'], 1338.75);
    });
  });
}
