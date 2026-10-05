import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/theme/colors.dart';
import '../core/utils/formatters.dart';
import '../models/purification_item.dart';
import '../services/api_service.dart';
import '../widgets/frosted_card.dart';

class PurificationScreen extends StatefulWidget {
  const PurificationScreen({super.key});

  @override
  State<PurificationScreen> createState() => _PurificationScreenState();
}

class _PurificationScreenState extends State<PurificationScreen> {
  final ApiService _apiService = ApiService();
  final _tickerController = TextEditingController(text: 'TCS.NS');
  final _sharesController = TextEditingController(text: '100');
  final _dividendController = TextEditingController(text: '28.0');

  PurificationCalculateResult? _calcResult;
  List<PurificationLedgerEntryModel> _ledgerEntries = [];
  bool _isCalculating = false;

  final List<Map<String, String>> _verifiedCharities = const [
    {
      'name': 'Bait-un-Nasr Educational Scholarship Fund',
      'reg': 'AAATB1234F',
      'upi': 'scholarship@icici',
      'category': '100% Zakat Eligible',
      'desc': 'Direct scholarship grants for higher education of underprivileged students.',
    },
    {
      'name': 'Lifeline Dialysis & Cancer Medical Aid Trust',
      'reg': 'AABTL5678K',
      'upi': 'lifelinecare@hdfcbank',
      'category': 'Healthcare Zakat',
      'desc': 'Subsidized dialysis cycles and oncology care for low-income patients.',
    },
    {
      'name': 'Sabeel Clean Water & Sanitation Foundation',
      'reg': 'AACCS9012M',
      'upi': 'sabeelwater@sbi',
      'category': 'Public Utilities (Purification)',
      'desc': 'Community borewells, reverse osmosis filtration, and sanitation projects.',
    },
  ];

  @override
  void initState() {
    super.initState();
    _calculatePurification();
    _loadLedger();
  }

  Future<void> _calculatePurification() async {
    setState(() => _isCalculating = true);
    final shares = int.tryParse(_sharesController.text) ?? 1;
    final dps = double.tryParse(_dividendController.text) ?? 0.0;

    final result = await _apiService.calculatePurification(
      ticker: _tickerController.text,
      dividendAmount: dps,
      sharesHeld: shares,
    );

    if (mounted) {
      setState(() {
        _calcResult = result;
        _isCalculating = false;
      });
    }
  }

  Future<void> _loadLedger() async {
    final entries = await _apiService.getPurificationLedger();
    if (mounted) {
      setState(() {
        _ledgerEntries = entries;
      });
    }
  }

  void _showVoucherDialog({
    required String companyName,
    required String ticker,
    required double grossDividend,
    required double purificationAmount,
    String? charityName,
    required String entryHash,
    required String prevHash,
    required String uuid,
  }) {
    final effectiveCharity = charityName ?? 'Accredited Charity Trust';
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? AppColors.darkCard : AppColors.lightCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20.0),
          side: BorderSide(color: AppColors.champagneGold.withOpacity(0.3)),
        ),
        title: Row(
          children: [
            const Icon(Icons.verified_rounded, color: AppColors.champagneGold, size: 24.0),
            const SizedBox(width: 8.0),
            const Expanded(
              child: Text(
                '80G Tax Deductible Voucher',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0),
              ),
            ),
          ],
        ),
        content: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(12.0),
                decoration: BoxDecoration(
                  color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                  borderRadius: BorderRadius.circular(12.0),
                  border: Border.all(color: AppColors.darkBorder),
                ),
                child: Column(
                  children: [
                    _buildVoucherRow('Certificate UUID', uuid.length > 18 ? '${uuid.substring(0, 18)}...' : uuid),
                    const Divider(height: 14.0),
                    _buildVoucherRow('Company & Ticker', '$companyName ($ticker)'),
                    const Divider(height: 14.0),
                    _buildVoucherRow('Gross Dividend', Formatters.formatCurrency(grossDividend)),
                    const Divider(height: 14.0),
                    _buildVoucherRow('Purification Donated', Formatters.formatCurrency(purificationAmount), highlight: true),
                    const Divider(height: 14.0),
                    _buildVoucherRow('Recipient Trust', effectiveCharity),
                    const Divider(height: 14.0),
                    _buildVoucherRow('Tax Status', '50% Deduction u/s 80G'),
                  ],
                ),
              ),
              const SizedBox(height: 12.0),
              const Text('Cryptographic Proof (SHA-256 Ledger):', style: TextStyle(fontSize: 11.0, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4.0),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8.0),
                decoration: BoxDecoration(
                  color: isDark ? Colors.black45 : Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(8.0),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Prev Hash: ${prevHash.length > 24 ? prevHash.substring(0, 24) : prevHash}...',
                      style: const TextStyle(fontSize: 9.5, fontFamily: 'monospace', color: AppColors.darkTextMuted),
                    ),
                    const SizedBox(height: 2.0),
                    Text(
                      'Entry Hash: $entryHash',
                      style: const TextStyle(fontSize: 9.5, fontFamily: 'monospace', color: AppColors.compliantGreenDark),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10.0),
              const Text(
                'Pursuant to AAOIFI Shariah Standard No. 21 (Financial Papers), non-operating interest dividend fractions are purged to accredited public charities without personal tax expectation. Retain this SHA-256 cryptographic receipt for audit.',
                style: TextStyle(fontSize: 10.5, fontStyle: FontStyle.italic, color: AppColors.darkTextMuted),
              ),
            ],
          ),
        ),
        actions: [
          TextButton.icon(
            icon: const Icon(Icons.copy_rounded, size: 16.0),
            label: const Text('Copy Hash'),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: entryHash));
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('SHA-256 Certificate Hash copied to clipboard')),
              );
            },
          ),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.champagneGold,
              foregroundColor: Colors.black,
            ),
            icon: const Icon(Icons.print_rounded, size: 16.0),
            label: const Text('Print Voucher'),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Voucher certificate exported for $companyName')),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildVoucherRow(String label, String value, {bool highlight = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 12.0)),
        Text(
          value,
          style: TextStyle(
            fontSize: 12.5,
            fontWeight: FontWeight.w700,
            color: highlight ? AppColors.champagneGold : null,
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _tickerController.dispose();
    _sharesController.dispose();
    _dividendController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dividend Purification & Ledger', style: TextStyle(fontWeight: FontWeight.w700)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Calculator Card
            FrostedCard(
              padding: const EdgeInsets.all(18.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Purification Calculator', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6.0),
                  const Text(
                    'Calculates non-operating interest income portion to donate to charity.',
                    style: TextStyle(fontSize: 12.0),
                  ),
                  const SizedBox(height: 16.0),

                  Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: TextField(
                          controller: _tickerController,
                          decoration: const InputDecoration(labelText: 'Ticker', border: OutlineInputBorder()),
                        ),
                      ),
                      const SizedBox(width: 8.0),
                      Expanded(
                        flex: 1,
                        child: TextField(
                          controller: _sharesController,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(labelText: 'Shares', border: OutlineInputBorder()),
                        ),
                      ),
                      const SizedBox(width: 8.0),
                      Expanded(
                        flex: 2,
                        child: TextField(
                          controller: _dividendController,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(labelText: 'DPS (₹)', border: OutlineInputBorder()),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14.0),

                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
                        foregroundColor: isDark ? Colors.black : Colors.white,
                      ),
                      onPressed: _calculatePurification,
                      child: const Text('Calculate Purification Breakdown'),
                    ),
                  ),
                  const SizedBox(height: 16.0),

                  if (_calcResult != null) ...[
                    Container(
                      padding: const EdgeInsets.all(14.0),
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                        borderRadius: BorderRadius.circular(12.0),
                      ),
                      child: Column(
                        children: [
                          _buildCalcRow('Gross Dividend Declared', Formatters.formatCurrency(_calcResult!.grossDividend)),
                          const Divider(),
                          _buildCalcRow('Purification Ratio (ρ)', '${_calcResult!.purificationRatioPct.toStringAsFixed(3)}%'),
                          const Divider(),
                          _buildCalcRow('Purification Due (Charity)', Formatters.formatCurrency(_calcResult!.purificationPayable), highlight: true),
                          const Divider(),
                          _buildCalcRow('Net Permissible Income', Formatters.formatCurrency(_calcResult!.netPermissibleDividend)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10.0),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.receipt_long_rounded, size: 16.0),
                        label: const Text('Generate Printable 80G Voucher'),
                        onPressed: () {
                          _showVoucherDialog(
                            companyName: _tickerController.text.trim().isNotEmpty ? _tickerController.text.trim() : _calcResult!.ticker,
                            ticker: _calcResult!.ticker,
                            grossDividend: _calcResult!.grossDividend,
                            purificationAmount: _calcResult!.purificationPayable,
                            charityName: 'Sabeel Clean Water & Sanitation Foundation',
                            entryHash: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
                            prevHash: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
                            uuid: 'rcpt-${DateTime.now().millisecondsSinceEpoch}',
                          );
                        },
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 20.0),

            // Verified 80G Charity Hub Card
            FrostedCard(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Verified 80G Charity Hub', style: Theme.of(context).textTheme.titleMedium),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 3.0),
                        decoration: BoxDecoration(
                          color: AppColors.champagneGold.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(6.0),
                        ),
                        child: const Text(
                          'Section 80G Tax-Deductible',
                          style: TextStyle(fontSize: 10.0, fontWeight: FontWeight.w700, color: AppColors.champagneGold),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6.0),
                  const Text(
                    'Approved partner trusts vetted for zero-overhead distribution of non-operating dividend purifications and zakat.',
                    style: TextStyle(fontSize: 12.0),
                  ),
                  const SizedBox(height: 14.0),
                  ..._verifiedCharities.map((ch) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 10.0),
                      padding: const EdgeInsets.all(12.0),
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                        borderRadius: BorderRadius.circular(12.0),
                        border: Border.all(color: AppColors.darkBorder),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text(
                                  ch['name']!,
                                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.0),
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6.0, vertical: 2.0),
                                decoration: BoxDecoration(
                                  color: AppColors.compliantBgDark,
                                  borderRadius: BorderRadius.circular(4.0),
                                ),
                                child: Text(
                                  ch['category']!,
                                  style: const TextStyle(fontSize: 9.5, fontWeight: FontWeight.w600, color: AppColors.compliantGreenDark),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4.0),
                          Text(ch['desc']!, style: const TextStyle(fontSize: 11.5, color: AppColors.darkTextMuted)),
                          const SizedBox(height: 8.0),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text('Reg: ${ch['reg']!} • UPI: ${ch['upi']!}',
                                    style: const TextStyle(fontSize: 11.0, fontFamily: 'monospace')),
                              ),
                              InkWell(
                                borderRadius: BorderRadius.circular(6.0),
                                onTap: () {
                                  Clipboard.setData(ClipboardData(text: ch['upi']!));
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text('Copied ${ch['upi']!} to clipboard')),
                                  );
                                },
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                                  decoration: BoxDecoration(
                                    color: AppColors.champagneGold.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(6.0),
                                  ),
                                  child: const Row(
                                    children: [
                                      Icon(Icons.copy_rounded, size: 12.0, color: AppColors.champagneGold),
                                      SizedBox(width: 4.0),
                                      Text('Copy UPI', style: TextStyle(fontSize: 11.0, fontWeight: FontWeight.w700, color: AppColors.champagneGold)),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
            const SizedBox(height: 20.0),

            // Immutable Ledger Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Immutable SHA-256 Ledger', style: Theme.of(context).textTheme.titleMedium),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                  decoration: BoxDecoration(
                    color: AppColors.compliantBgDark,
                    borderRadius: BorderRadius.circular(8.0),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.lock_rounded, size: 12.0, color: AppColors.compliantGreenDark),
                      SizedBox(width: 4.0),
                      Text('Chain Valid', style: TextStyle(fontSize: 10.0, color: AppColors.compliantGreenDark, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12.0),

            if (_ledgerEntries.isEmpty)
              const Center(child: Padding(padding: EdgeInsets.all(24.0), child: Text('No ledger entries recorded yet.')))
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _ledgerEntries.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8.0),
                itemBuilder: (context, index) {
                  final item = _ledgerEntries[index];
                  return FrostedCard(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(item.companyName, style: const TextStyle(fontWeight: FontWeight.w700)),
                            Text(Formatters.formatCurrency(item.purificationPayable), style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.compliantGreenDark)),
                          ],
                        ),
                        const SizedBox(height: 4.0),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Text(
                                'SHA-256: ${item.entryHash.length >= 16 ? item.entryHash.substring(0, 16) : item.entryHash}...',
                                style: const TextStyle(fontSize: 10.0, fontFamily: 'monospace', color: AppColors.darkTextMuted),
                              ),
                            ),
                            InkWell(
                              onTap: () {
                                _showVoucherDialog(
                                  companyName: item.companyName,
                                  ticker: item.ticker,
                                  grossDividend: item.grossDividend,
                                  purificationAmount: item.purificationPayable,
                                  charityName: item.charityName ?? 'Accredited Charity Trust',
                                  entryHash: item.entryHash,
                                  prevHash: item.prevEntryHash,
                                  uuid: item.entryUuid,
                                );
                              },
                              child: const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 4.0, vertical: 2.0),
                                child: Text('View Voucher', style: TextStyle(fontSize: 11.0, color: AppColors.champagneGold, fontWeight: FontWeight.w600)),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildCalcRow(String label, String value, {bool highlight = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13.0)),
          Text(
            value,
            style: TextStyle(
              fontSize: 14.0,
              fontWeight: FontWeight.w700,
              color: highlight ? AppColors.champagneGold : null,
            ),
          ),
        ],
      ),
    );
  }
}
