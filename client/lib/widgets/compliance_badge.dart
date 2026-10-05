import 'package:flutter/material.dart';
import '../core/theme/colors.dart';
import '../models/stock_model.dart';

class ComplianceBadge extends StatelessWidget {
  final ComplianceStatus status;
  final String? standardLabel; // 'AAOIFI' or 'TASIS'
  final bool compact;

  const ComplianceBadge({
    super.key,
    required this.status,
    this.standardLabel,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    Color fg;
    Color bg;
    IconData icon;
    String label;

    switch (status) {
      case ComplianceStatus.compliant:
        fg = isDark ? AppColors.compliantGreenDark : AppColors.compliantGreenLight;
        bg = isDark ? AppColors.compliantBgDark : AppColors.compliantBgLight;
        icon = Icons.check_circle_rounded;
        label = 'COMPLIANT';
        break;
      case ComplianceStatus.questionable:
        fg = isDark ? AppColors.questionableAmberDark : AppColors.questionableAmberLight;
        bg = isDark ? AppColors.questionableBgDark : AppColors.questionableBgLight;
        icon = Icons.warning_amber_rounded;
        label = 'QUESTIONABLE';
        break;
      case ComplianceStatus.nonCompliant:
        fg = isDark ? AppColors.nonCompliantCrimsonDark : AppColors.nonCompliantCrimsonLight;
        bg = isDark ? AppColors.nonCompliantBgDark : AppColors.nonCompliantBgLight;
        icon = Icons.cancel_rounded;
        label = 'NON-COMPLIANT';
        break;
    }

    final displayText = standardLabel != null ? '$standardLabel: $label' : label;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOutCubic,
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8.0 : 12.0,
        vertical: compact ? 4.0 : 6.0,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20.0),
        border: Border.all(color: fg.withOpacity(0.5), width: 1.0),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: compact ? 12.0 : 16.0, color: fg),
          SizedBox(width: compact ? 4.0 : 6.0),
          Text(
            displayText,
            style: TextStyle(
              fontSize: compact ? 10.0 : 12.0,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
              color: fg,
            ),
          ),
        ],
      ),
    );
  }
}
