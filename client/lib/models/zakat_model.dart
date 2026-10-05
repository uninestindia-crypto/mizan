class ZakatHoldingBreakdownModel {
  final String ticker;
  final String? symbol;
  final String? companyName;
  final int shares;
  final double? currentPrice;
  final double? marketValue;
  final double znwaPerShare;
  final double zakatableAmount;
  final String methodApplied;

  ZakatHoldingBreakdownModel({
    required this.ticker,
    this.symbol,
    this.companyName,
    required this.shares,
    this.currentPrice,
    this.marketValue,
    required this.znwaPerShare,
    required this.zakatableAmount,
    required this.methodApplied,
  });

  factory ZakatHoldingBreakdownModel.fromJson(Map<String, dynamic> json) {
    return ZakatHoldingBreakdownModel(
      ticker: json['ticker'] ?? '',
      symbol: json['symbol'],
      companyName: json['company_name'],
      shares: json['shares'] ?? 0,
      currentPrice: (json['current_price'] as num?)?.toDouble(),
      marketValue: (json['market_value'] as num?)?.toDouble(),
      znwaPerShare: (json['znwa_per_share'] as num?)?.toDouble() ?? 0.0,
      zakatableAmount: (json['zakatable_amount'] as num?)?.toDouble() ?? 0.0,
      methodApplied: json['method_applied'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'symbol': symbol,
    'company_name': companyName,
    'shares': shares,
    'current_price': currentPrice,
    'market_value': marketValue,
    'znwa_per_share': znwaPerShare,
    'zakatable_amount': zakatableAmount,
    'method_applied': methodApplied,
  };
}

class ZakatCalculationResult {
  final String method;
  final String calendar;
  final double rate;
  final double ratePct;
  final double zakatableBase;
  final double portfolioValue;
  final double cashBalance;
  final double nisabThreshold;
  final bool isObligatory;
  final double zakatDue;
  final List<ZakatHoldingBreakdownModel> breakdown;
  final String methodNotes;

  ZakatCalculationResult({
    required this.method,
    required this.calendar,
    required this.rate,
    required this.ratePct,
    required this.zakatableBase,
    required this.portfolioValue,
    required this.cashBalance,
    required this.nisabThreshold,
    required this.isObligatory,
    required this.zakatDue,
    required this.breakdown,
    required this.methodNotes,
  });

  factory ZakatCalculationResult.fromJson(Map<String, dynamic> json) {
    return ZakatCalculationResult(
      method: json['method'] ?? 'active',
      calendar: json['calendar'] ?? 'lunar',
      rate: (json['rate'] as num?)?.toDouble() ?? 0.025,
      ratePct: (json['rate_pct'] as num?)?.toDouble() ?? 2.5,
      zakatableBase: (json['zakatable_base'] as num?)?.toDouble() ?? 0.0,
      portfolioValue: (json['portfolio_value'] as num?)?.toDouble() ?? 0.0,
      cashBalance: (json['cash_balance'] as num?)?.toDouble() ?? 0.0,
      nisabThreshold: (json['nisab_threshold'] as num?)?.toDouble() ?? 53550.0,
      isObligatory: json['is_obligatory'] ?? false,
      zakatDue: (json['zakat_due'] as num?)?.toDouble() ?? 0.0,
      breakdown: (json['breakdown'] as List<dynamic>? ?? [])
          .map((e) => ZakatHoldingBreakdownModel.fromJson(e))
          .toList(),
      methodNotes: json['method_notes'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'method': method,
    'calendar': calendar,
    'rate': rate,
    'rate_pct': ratePct,
    'zakatable_base': zakatableBase,
    'portfolio_value': portfolioValue,
    'cash_balance': cashBalance,
    'nisab_threshold': nisabThreshold,
    'is_obligatory': isObligatory,
    'zakat_due': zakatDue,
    'breakdown': breakdown.map((e) => e.toJson()).toList(),
    'method_notes': methodNotes,
  };
}
