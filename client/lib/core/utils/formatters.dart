import 'package:intl/intl.dart';

class Formatters {
  Formatters._();

  static final NumberFormat _currencyFormatter = NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 2,
  );

  static final NumberFormat _compactCurrencyFormatter = NumberFormat.compactCurrency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 1,
  );

  static final NumberFormat _percentFormatter = NumberFormat.percentPattern('en_IN')
    ..maximumFractionDigits = 2;

  static String formatCurrency(num amount) => _currencyFormatter.format(amount);

  static String formatCompactCurrency(num amount) => _compactCurrencyFormatter.format(amount);

  static String formatPercentage(num ratio) => '${(ratio * 100).toStringAsFixed(2)}%';

  static String formatNumber(num number) => NumberFormat('#,##,###.##', 'en_IN').format(number);
}
