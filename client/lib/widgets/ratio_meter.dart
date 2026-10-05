import 'package:flutter/material.dart';
import '../core/theme/colors.dart';
import '../models/screening_result.dart';

class RatioMeterWidget extends StatelessWidget {
  final RatioMeterData data;

  const RatioMeterWidget({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final maxRatio = data.thresholdPct * 1.5;
    final progress = (data.actualPct / maxRatio).clamp(0.0, 1.0);
    final thresholdPosition = (data.thresholdPct / maxRatio).clamp(0.0, 1.0);

    Color barColor;
    if (data.isCompliant) {
      barColor = data.isWarning
          ? (isDark ? AppColors.questionableAmberDark : AppColors.questionableAmberLight)
          : (isDark ? AppColors.compliantGreenDark : AppColors.compliantGreenLight);
    } else {
      barColor = isDark ? AppColors.nonCompliantCrimsonDark : AppColors.nonCompliantCrimsonLight;
    }

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8.0),
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkCard : AppColors.lightCard,
        borderRadius: BorderRadius.circular(12.0),
        border: Border.all(
          color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                data.metricName,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.0),
              ),
              Text(
                '${data.actualPct.toStringAsFixed(2)}% / <${data.thresholdPct.toStringAsFixed(0)}%',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 13.0,
                  color: barColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8.0),
          LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth;
              final markerLeft = (thresholdPosition * width).clamp(0.0, width > 2 ? width - 2 : 0.0);

              return Stack(
                children: [
                  // Track
                  Container(
                    height: 8.0,
                    width: width,
                    decoration: BoxDecoration(
                      color: isDark ? Colors.white10 : Colors.black12,
                      borderRadius: BorderRadius.circular(4.0),
                    ),
                  ),
                  // Value Bar
                  FractionallySizedBox(
                    widthFactor: progress,
                    child: Container(
                      height: 8.0,
                      decoration: BoxDecoration(
                        color: barColor,
                        borderRadius: BorderRadius.circular(4.0),
                      ),
                    ),
                  ),
                  // Threshold Marker Line
                  Positioned(
                    left: markerLeft,
                    top: 0,
                    bottom: 0,
                    child: Container(
                      width: 2.0,
                      color: isDark ? Colors.white38 : Colors.black38,
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 6.0),
          Text(
            '${data.numeratorLabel}: ₹${data.numeratorValueInrCr.toStringAsFixed(2)} Cr  ÷  ${data.denominatorLabel}: ₹${data.denominatorValueInrCr.toStringAsFixed(2)} Cr',
            style: TextStyle(
              fontSize: 11.0,
              color: isDark ? AppColors.darkTextMuted : AppColors.lightTextMuted,
            ),
          ),
        ],
      ),
    );
  }
}
