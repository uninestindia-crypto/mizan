class BasketConstituentModel {
  final String ticker;
  final String symbol;
  final String companyName;
  final double weight;
  final double currentPrice;

  BasketConstituentModel({
    required this.ticker,
    required this.symbol,
    required this.companyName,
    required this.weight,
    required this.currentPrice,
  });

  factory BasketConstituentModel.fromJson(Map<String, dynamic> json) {
    return BasketConstituentModel(
      ticker: json['ticker'] ?? '',
      symbol: json['symbol'] ?? '',
      companyName: json['company_name'] ?? json['symbol'] ?? '',
      weight: (json['weight'] as num?)?.toDouble() ?? 0.0,
      currentPrice: (json['current_price'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'symbol': symbol,
    'company_name': companyName,
    'weight': weight,
    'current_price': currentPrice,
  };
}

class BasketModel {
  final String id;
  final String name;
  final String thesis;
  final String category;
  final int constituentCount;
  final double expectedCagr;
  final double expectedSharpe;
  final double maxDrawdown;
  final double annualizedVolatility;
  final double weightedPurificationRatio;
  final double minimumInvestment;
  final List<BasketConstituentModel> constituents;

  BasketModel({
    required this.id,
    required this.name,
    required this.thesis,
    required this.category,
    required this.constituentCount,
    required this.expectedCagr,
    required this.expectedSharpe,
    required this.maxDrawdown,
    required this.annualizedVolatility,
    required this.weightedPurificationRatio,
    required this.minimumInvestment,
    required this.constituents,
  });

  factory BasketModel.fromJson(Map<String, dynamic> json) {
    return BasketModel(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      thesis: json['thesis'] ?? '',
      category: json['category'] ?? '',
      constituentCount: json['constituent_count'] ?? 0,
      expectedCagr: (json['expected_cagr'] as num?)?.toDouble() ?? 0.0,
      expectedSharpe: (json['expected_sharpe'] as num?)?.toDouble() ?? 0.0,
      maxDrawdown: (json['max_drawdown'] as num?)?.toDouble() ?? 0.0,
      annualizedVolatility: (json['annualized_volatility'] as num?)?.toDouble() ?? 0.0,
      weightedPurificationRatio: (json['weighted_purification_ratio'] as num?)?.toDouble() ?? 0.0,
      minimumInvestment: (json['minimum_investment'] as num?)?.toDouble() ?? 5000.0,
      constituents: (json['constituents'] as List<dynamic>? ?? [])
          .map((e) => BasketConstituentModel.fromJson(e))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'thesis': thesis,
    'category': category,
    'constituent_count': constituentCount,
    'expected_cagr': expectedCagr,
    'expected_sharpe': expectedSharpe,
    'max_drawdown': maxDrawdown,
    'annualized_volatility': annualizedVolatility,
    'weighted_purification_ratio': weightedPurificationRatio,
    'minimum_investment': minimumInvestment,
    'constituents': constituents.map((e) => e.toJson()).toList(),
  };
}

class BrokerOrderModel {
  final String symbol;
  final String ticker;
  final int shares;
  final double price;
  final double allocationAmount;
  final String orderLine;

  BrokerOrderModel({
    required this.symbol,
    required this.ticker,
    required this.shares,
    required this.price,
    required this.allocationAmount,
    required this.orderLine,
  });

  factory BrokerOrderModel.fromJson(Map<String, dynamic> json) {
    return BrokerOrderModel(
      symbol: json['symbol'] ?? '',
      ticker: json['ticker'] ?? '',
      shares: json['shares'] ?? 0,
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      allocationAmount: (json['allocation_amount'] as num?)?.toDouble() ?? 0.0,
      orderLine: json['order_line'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'symbol': symbol,
    'ticker': ticker,
    'shares': shares,
    'price': price,
    'allocation_amount': allocationAmount,
    'order_line': orderLine,
  };
}

class BasketExportResult {
  final String basketId;
  final String basketName;
  final String broker;
  final double targetCapital;
  final double totalAllocatedCapital;
  final double residualCash;
  final int orderCount;
  final List<BrokerOrderModel> orders;
  final String csvContent;
  final String clipboardPayload;

  BasketExportResult({
    required this.basketId,
    required this.basketName,
    required this.broker,
    required this.targetCapital,
    required this.totalAllocatedCapital,
    required this.residualCash,
    required this.orderCount,
    required this.orders,
    required this.csvContent,
    required this.clipboardPayload,
  });

  factory BasketExportResult.fromJson(Map<String, dynamic> json) {
    return BasketExportResult(
      basketId: json['basket_id'] ?? '',
      basketName: json['basket_name'] ?? '',
      broker: json['broker'] ?? '',
      targetCapital: (json['target_capital'] as num?)?.toDouble() ?? 0.0,
      totalAllocatedCapital: (json['total_allocated_capital'] as num?)?.toDouble() ?? 0.0,
      residualCash: (json['residual_cash'] as num?)?.toDouble() ?? 0.0,
      orderCount: json['order_count'] ?? 0,
      orders: (json['orders'] as List<dynamic>? ?? [])
          .map((e) => BrokerOrderModel.fromJson(e))
          .toList(),
      csvContent: json['csv_content'] ?? '',
      clipboardPayload: json['clipboard_payload'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'basket_id': basketId,
    'basket_name': basketName,
    'broker': broker,
    'target_capital': targetCapital,
    'total_allocated_capital': totalAllocatedCapital,
    'residual_cash': residualCash,
    'order_count': orderCount,
    'orders': orders.map((e) => e.toJson()).toList(),
    'csv_content': csvContent,
    'clipboard_payload': clipboardPayload,
  };
}

/// Indian Statutory Tax & Brokerage Calculation DTO
class TaxCalculationResponse {
  final double investmentAmount;
  final String broker;
  final String exchange;
  final double brokerage;
  final double sttCtt;
  final double exchangeCharges;
  final double sebiCharges;
  final double stampDuty;
  final double gst;
  final double totalStatutoryCharges;
  final double estimatedDividendPurificationRatio;
  final double netEffectiveCost;
  final double effectiveTaxRatePct;

  TaxCalculationResponse({
    required this.investmentAmount,
    required this.broker,
    required this.exchange,
    required this.brokerage,
    required this.sttCtt,
    required this.exchangeCharges,
    required this.sebiCharges,
    required this.stampDuty,
    required this.gst,
    required this.totalStatutoryCharges,
    required this.estimatedDividendPurificationRatio,
    required this.netEffectiveCost,
    required this.effectiveTaxRatePct,
  });

  factory TaxCalculationResponse.fromJson(Map<String, dynamic> json) {
    return TaxCalculationResponse(
      investmentAmount: (json['investment_amount'] as num?)?.toDouble() ?? 0.0,
      broker: json['broker'] ?? 'Zerodha',
      exchange: json['exchange'] ?? 'NSE',
      brokerage: (json['brokerage'] as num?)?.toDouble() ?? 0.0,
      sttCtt: (json['stt_ctt'] as num?)?.toDouble() ?? 0.0,
      exchangeCharges: (json['exchange_charges'] as num?)?.toDouble() ?? 0.0,
      sebiCharges: (json['sebi_charges'] as num?)?.toDouble() ?? 0.0,
      stampDuty: (json['stamp_duty'] as num?)?.toDouble() ?? 0.0,
      gst: (json['gst'] as num?)?.toDouble() ?? 0.0,
      totalStatutoryCharges: (json['total_statutory_charges'] as num?)?.toDouble() ?? 0.0,
      estimatedDividendPurificationRatio: (json['estimated_dividend_purification_ratio'] as num?)?.toDouble() ?? 0.0042,
      netEffectiveCost: (json['net_effective_cost'] as num?)?.toDouble() ?? 0.0,
      effectiveTaxRatePct: (json['effective_tax_rate_pct'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'investment_amount': investmentAmount,
    'broker': broker,
    'exchange': exchange,
    'brokerage': brokerage,
    'stt_ctt': sttCtt,
    'exchange_charges': exchangeCharges,
    'sebi_charges': sebiCharges,
    'stamp_duty': stampDuty,
    'gst': gst,
    'total_statutory_charges': totalStatutoryCharges,
    'estimated_dividend_purification_ratio': estimatedDividendPurificationRatio,
    'net_effective_cost': netEffectiveCost,
    'effective_tax_rate_pct': effectiveTaxRatePct,
  };
}

/// Curated Indian Shariah Mutual Funds, ETFs and 24K Gold DTO
class FundModel {
  final String id;
  final String name;
  final String type;
  final String? ticker;
  final double aumInrCr;
  final double nav;
  final double cagr3yr;
  final double cagr5yr;
  final double expenseRatio;
  final String shariahBoard;
  final double minSip;
  final String risk;
  final String benchmark;
  final String description;
  final String topHoldings;

  FundModel({
    required this.id,
    required this.name,
    required this.type,
    this.ticker,
    required this.aumInrCr,
    required this.nav,
    required this.cagr3yr,
    required this.cagr5yr,
    required this.expenseRatio,
    required this.shariahBoard,
    required this.minSip,
    required this.risk,
    required this.benchmark,
    required this.description,
    required this.topHoldings,
  });

  factory FundModel.fromJson(Map<String, dynamic> json) {
    return FundModel(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      type: json['type'] ?? '',
      ticker: json['ticker'],
      aumInrCr: (json['aum_inr_cr'] as num?)?.toDouble() ?? 0.0,
      nav: (json['nav'] as num?)?.toDouble() ?? 0.0,
      cagr3yr: (json['cagr_3yr'] as num?)?.toDouble() ?? 0.0,
      cagr5yr: (json['cagr_5yr'] as num?)?.toDouble() ?? 0.0,
      expenseRatio: (json['expense_ratio'] as num?)?.toDouble() ?? 0.0,
      shariahBoard: json['shariah_board'] ?? '',
      minSip: (json['min_sip'] as num?)?.toDouble() ?? 500.0,
      risk: json['risk'] ?? 'Moderate',
      benchmark: json['benchmark'] ?? '',
      description: json['description'] ?? '',
      topHoldings: json['top_holdings'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'type': type,
    'ticker': ticker,
    'aum_inr_cr': aumInrCr,
    'nav': nav,
    'cagr_3yr': cagr3yr,
    'cagr_5yr': cagr5yr,
    'expense_ratio': expenseRatio,
    'shariah_board': shariahBoard,
    'min_sip': minSip,
    'risk': risk,
    'benchmark': benchmark,
    'description': description,
    'top_holdings': topHoldings,
  };
}
