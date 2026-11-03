import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../widgets/common.dart';

/// Wireframe 8 – What-if simulator (Feature 12). Each change is sent to the server,
/// which computes the monthly change and the inverter's payback.
class WhatIfScreen extends StatefulWidget {
  const WhatIfScreen({super.key});

  @override
  State<WhatIfScreen> createState() => _WhatIfScreenState();
}

class _WhatIfScreenState extends State<WhatIfScreen> {
  final Map<String, Json> _changes = {};
  double _saving = 35;
  final _extra = TextEditingController(text: '12000');
  Json? _d;

  @override
  void initState() {
    super.initState();
    _calc();
  }

  @override
  void dispose() {
    _extra.dispose();
    super.dispose();
  }

  Future<void> _calc() async {
    try {
      final r = await context.read<AppState>().whatIf(_changes, _saving, double.tryParse(_extra.text.replaceAll(',', '')) ?? 0);
      if (mounted) setState(() => _d = r);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  static String _label(double h) => h == 0 ? 'no change' : '${h > 0 ? '+' : '−'}${hours(h.abs())}';

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_d == null) return Scaffold(appBar: AppBar(title: const Text('What if…')), body: const Center(child: CircularProgressIndicator()));
    final r = obj(_d!['result'])!;
    final good = d(r['monthlyPeso']) <= 0;
    final anyInverter = _changes.values.any((c) => c['inv'] == true);
    return Scaffold(
      appBar: AppBar(title: const Text('What if…')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        InfoCard(
          label: d(r['monthlyPeso']) < 0 ? 'You would save each month' : (d(r['monthlyPeso']) > 0 ? 'You would pay more each month' : 'Move a slider to see the change'),
          color: good ? Colors.green.withOpacity(0.10) : cs.error.withOpacity(0.10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(peso(d(r['monthlyPeso']).abs()), key: const Key('whatIfPeso'),
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, color: good ? Colors.green.shade800 : cs.error)),
            if (r['payback'] != null)
              Text('Inverter pays for itself in about ${d(r['payback']).toStringAsFixed(0)} months.', style: const TextStyle(fontWeight: FontWeight.w600)),
          ]),
        ),
        const SizedBox(height: 12),
        for (final a in list(_d!['appliances']))
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 6),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text('${appEmoji('${a['type']}')} ${a['type']}', style: const TextStyle(fontWeight: FontWeight.w700))),
                  Text('now ${hours(d(a['usualH']))} a day'),
                ]),
                Row(children: [
                  Expanded(
                    child: Slider(
                      min: -4,
                      max: 2,
                      divisions: 12,
                      value: d(_changes['${a['id']}']?['dh']),
                      label: _label(d(_changes['${a['id']}']?['dh'])),
                      onChanged: (v) => setState(() => (_changes['${a['id']}'] ??= {'dh': 0.0, 'inv': false})['dh'] = v),
                      onChangeEnd: (_) => _calc(),
                    ),
                  ),
                  SizedBox(width: 72, child: Text(_label(d(_changes['${a['id']}']?['dh'])), textAlign: TextAlign.end)),
                ]),
                if (a['inverterOption'] == true)
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Switch to an inverter model'),
                    value: _changes['${a['id']}']?['inv'] == true,
                    onChanged: (v) {
                      setState(() => (_changes['${a['id']}'] ??= {'dh': 0.0, 'inv': false})['inv'] = v ?? false);
                      _calc();
                    },
                  ),
              ]),
            ),
          ),
        if (anyInverter) ...[
          Text('Inverter saves about ${_saving.round()}%'),
          Slider(min: 10, max: 50, divisions: 8, value: _saving, onChanged: (v) => setState(() => _saving = v), onChangeEnd: (_) => _calc()),
          TextField(
            controller: _extra,
            keyboardType: TextInputType.number,
            onSubmitted: (_) => _calc(),
            decoration: const InputDecoration(labelText: 'Extra cost of the inverter model (₱)'),
          ),
        ],
        const SizedBox(height: 12),
        Text('Based on your average use in the last 14 days. Inverter savings vary by model.', style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}
