import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'state/app_state.dart';
import 'ui/screens/app_shell.dart';
import 'ui/screens/connect_screen.dart';
import 'ui/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  await state.init();
  runApp(ChangeNotifierProvider.value(value: state, child: const ElectricityRegulatorApp()));
}

class ElectricityRegulatorApp extends StatelessWidget {
  const ElectricityRegulatorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Electricity Regulator',
      debugShowCheckedModeBanner: false,
      theme: appTheme(Brightness.light),
      darkTheme: appTheme(Brightness.dark),
      home: Consumer<AppState>(
        builder: (context, s, _) => !s.ready
            ? const Scaffold(body: Center(child: CircularProgressIndicator()))
            : (s.signedIn ? const AppShell() : const ConnectScreen()),
      ),
    );
  }
}
