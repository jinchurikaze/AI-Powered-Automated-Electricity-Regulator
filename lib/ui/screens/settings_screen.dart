import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../widgets/actions.dart';

/// Settings: limits and alerts, rate and billing cycle, privacy, server, and the demo controls.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final me = s.me ?? {};
    void go(Widget w) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => w));
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(padding: const EdgeInsets.only(bottom: 24), children: [
        ListTile(leading: const Icon(Icons.notifications_active_outlined), title: const Text('Limits and alerts'), onTap: () => go(const LimitsScreen())),
        ListTile(
          leading: const Icon(Icons.payments_outlined),
          title: const Text('Rate and billing cycle'),
          subtitle: Text('${peso(d(me['rate']))} per kWh · starts day ${i(me['cycleDay'])}'),
          onTap: () => go(const RateScreen()),
        ),
        ListTile(leading: const Icon(Icons.privacy_tip_outlined), title: const Text('Your data and privacy'), subtitle: const Text('Export or delete your data'), onTap: () => go(const DataScreen())),
        ListTile(leading: const Icon(Icons.dns_outlined), title: const Text('Server'), subtitle: Text(s.api.baseUrl)),
        const Divider(),
        if (s.simulated) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Text('SAMPLE HOUSEHOLD DEMO CONTROLS · clock ${dateTime(dt(me['now'])!)}', style: Theme.of(context).textTheme.labelSmall),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Wrap(spacing: 8, runSpacing: 8, children: [
              OutlinedButton(onPressed: () => run(context, () => s.demoAdvance(1)), child: const Text('+1 hour')),
              OutlinedButton(onPressed: () => run(context, s.demoDay), child: const Text('+1 day (log usual hours)')),
              OutlinedButton(onPressed: () => run(context, () => s.demoUse(80)), child: const Text('Use up to 80%')),
              OutlinedButton(onPressed: () => run(context, () => s.demoUse(100)), child: const Text('Reach 100%')),
              OutlinedButton(onPressed: () => run(context, s.demoMeter), child: const Text('Add a meter reading now')),
              OutlinedButton(onPressed: () => run(context, s.demoReset), child: const Text('Reload sample household')),
            ]),
          ),
        ],
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            Text('Signed in as ${me['email'] ?? ''}', textAlign: TextAlign.center),
            TextButton(
              onPressed: () async {
                await s.signOut();
                if (context.mounted) Navigator.of(context).popUntil((r) => r.isFirst);
              },
              child: const Text('Sign out'),
            ),
          ]),
        ),
      ]),
    );
  }
}

class RateScreen extends StatefulWidget {
  const RateScreen({super.key});

  @override
  State<RateScreen> createState() => _RateScreenState();
}

class _RateScreenState extends State<RateScreen> {
  final _rate = TextEditingController();
  int _day = 1;
  String? _error;

  @override
  void initState() {
    super.initState();
    final me = context.read<AppState>().me ?? {};
    _rate.text = d(me['rate']).toStringAsFixed(2);
    _day = i(me['cycleDay']) == 0 ? 1 : i(me['cycleDay']);
  }

  @override
  void dispose() {
    _rate.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.read<AppState>();
    return Scaffold(
      appBar: AppBar(title: const Text('Rate and billing cycle')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: _rate, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: 'Electricity rate per kWh (₱)', errorText: _error)),
        const SizedBox(height: 12),
        DropdownButtonFormField<int>(
          initialValue: _day,
          decoration: const InputDecoration(labelText: 'Billing cycle starts on day'),
          items: [for (var x = 1; x <= 31; x++) DropdownMenuItem(value: x, child: Text('$x'))],
          onChanged: (v) => setState(() => _day = v ?? 1),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: () async {
            try {
              await s.updateSettings(_rate.text, _day);
              if (context.mounted) Navigator.of(context).pop();
            } on ApiException catch (e) {
              setState(() => _error = e.message);
            }
          },
          child: const Text('Save'),
        ),
      ]),
    );
  }
}

class LimitsScreen extends StatefulWidget {
  const LimitsScreen({super.key});

  @override
  State<LimitsScreen> createState() => _LimitsScreenState();
}

class _LimitsScreenState extends State<LimitsScreen> {
  final _monthly = TextEditingController();
  final _daily = TextEditingController();
  String _mUnit = 'PESO';
  String _dUnit = 'KWH';
  bool _alerts = true;
  List<Json> _history = [];
  Map<String, String> _errors = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final r = await context.read<AppState>().limits();
    final m = obj(r['monthly'])!, dl = obj(r['daily'])!;
    setState(() {
      _monthly.text = i(m['active']) == 1 ? d(m['value']).toStringAsFixed(0) : '';
      _daily.text = i(dl['active']) == 1 ? d(dl['value']).toStringAsFixed(0) : '';
      _mUnit = '${m['unit']}';
      _dUnit = '${dl['unit']}';
      _alerts = r['alertsEnabled'] == true;
      _history = list(r['alerts']);
    });
  }

  @override
  void dispose() {
    _monthly.dispose();
    _daily.dispose();
    super.dispose();
  }

  Widget _unit(String v, ValueChanged<String> on) => SegmentedButton<String>(
        segments: const [ButtonSegment(value: 'KWH', label: Text('kWh')), ButtonSegment(value: 'PESO', label: Text('₱'))],
        selected: {v},
        onSelectionChanged: (x) => on(x.first),
      );

  @override
  Widget build(BuildContext context) {
    final s = context.read<AppState>();
    return Scaffold(
      appBar: AppBar(title: const Text('Limits and alerts')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Row(children: [
          Expanded(child: TextField(controller: _monthly, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: 'Monthly limit', hintText: 'Not set', errorText: _errors['monthly']))),
          const SizedBox(width: 8),
          _unit(_mUnit, (v) => setState(() => _mUnit = v)),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: TextField(controller: _daily, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: 'Daily limit', hintText: 'Not set', errorText: _errors['daily']))),
          const SizedBox(width: 8),
          _unit(_dUnit, (v) => setState(() => _dUnit = v)),
        ]),
        SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Warn me at 80% and 100%'), value: _alerts, onChanged: (v) => setState(() => _alerts = v)),
        FilledButton(
          onPressed: () async {
            try {
              await s.saveLimits({'monthly': _monthly.text, 'monthlyUnit': _mUnit, 'daily': _daily.text, 'dailyUnit': _dUnit, 'alertsEnabled': _alerts});
              setState(() => _errors = {});
              await _load();
              if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Limits saved.')));
            } on ApiException catch (e) {
              setState(() => _errors = e.errors);
            }
          },
          child: const Text('Save limits'),
        ),
        const SizedBox(height: 16),
        Text('ALERT HISTORY', style: Theme.of(context).textTheme.labelSmall),
        if (_history.isEmpty) const Text('No alerts yet.'),
        for (final a in _history)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text('${shortDate(DateTime.parse('${a['sent_at']}'.replaceFirst(' ', 'T')))} · ${i(a['threshold']) == 100 ? 'Limit reached' : 'Warning'} (${i(a['threshold'])}%, ${a['period']})'),
            trailing: Text(a['unit'] == 'PESO' ? peso(d(a['amount'])) : kwh(d(a['amount']), decimals: 1)),
          ),
      ]),
    );
  }
}

class DataScreen extends StatelessWidget {
  const DataScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.read<AppState>();
    return Scaffold(
      appBar: AppBar(title: const Text('Your data and privacy')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Your data is used only to run this app, in line with the Data Privacy Act of 2012 (RA 10173). Bill photos are read on your phone and are not uploaded.'),
        const SizedBox(height: 12),
        FutureBuilder<Json>(
          future: s.exportData(),
          builder: (c, snap) => SelectableText(snap.hasData ? const JsonEncoder.withIndent(' ').convert(snap.data) : 'Loading…',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
        ),
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: () async {
            final ok = await showDialog<bool>(
              context: context,
              builder: (c) => AlertDialog(
                title: const Text('Delete your account and all data?'),
                content: const Text('This cannot be undone.'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
                  FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Delete everything')),
                ],
              ),
            );
            if (ok == true && context.mounted) {
              await run(context, s.deleteAccount);
              if (context.mounted) Navigator.of(context).popUntil((r) => r.isFirst);
            }
          },
          child: const Text('Delete my account and data'),
        ),
      ]),
    );
  }
}
