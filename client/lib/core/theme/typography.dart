import 'dart:ui' show FontFeature;
import 'package:flutter/material.dart';

/// Apple Human Interface Guidelines Typography Hierarchy
class AppTypography {
  AppTypography._();

  static const List<String> fontFamilyFallback = [
    '-apple-system',
    'SF Pro Display',
    'SF Pro Text',
    'Roboto',
    'Segoe UI',
    'sans-serif',
  ];

  /// Tabular figure font feature for numerical/financial metrics to prevent width jitter
  static List<FontFeature> get tabularFigures => const [
    FontFeature.tabularFigures(),
  ];

  static TextStyle tabularNumeric({
    double fontSize = 15.0,
    FontWeight fontWeight = FontWeight.w600,
    Color? color,
    double? letterSpacing,
  }) {
    return TextStyle(
      fontFamilyFallback: fontFamilyFallback,
      fontSize: fontSize,
      fontWeight: fontWeight,
      letterSpacing: letterSpacing ?? -0.2,
      color: color,
      fontFeatures: const [FontFeature.tabularFigures()],
    );
  }

  static TextTheme createTextTheme(Color primary, Color secondary, Color muted) {
    return TextTheme(
      displayLarge: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 34.0,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.37,
        color: primary,
      ),
      displayMedium: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 28.0,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.36,
        color: primary,
      ),
      titleLarge: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 22.0,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.35,
        color: primary,
      ),
      titleMedium: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 17.0,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.41,
        color: primary,
      ),
      headlineMedium: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 15.0,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.24,
        color: secondary,
      ),
      bodyLarge: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 17.0,
        fontWeight: FontWeight.w400,
        letterSpacing: -0.41,
        color: primary,
      ),
      bodyMedium: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 14.0,
        fontWeight: FontWeight.w400,
        letterSpacing: -0.08,
        color: secondary,
      ),
      labelLarge: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 13.0,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.08,
        color: primary,
      ),
      labelSmall: TextStyle(
        fontFamilyFallback: fontFamilyFallback,
        fontSize: 11.0,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.06,
        color: muted,
      ),
    );
  }
}
