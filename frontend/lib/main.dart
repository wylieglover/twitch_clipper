import 'package:flutter/material.dart';
import 'theme/theme.dart';
import 'screens/editor_screen.dart';

void main() => runApp(const TwitchClipEditorApp());

class TwitchClipEditorApp extends StatefulWidget {
  const TwitchClipEditorApp({super.key});
  @override
  State<TwitchClipEditorApp> createState() => _TwitchClipEditorAppState();
}

class _TwitchClipEditorAppState extends State<TwitchClipEditorApp> {
  ThemeMode _themeMode = ThemeMode.dark;

  @override
  Widget build(BuildContext ctx) {
    return MaterialApp(
      title: 'Twitch Clip AI Editor',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: _themeMode,
      home: EditorScreen(onToggleTheme: () {
        setState(() => _themeMode =
            _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark);
      }),
    );
  }
}
