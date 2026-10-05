import 'dart:async';
import '../models/stock_model.dart';
import 'api_service.dart';

class TrieNode {
  final Map<String, TrieNode> children = {};
  final Set<StockSummary> matchedStocks = {};
  bool isEndOfWord = false;
}

/// In-memory Prefix Trie with debounced query caching (<50ms response SLA)
class SearchService {
  final ApiService _apiService;
  final TrieNode _root = TrieNode();
  final Map<String, List<StockSummary>> _queryCache = {};
  Timer? _debounceTimer;

  SearchService({ApiService? apiService})
      : _apiService = apiService ?? ApiService() {
    _initializeLocalIndex();
  }

  void _initializeLocalIndex() {
    // Populate trie with offline reference equities
    final initialList = _apiService.getFallbackStocks();
    for (final stock in initialList) {
      insertStock(stock);
    }
    // Asynchronously index full universe of bundled stocks
    _apiService.loadBundledStocks().then((bundled) {
      for (final stock in bundled) {
        insertStock(stock);
      }
    });
  }

  void insertStock(StockSummary stock) {
    _insertToken(stock.symbol.toLowerCase(), stock);
    _insertToken(stock.ticker.toLowerCase(), stock);
    final words = stock.companyName.toLowerCase().split(RegExp(r'\s+'));
    for (final word in words) {
      if (word.length >= 2) {
        _insertToken(word, stock);
      }
    }
    final sectorWords = stock.sector.toLowerCase().split(RegExp(r'\s+'));
    for (final sword in sectorWords) {
      if (sword.length >= 3) {
        _insertToken(sword, stock);
      }
    }
  }

  void _insertToken(String token, StockSummary stock) {
    TrieNode current = _root;
    for (int i = 0; i < token.length; i++) {
      final char = token[i];
      current = current.children.putIfAbsent(char, () => TrieNode());
      current.matchedStocks.add(stock);
    }
    current.isEndOfWord = true;
  }

  /// Instant local search via Trie (typical latency < 1ms)
  List<StockSummary> searchLocal(String query) {
    final clean = query.trim().toLowerCase();
    if (clean.isEmpty) return [];

    if (_queryCache.containsKey(clean)) {
      return _queryCache[clean]!;
    }

    TrieNode? current = _root;
    for (int i = 0; i < clean.length; i++) {
      final char = clean[i];
      if (!current!.children.containsKey(char)) {
        _queryCache[clean] = [];
        return [];
      }
      current = current.children[char];
    }

    final results = current!.matchedStocks.toList();
    _queryCache[clean] = results;
    return results;
  }

  /// Debounced search: returns local results instantly, then syncs with API if online
  Future<List<StockSummary>> searchDebounced(
    String query, {
    Duration debounceDuration = const Duration(milliseconds: 200),
    String standard = 'aaoifi',
  }) {
    final completer = Completer<List<StockSummary>>();
    _debounceTimer?.cancel();

    // 1. Resolve immediately from local trie
    final localResults = searchLocal(query);

    _debounceTimer = Timer(debounceDuration, () async {
      if (query.trim().isEmpty) {
        completer.complete([]);
        return;
      }

      try {
        final remote = await _apiService.getStocks(
          query: query,
          standard: standard,
          limit: 15,
        );
        for (final stock in remote) {
          insertStock(stock);
        }
        completer.complete(remote.isNotEmpty ? remote : localResults);
      } catch (_) {
        completer.complete(localResults);
      }
    });

    return completer.future;
  }

  void dispose() {
    _debounceTimer?.cancel();
  }
}
