import 'package:flutter/material.dart';
import '../core/theme/colors.dart';
import '../core/utils/formatters.dart';
import '../models/stock_model.dart';
import '../services/api_service.dart';
import '../services/search_service.dart';
import '../widgets/compliance_badge.dart';
import '../widgets/frosted_card.dart';
import 'stock_detail_screen.dart';

class ScreenerScreen extends StatefulWidget {
  const ScreenerScreen({super.key});

  @override
  State<ScreenerScreen> createState() => _ScreenerScreenState();
}

class _ScreenerScreenState extends State<ScreenerScreen> {
  final ApiService _apiService = ApiService();
  late final SearchService _searchService;
  final TextEditingController _searchController = TextEditingController();

  String _selectedStandard = 'aaoifi'; // 'aaoifi' or 'tasis'
  String? _selectedSector;
  String? _selectedStatus;
  List<StockSummary> _stocks = [];
  bool _isLoading = false;
  bool _isTableView = false;
  int? _sortColumnIndex;
  bool _sortAscending = true;

  void _sort<T>(Comparable<T> Function(StockSummary s) getField, int columnIndex, bool ascending) {
    setState(() {
      _sortColumnIndex = columnIndex;
      _sortAscending = ascending;
      _stocks.sort((a, b) {
        final aValue = getField(a);
        final bValue = getField(b);
        return ascending
            ? Comparable.compare(aValue, bValue)
            : Comparable.compare(bValue, aValue);
      });
    });
  }

  final List<String> _sectors = [
    'Information Technology',
    'Consumer Goods',
    'Utilities',
    'Healthcare',
    'Industrial Manufacturing',
    'Chemicals',
  ];

  @override
  void initState() {
    super.initState();
    _searchService = SearchService(apiService: _apiService);
    _fetchStocks();
  }

  Future<void> _fetchStocks() async {
    setState(() => _isLoading = true);
    final results = await _apiService.getStocks(
      query: _searchController.text,
      sector: _selectedSector,
      status: _selectedStatus,
      standard: _selectedStandard,
    );
    if (mounted) {
      setState(() {
        _stocks = results;
        _isLoading = false;
      });
    }
  }

  void _onSearchChanged(String val) {
    if (val.isEmpty) {
      _fetchStocks();
      return;
    }
    // Instant local Trie lookup for <50ms responsiveness
    final instantLocal = _searchService.searchLocal(val);
    if (instantLocal.isNotEmpty) {
      setState(() {
        _stocks = instantLocal;
      });
    }
    // Debounced API sync
    _searchService.searchDebounced(val, standard: _selectedStandard).then((remote) {
      if (mounted && _searchController.text == val) {
        setState(() {
          _stocks = remote;
        });
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dual-Standard Screener', style: TextStyle(fontWeight: FontWeight.w700)),
        centerTitle: false,
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Search & Standard Controls
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Column(
              children: [
                // Instant Fuzzy Search Input
                TextField(
                  controller: _searchController,
                  onChanged: _onSearchChanged,
                  decoration: InputDecoration(
                    hintText: 'Instant search ticker, company or sector...',
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear_rounded),
                            onPressed: () {
                              _searchController.clear();
                              _fetchStocks();
                            },
                          )
                        : null,
                    filled: true,
                    fillColor: isDark ? AppColors.darkCard : AppColors.lightCard,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14.0),
                      borderSide: BorderSide(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
                  ),
                ),
                const SizedBox(height: 12.0),

                // AAOIFI vs TASIS Segmented Switch + View Mode Toggle
                Row(
                  children: [
                    const Text('Standard:', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0)),
                    const SizedBox(width: 8.0),
                    Expanded(
                      child: SegmentedButton<String>(
                        segments: const [
                          ButtonSegment(value: 'aaoifi', label: Text('AAOIFI (Mcap)')),
                          ButtonSegment(value: 'tasis', label: Text('TASIS (Assets)')),
                        ],
                        selected: {_selectedStandard},
                        onSelectionChanged: (newSelection) {
                          setState(() {
                            _selectedStandard = newSelection.first;
                          });
                          _fetchStocks();
                        },
                      ),
                    ),
                    const SizedBox(width: 8.0),
                    SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment(value: false, icon: Icon(Icons.view_agenda_rounded, size: 18), tooltip: 'Cards'),
                        ButtonSegment(value: true, icon: Icon(Icons.table_chart_rounded, size: 18), tooltip: 'Bloomberg Table'),
                      ],
                      selected: {_isTableView},
                      onSelectionChanged: (val) {
                        setState(() => _isTableView = val.first);
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 10.0),

                // Sector Filter Chips
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  child: Row(
                    children: [
                      FilterChip(
                        label: const Text('All Sectors'),
                        selected: _selectedSector == null,
                        onSelected: (selected) {
                          setState(() => _selectedSector = null);
                          _fetchStocks();
                        },
                      ),
                      const SizedBox(width: 8.0),
                      ..._sectors.map((sector) {
                        return Padding(
                          padding: const EdgeInsets.only(right: 8.0),
                          child: FilterChip(
                            label: Text(sector),
                            selected: _selectedSector == sector,
                            onSelected: (selected) {
                              setState(() {
                                _selectedSector = selected ? sector : null;
                              });
                              _fetchStocks();
                            },
                          ),
                        );
                      }),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),

          // Stock Results View (Cards vs Bloomberg Table)
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _stocks.isEmpty
                    ? const Center(child: Text('No equities match selected criteria.'))
                    : _isTableView
                        ? SingleChildScrollView(
                            physics: const BouncingScrollPhysics(),
                            scrollDirection: Axis.vertical,
                            child: SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              physics: const BouncingScrollPhysics(),
                              child: DataTable(
                                sortColumnIndex: _sortColumnIndex,
                                sortAscending: _sortAscending,
                                columns: [
                                  DataColumn(
                                    label: const Text('Ticker', style: TextStyle(fontWeight: FontWeight.w700)),
                                    onSort: (col, asc) => _sort((s) => s.symbol, col, asc),
                                  ),
                                  DataColumn(
                                    label: const Text('Company', style: TextStyle(fontWeight: FontWeight.w700)),
                                    onSort: (col, asc) => _sort((s) => s.companyName, col, asc),
                                  ),
                                  DataColumn(
                                    label: const Text('Sector', style: TextStyle(fontWeight: FontWeight.w700)),
                                    onSort: (col, asc) => _sort((s) => s.sector, col, asc),
                                  ),
                                  DataColumn(
                                    label: const Text('Live Price (₹)', style: TextStyle(fontWeight: FontWeight.w700)),
                                    numeric: true,
                                    onSort: (col, asc) => _sort((s) => s.currentPrice, col, asc),
                                  ),
                                  DataColumn(
                                    label: const Text('Debt Ratio', style: TextStyle(fontWeight: FontWeight.w700)),
                                    numeric: true,
                                    onSort: (col, asc) => _sort((s) => s.purificationRatio, col, asc),
                                  ),
                                  DataColumn(label: const Text('Status', style: TextStyle(fontWeight: FontWeight.w700))),
                                  DataColumn(label: const Text('Action', style: TextStyle(fontWeight: FontWeight.w700))),
                                ],
                                rows: _stocks.map((stock) {
                                  final status = _selectedStandard == 'aaoifi' ? stock.aaoifiStatus : stock.tasisStatus;
                                  return DataRow(
                                    cells: [
                                      DataCell(Text(stock.symbol, style: const TextStyle(fontWeight: FontWeight.w700))),
                                      DataCell(
                                        ConstrainedBox(
                                          constraints: const BoxConstraints(maxWidth: 160),
                                          child: Text(stock.companyName, overflow: TextOverflow.ellipsis),
                                        ),
                                      ),
                                      DataCell(Text(stock.sector, style: const TextStyle(fontSize: 12))),
                                      DataCell(Text(Formatters.formatCurrency(stock.currentPrice), style: const TextStyle(fontWeight: FontWeight.w600))),
                                      DataCell(Text('${(stock.purificationRatio * 100).toStringAsFixed(2)}%')),
                                      DataCell(ComplianceBadge(status: status, compact: true)),
                                      DataCell(
                                        IconButton(
                                          icon: const Icon(Icons.analytics_outlined, size: 20),
                                          tooltip: 'Audit Modal',
                                          onPressed: () => _showStockAuditModal(stock),
                                        ),
                                      ),
                                    ],
                                    onSelectChanged: (_) => _showStockAuditModal(stock),
                                  );
                                }).toList(),
                              ),
                            ),
                          )
                        : ListView.builder(
                            physics: const BouncingScrollPhysics(),
                            padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
                            itemCount: _stocks.length,
                            itemBuilder: (context, index) {
                              final stock = _stocks[index];
                              final status = _selectedStandard == 'aaoifi' ? stock.aaoifiStatus : stock.tasisStatus;

                              return Padding(
                                padding: const EdgeInsets.only(bottom: 10.0),
                                child: FrostedCard(
                                  onTap: () => _showStockAuditModal(stock),
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Text(stock.symbol, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16.0)),
                                                const SizedBox(width: 8.0),
                                                Text(
                                                  stock.sector,
                                                  style: TextStyle(
                                                    fontSize: 11.0,
                                                    color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
                                                  ),
                                                ),
                                              ],
                                            ),
                                            const SizedBox(height: 4.0),
                                            Text(
                                              stock.companyName,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: TextStyle(
                                                fontSize: 13.0,
                                                color: isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary,
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
                                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.0),
                                          ),
                                          const SizedBox(height: 6.0),
                                          ComplianceBadge(status: status, compact: true),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }

  void _showStockAuditModal(StockSummary stock) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        final isDark = Theme.of(context).brightness == Brightness.dark;

        return Container(
          padding: const EdgeInsets.only(top: 12.0, left: 20.0, right: 20.0, bottom: 28.0),
          decoration: BoxDecoration(
            color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24.0)),
            border: Border.all(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
          ),
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Drag handle pill
                Center(
                  child: Container(
                    width: 36,
                    height: 4,
                    decoration: BoxDecoration(
                      color: isDark ? Colors.white24 : Colors.black26,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16.0),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            stock.symbol,
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 20.0),
                          ),
                          Text(
                            stock.companyName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 13.0,
                              color: isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      Formatters.formatCurrency(stock.currentPrice),
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18.0),
                    ),
                  ],
                ),
                const SizedBox(height: 14.0),
                // Dual AAOIFI & TASIS Badges
                Row(
                  children: [
                    ComplianceBadge(status: stock.aaoifiStatus, standardLabel: 'AAOIFI'),
                    const SizedBox(width: 10.0),
                    ComplianceBadge(status: stock.tasisStatus, standardLabel: 'TASIS'),
                  ],
                ),
                const SizedBox(height: 14.0),
                // Divergence Alert Banner
                if (stock.aaoifiStatus != stock.tasisStatus) ...[
                  Container(
                    padding: const EdgeInsets.all(10.0),
                    decoration: BoxDecoration(
                      color: AppColors.questionableBgDark,
                      borderRadius: BorderRadius.circular(10.0),
                      border: Border.all(color: AppColors.questionableAmberDark),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, size: 18, color: AppColors.questionableAmberDark),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Standard Divergence: Evaluation differs between AAOIFI (36m Mcap) and TASIS (Total Assets).',
                            style: TextStyle(fontSize: 12.0),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14.0),
                ],
                // 4 Live Ratio Meters / Metrics
                Container(
                  padding: const EdgeInsets.all(12.0),
                  decoration: BoxDecoration(
                    color: isDark ? AppColors.darkCard : AppColors.lightElevated,
                    borderRadius: BorderRadius.circular(12.0),
                  ),
                  child: Column(
                    children: [
                      _buildAuditMetricRow('36m Avg Market Cap', '₹${(stock.avg36mMarketCap / 1000).toStringAsFixed(1)}k Cr'),
                      _buildAuditMetricRow('Live Market Cap', '₹${(stock.marketCap / 1000).toStringAsFixed(1)}k Cr'),
                      _buildAuditMetricRow('Dividend Purification Ratio', '${(stock.purificationRatio * 100).toStringAsFixed(2)}%'),
                      _buildAuditMetricRow('Sector Permissibility', '100% Permissible (${stock.sector})'),
                    ],
                  ),
                ),
                const SizedBox(height: 18.0),
                // Open Full Filing Details Button
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
                      foregroundColor: isDark ? Colors.black : Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
                    ),
                    icon: const Icon(Icons.description_outlined),
                    label: const Text('Open Full Shariah Audit Filing', style: TextStyle(fontWeight: FontWeight.w700)),
                    onPressed: () {
                      Navigator.pop(context);
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => StockDetailScreen(ticker: stock.ticker),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildAuditMetricRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12.0, color: AppColors.darkTextMuted)),
          Text(value, style: const TextStyle(fontSize: 12.0, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
