import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../theme.dart';
import '../widgets/actions.dart';
import '../widgets/common.dart';
import 'app_shell.dart';

/// Wireframe 3 – Appliance list with start/stop timers (REQ-APL-5, REQ-MON-1).
class AppliancesScreen extends StatelessWidget {
  const AppliancesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final apps = list(s.appliances?['appliances']);
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const ApplianceFormScreen())),
        icon: const Icon(Icons.add),
        label: const Text('Add'),
      ),
      body: ListView(padding: const EdgeInsets.only(bottom: 96), children: [
        const PageHeader('Appliances'),
        const Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 8), child: Text('Tap Start when you turn something on and Stop when you turn it off.')),
        if (apps.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No appliances yet. Tap Add to register one.'))),
        for (final a in apps)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Card(
              margin: EdgeInsets.zero,
              child: ListTile(
                minVerticalPadding: 12,
                leading: CircleAvatar(radius: 24, backgroundColor: a['running'] == true ? sun.withValues(alpha: 0.35) : Theme.of(context).colorScheme.primaryContainer, child: Text(appEmoji('${a['type']}'), style: const TextStyle(fontSize: 22))),
                title: Text('${a['type']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                subtitle: Text(a['running'] == true ? 'On for ${hours(d(a['elapsedH']))}' : '${watts(d(a['watt']))} · today ${peso(d(a['todayKwh']) * d(s.me?['rate']))}${a['essential'] == true ? ' · essential' : ''}'),
                trailing: a['running'] == true
                    ? OutlinedButton(
                        key: Key('stop-${a['id']}'),
                        onPressed: () => run(context, () => s.stopTimer(i(a['id']))),
                        child: const Text('Stop'),
                      )
                    : FilledButton(
                        key: Key('start-${a['id']}'),
                        style: FilledButton.styleFrom(minimumSize: const Size(72, 40)),
                        onPressed: () => run(context, () => s.startTimer(i(a['id']))),
                        child: const Text('Start'),
                      ),
                onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ApplianceDetailScreen(id: i(a['id'])))),
              ),
            ),
          ),
        const Padding(padding: EdgeInsets.all(16), child: Text('Tap Start when you turn an appliance on and Stop when you turn it off.', textAlign: TextAlign.center)),
      ]),
    );
  }
}

/// Wireframe 4 – Add / edit appliance (REQ-APL-1, REQ-APL-2).
class ApplianceFormScreen extends StatefulWidget {
  final Json? appliance;
  const ApplianceFormScreen({super.key, this.appliance});

  @override
  State<ApplianceFormScreen> createState() => _ApplianceFormScreenState();
}

class _ApplianceFormScreenState extends State<ApplianceFormScreen> {
  static const types = ['Air conditioner', 'Refrigerator', 'Electric fan', 'Television', 'Washing machine', 'Rice cooker',
    'Computer', 'Lights', 'Water dispenser', 'Other'];
  final _brand = TextEditingController();
  final _model = TextEditingController();
  final _watt = TextEditingController();
  final _loc = TextEditingController();
  final _hours = TextEditingController();
  String _type = '';
  bool _essential = false;
  Map<String, String> _errors = {};

  @override
  void initState() {
    super.initState();
    final a = widget.appliance;
    if (a != null) {
      _type = '${a['type']}';
      _brand.text = '${a['brand'] ?? ''}';
      _model.text = '${a['model'] ?? ''}';
      _watt.text = '${i(a['watt'])}';
      _loc.text = '${a['location'] ?? ''}';
      _hours.text = d(a['hours']) == 0 ? '' : '${d(a['hours'])}';
      _essential = a['essential'] == true;
    }
  }

  @override
  void dispose() {
    for (final c in [_brand, _model, _watt, _loc, _hours]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final s = context.read<AppState>();
    try {
      await s.saveAppliance({
        'type': _type,
        'brand': _brand.text,
        'model': _model.text,
        'watt': _watt.text,
        'location': _loc.text,
        'hours': _hours.text,
        'essential': _essential,
      }, id: widget.appliance == null ? null : i(widget.appliance!['id']));
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      setState(() => _errors = e.errors);
    }
  }

  Future<void> _delete() async {
    final s = context.read<AppState>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text('Delete $_type?'),
        content: const Text('It will be removed from your list. Its past usage stays in your summaries.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true && mounted) {
      if (await run(context, () => s.deleteAppliance(i(widget.appliance!['id']))) && mounted) {
        Navigator.of(context).popUntil((r) => r.isFirst);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.appliance != null;
    return Scaffold(
      appBar: AppBar(title: Text(editing ? 'Edit appliance' : 'Add appliance')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        DropdownButtonFormField<String>(
          initialValue: _type.isEmpty ? null : _type,
          decoration: InputDecoration(labelText: 'Type *', errorText: _errors['type']),
          items: [for (final t in types) DropdownMenuItem(value: t, child: Text(t))],
          onChanged: (v) => setState(() => _type = v ?? ''),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: TextField(controller: _brand, decoration: const InputDecoration(labelText: 'Brand'))),
          const SizedBox(width: 12),
          Expanded(child: TextField(controller: _model, decoration: const InputDecoration(labelText: 'Model'))),
        ]),
        const SizedBox(height: 12),
        TextField(
          key: const Key('wattage'),
          controller: _watt,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(labelText: 'Rated wattage (W) *', helperText: '1 to 10,000 W · printed on the appliance label', errorText: _errors['watt']),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: TextField(controller: _loc, decoration: const InputDecoration(labelText: 'Location'))),
          const SizedBox(width: 12),
          Expanded(
            child: TextField(
              controller: _hours,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: 'Usual hours a day', errorText: _errors['hours']),
            ),
          ),
        ]),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Essential appliance'),
          subtitle: const Text('Never cut in the usage plan, e.g. the refrigerator'),
          value: _essential,
          onChanged: (v) => setState(() => _essential = v),
        ),
        const SizedBox(height: 12),
        FilledButton(onPressed: _save, child: Text(editing ? 'Save changes' : 'Save appliance')),
        if (editing) ...[
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _delete, child: const Text('Delete appliance')),
        ],
      ]),
    );
  }
}

/// Wireframe 5 – Appliance detail: timer, hour logging, today's plan, recent entries
/// (REQ-MON-1 to REQ-MON-5, Feature 10).
class ApplianceDetailScreen extends StatefulWidget {
  final int id;
  const ApplianceDetailScreen({super.key, required this.id});

  @override
  State<ApplianceDetailScreen> createState() => _ApplianceDetailScreenState();
}

class _ApplianceDetailScreenState extends State<ApplianceDetailScreen> {
  final _hours = TextEditingController();
  Json? _d;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _hours.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final r = await context.read<AppState>().appliance(widget.id);
      if (mounted) setState(() => _d = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _message = e.message);
    }
  }

  Future<void> _do(Future<Json> Function() f) async {
    try {
      final r = await f();
      setState(() {
        _d = r;
        _message = null;
      });
    } on ApiException catch (e) {
      setState(() => _message = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final cs = Theme.of(context).colorScheme;
    if (_d == null) return Scaffold(appBar: AppBar(), body: Center(child: _message == null ? const CircularProgressIndicator() : Text(_message!)));
    final a = obj(_d!['appliance'])!;
    final running = a['running'] == true;
    final plan = obj(_d!['plan']);
    final recent = list(_d!['recent']);
    final started = dt(a['timerStart']);
    return Scaffold(
      appBar: AppBar(title: Text('${a['type']}', style: const TextStyle(fontWeight: FontWeight.w800)), actions: [
        TextButton(
          onPressed: () => Navigator.of(context)
              .push(MaterialPageRoute<void>(builder: (_) => ApplianceFormScreen(appliance: a)))
              .then((_) => _load()),
          child: const Text('Edit'),
        ),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('${watts(d(a['watt']))} rated · ${a['brand']} ${a['model']}'),
        Text('${'${a['location']}'.isEmpty ? 'No location' : a['location']}${a['essential'] == true ? ' · essential' : ''}'),
        const SizedBox(height: 12),
        InfoCard(
          label: running && started != null ? 'Timer running since ${time(started)}' : 'Usage timer',
          child: Column(children: [
            Text(running ? hours(d(a['elapsedH'])) : 'Off', style: Theme.of(context).textTheme.headlineMedium),
            if (running) Text('${kwh(d(a['watt']) * d(a['elapsedH']) / 1000)} so far'),
            const SizedBox(height: 8),
            SizedBox(
              width: 116,
              height: 116,
              child: FilledButton(
                key: const Key('timer'),
                style: FilledButton.styleFrom(shape: const CircleBorder(), backgroundColor: running ? cs.error : Colors.green),
                onPressed: () => _do(() => running ? s.stopTimer(widget.id) : s.startTimer(widget.id)),
                child: Text(running ? 'STOP' : 'START', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
              ),
            ),
            Text(running ? 'Tap when you turn it off' : 'Tap when you turn it on'),
            if (plan != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                    d(plan['leftH']) > 0
                        ? 'Today\'s plan: ${hours(d(plan['allowH']))} · ${hours(d(plan['leftH']))} left'
                        : 'Today\'s plan of ${hours(d(plan['allowH']))} is used up',
                    style: TextStyle(fontWeight: FontWeight.w600, color: d(plan['leftH']) > 0 ? null : cs.error)),
              ),
          ]),
        ),
        const SizedBox(height: 12),
        InfoCard(
          label: 'Forgot the timer? Log hours for today',
          child: Row(children: [
            Expanded(
              child: TextField(
                key: const Key('logHours'),
                controller: _hours,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(hintText: d(a['hours']) > 0 ? 'Usual: ${d(a['hours'])} h' : 'Hours, e.g. 5', errorText: _message),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: () async {
                await _do(() => s.logHours(widget.id, _hours.text));
                if (_message == null) _hours.clear();
              },
              child: const Text('Log'),
            ),
          ]),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: InfoCard(label: 'Today', child: Text(kwh(d(a['todayKwh']))))),
          const SizedBox(width: 12),
          Expanded(child: InfoCard(label: 'This cycle', child: Text('${kwh(d(_d!['cycleKwh']), decimals: 1)} · ${peso(d(_d!['cycleCost']))}'))),
        ]),
        const SizedBox(height: 12),
        InfoCard(
          label: 'Recent entries',
          child: Column(children: [
            if (recent.isEmpty) const Text('No entries yet.'),
            for (final r in recent)
              Row(children: [
                Expanded(child: Text('${shortDate(dt(r['ts'])!)} · ${hours(d(r['hours']))} · ${kwh(d(r['kwh']))}')),
                StatusChip(r['src'] == 'TIMER' ? 'Timer' : 'Logged', r['src'] == 'TIMER' ? Colors.green : Colors.blueGrey),
              ]),
          ]),
        ),
      ]),
    );
  }
}
