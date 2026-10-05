import 'package:flutter/material.dart';
import '../core/theme/colors.dart';
import '../core/utils/formatters.dart';
import '../models/stock_model.dart';
import '../services/api_service.dart';
import '../widgets/compliance_badge.dart';
import '../widgets/frosted_card.dart';
import '../widgets/sparkline_chart.dart';
import 'stock_detail_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();
  List<StockSummary> _topStocks = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    final stocks = await _apiService.getStocks(limit: 6);
    if (mounted) {
      setState(() {
        _topStocks = stocks;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Halal Wealth Dashboard', style: TextStyle(fontWeight: FontWeight.w700)),
        centerTitle: false,
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () {
              setState(() => _isLoading = true);
              _loadDashboardData();
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Welcome & Market Pulse Card
            FrostedCard(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'NIFTY 500 SHARIAH PULSE',
                            style: TextStyle(
                              fontSize: 12.0,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 1.2,
                              color: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
                            ),
                          ),
                          const SizedBox(height: 6.0),
                          const Text(
                            '18,452.80',
                            style: TextStyle(fontSize: 28.0, fontWeight: FontWeight.w700),
                          ),
                        ],
                      ),
                      const SparklineChart(
                        dataPoints: [18100, 18180, 18150, 18240, 18350, 18452.8],
                        lineColor: AppColors.emeraldAccent,
                        width: 90,
                        height: 40,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12.0),
                  Row(
                    children: const [
                      Icon(Icons.arrow_upward_rounded, size: 16.0, color: AppColors.compliantGreenDark),
                      SizedBox(width: 4.0),
                      Text(
                        '+142.30 (+0.78%) Today',
                        style: TextStyle(
                          color: AppColors.compliantGreenDark,
                          fontWeight: FontWeight.w600,
                          fontSize: 13.0,
                        ),
                      ),
                      Spacer(),
                      Text('Strict Dual-Screen Active', style: TextStyle(fontSize: 11.0, color: AppColors.darkTextMuted)),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16.0),

            // 2. Halal Market Overview Metric Chips
            Wrap(
              spacing: 12.0,
              runSpacing: 12.0,
              children: [
                _buildMetricCard('Total Screened', '500', 'Indian Equities', isDark),
                _buildMetricCard('Compliant', '328', '65.6% Passing', isDark, color: AppColors.compliantGreenDark),
                _buildMetricCard('Questionable', '42', 'Borderline Ratios', isDark, color: AppColors.questionableAmberDark),
                _buildMetricCard('Non-Compliant', '130', 'Prohibited Sector/Debt', isDark, color: AppColors.nonCompliantCrimsonDark),
              ],
            ),
            const SizedBox(height: 24.0),

            // 3. Quick Shariah Action Banners
            Row(
              children: [
                Text(
                  'Top Shariah-Compliant Equities',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const Spacer(),
                Text(
                  'AAOIFI & TASIS',
                  style: TextStyle(
                    fontSize: 12.0,
                    fontWeight: FontWeight.w600,
                    color: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12.0),

            if (_isLoading)
              const Center(child: Padding(padding: EdgeInsets.all(32.0), child: CircularProgressIndicator()))
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _topStocks.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10.0),
                itemBuilder: (context, index) {
                  final stock = _topStocks[index];
                  return FrostedCard(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => StockDetailScreen(ticker: stock.ticker),
                        ),
                      );
                    },
                    child: Row(
                      children: [
                        Container(
                          width: 42.0,
                          height: 42.0,
                          decoration: BoxDecoration(
                            color: isDark ? Colors.white10 : Colors.black.withOpacity(0.04),
                            borderRadius: BorderRadius.circular(10.0),
                          ),
                          child: Center(
                            child: Text(
                              stock.symbol.substring(0, stock.symbol.length > 2 ? 2 : stock.symbol.length),
                              style: const TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                        ),
                        const SizedBox(width: 14.0),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(stock.symbol, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.0)),
                              const SizedBox(height: 2.0),
                              Text(
                                stock.companyName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 12.0,
                                  color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              Formatters.formatCurrency(stock.currentPrice),
                              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.0),
                            ),
                            const SizedBox(height: 4.0),
                            ComplianceBadge(status: stock.aaoifiStatus, compact: true),
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

  Widget _buildMetricCard(String title, String value, String subtitle, bool isDark, {Color? color}) {
    return Container(
      width: 160.0,
      padding: const EdgeInsets.all(14.0),
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkCard : AppColors.lightCard,
        borderRadius: BorderRadius.circular(14.0),
        border: Border.all(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 11.0,
              fontWeight: FontWeight.w600,
              color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
            ),
          ),
          const SizedBox(height: 6.0),
          Text(
            value,
            style: TextStyle(
              fontSize: 22.0,
              fontWeight: FontWeight.w700,
              color: color ?? (isDark ? Colors.white : Colors.black),
            ),
          ),
          const SizedBox(height: 4.0),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 10.0,
              color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
            ),
          ),
        ],
      ),
    );
  }
}
