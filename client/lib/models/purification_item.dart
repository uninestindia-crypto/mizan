class PurificationCalculateResult {
  final String ticker;
  final int sharesHeld;
  final double dividendPerShare;
  final double grossDividend;
  final double purificationRatio;
  final double purificationRatioPct;
  final double purificationPayable;
  final double netPermissibleDividend;

  String get companyName => ticker;

  PurificationCalculateResult({
    required this.ticker,
    required this.sharesHeld,
    required this.dividendPerShare,
    required this.grossDividend,
    required this.purificationRatio,
    required this.purificationRatioPct,
    required this.purificationPayable,
    required this.netPermissibleDividend,
  });

  factory PurificationCalculateResult.fromJson(Map<String, dynamic> json) {
    return PurificationCalculateResult(
      ticker: json['ticker'] ?? '',
      sharesHeld: json['shares_held'] ?? 1,
      dividendPerShare: (json['dividend_per_share'] as num?)?.toDouble() ?? 0.0,
      grossDividend: (json['gross_dividend'] as num?)?.toDouble() ?? 0.0,
      purificationRatio: (json['purification_ratio'] as num?)?.toDouble() ?? 0.0,
      purificationRatioPct: (json['purification_ratio_pct'] as num?)?.toDouble() ?? 0.0,
      purificationPayable: (json['purification_payable'] as num?)?.toDouble() ?? 0.0,
      netPermissibleDividend: (json['net_permissible_dividend'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'ticker': ticker,
    'shares_held': sharesHeld,
    'dividend_per_share': dividendPerShare,
    'gross_dividend': grossDividend,
    'purification_ratio': purificationRatio,
    'purification_ratio_pct': purificationRatioPct,
    'purification_payable': purificationPayable,
    'net_permissible_dividend': netPermissibleDividend,
  };
}

class PurificationLedgerEntryModel {
  final int id;
  final String entryUuid;
  final String ticker;
  final String companyName;
  final int sharesHeld;
  final double dpsInr;
  final double grossDividend;
  final double purificationRatio;
  final double purificationPayable;
  final double netPermissibleDividend;
  final String? charityName;
  final String disbursementStatus;
  final String prevEntryHash;
  final String entryHash;
  final String timestamp;

  PurificationLedgerEntryModel({
    required this.id,
    required this.entryUuid,
    required this.ticker,
    required this.companyName,
    required this.sharesHeld,
    required this.dpsInr,
    required this.grossDividend,
    required this.purificationRatio,
    required this.purificationPayable,
    required this.netPermissibleDividend,
    this.charityName,
    required this.disbursementStatus,
    required this.prevEntryHash,
    required this.entryHash,
    required this.timestamp,
  });

  factory PurificationLedgerEntryModel.fromJson(Map<String, dynamic> json) {
    return PurificationLedgerEntryModel(
      id: json['id'] ?? 0,
      entryUuid: json['entry_uuid'] ?? '',
      ticker: json['ticker'] ?? '',
      companyName: json['company_name'] ?? json['ticker'] ?? '',
      sharesHeld: json['shares_held'] ?? 1,
      dpsInr: (json['dps_inr'] as num?)?.toDouble() ?? 0.0,
      grossDividend: (json['gross_dividend'] as num?)?.toDouble() ?? 0.0,
      purificationRatio: (json['purification_ratio'] as num?)?.toDouble() ?? 0.0,
      purificationPayable: (json['purification_payable'] as num?)?.toDouble() ?? 0.0,
      netPermissibleDividend: (json['net_permissible_dividend'] as num?)?.toDouble() ?? 0.0,
      charityName: json['charity_name'],
      disbursementStatus: json['disbursement_status'] ?? 'UNPURIFIED',
      prevEntryHash: json['prev_entry_hash'] ?? '0' * 64,
      entryHash: json['entry_hash'] ?? '',
      timestamp: json['timestamp'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'entry_uuid': entryUuid,
    'ticker': ticker,
    'company_name': companyName,
    'shares_held': sharesHeld,
    'dps_inr': dpsInr,
    'gross_dividend': grossDividend,
    'purification_ratio': purificationRatio,
    'purification_payable': purificationPayable,
    'net_permissible_dividend': netPermissibleDividend,
    'charity_name': charityName,
    'disbursement_status': disbursementStatus,
    'prev_entry_hash': prevEntryHash,
    'entry_hash': entryHash,
    'timestamp': timestamp,
  };
}

/// Cryptographically verifiable printable 80G tax & charity voucher receipt
class PurificationReceipt {
  final String receiptId;
  final String entryUuid;
  final String ticker;
  final String companyName;
  final double grossDividend;
  final double purificationAmount;
  final String charityName;
  final String charity80gReg;
  final String entryHash;
  final String timestamp;

  PurificationReceipt({
    required this.receiptId,
    required this.entryUuid,
    required this.ticker,
    required this.companyName,
    required this.grossDividend,
    required this.purificationAmount,
    required this.charityName,
    required this.charity80gReg,
    required this.entryHash,
    required this.timestamp,
  });

  factory PurificationReceipt.fromJson(Map<String, dynamic> json) {
    return PurificationReceipt(
      receiptId: json['receipt_id'] ?? '',
      entryUuid: json['entry_uuid'] ?? '',
      ticker: json['ticker'] ?? '',
      companyName: json['company_name'] ?? '',
      grossDividend: (json['gross_dividend'] as num?)?.toDouble() ?? 0.0,
      purificationAmount: (json['purification_amount'] as num?)?.toDouble() ?? 0.0,
      charityName: json['charity_name'] ?? '',
      charity80gReg: json['charity_80g_reg'] ?? '',
      entryHash: json['entry_hash'] ?? '',
      timestamp: json['timestamp'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'receipt_id': receiptId,
    'entry_uuid': entryUuid,
    'ticker': ticker,
    'company_name': companyName,
    'gross_dividend': grossDividend,
    'purification_amount': purificationAmount,
    'charity_name': charityName,
    'charity_80g_reg': charity80gReg,
    'entry_hash': entryHash,
    'timestamp': timestamp,
  };
}
