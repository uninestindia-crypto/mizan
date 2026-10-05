import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/theme/colors.dart';
import '../core/utils/formatters.dart';
import '../models/zakat_model.dart';
import '../services/api_service.dart';
import '../widgets/frosted_card.dart';

class AcademyZakatScreen extends StatefulWidget {
  const AcademyZakatScreen({super.key});

  @override
  State<AcademyZakatScreen> createState() => _AcademyZakatScreenState();
}

class _AcademyZakatScreenState extends State<AcademyZakatScreen> with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  late TabController _tabController;

  // Zakat form state
  String _zakatMethod = 'active'; // 'active' or 'long_term'
  String _zakatCalendar = 'lunar'; // 'lunar' (2.5%) or 'solar' (2.577%)
  final _portfolioValueController = TextEditingController(text: '1000000');
  final _cashBalanceController = TextEditingController(text: '200000');
  ZakatCalculationResult? _zakatResult;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _calculateZakat();
  }

  Future<void> _calculateZakat() async {
    final pval = double.tryParse(_portfolioValueController.text) ?? 0.0;
    final cash = double.tryParse(_cashBalanceController.text) ?? 0.0;

    final rawHoldings = [
      {'ticker': 'TCS.NS', 'shares': 100, 'znwa_per_share': 88.14},
      {'ticker': 'INFY.NS', 'shares': 200, 'znwa_per_share': 68.59},
    ];

    // Enforce clamped ZNWA floor at >= 0.0 to prevent negative working capital distortion
    final holdings = rawHoldings.map((h) {
      final znwa = (h['znwa_per_share'] as num).toDouble();
      final clampedZnwa = znwa < 0.0 ? 0.0 : znwa;
      return {
        'ticker': h['ticker'],
        'shares': h['shares'],
        'znwa_per_share': clampedZnwa,
      };
    }).toList();

    final result = await _apiService.calculateZakat(
      method: _zakatMethod,
      portfolioValue: pval,
      cashBalance: cash,
      holdings: holdings,
      calendar: _zakatCalendar,
    );

    if (mounted) {
      setState(() {
        _zakatResult = result;
      });
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _portfolioValueController.dispose();
    _cashBalanceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Halal Academy & Zakat', style: TextStyle(fontWeight: FontWeight.w700)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Zakat Calculator'),
            Tab(text: 'Wealth Academy'),
            Tab(text: 'Non-Margin Demat'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildZakatTab(),
          _buildAcademyTab(),
          _buildDematGuideTab(),
        ],
      ),
    );
  }

  Widget _buildZakatTab() {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          FrostedCard(
            padding: const EdgeInsets.all(18.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Dual-Method Equity Zakat Engine', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 6.0),
                const Text(
                  'Calculates Zakat obligations calibrated against Indian Silver Nisab (₹53,550.00).',
                  style: TextStyle(fontSize: 12.0),
                ),
                const SizedBox(height: 16.0),

                // Method Selector
                const Text('Investment Horizon Method:', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0)),
                const SizedBox(height: 6.0),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'active', label: Text('Active Trader (100% NLV)')),
                    ButtonSegment(value: 'long_term', label: Text('Long-Term (ZNWA)')),
                  ],
                  selected: {_zakatMethod},
                  onSelectionChanged: (val) {
                    setState(() => _zakatMethod = val.first);
                    _calculateZakat();
                  },
                ),
                const SizedBox(height: 12.0),

                // Calendar Selector
                const Text('Zakat Calendar Year:', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0)),
                const SizedBox(height: 6.0),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'lunar', label: Text('Lunar Hijri (2.500%)')),
                    ButtonSegment(value: 'solar', label: Text('Solar Gregorian (2.577%)')),
                  ],
                  selected: {_zakatCalendar},
                  onSelectionChanged: (val) {
                    setState(() => _zakatCalendar = val.first);
                    _calculateZakat();
                  },
                ),
                const SizedBox(height: 16.0),

                // Inputs
                TextField(
                  controller: _portfolioValueController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Total Portfolio Market Value (INR)',
                    prefixText: '₹ ',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (_) => _calculateZakat(),
                ),
                const SizedBox(height: 12.0),
                TextField(
                  controller: _cashBalanceController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Uninvested Cash / Bank Balance (INR)',
                    prefixText: '₹ ',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (_) => _calculateZakat(),
                ),
                const SizedBox(height: 16.0),

                // Results Card
                if (_zakatResult != null) ...[
                  Container(
                    padding: const EdgeInsets.all(16.0),
                    decoration: BoxDecoration(
                      color: isDark ? AppColors.darkBackground : AppColors.lightElevated,
                      borderRadius: BorderRadius.circular(14.0),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Zakatable Base:'),
                            Text(Formatters.formatCurrency(_zakatResult!.zakatableBase), style: const TextStyle(fontWeight: FontWeight.w700)),
                          ],
                        ),
                        const SizedBox(height: 6.0),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Indian Silver Nisab:'),
                            Text(Formatters.formatCurrency(_zakatResult!.nisabThreshold), style: const TextStyle(fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const Divider(height: 18.0),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Zakat Obligation:', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0)),
                            Text(
                              Formatters.formatCurrency(_zakatResult!.zakatDue),
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 20.0,
                                color: AppColors.champagneGold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8.0),
                        Text(
                          _zakatResult!.isObligatory
                              ? 'Status: Obligatory (Portfolio exceeds Silver Nisab)'
                              : 'Status: Exempt (Portfolio below Silver Nisab ₹53,550.00)',
                          style: TextStyle(
                            fontSize: 12.0,
                            fontWeight: FontWeight.w600,
                            color: _zakatResult!.isObligatory ? AppColors.compliantGreenDark : AppColors.questionableAmberDark,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAcademyTab() {
    final stages = [
      {'num': '1', 'name': 'Musharakah', 'status': 'completed'},
      {'num': '2', 'name': 'Inflation', 'status': 'completed'},
      {'num': '3', 'name': 'Dual Screen', 'status': 'active'},
      {'num': '4', 'name': 'Purification', 'status': 'locked'},
      {'num': '5', 'name': 'Certify', 'status': 'locked'},
    ];

    final modules = [
      {
        'stage': 'Stage 1',
        'title': 'Module 1: Musharakah & Mudarabah',
        'subtitle': 'Why Muslims Must Invest in Equities',
        'desc': 'Understanding partnership-based wealth generation vs prohibited interest-based debt.',
        'completed': true,
        'xp': '+250 XP',
      },
      {
        'stage': 'Stage 2',
        'title': 'Module 2: The Inflation Thief',
        'subtitle': 'Protecting Ummah Wealth Against Fiat Devaluation',
        'desc': 'How idle cash loses 6-8% purchasing power annually and how productive halal equity compounds wealth.',
        'completed': true,
        'xp': '+250 XP',
      },
      {
        'stage': 'Stage 3',
        'title': 'Module 3: Dual Shariah Screening Standards',
        'subtitle': 'AAOIFI vs TASIS Demystified',
        'desc': 'Deep-dive into 33% debt limits, 36-month market cap denominators vs total assets denominators.',
        'completed': false,
        'xp': '+300 XP (In Progress)',
      },
      {
        'stage': 'Stage 4',
        'title': 'Module 4: Purification & Zakat',
        'subtitle': 'Spiritual Accounting & Wealth Sanctification',
        'desc': 'How to purify tainted interest portions and calculate exact Zakat on stock portfolios.',
        'completed': false,
        'xp': '+300 XP (Locked)',
      },
      {
        'stage': 'Stage 5',
        'title': 'Module 5: Demat & Zakat Certification',
        'subtitle': 'Practical Zero-Riba Execution & Annual Zakat Purging',
        'desc': 'Complete non-margin Demat setup, broker compliance checks, and automated annual zakat certification.',
        'completed': false,
        'xp': '+400 XP (Locked)',
      },
    ];

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ListView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16.0),
      children: [
        // 5-Stage Gamified Milestone Progress Card
        FrostedCard(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Halal Wealth Mastery Path', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0)),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 3.0),
                    decoration: BoxDecoration(
                      color: AppColors.champagneGold.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(6.0),
                    ),
                    child: const Text(
                      'Stage 3 of 5 • 60% Complete',
                      style: TextStyle(fontSize: 10.0, fontWeight: FontWeight.w700, color: AppColors.champagneGold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6.0),
              const Text(
                'Complete all 5 stages to unlock the Certified Halal Retail Investor badge and automated Demat compliance attestations.',
                style: TextStyle(fontSize: 12.0),
              ),
              const SizedBox(height: 14.0),
              ClipRRect(
                borderRadius: BorderRadius.circular(4.0),
                child: LinearProgressIndicator(
                  value: 0.60,
                  minHeight: 7.0,
                  backgroundColor: isDark ? AppColors.darkBorder : Colors.grey.shade300,
                  valueColor: const AlwaysStoppedAnimation<Color>(AppColors.champagneGold),
                ),
              ),
              const SizedBox(height: 14.0),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: stages.map((st) {
                  final isDone = st['status'] == 'completed';
                  final isActive = st['status'] == 'active';
                  final color = isDone
                      ? AppColors.compliantGreenDark
                      : (isActive ? AppColors.champagneGold : AppColors.darkTextMuted);
                  return Column(
                    children: [
                      Container(
                        width: 28.0,
                        height: 28.0,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isDone
                              ? AppColors.compliantGreenDark.withOpacity(0.2)
                              : (isActive ? AppColors.champagneGold.withOpacity(0.2) : Colors.transparent),
                          border: Border.all(color: color, width: 1.5),
                        ),
                        child: Center(
                          child: isDone
                              ? const Icon(Icons.check, size: 14.0, color: AppColors.compliantGreenDark)
                              : (isActive
                                  ? const Icon(Icons.play_arrow_rounded, size: 14.0, color: AppColors.champagneGold)
                                  : Text(st['num']!, style: TextStyle(fontSize: 11.0, color: color, fontWeight: FontWeight.w700))),
                        ),
                      ),
                      const SizedBox(height: 4.0),
                      Text(
                        st['name']!,
                        style: TextStyle(fontSize: 9.5, color: color, fontWeight: FontWeight.w600),
                      ),
                    ],
                  );
                }).toList(),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16.0),

        // Course Modules
        ...modules.map((m) {
          final isCompleted = m['completed'] as bool;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12.0),
            child: FrostedCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6.0, vertical: 2.0),
                        decoration: BoxDecoration(
                          color: isCompleted
                              ? AppColors.compliantBgDark
                              : AppColors.darkBorder,
                          borderRadius: BorderRadius.circular(4.0),
                        ),
                        child: Text(
                          m['stage'] as String,
                          style: TextStyle(
                            fontSize: 10.0,
                            fontWeight: FontWeight.w600,
                            color: isCompleted ? AppColors.compliantGreenDark : AppColors.darkTextMuted,
                          ),
                        ),
                      ),
                      Text(
                        m['xp'] as String,
                        style: const TextStyle(fontSize: 11.0, fontWeight: FontWeight.w700, color: AppColors.champagneGold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8.0),
                  Text(m['title'] as String, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0)),
                  const SizedBox(height: 4.0),
                  Text(m['subtitle'] as String, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0, color: AppColors.champagneGold)),
                  const SizedBox(height: 8.0),
                  Text(m['desc'] as String, style: const TextStyle(fontSize: 12.0)),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _buildDematGuideTab() {
    final rules = [
      '1. Strict CNC (Cash and Carry) / Delivery Mode — Zero Intraday Leverage',
      '2. Deactivate MTF (Margin Trading Facility) — Prohibits interest-bearing margin loans',
      '3. Deactivate SLBM (Securities Lending and Borrowing) — Prevents lending shares for short-selling',
      '4. Disable F&O (Futures & Options) — Eliminates Gharar (excessive uncertainty) and Maysir (gambling)',
    ];

    return ListView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16.0),
      children: [
        FrostedCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Universal Anti-Riba Demat Rules', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0)),
              const SizedBox(height: 12.0),
              ...rules.map((r) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4.0),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle_outline_rounded, size: 16.0, color: AppColors.compliantGreenDark),
                        const SizedBox(width: 8.0),
                        Expanded(child: Text(r, style: const TextStyle(fontSize: 13.0))),
                      ],
                    ),
                  )),
            ],
          ),
        ),
      ],
    );
  }
}
