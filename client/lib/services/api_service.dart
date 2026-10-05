import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import '../core/constants/api_constants.dart';
import '../models/stock_model.dart';
import '../models/screening_result.dart';
import '../models/basket_model.dart';
import '../models/purification_item.dart';
import '../models/zakat_model.dart';

class ApiService {
  final http.Client _client;
  final String _baseUrl;

  // In-memory cache for ultra-fast offline responsiveness
  static final Map<String, dynamic> _responseCache = {};
  static List<StockSummary>? _bundledStocksCache;

  ApiService({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? ApiConstants.baseUrl;

  /// Loads bundled NIFTY 500 stocks from assets/data/sample_nifty500.json
  Future<List<StockSummary>> loadBundledStocks() async {
    if (_bundledStocksCache != null && _bundledStocksCache!.isNotEmpty) {
      return _bundledStocksCache!;
    }
    try {
      final jsonStr = await rootBundle.loadString('assets/data/sample_nifty500.json');
      final List decoded = jsonDecode(jsonStr);
      final list = decoded.map((e) => StockSummary.fromJson(e)).toList();
      _bundledStocksCache = list;
      return list;
    } catch (_) {
      return getFallbackStocks();
    }
  }

  // 1. Stock Universe & List
  Future<List<StockSummary>> getStocks({
    String? query,
    String? sector,
    String? status,
    String standard = 'aaoifi',
    int limit = 50,
    int offset = 0,
  }) async {
    final queryParams = {
      if (query != null && query.isNotEmpty) 'q': query,
      if (sector != null && sector.isNotEmpty) 'sector': sector,
      if (status != null && status.isNotEmpty) 'status': status,
      'standard': standard.toLowerCase(),
      'limit': limit.toString(),
      'offset': offset.toString(),
    };

    final cacheKey = 'stocks_${query}_${sector}_${status}_${standard}_$limit';
    final uri = Uri.parse('$_baseUrl${ApiConstants.stocks}').replace(queryParameters: queryParams);
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List items = data['items'] ?? [];
        final results = items.map((e) => StockSummary.fromJson(e)).toList();
        _responseCache[cacheKey] = results;
        return results;
      }
    } catch (_) {}

    if (_responseCache.containsKey(cacheKey)) {
      return _responseCache[cacheKey] as List<StockSummary>;
    }
    if (_bundledStocksCache != null && _bundledStocksCache!.isNotEmpty) {
      return _bundledStocksCache!;
    }
    return getFallbackStocks();
  }

  // 2. Full Shariah Audit Detail
  Future<ShariahAuditDetail?> getShariahAudit(String ticker) async {
    final cacheKey = 'audit_$ticker';
    if (_responseCache.containsKey(cacheKey)) {
      return _responseCache[cacheKey] as ShariahAuditDetail;
    }

    final uri = Uri.parse('$_baseUrl${ApiConstants.stocks}/$ticker/audit');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final result = ShariahAuditDetail.fromJson(jsonDecode(response.body));
        _responseCache[cacheKey] = result;
        return result;
      }
    } catch (_) {}
    return null;
  }

  // 3. Curated Baskets
  Future<List<BasketModel>> getBaskets() async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.baskets}');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        return data.map((e) => BasketModel.fromJson(e)).toList();
      }
    } catch (_) {}
    return getFallbackBaskets();
  }

  // 4. Broker Order Export
  Future<BasketExportResult?> exportBasketOrders({
    required String basketId,
    required String broker,
    required double capital,
  }) async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.baskets}/$basketId/export');
    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'broker': broker.toLowerCase(),
          'capital': capital,
        }),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return BasketExportResult.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return null;
  }

  // 5. Calculate Purification
  Future<PurificationCalculateResult?> calculatePurification({
    required String ticker,
    required double dividendAmount,
    required int sharesHeld,
  }) async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.purificationCalculate}');
    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'ticker': ticker,
          'dividend_amount': dividendAmount,
          'shares_held': sharesHeld,
        }),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return PurificationCalculateResult.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return null;
  }

  // 6. List Purification Ledger
  Future<List<PurificationLedgerEntryModel>> getPurificationLedger() async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.purificationLedger}');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List items = data['items'] ?? [];
        return items.map((e) => PurificationLedgerEntryModel.fromJson(e)).toList();
      }
    } catch (_) {}
    return [];
  }

  // 7. Calculate Zakat
  Future<ZakatCalculationResult?> calculateZakat({
    required String method,
    required double portfolioValue,
    required double cashBalance,
    required List<Map<String, dynamic>> holdings,
    String calendar = 'lunar',
  }) async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.zakatCalculate}');
    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'method': method,
          'portfolio_value': portfolioValue,
          'cash_balance': cashBalance,
          'holdings': holdings,
          'calendar': calendar,
        }),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return ZakatCalculationResult.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}
    return null;
  }

  // 8. Indian Statutory Tax & Brokerage Calculator
  Future<TaxCalculationResponse> calculateStatutoryTaxes({
    required double investmentAmount,
    String broker = 'Zerodha',
    String exchange = 'NSE',
  }) async {
    final uri = Uri.parse('$_baseUrl${ApiConstants.baskets}/tax-calculator');
    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'investment_amount': investmentAmount,
          'broker': broker,
          'exchange': exchange,
        }),
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return TaxCalculationResponse.fromJson(jsonDecode(response.body));
      }
    } catch (_) {}

    // Precise local calculation fallback
    final turnover = investmentAmount;
    final brokerage = 0.0;
    final stt = (turnover * 0.001 * 100).round() / 100.0;
    final exRate = exchange.toUpperCase() == 'NSE' ? 0.0000325 : 0.0000375;
    final exchangeCharges = (turnover * exRate * 100).round() / 100.0;
    final sebiCharges = (turnover * 0.000001 * 100).round() / 100.0;
    final stampDuty = (turnover * 0.00015 * 100).round() / 100.0;
    final gst = ((brokerage + exchangeCharges + sebiCharges) * 0.18 * 100).round() / 100.0;
    final totalCharges = (stt + exchangeCharges + sebiCharges + stampDuty + gst);
    final netCost = turnover + totalCharges;
    final taxRate = (totalCharges / turnover) * 100.0;

    return TaxCalculationResponse(
      investmentAmount: turnover,
      broker: broker,
      exchange: exchange.toUpperCase(),
      brokerage: brokerage,
      sttCtt: stt,
      exchangeCharges: exchangeCharges,
      sebiCharges: sebiCharges,
      stampDuty: stampDuty,
      gst: gst,
      totalStatutoryCharges: totalCharges,
      estimatedDividendPurificationRatio: 0.0042,
      netEffectiveCost: netCost,
      effectiveTaxRatePct: taxRate,
    );
  }

  // 9. Curated Halal Mutual Funds & ETFs
  Future<List<FundModel>> getFunds() async {
    final uri = Uri.parse('$_baseUrl/funds');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final List list = jsonDecode(response.body);
        return list.map((e) => FundModel.fromJson(e)).toList();
      }
    } catch (_) {}

    return [
      FundModel(
        id: 'tata-ethical-fund',
        name: 'Tata Ethical Fund',
        type: 'Mutual Fund (Equity)',
        aumInrCr: 2640.0,
        nav: 412.35,
        cagr3yr: 22.4,
        cagr5yr: 21.8,
        expenseRatio: 0.92,
        shariahBoard: 'TASIS (Tasis Shariah Advisory)',
        minSip: 500.0,
        risk: 'Moderate',
        benchmark: 'NIFTY 500 Shariah TRI',
        description: "India's oldest and largest Shariah-compliant mutual fund investing exclusively in audited Shariah-permissible Indian growth equities.",
        topHoldings: 'TCS (8.2%), Infosys (7.5%), Titan (5.4%), Tata Motors (4.8%), HCL Tech (4.2%)',
      ),
      FundModel(
        id: 'taurus-ethical-fund',
        name: 'Taurus Ethical Fund',
        type: 'Mutual Fund (Equity)',
        aumInrCr: 185.0,
        nav: 114.60,
        cagr3yr: 24.1,
        cagr5yr: 22.5,
        expenseRatio: 1.15,
        shariahBoard: 'TASIS',
        minSip: 500.0,
        risk: 'Moderate to High',
        benchmark: 'S&P BSE 500 Shariah TRI',
        description: 'Actively managed equity scheme investing in Shariah-compliant universe screened under strict debt and revenue rules.',
        topHoldings: 'Infosys (8.8%), TCS (8.1%), Persistent (5.2%), Abbott India (4.9%)',
      ),
      FundModel(
        id: 'nippon-shariah-bees',
        name: 'Nippon India ETF Shariah BeES',
        ticker: 'SHARIABEES.NS',
        type: 'Exchange Traded Fund (ETF)',
        aumInrCr: 82.0,
        nav: 524.10,
        cagr3yr: 20.8,
        cagr5yr: 19.9,
        expenseRatio: 0.45,
        shariahBoard: 'NSE Indices Shariah Council',
        minSip: 524.0,
        risk: 'Moderate',
        benchmark: 'NIFTY 50 Shariah Index',
        description: "Lowest-cost index fund tracking India's premier NIFTY 50 Shariah Index directly on the NSE cash market.",
        topHoldings: 'TCS, Infosys, Bharti Airtel, Titan, Sun Pharma',
      ),
      FundModel(
        id: 'physical-digital-gold',
        name: '24K Certified Physical Gold / Gold ETF',
        ticker: 'GOLDBEES.NS',
        type: 'Ethical Commodity Store of Value',
        aumInrCr: 12500.0,
        nav: 68.20,
        cagr3yr: 17.5,
        cagr5yr: 16.2,
        expenseRatio: 0.50,
        shariahBoard: 'AAOIFI Shariah Standard No. 57 (Gold)',
        minSip: 100.0,
        risk: 'Low to Moderate',
        benchmark: 'Domestic Spot Gold Price (99.5% Purity)',
        description: '100% physical gold backed vault storage meeting AAOIFI Gold Standard rules: spot settlement with full constructive possession and no interest leverage.',
        topHoldings: '99.5% Fine Gold Bullion in Custodial Vaults',
      ),
    ];
  }

  // 10. Community Overview & 80G Charity Hub
  Future<Map<String, dynamic>> getCommunityOverview() async {
    final uri = Uri.parse('$_baseUrl/community/overview');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (_) {}

    return {
      'metrics': {
        'halal_wealth_tracked_inr': 48500000.0,
        'riba_avoided_inr': 3420000.0,
        'zakat_empowered_inr': 1210000.0,
        'active_investors_count': 1420,
      },
      'verified_causes': [
        {
          'id': 'edu-scholarship',
          'title': 'Bait-un-Nasr Educational Scholarship Fund',
          'category': 'Education (Zakat Eligible)',
          'reg_80g': 'AAATB1234F',
          'upi_id': 'scholarship@icici',
          'desc': '100% Zakat eligible: School & college fee sponsorship for meritorious underprivileged students.',
        },
        {
          'id': 'medical-dialysis',
          'title': 'Lifeline Dialysis & Cancer Medical Aid Trust',
          'category': 'Healthcare (Zakat Eligible)',
          'reg_80g': 'AABTL5678K',
          'upi_id': 'lifelinecare@hdfcbank',
          'desc': 'Life-saving dialysis and chemotherapy support for families below poverty line.',
        },
        {
          'id': 'clean-water-infra',
          'title': 'Sabeel Clean Water & Sanitation Foundation',
          'category': 'Public Utilities (Ideal for Interest Purification)',
          'reg_80g': 'AACCS9012M',
          'upi_id': 'sabeelwater@sbi',
          'desc': 'Borewells, water coolers, and public filtration plants—perfect for non-reward dividend interest purification.',
        },
      ],
    };
  }

  // 11. Corporate Actions Radar & IPOs
  Future<Map<String, dynamic>> getRadarEvents() async {
    final uri = Uri.parse('$_baseUrl/radar/events');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (_) {}

    return {
      'ex_dividends': [
        {
          'ticker': 'TCS.NS',
          'company': 'Tata Consultancy Services',
          'dividend_amount': 28.0,
          'purification_ratio': 0.0058,
          'ex_date': '2026-10-18',
          'record_date': '2026-10-19',
          'status': 'ACTIVE',
        },
        {
          'ticker': 'INFY.NS',
          'company': 'Infosys Limited',
          'dividend_amount': 18.5,
          'purification_ratio': 0.0048,
          'ex_date': '2026-10-25',
          'record_date': '2026-10-27',
          'status': 'UPCOMING',
        },
      ],
      'compliance_drift': [
        {
          'ticker': 'BHARTIARTL.NS',
          'company': 'Bharti Airtel',
          'current_debt_ratio': 31.8,
          'threshold': 33.0,
          'drift_direction': 'INCREASING',
          'warning': 'Approaching 33% debt threshold. High monitoring recommended.',
        },
      ],
    };
  }

  // Fallback fixtures for offline / resilience
  List<StockSummary> getFallbackStocks() {
    return [
      StockSummary(
        ticker: 'TCS.NS',
        symbol: 'TCS',
        isin: 'INE467B01029',
        companyName: 'Tata Consultancy Services Ltd',
        sector: 'Information Technology',
        industry: 'IT Services & Consulting',
        currentPrice: 3840.50,
        marketCap: 1390450.0,
        avg36mMarketCap: 1320000.0,
        aaoifiStatus: ComplianceStatus.compliant,
        tasisStatus: ComplianceStatus.compliant,
        purificationRatio: 0.0052,
        isNifty50: true,
      ),
      StockSummary(
        ticker: 'INFY.NS',
        symbol: 'INFY',
        isin: 'INE009A01021',
        companyName: 'Infosys Limited',
        sector: 'Information Technology',
        industry: 'IT Services & Consulting',
        currentPrice: 1540.20,
        marketCap: 640320.0,
        avg36mMarketCap: 610000.0,
        aaoifiStatus: ComplianceStatus.compliant,
        tasisStatus: ComplianceStatus.compliant,
        purificationRatio: 0.0048,
        isNifty50: true,
      ),
      StockSummary(
        ticker: 'HINDUNILVR.NS',
        symbol: 'HINDUNILVR',
        isin: 'INE030A01027',
        companyName: 'Hindustan Unilever Ltd',
        sector: 'Consumer Goods',
        industry: 'FMCG',
        currentPrice: 2420.00,
        marketCap: 568900.0,
        avg36mMarketCap: 580000.0,
        aaoifiStatus: ComplianceStatus.compliant,
        tasisStatus: ComplianceStatus.compliant,
        purificationRatio: 0.0035,
        isNifty50: true,
      ),
      StockSummary(
        ticker: 'TATAPOWER.NS',
        symbol: 'TATAPOWER',
        isin: 'INE245A01021',
        companyName: 'Tata Power Company Ltd',
        sector: 'Utilities',
        industry: 'Electric Utilities',
        currentPrice: 395.40,
        marketCap: 126340.0,
        avg36mMarketCap: 95000.0,
        aaoifiStatus: ComplianceStatus.compliant,
        tasisStatus: ComplianceStatus.compliant,
        purificationRatio: 0.0080,
        isNifty50: false,
      ),
      StockSummary(
        ticker: 'HDFCBANK.NS',
        symbol: 'HDFCBANK',
        isin: 'INE040A01034',
        companyName: 'HDFC Bank Ltd',
        sector: 'Financial Services',
        industry: 'Commercial Banking',
        currentPrice: 1650.00,
        marketCap: 1250000.0,
        avg36mMarketCap: 1100000.0,
        aaoifiStatus: ComplianceStatus.nonCompliant,
        tasisStatus: ComplianceStatus.nonCompliant,
        purificationRatio: 1.0,
        isNifty50: true,
      ),
    ];
  }

  List<BasketModel> getFallbackBaskets() {
    return [
      BasketModel(
        id: 'halal-tech-giants',
        name: 'Halal Tech Giants',
        thesis: 'World-leading Indian IT enterprises with zero net debt, export earnings, and superior ROE.',
        category: 'Information Technology',
        constituentCount: 5,
        expectedCagr: 0.148,
        expectedSharpe: 1.12,
        maxDrawdown: -0.165,
        annualizedVolatility: 0.182,
        weightedPurificationRatio: 0.0051,
        minimumInvestment: 5000.0,
        constituents: [
          BasketConstituentModel(ticker: 'TCS.NS', symbol: 'TCS', companyName: 'Tata Consultancy Services', weight: 0.25, currentPrice: 3840.50),
          BasketConstituentModel(ticker: 'INFY.NS', symbol: 'INFY', companyName: 'Infosys Ltd', weight: 0.25, currentPrice: 1540.20),
          BasketConstituentModel(ticker: 'HCLTECH.NS', symbol: 'HCLTECH', companyName: 'HCL Technologies', weight: 0.20, currentPrice: 1420.00),
          BasketConstituentModel(ticker: 'TECHM.NS', symbol: 'TECHM', companyName: 'Tech Mahindra Ltd', weight: 0.15, currentPrice: 1310.00),
          BasketConstituentModel(ticker: 'LTIM.NS', symbol: 'LTIM', companyName: 'LTIMindtree Ltd', weight: 0.15, currentPrice: 5120.00),
        ],
      ),
      BasketModel(
        id: 'shariah-high-growth-champions',
        name: 'Shariah High-Growth Champions',
        thesis: 'High-growth Indian mid-cap leaders in specialty chemicals, engineering design, and automotive tech.',
        category: 'Midcap Growth',
        constituentCount: 5,
        expectedCagr: 0.264,
        expectedSharpe: 1.45,
        maxDrawdown: -0.210,
        annualizedVolatility: 0.225,
        weightedPurificationRatio: 0.0065,
        minimumInvestment: 5000.0,
        constituents: [
          BasketConstituentModel(ticker: 'PERSISTENT.NS', symbol: 'PERSISTENT', companyName: 'Persistent Systems', weight: 0.20, currentPrice: 4890.00),
          BasketConstituentModel(ticker: 'TATAELXSI.NS', symbol: 'TATAELXSI', companyName: 'Tata Elxsi Ltd', weight: 0.20, currentPrice: 7200.00),
          BasketConstituentModel(ticker: 'DEEPAKNTR.NS', symbol: 'DEEPAKNTR', companyName: 'Deepak Nitrite Ltd', weight: 0.20, currentPrice: 2150.00),
          BasketConstituentModel(ticker: 'PIDILITIND.NS', symbol: 'PIDILITIND', companyName: 'Pidilite Industries', weight: 0.20, currentPrice: 2950.00),
          BasketConstituentModel(ticker: 'MARICO.NS', symbol: 'MARICO', companyName: 'Marico Ltd', weight: 0.20, currentPrice: 620.00),
        ],
      ),
      BasketModel(
        id: 'green-ethical-infrastructure',
        name: 'Green & Ethical Infrastructure',
        thesis: "Enterprises accelerating India's clean energy, electric transmission, and environmental sustainability.",
        category: 'Clean Energy & Infra',
        constituentCount: 5,
        expectedCagr: 0.312,
        expectedSharpe: 1.60,
        maxDrawdown: -0.195,
        annualizedVolatility: 0.240,
        weightedPurificationRatio: 0.0078,
        minimumInvestment: 5000.0,
        constituents: [
          BasketConstituentModel(ticker: 'TATAPOWER.NS', symbol: 'TATAPOWER', companyName: 'Tata Power Company', weight: 0.25, currentPrice: 395.40),
          BasketConstituentModel(ticker: 'THERMAX.NS', symbol: 'THERMAX', companyName: 'Thermax Ltd', weight: 0.20, currentPrice: 4850.00),
          BasketConstituentModel(ticker: 'SIEMENS.NS', symbol: 'SIEMENS', companyName: 'Siemens India Ltd', weight: 0.20, currentPrice: 5600.00),
          BasketConstituentModel(ticker: 'ABB.NS', symbol: 'ABB', companyName: 'ABB India Ltd', weight: 0.20, currentPrice: 6100.00),
          BasketConstituentModel(ticker: 'KEC.NS', symbol: 'KEC', companyName: 'KEC International Ltd', weight: 0.15, currentPrice: 820.00),
        ],
      ),
      BasketModel(
        id: 'nifty-shariah-25',
        name: 'NIFTY Shariah 25 Index Basket',
        thesis: 'Core wealth compounding mirroring the top 25 Shariah-compliant large-cap leaders in NIFTY 100.',
        category: 'Large Cap Core',
        constituentCount: 6,
        expectedCagr: 0.165,
        expectedSharpe: 1.05,
        maxDrawdown: -0.175,
        annualizedVolatility: 0.168,
        weightedPurificationRatio: 0.0042,
        minimumInvestment: 5000.0,
        constituents: [
          BasketConstituentModel(ticker: 'TCS.NS', symbol: 'TCS', companyName: 'Tata Consultancy Services', weight: 0.08, currentPrice: 3840.50),
          BasketConstituentModel(ticker: 'INFY.NS', symbol: 'INFY', companyName: 'Infosys Ltd', weight: 0.08, currentPrice: 1540.20),
          BasketConstituentModel(ticker: 'HINDUNILVR.NS', symbol: 'HINDUNILVR', companyName: 'Hindustan Unilever Ltd', weight: 0.07, currentPrice: 2420.00),
          BasketConstituentModel(ticker: 'SUNPHARMA.NS', symbol: 'SUNPHARMA', companyName: 'Sun Pharma Industries', weight: 0.06, currentPrice: 1580.00),
          BasketConstituentModel(ticker: 'CIPLA.NS', symbol: 'CIPLA', companyName: 'Cipla Ltd', weight: 0.05, currentPrice: 1450.00),
          BasketConstituentModel(ticker: 'DRREDDY.NS', symbol: 'DRREDDY', companyName: "Dr. Reddy's Laboratories", weight: 0.04, currentPrice: 6200.00),
        ],
      ),
    ];
  }
}
