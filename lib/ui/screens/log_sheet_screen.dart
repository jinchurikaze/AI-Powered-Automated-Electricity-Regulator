import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';

/// "Log today's hours" – one screen for all appliances without a running timer (REQ-MON-6).
class LogSheetScreen extends StatefulWidget {
  const LogSheetScreen({super.key});

  @override
  State<LogSheetScreen> createState() => _LogSheetScreenState();
}

class _LogSheetScreenState extends State<LogSheetScreen> {
  final Map<String, TextEditingController> _c = {};
  Map<String, String> _errors = {};

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final s = context.read<AppState>();
    try {
      await s.logMany({for (final e in _c.entries) e.key: e.value.text});
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      // Entries that were saved are cleared so a retry does not log them twice.
      for (final x in _c.entries) {
        if (!e.errors.containsKey(x.key)) x.value.clear();
      }
      setState(() => _errors = e.errors);
      await s.refreshAll();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final apps = list(s.appliances?['appliances']).where((a) => a['running'] != true).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Log today\'s hours')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Enter the hours each appliance was on today. Leave a box empty to skip it.'),
        const SizedBox(height: 12),
        for (final a in apps)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${a['type']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text('${watts(d(a['watt']))}${a['loggedToday'] == true ? ' · already logged today' : ''}', style: Theme.of(context).textTheme.bodySmall),
                ]),
              ),
              SizedBox(
                width: 110,
                child: TextField(
                  key: Key('log-${a['id']}'),
                  controller: _c.putIfAbsent('${a['id']}', TextEditingController.new),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(
                    hintText: d(a['hours']) > 0 ? '${d(a['hours'])} h' : 'hours',
                    errorText: _errors['${a['id']}'],
                    errorMaxLines: 3,
                  ),
                ),
              ),
            ]),
          ),
        FilledButton(onPressed: _save, child: const Text('Save hours')),
      ]),
    );
  }
}
