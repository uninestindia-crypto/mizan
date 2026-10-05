enum ComplianceStatus {
  compliant,
  questionable,
  nonCompliant;

  static ComplianceStatus fromString(String val) {
    switch (val.toUpperCase()) {
      case 'COMPLIANT':
        return ComplianceStatus.compliant;
      case 'QUESTIONABLE':
        return ComplianceStatus.questionable;
      default:
        return ComplianceStatus.nonCompliant;
    }
  }

  String toDisplayString() {
    switch (this) {
      case ComplianceStatus.compliant:
        return 'COMPLIANT';
      case ComplianceStatus.questionable:
        return 'QUESTIONABLE';
      case ComplianceStatus.nonCompliant:
        return 'NON-COMPLIANT';
    }
  }
}

class StockSummary {
  final String ticker;
  final String symbol;
  final String isin;
  final String companyName;
  final String sector;
  final String industry;
  final double currentPrice;
  final double marketCap;
  final double avg36mMarketCap;
  final ComplianceStatus aaoifiStatus;
  final ComplianceStatus tasisStatus;
  final double purificationRatio;
  final bool isNifty50;

  StockSummary({
    required this.ticker,
    required this.symbol,
    required this.isin,
    required this.companyName,
    required this.sector,
    required this.industry,
    required this.currentPrice,
    required this.marketCap,
    required this.avg36mMarketCap,
    required this.aaoifiStatus,
    required this.tasisStatus,
    required this.purificationRatio,
    this.isNifty50 = false,
  });

  factory StockSummary.fromJson(Map<String, dynamic> json) {
    return StockSummary(
      ticker: json['ticker'] ?? '',
      symbol: json['symbol'] ?? '',
      isin: json['isin'] ?? '',
      companyName: json['company_name'] ?? '',
      sector: json['sector'] ?? '',
      industry: json['industry'] ?? '',
      currentPrice: (json['current_price'] as num?)?.toDouble() ?? 0.0,
      marketCap: (json['market_cap'] as num?)?.toDouble() ?? 0.0,
      avg36mMarketCap: (json['avg_36m_market_cap'] as num?)?.toDouble() ?? 0.0,
      aaoifiStatus: ComplianceStatus.fromString(json['aaoifi_status'] ?? 'NON_COMPLIANT'),
      tasisStatus: ComplianceStatus.fromString(json['tasis_status'] ?? 'NON_COMPLIANT'),
      purificationRatio: (json['purification_ratio'] as num?)?.toDouble() ?? 0.0,
      isNifty50: json['is_nifty_50'] == true || json['is_nifty_50'] == 1,
    );
  }

  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'symbol': symbol,
    'isin': isin,
    'company_name': companyName,
    'sector': sector,
    'industry': industry,
    'current_price': currentPrice,
    'market_cap': marketCap,
    'avg_36m_market_cap': avg36mMarketCap,
    'aaoifi_status': aaoifiStatus.toDisplayString(),
    'tasis_status': tasisStatus.toDisplayString(),
    'purification_ratio': purificationRatio,
    'is_nifty_50': isNifty50,
  };
}
