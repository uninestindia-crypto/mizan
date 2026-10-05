import 'package:flutter/material.dart';
import '../core/theme/colors.dart';
import '../models/screening_result.dart';
import '../services/api_service.dart';
import '../widgets/compliance_badge.dart';
import '../widgets/frosted_card.dart';
import '../widgets/ratio_meter.dart';

class StockDetailScreen extends StatefulWidget {
  final String ticker;

  const StockDetailScreen({super.key, required this.ticker});

  @override
  State<StockDetailScreen> createState() => _StockDetailScreenState();
}

class _StockDetailScreenState extends State<StockDetailScreen> with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  ShariahAuditDetail? _auditDetail;
  bool _isLoading = true;
  late TabController _tabController;
  String _detailStandard = 'aaoifi';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadAudit();
  }

  Future<void> _loadAudit() async {
    final detail = await _apiService.getShariahAudit(widget.ticker);
    if (mounted) {
      setState(() {
        _auditDetail = detail;
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.ticker, style: const TextStyle(fontWeight: FontWeight.w700)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _auditDetail == null
              ? const Center(child: Text('Company audit details not available.'))
              : SingleChildScrollView(
                  physics: const BouncingScrollPhysics(),
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header Card
                      FrostedCard(
                        padding: const EdgeInsets.all(18.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _auditDetail!.companyName,
                              style: const TextStyle(fontSize: 20.0, fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 4.0),
                            Text(
                              '${_auditDetail!.sector} • ISIN: ${_auditDetail!.isin}',
                              style: TextStyle(
                                fontSize: 12.0,
                                color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
                              ),
                            ),
                            const SizedBox(height: 16.0),

                            // Dual Badge Comparison
                            Row(
                              children: [
                                ComplianceBadge(
                                  status: _auditDetail!.aaoifiEvaluation.status,
                                  standardLabel: 'AAOIFI',
                                ),
                                const SizedBox(width: 12.0),
                                ComplianceBadge(
                                  status: _auditDetail!.tasisEvaluation.status,
                                  standardLabel: 'TASIS',
                                ),
                              ],
                            ),

                            if (_auditDetail!.divergenceNoted) ...[
                              const SizedBox(height: 12.0),
                              Container(
                                padding: const EdgeInsets.all(10.0),
                                decoration: BoxDecoration(
                                  color: AppColors.questionableBgDark,
                                  borderRadius: BorderRadius.circular(10.0),
                                  border: Border.all(color: AppColors.questionableAmberDark),
                                ),
                                child: Text(
                                  _auditDetail!.divergenceExplanation ?? 'Divergence noted between AAOIFI and TASIS.',
                                  style: const TextStyle(fontSize: 12.0),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 20.0),

                      // Ratio Meters (Dual Standard Toggle: AAOIFI vs TASIS)
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              _detailStandard == 'aaoifi'
                                  ? 'AAOIFI Ratios (36m Mcap)'
                                  : 'TASIS Ratios (Total Assets)',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                          ),
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment(value: 'aaoifi', label: Text('AAOIFI')),
                              ButtonSegment(value: 'tasis', label: Text('TASIS')),
                            ],
                            selected: {_detailStandard},
                            onSelectionChanged: (val) {
                              setState(() => _detailStandard = val.first);
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 8.0),
                      if (_detailStandard == 'aaoifi') ...[
                        RatioMeterWidget(data: _auditDetail!.aaoifiEvaluation.debtRatio),
                        RatioMeterWidget(data: _auditDetail!.aaoifiEvaluation.cashRatio),
                        RatioMeterWidget(data: _auditDetail!.aaoifiEvaluation.receivablesRatio),
                        RatioMeterWidget(data: _auditDetail!.aaoifiEvaluation.impermissibleIncomeRatio),
                      ] else ...[
                        RatioMeterWidget(data: _auditDetail!.tasisEvaluation.debtRatio),
                        RatioMeterWidget(data: _auditDetail!.tasisEvaluation.cashRatio),
                        RatioMeterWidget(data: _auditDetail!.tasisEvaluation.receivablesRatio),
                        RatioMeterWidget(data: _auditDetail!.tasisEvaluation.impermissibleIncomeRatio),
                      ],
                      const SizedBox(height: 20.0),

                      // Line-Item Audit Trail
                      Text('Line-Item Audit Evidence', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 10.0),
                      TabBar(
                        controller: _tabController,
                        tabs: const [
                          Tab(text: 'Balance Sheet Evidence'),
                          Tab(text: 'Income Statement Evidence'),
                        ],
                      ),
                      SizedBox(
                        height: 240.0,
                        child: TabBarView(
                          controller: _tabController,
                          children: [
                            _buildAuditTable(_auditDetail!.balanceSheetLines, isDark),
                            _buildAuditTable(_auditDetail!.incomeStatementLines, isDark),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildAuditTable(List<AuditEvidenceLineData> lines, bool isDark) {
    if (lines.isEmpty) {
      return const Center(child: Text('No verified line items.'));
    }
    return ListView.separated(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      itemCount: lines.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final line = lines[index];
        return ListTile(
          dense: true,
          title: Text(line.lineItem, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0)),
          subtitle: line.noteRef != null
              ? Text('Note Citation: ${line.noteRef}', style: const TextStyle(fontSize: 11.0))
              : null,
          trailing: Text(
            '₹${line.valueInrCr.toStringAsFixed(2)} Cr',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.0),
          ),
        );
      },
    );
  }
}
