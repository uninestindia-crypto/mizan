import 'stock_model.dart';

class RatioMeterData {
  final String metricName;
  final double actualValue;
  final double actualPct;
  final double thresholdPct;
  final bool isCompliant;
  final bool isWarning;
  final String numeratorLabel;
  final double numeratorValueInrCr;
  final String denominatorLabel;
  final double denominatorValueInrCr;
  final String? noteReference;

  RatioMeterData({
    required this.metricName,
    required this.actualValue,
    required this.actualPct,
    required this.thresholdPct,
    required this.isCompliant,
    required this.isWarning,
    required this.numeratorLabel,
    required this.numeratorValueInrCr,
    required this.denominatorLabel,
    required this.denominatorValueInrCr,
    this.noteReference,
  });

  factory RatioMeterData.fromJson(Map<String, dynamic> json) {
    return RatioMeterData(
      metricName: json['metric_name'] ?? '',
      actualValue: (json['actual_value'] as num?)?.toDouble() ?? 0.0,
      actualPct: (json['actual_pct'] as num?)?.toDouble() ?? 0.0,
      thresholdPct: (json['threshold_pct'] as num?)?.toDouble() ?? 33.0,
      isCompliant: json['is_compliant'] ?? false,
      isWarning: json['is_warning'] ?? false,
      numeratorLabel: json['numerator_label'] ?? '',
      numeratorValueInrCr: (json['numerator_value_inr_cr'] as num?)?.toDouble() ?? 0.0,
      denominatorLabel: json['denominator_label'] ?? '',
      denominatorValueInrCr: (json['denominator_value_inr_cr'] as num?)?.toDouble() ?? 0.0,
      noteReference: json['note_reference'],
    );
  }

  Map<String, dynamic> toJson() => {
    'metric_name': metricName,
    'actual_value': actualValue,
    'actual_pct': actualPct,
    'threshold_pct': thresholdPct,
    'is_compliant': isCompliant,
    'is_warning': isWarning,
    'numerator_label': numeratorLabel,
    'numerator_value_inr_cr': numeratorValueInrCr,
    'denominator_label': denominatorLabel,
    'denominator_value_inr_cr': denominatorValueInrCr,
    'note_reference': noteReference,
  };
}

class StandardEvaluationData {
  final String standard;
  final ComplianceStatus status;
  final bool isCompliant;
  final RatioMeterData debtRatio;
  final RatioMeterData cashRatio;
  final RatioMeterData receivablesRatio;
  final RatioMeterData impermissibleIncomeRatio;
  final String summary;

  StandardEvaluationData({
    required this.standard,
    required this.status,
    required this.isCompliant,
    required this.debtRatio,
    required this.cashRatio,
    required this.receivablesRatio,
    required this.impermissibleIncomeRatio,
    required this.summary,
  });

  factory StandardEvaluationData.fromJson(Map<String, dynamic> json) {
    return StandardEvaluationData(
      standard: json['standard'] ?? 'AAOIFI',
      status: ComplianceStatus.fromString(json['status'] ?? 'NON_COMPLIANT'),
      isCompliant: json['is_compliant'] ?? false,
      debtRatio: RatioMeterData.fromJson(json['debt_ratio'] ?? {}),
      cashRatio: RatioMeterData.fromJson(json['cash_ratio'] ?? {}),
      receivablesRatio: RatioMeterData.fromJson(json['receivables_ratio'] ?? {}),
      impermissibleIncomeRatio: RatioMeterData.fromJson(json['impermissible_income_ratio'] ?? {}),
      summary: json['summary'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'standard': standard,
    'status': status.toDisplayString(),
    'is_compliant': isCompliant,
    'debt_ratio': debtRatio.toJson(),
    'cash_ratio': cashRatio.toJson(),
    'receivables_ratio': receivablesRatio.toJson(),
    'impermissible_income_ratio': impermissibleIncomeRatio.toJson(),
    'summary': summary,
  };
}

class AuditEvidenceLineData {
  final String lineItem;
  final double valueInrCr;
  final String? noteRef;
  final String? filingSchedule;
  final String verificationStatus;

  AuditEvidenceLineData({
    required this.lineItem,
    required this.valueInrCr,
    this.noteRef,
    this.filingSchedule,
    this.verificationStatus = 'VERIFIED',
  });

  factory AuditEvidenceLineData.fromJson(Map<String, dynamic> json) {
    return AuditEvidenceLineData(
      lineItem: json['line_item'] ?? '',
      valueInrCr: (json['value_inr_cr'] as num?)?.toDouble() ?? 0.0,
      noteRef: json['note_ref'],
      filingSchedule: json['filing_schedule'],
      verificationStatus: json['verification_status'] ?? 'VERIFIED',
    );
  }

  Map<String, dynamic> toJson() => {
    'line_item': lineItem,
    'value_inr_cr': valueInrCr,
    'note_ref': noteRef,
    'filing_schedule': filingSchedule,
    'verification_status': verificationStatus,
  };
}

class ShariahAuditDetail {
  final String ticker;
  final String symbol;
  final String companyName;
  final String isin;
  final String sector;
  final bool sectorCompliant;
  final String? sectorFailureReason;
  final StandardEvaluationData aaoifiEvaluation;
  final StandardEvaluationData tasisEvaluation;
  final bool divergenceNoted;
  final String? divergenceExplanation;
  final double purificationRatioPct;
  final double zakatableAssetsPerShareInr;
  final List<AuditEvidenceLineData> balanceSheetLines;
  final List<AuditEvidenceLineData> incomeStatementLines;

  ShariahAuditDetail({
    required this.ticker,
    required this.symbol,
    required this.companyName,
    required this.isin,
    required this.sector,
    required this.sectorCompliant,
    this.sectorFailureReason,
    required this.aaoifiEvaluation,
    required this.tasisEvaluation,
    required this.divergenceNoted,
    this.divergenceExplanation,
    required this.purificationRatioPct,
    required this.zakatableAssetsPerShareInr,
    required this.balanceSheetLines,
    required this.incomeStatementLines,
  });

  factory ShariahAuditDetail.fromJson(Map<String, dynamic> json) {
    return ShariahAuditDetail(
      ticker: json['ticker'] ?? '',
      symbol: json['symbol'] ?? '',
      companyName: json['company_name'] ?? '',
      isin: json['isin'] ?? '',
      sector: json['sector'] ?? '',
      sectorCompliant: json['sector_compliant'] ?? true,
      sectorFailureReason: json['sector_failure_reason'],
      aaoifiEvaluation: StandardEvaluationData.fromJson(json['aaoifi_evaluation'] ?? {}),
      tasisEvaluation: StandardEvaluationData.fromJson(json['tasis_evaluation'] ?? {}),
      divergenceNoted: json['divergence_noted'] ?? false,
      divergenceExplanation: json['divergence_explanation'],
      purificationRatioPct: (json['purification_ratio_pct'] as num?)?.toDouble() ?? 0.0,
      zakatableAssetsPerShareInr: (json['zakatable_assets_per_share_inr'] as num?)?.toDouble() ?? 0.0,
      balanceSheetLines: (json['balance_sheet_lines'] as List<dynamic>? ?? [])
          .map((e) => AuditEvidenceLineData.fromJson(e))
          .toList(),
      incomeStatementLines: (json['income_statement_lines'] as List<dynamic>? ?? [])
          .map((e) => AuditEvidenceLineData.fromJson(e))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'symbol': symbol,
    'company_name': companyName,
    'isin': isin,
    'sector': sector,
    'sector_compliant': sectorCompliant,
    'sector_failure_reason': sectorFailureReason,
    'aaoifi_evaluation': aaoifiEvaluation.toJson(),
    'tasis_evaluation': tasisEvaluation.toJson(),
    'divergence_noted': divergenceNoted,
    'divergence_explanation': divergenceExplanation,
    'purification_ratio_pct': purificationRatioPct,
    'zakatable_assets_per_share_inr': zakatableAssetsPerShareInr,
    'balance_sheet_lines': balanceSheetLines.map((e) => e.toJson()).toList(),
    'income_statement_lines': incomeStatementLines.map((e) => e.toJson()).toList(),
  };
}
