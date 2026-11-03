import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../theme.dart';
import '../widgets/actions.dart';
import '../widgets/common.dart';
import 'app_shell.dart';
import 'bill_form_screen.dart';

/// Wireframe 9 – Check: bill and meter readings against recorded use (Feature 11).
class CheckScreen extends StatefulWidget {
  const CheckScreen({super.key});

  @override
  State<CheckScreen> createState() => _CheckScreenState();
}

class _CheckScreenState extends State<CheckScreen> {
  final _reading = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _reading.dispose();
    super.dispose();
  }

  Widget _row(String k, String v, {Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(children: [Expanded(child: Text(k)), Text(v, style: TextStyle(fontWeight: FontWeight.w600, color: color))]),
      );

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final c = s.check ?? {};
    final b = obj(c['bill']);
    final m = obj(c['meter']);
    final cs = Theme.of(context).colorScheme;
    return ListView(padding: const EdgeInsets.only(bottom: 24), children: [
      const PageHeader('Check'),
      const Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 12), child: Text('Did the app catch everything? Compare it with your real bill.')),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          InfoCard(
            label: b == null ? 'Your last bill' : 'Bill for ${shortDate(dt(b['start'])!)} – ${longDate(dt(b['end'])!)}',
            child: b == null
                ? const Text('Add your last electric bill to see how much the app caught.')
                : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('The app recorded ${d(b['coverage']).round()}% of your bill', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 6),
                    ClipRRect(borderRadius: BorderRadius.circular(6), child: LinearProgressIndicator(value: (d(b['coverage']) / 100).clamp(0, 1).toDouble(), minHeight: 10)),
                    const SizedBox(height: 8),
                    _row('Your bill', '${kwh(d(b['kwh']), decimals: 0)} · ${peso(d(b['amount']))}'),
                    _row('Recorded in the app', kwh(d(b['recordedKwh']), decimals: 0)),
                    _row('Missed', 'about ${peso(d(b['missingPeso']))}', color: cs.error),
                    if (d(b['coverage']) < 90) const Text("Some use wasn't logged. Try starting timers for appliances you often forget."),
                    if (b['rateDiffers'] == true) ...[
                      const SizedBox(height: 8),
                      StatusBox(
                        title: 'Your bill works out to ${peso(d(b['rate']))}/kWh.',
                        body: 'The app is using ${peso(d(s.me?['rate']))}. Use the bill\'s rate for better estimates?',
                        color: warn,
                      ),
                      const SizedBox(height: 8),
                      OutlinedButton(
                        key: const Key('useRate'),
                        onPressed: () => run(context, s.useBillRate, done: 'Rate updated.'),
                        child: Text('Use ${peso(d(b['rate']))} as my rate'),
                      ),
                    ],
                    HowCalculated('Missed = ${kwh(d(b['kwh']), decimals: 0)} on the bill − ${kwh(d(b['recordedKwh']), decimals: 0)} recorded = '
                        '${kwh(d(b['missingKwh']), decimals: 0)}. The rate is the bill\'s total amount ÷ kWh, so it includes all charges.'),
                  ]),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            key: const Key('addBill'),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const BillFormScreen())),
            icon: const Icon(Icons.document_scanner_outlined),
            label: const Text('Scan or enter a bill'),
          ),
          const SizedBox(height: 16),
          InfoCard(
            label: 'Meter readings (optional)',
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (m == null)
                const Text('Write down the number on your electric meter now, then again in a few days.')
              else ...[
                Text('${shortDate(DateTime.parse('${m['from']}'.replaceFirst(' ', 'T')))} → ${shortDate(DateTime.parse('${m['to']}'.replaceFirst(' ', 'T')))}: '
                    'the meter counted ${kwh(d(m['measured']), decimals: 1)}'),
                Text('The app recorded ${kwh(d(m['recorded']), decimals: 1)} (${d(m['coverage']).round()}%)'),
                if (d(m['missing']) > 0) Text('Not recorded: ${kwh(d(m['missing']), decimals: 1)}', style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                  child: TextField(
                    key: const Key('meterReading'),
                    controller: _reading,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(labelText: 'Meter reading now (kWh)', errorText: _error, errorMaxLines: 3),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () async {
                    try {
                      await s.addMeterReading(_reading.text);
                      _reading.clear();
                      setState(() => _error = null);
                    } on ApiException catch (e) {
                      setState(() => _error = e.message);
                    }
                  },
                  child: const Text('Save'),
                ),
              ]),
            ]),
          ),
        ]),
      ),
    ]);
  }
}
