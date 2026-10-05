class ApiConstants {
  ApiConstants._();

  static const String baseUrl = 'http://127.0.0.1:8000/api/v1';

  // Endpoints
  static const String health = '/health';
  static const String stocks = '/stocks';
  static const String stockSearch = '/stocks/search';
  static const String baskets = '/baskets';
  static const String purificationCalculate = '/purification/calculate';
  static const String purificationLedger = '/purification/ledger';
  static const String zakatCalculate = '/zakat/calculate';
  static const String academyModules = '/academy/modules';
  static const String dematGuide = '/academy/demat-guide';

  // Constants
  static const double silverNisabThresholdInr = 53550.0;
  static const double lunarZakatRate = 0.025000;
  static const double solarZakatRate = 0.025770;
}
