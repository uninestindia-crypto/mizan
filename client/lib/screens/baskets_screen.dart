import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/theme/colors.dart';
import '../core/utils/formatters.dart';
import '../models/basket_model.dart';
import '../services/api_service.dart';
import '../widgets/frosted_card.dart';

class BasketsScreen extends StatefulWidget {
  const BasketsScreen({super.key});

  @override
  State<BasketsScreen> createState() => _BasketsScreenState();
}

class _BasketsScreenState extends State<BasketsScreen> with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  late TabController _tabController;
  List<BasketModel> _baskets = [];
  List<FundModel> _funds = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final basketsList = await _apiService.getBaskets();
    final fundsList = await _apiService.getFunds();
    if (mounted) {
      setState(() {
        _baskets = basketsList;
        _funds = fundsList;
        _isLoading = false;
      });
    }
  }

  void _showBrokerExportModal(BasketModel basket) {
    String selectedBroker = 'zerodha';
    double capital = 50000.0;
    final capitalController = TextEditingController(text: '50000');

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final isDark = Theme.of(context).brightness == Brightness.dark;

            return Container(
              padding: EdgeInsets.only(
                top: 24.0,
                left: 20.0,
                right: 20.0,
                bottom: MediaQuery.of(context).viewInsets.bottom + 24.0,
              ),
              decoration: BoxDecoration(
                color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(24.0)),
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('1-Click Indian Broker Export', style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 6.0),
                    Text(
                      'Export order sheet for ${basket.name} to Indian discount brokers with strict delivery/CNC cash modes.',
                      style: const TextStyle(fontSize: 12.0),
                    ),
                    const SizedBox(height: 18.0),

                    // Broker Selection
                    const Text('Select Broker:', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0)),
                    const SizedBox(height: 8.0),
                    Wrap(
                      spacing: 8.0,
                      children: ['zerodha', 'upstox', 'groww', 'angelone'].map((broker) {
                        return ChoiceChip(
                          label: Text(broker.toUpperCase()),
                          selected: selectedBroker == broker,
                          onSelected: (val) {
                            if (val) setModalState(() => selectedBroker = broker);
                          },
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 16.0),

                    // Capital Input
                    TextField(
                      controller: capitalController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Investment Capital (INR)',
                        prefixText: '₹ ',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (val) {
                        setModalState(() {
                          capital = double.tryParse(val) ?? 50000.0;
                        });
                      },
                    ),
                    const SizedBox(height: 14.0),

                    // Indian Statutory Tax & Brokerage Breakdown
                    Container(
                      padding: const EdgeInsets.all(12.0),
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                        borderRadius: BorderRadius.circular(10.0),
                        border: Border.all(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Statutory Taxes & Brokerage Breakdown (CNC Delivery)',
                            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.0),
                          ),
                          const SizedBox(height: 8.0),
                          _buildTaxRow('Brokerage (Free Delivery)', '₹0.00'),
                          _buildTaxRow('Securities Transaction Tax (STT 0.1%)', '₹${(capital * 0.001).toStringAsFixed(2)}'),
                          _buildTaxRow('Stamp Duty (0.015% on buy)', '₹${(capital * 0.00015).toStringAsFixed(2)}'),
                          _buildTaxRow('SEBI Charges & Turnover Fees', '₹${(capital * 0.0000335).toStringAsFixed(2)}'),
                          _buildTaxRow('GST (18% on statutory fees)', '₹${((capital * 0.0000335) * 0.18).toStringAsFixed(2)}'),
                          const Divider(height: 12.0),
                          _buildTaxRow(
                            'Total Statutory Charges',
                            '₹${(capital * 0.001 + capital * 0.00015 + capital * 0.0000335 * 1.18).toStringAsFixed(2)}',
                            isBold: true,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18.0),

                    // Export Action Button
                    SizedBox(
                      width: double.infinity,
                      height: 48.0,
                      child: ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.champagneGold,
                          foregroundColor: Colors.black,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
                        ),
                        icon: const Icon(Icons.copy_rounded),
                        label: const Text('Generate & Copy Broker CSV', style: TextStyle(fontWeight: FontWeight.w700)),
                        onPressed: () async {
                          final export = await _apiService.exportBasketOrders(
                            basketId: basket.id,
                            broker: selectedBroker,
                            capital: capital,
                          );
                          if (export != null) {
                            await Clipboard.setData(ClipboardData(text: export.clipboardPayload));
                            if (context.mounted) {
                              Navigator.pop(context);
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Order sheet for ${selectedBroker.toUpperCase()} copied to clipboard!'),
                                  backgroundColor: AppColors.compliantGreenDark,
                                ),
                              );
                            }
                          }
                        },
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildTaxRow(String label, String value, {bool isBold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontSize: 11.5, fontWeight: isBold ? FontWeight.w700 : FontWeight.w400)),
          Text(value, style: TextStyle(fontSize: 11.5, fontWeight: isBold ? FontWeight.w700 : FontWeight.w600)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Baskets & Halal Funds', style: TextStyle(fontWeight: FontWeight.w700)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Thematic Baskets'),
            Tab(text: 'Halal Funds & 24K Gold'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildBasketsTab(context),
                _buildFundsTab(context),
              ],
            ),
    );
  }

  Widget _buildBasketsTab(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ListView.separated(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16.0),
      itemCount: _baskets.length,
      separatorBuilder: (_, __) => const SizedBox(height: 16.0),
      itemBuilder: (context, index) {
        final basket = _baskets[index];

        return FrostedCard(
          padding: const EdgeInsets.all(18.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      basket.name,
                      style: const TextStyle(fontSize: 18.0, fontWeight: FontWeight.w700),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10.0, vertical: 4.0),
                    decoration: BoxDecoration(
                      color: AppColors.goldGlow,
                      borderRadius: BorderRadius.circular(12.0),
                    ),
                    child: Text(
                      basket.category,
                      style: TextStyle(
                        fontSize: 11.0,
                        fontWeight: FontWeight.w600,
                        color: isDark ? AppColors.champagneGold : AppColors.mutedGold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8.0),
              Text(
                basket.thesis,
                style: TextStyle(
                  fontSize: 13.0,
                  color: isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary,
                ),
              ),
              const SizedBox(height: 16.0),

              // Tear-Sheet Metrics Grid
              Container(
                padding: const EdgeInsets.all(12.0),
                decoration: BoxDecoration(
                  color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                  borderRadius: BorderRadius.circular(12.0),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildTearSheetStat('Expected CAGR', Formatters.formatPercentage(basket.expectedCagr), AppColors.compliantGreenDark),
                    _buildTearSheetStat('Sharpe Ratio', basket.expectedSharpe.toStringAsFixed(2), null),
                    _buildTearSheetStat('Max Drawdown', Formatters.formatPercentage(basket.maxDrawdown), AppColors.nonCompliantCrimsonDark),
                    _buildTearSheetStat('Purification', Formatters.formatPercentage(basket.weightedPurificationRatio), null),
                  ],
                ),
              ),
              const SizedBox(height: 16.0),

              // Constituents Tags
              Wrap(
                spacing: 6.0,
                runSpacing: 6.0,
                children: basket.constituents.map((c) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                    decoration: BoxDecoration(
                      color: isDark ? Colors.white10 : Colors.black.withOpacity(0.04),
                      borderRadius: BorderRadius.circular(6.0),
                    ),
                    child: Text(
                      '${c.symbol} ${(c.weight * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(fontSize: 11.0, fontWeight: FontWeight.w600),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16.0),

              // Export Button
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(
                      color: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
                    ),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10.0)),
                  ),
                  icon: const Icon(Icons.send_to_mobile_rounded, size: 18.0),
                  label: const Text('1-Click Indian Broker Order Export'),
                  onPressed: () => _showBrokerExportModal(basket),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildFundsTab(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ListView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16.0),
      children: [
        // SIP Compounding Simulator Card
        FrostedCard(
          padding: const EdgeInsets.all(18.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Halal SIP Compounding Calculator', style: TextStyle(fontSize: 16.0, fontWeight: FontWeight.w700)),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 3.0),
                    decoration: BoxDecoration(color: AppColors.goldGlow, borderRadius: BorderRadius.circular(8.0)),
                    child: const Text('15% Expected CAGR', style: TextStyle(fontSize: 11.0, fontWeight: FontWeight.w600, color: AppColors.champagneGold)),
                  ),
                ],
              ),
              const SizedBox(height: 6.0),
              const Text('Calculates disciplined rupee compounding vs 7% cash inflation loss.', style: TextStyle(fontSize: 12.0)),
              const SizedBox(height: 14.0),
              Container(
                padding: const EdgeInsets.all(12.0),
                decoration: BoxDecoration(
                  color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                  borderRadius: BorderRadius.circular(10.0),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildTearSheetStat('5-Year SIP (₹5k/mo)', '₹4.48 Lakh', AppColors.compliantGreenDark),
                    _buildTearSheetStat('10-Year SIP (₹5k/mo)', '₹13.93 Lakh', AppColors.compliantGreenDark),
                    _buildTearSheetStat('15-Year SIP (₹5k/mo)', '₹33.84 Lakh', AppColors.champagneGold),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16.0),

        // Curated Funds & Gold List
        ..._funds.map((fund) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 14.0),
            child: FrostedCard(
              padding: const EdgeInsets.all(18.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          fund.name,
                          style: const TextStyle(fontSize: 17.0, fontWeight: FontWeight.w700),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 3.0),
                        decoration: BoxDecoration(
                          color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                          borderRadius: BorderRadius.circular(8.0),
                        ),
                        child: Text(
                          fund.type,
                          style: const TextStyle(fontSize: 11.0, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6.0),
                  Text(fund.description, style: TextStyle(fontSize: 12.5, color: isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary)),
                  const SizedBox(height: 12.0),
                  Container(
                    padding: const EdgeInsets.all(10.0),
                    decoration: BoxDecoration(
                      color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                      borderRadius: BorderRadius.circular(10.0),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _buildTearSheetStat('NAV / Price', '₹${fund.nav.toStringAsFixed(2)}', null),
                        _buildTearSheetStat('3Y CAGR', '${fund.cagr3yr}%', AppColors.compliantGreenDark),
                        _buildTearSheetStat('Min SIP', '₹${fund.minSip.toStringAsFixed(0)}', null),
                        _buildTearSheetStat('Expense Ratio', '${fund.expenseRatio}%', null),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8.0),
                  Text(
                    'Shariah Board: ${fund.shariahBoard} • Risk: ${fund.risk}',
                    style: const TextStyle(fontSize: 11.0, color: AppColors.champagneGold, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _buildTearSheetStat(String label, String value, Color? color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14.0, color: color)),
        const SizedBox(height: 2.0),
        Text(label, style: const TextStyle(fontSize: 10.0, color: AppColors.darkTextMuted)),
      ],
    );
  }
}
