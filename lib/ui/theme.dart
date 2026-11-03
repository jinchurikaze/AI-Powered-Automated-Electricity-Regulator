import 'package:flutter/material.dart';

/// Calm blue with a warm yellow accent, rounded shapes, and larger text (same look as the web pages).
const brandBlue = Color(0xFF2F5BD3);
const sun = Color(0xFFFFC24B);
const good = Color(0xFF1E9E6A);
const warn = Color(0xFFC77700);
const bad = Color(0xFFD04040);

ThemeData appTheme(Brightness b) {
  final dark = b == Brightness.dark;
  final cs = ColorScheme.fromSeed(seedColor: brandBlue, brightness: b, primary: dark ? const Color(0xFF8FB0FF) : brandBlue, error: bad);
  final base = ThemeData(colorScheme: cs, useMaterial3: true, brightness: b);
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(22));
  return base.copyWith(
    scaffoldBackgroundColor: dark ? const Color(0xFF111827) : const Color(0xFFEEF2F7),
    cardTheme: CardThemeData(elevation: 0, color: dark ? const Color(0xFF1C2433) : Colors.white, shape: shape, margin: EdgeInsets.zero),
    textTheme: base.textTheme.apply(fontSizeFactor: 1.05),
    filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size(48, 52), shape: const StadiumBorder(), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800))),
    outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48), shape: const StadiumBorder(), textStyle: const TextStyle(fontWeight: FontWeight.w700))),
    inputDecorationTheme: InputDecorationTheme(filled: true, border: OutlineInputBorder(borderRadius: BorderRadius.circular(14))),
    navigationBarTheme: NavigationBarThemeData(backgroundColor: dark ? const Color(0xFF1C2433) : Colors.white, indicatorColor: cs.primaryContainer),
  );
}
