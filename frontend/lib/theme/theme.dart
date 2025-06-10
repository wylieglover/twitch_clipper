import 'package:flutter/material.dart';

final lightTheme = ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xFF9146FF), // Twitch purple
    brightness: Brightness.light,
  ),
  cardTheme: CardThemeData(
    elevation: 2,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
  ),
);

final darkTheme = ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xFF9146FF),
    brightness: Brightness.dark,
  ),
  scaffoldBackgroundColor: const Color(0xFF0E0E10),
  cardTheme: CardThemeData(
    color: const Color(0xFF18181B),
    elevation: 4,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF1F1F23),
    elevation: 0,
  ),
);
