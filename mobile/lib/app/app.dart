import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/app/router.dart';

class BiletFlowVerifyApp extends ConsumerWidget {
  const BiletFlowVerifyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'BiletFlow Verify',
      debugShowCheckedModeBanner: false,
      theme: _theme(Brightness.light),
      darkTheme: _theme(Brightness.dark),
      routerConfig: ref.watch(routerProvider),
    );
  }

  static ThemeData _theme(Brightness brightness) {
    const yellow = Color(0xFFF2EF1D);
    final dark = brightness == Brightness.dark;
    final background = dark ? Colors.black : Colors.white;
    final foreground = dark ? Colors.white : Colors.black;
    final panel = dark ? const Color(0xFF1A1A1A) : const Color(0xFFF3F3F3);
    final chip = dark ? const Color(0xFF333333) : const Color(0xFFEBEBEB);
    final line = dark ? const Color(0xFF2A2A2A) : const Color(0xFFE4E4E4);
    final muted = dark ? const Color(0x9EFFFFFF) : const Color(0xFF666666);
    final corners = BorderRadius.circular(8);

    const buttonText = TextStyle(
      fontSize: 13,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.8,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      fontFamily: 'BiletSans',
      scaffoldBackgroundColor: background,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: foreground,
        onPrimary: background,
        secondary: yellow,
        onSecondary: Colors.black,
        surface: background,
        onSurface: foreground,
        surfaceContainerHighest: panel,
        outline: line,
        error: const Color(0xFFC62828),
        onError: Colors.white,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 52),
          shape: const StadiumBorder(),
          textStyle: buttonText,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 52),
          backgroundColor: chip,
          foregroundColor: foreground,
          side: BorderSide.none,
          shape: const StadiumBorder(),
          textStyle: buttonText,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: panel,
        labelStyle: TextStyle(color: muted),
        border: OutlineInputBorder(
          borderRadius: corners,
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: corners,
          borderSide: BorderSide(color: dark ? yellow : Colors.black, width: 2),
        ),
      ),
      cardTheme: CardThemeData(
        color: panel,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: corners),
      ),
      dividerTheme: DividerThemeData(color: line, thickness: 1),
      chipTheme: ChipThemeData(
        backgroundColor: chip,
        selectedColor: yellow,
        side: BorderSide.none,
        shape: RoundedRectangleBorder(borderRadius: corners),
      ),
    );
  }
}
