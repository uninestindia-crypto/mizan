import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'widgets/adaptive_scaffold.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const HalalInvestmentApp());
}

class HalalInvestmentApp extends StatefulWidget {
  const HalalInvestmentApp({super.key});

  @override
  State<HalalInvestmentApp> createState() => _HalalInvestmentAppState();
}

class _HalalInvestmentAppState extends State<HalalInvestmentApp> {
  ThemeMode _themeMode = ThemeMode.dark;

  void _toggleTheme() {
    setState(() {
      _themeMode = _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Halal Investment Platform',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      themeMode: _themeMode,
      home: AdaptiveScaffold(
        themeMode: _themeMode,
        onToggleTheme: _toggleTheme,
      ),
    );
  }
}
