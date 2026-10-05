import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/theme/colors.dart';
import '../screens/dashboard_screen.dart';
import '../screens/screener_screen.dart';
import '../screens/baskets_screen.dart';
import '../screens/purification_screen.dart';
import '../screens/academy_zakat_screen.dart';

class AdaptiveScaffold extends StatefulWidget {
  final ThemeMode themeMode;
  final VoidCallback onToggleTheme;

  const AdaptiveScaffold({
    super.key,
    required this.themeMode,
    required this.onToggleTheme,
  });

  @override
  State<AdaptiveScaffold> createState() => _AdaptiveScaffoldState();
}

class _AdaptiveScaffoldState extends State<AdaptiveScaffold> {
  int _selectedIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    ScreenerScreen(),
    BasketsScreen(),
    PurificationScreen(),
    AcademyZakatScreen(),
  ];

  void _onDestinationSelected(int index) {
    if (_selectedIndex != index) {
      HapticFeedback.selectionClick();
      setState(() {
        _selectedIndex = index;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth >= 768.0; // constraints.maxWidth >= 600.0

        if (isDesktop) {
          return Scaffold(
            body: Row(
              children: [
                _buildNavigationRail(context),
                const VerticalDivider(width: 1, thickness: 1, color: AppColors.darkBorder),
                Expanded(
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1440),
                      child: _screens[_selectedIndex],
                    ),
                  ),
                ),
              ],
            ),
          );
        }

        // Mobile Layout (<768dp) with Frosted Glass Cupertino Blur
        final isDark = Theme.of(context).brightness == Brightness.dark;
        return Scaffold(
          body: _screens[_selectedIndex],
          bottomNavigationBar: ClipRect(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
              child: Container(
                decoration: BoxDecoration(
                  color: (isDark ? AppColors.darkSurface : AppColors.lightSurface).withOpacity(0.85),
                  border: Border(
                    top: BorderSide(
                      color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
                      width: 0.5,
                    ),
                  ),
                ),
                child: BottomNavigationBar(
                  backgroundColor: Colors.transparent,
                  elevation: 0,
                  currentIndex: _selectedIndex,
                  onTap: _onDestinationSelected,
                  items: const [
                    BottomNavigationBarItem(
                      icon: Icon(Icons.dashboard_rounded),
                      label: 'Dashboard',
                    ),
                    BottomNavigationBarItem(
                      icon: Icon(Icons.filter_list_rounded),
                      label: 'Screener',
                    ),
                    BottomNavigationBarItem(
                      icon: Icon(Icons.pie_chart_rounded),
                      label: 'Baskets',
                    ),
                    BottomNavigationBarItem(
                      icon: Icon(Icons.cleaning_services_rounded),
                      label: 'Purify',
                    ),
                    BottomNavigationBarItem(
                      icon: Icon(Icons.school_rounded),
                      label: 'Academy',
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildNavigationRail(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return NavigationRail(
      selectedIndex: _selectedIndex,
      onDestinationSelected: _onDestinationSelected,
      labelType: NavigationRailLabelType.all,
      leading: Padding(
        padding: const EdgeInsets.symmetric(vertical: 24.0),
        child: Column(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [AppColors.champagneGold, AppColors.emeraldPrimaryDark],
                  center: Alignment(-0.2, -0.2),
                ),
                boxShadow: [
                  BoxShadow(color: AppColors.goldGlow, blurRadius: 12, spreadRadius: 1),
                ],
              ),
              child: const Center(
                child: Icon(Icons.auto_awesome, color: Colors.white, size: 22),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'HALAL\nWEALTH',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.2,
                color: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
              ),
            ),
          ],
        ),
      ),
      trailing: Expanded(
        child: Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 24.0),
            child: IconButton(
              icon: Icon(
                widget.themeMode == ThemeMode.dark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                color: isDark ? AppColors.champagneGold : AppColors.emeraldPrimaryLight,
              ),
              tooltip: 'Toggle Theme',
              onPressed: widget.onToggleTheme,
            ),
          ),
        ),
      ),
      destinations: const [
        NavigationRailDestination(
          icon: Icon(Icons.dashboard_outlined),
          selectedIcon: Icon(Icons.dashboard_rounded),
          label: Text('Dashboard'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.filter_list_outlined),
          selectedIcon: Icon(Icons.filter_list_rounded),
          label: Text('Screener'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.pie_chart_outline_rounded),
          selectedIcon: Icon(Icons.pie_chart_rounded),
          label: Text('Baskets'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.cleaning_services_outlined),
          selectedIcon: Icon(Icons.cleaning_services_rounded),
          label: Text('Purify'),
        ),
        NavigationRailDestination(
          icon: Icon(Icons.school_outlined),
          selectedIcon: Icon(Icons.school_rounded),
          label: Text('Academy'),
        ),
      ],
    );
  }
}
