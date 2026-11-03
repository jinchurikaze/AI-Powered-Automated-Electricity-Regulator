import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../theme.dart';
import '../widgets/actions.dart';
import '../widgets/common.dart';
import 'app_shell.dart';
import 'whatif_screen.dart';

/// Wireframe 7 – Save: expected bill (weather-aware forecast), daily plan, top 3 tips (Features 8, 9, 10).
class SaveScreen extends StatelessWidget {
  const SaveScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final t = Theme.of(context).textTheme;
    final v = s.save ?? {};
    final f = obj(v['forecast']);
    final plan = obj(v['plan']);
    final limit = v['limitPeso'] == null ? null : d(v['limitPeso']);
    final tips = list(v['tips']);
    return ListView(padding: const EdgeInsets.only(bottom: 24), children: [
      const PageHeader('Save'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (f == null)
            InfoCard(
              label: 'Forecast coming soon',
              child: Text('We need ${i(v['need'])} more day${i(v['need']) == 1 ? '' : 's'} of records before we can predict your bill.'),
            )
          else
            InfoCard(
              label: '',
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Expected bill this month', style: t.bodySmall),
                Text(peso(d(f['projCost'])), style: t.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                if (limit != null)
                  d(f['projCost']) > limit
                      ? StatusChip('${peso(d(f['projCost']) - limit)} over your budget', bad)
                      : StatusChip('${peso(limit - d(f['projCost']))} under your budget', good),
                const SizedBox(height: 12),
                Text('Next 7 days, with the expected high temperature', style: t.bodySmall),
                const SizedBox(height: 6),
                BarChart(
                  values: [for (final x in list(f['next'])) d(x['kwh'])],
                  labels: [for (final x in list(f['next'])) x['tmax'] == null ? '${dt(x['day'])!.day}' : '${dt(x['day'])!.day} · ${d(x['tmax']).round()}°'],
                  dashedForecast: true,
                ),
                if (f['perDegree'] != null && d(f['perDegree']) > 0)
                  Text('Hot days cost more: each 1°C hotter adds about ${d(f['perDegree']).toStringAsFixed(1)} kWh a day in your home.'),
                HowCalculated('Model: ${f['model']}${f['mae'] == null ? '' : '. Average error ${d(f['mae']).toStringAsFixed(1)} kWh a day over the last week'}. '
                    'Forecast ${kwh(d(f['projKwh']), decimals: 1)} for the month.'),
              ]),
            ),
          if (plan != null) ...[
            const SizedBox(height: 12),
            InfoCard(
              label: 'Daily plan',
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (plan['needed'] != true)
                  const Text("You're on track. No cuts needed today.")
                else ...[
                  Text('To stay within ${limit == null ? 'your budget' : peso(limit)}, use these appliances a little less each day:'),
                  const SizedBox(height: 6),
                  for (final it in list(plan['items']))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(children: [
                        Expanded(child: Text('${appEmoji('${it['type']}')} ${it['type']}')),
                        Text('${hours(d(it['allowH']))} a day', style: const TextStyle(fontWeight: FontWeight.w800)),
                      ]),
                    ),
                ],
                SwitchListTile(
                  key: const Key('planSwitch'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Plan and reminders', style: TextStyle(fontWeight: FontWeight.w700)),
                  subtitle: const Text("We'll remind you 15 minutes before an appliance uses up today's hours."),
                  value: plan['active'] == true,
                  onChanged: (on) => run(context, () => s.setPlan(on)),
                ),
                HowCalculated('About ${kwh(d(plan['daily']), decimals: 1)} a day for the ${i(plan['daysLeft'])} days left, '
                    'including ${kwh(d(plan['essential']), decimals: 1)} for essential appliances like the refrigerator. '
                    'Other appliances get ${(d(plan['scale']) * 100).round()}% of their usual hours.'),
              ]),
            ),
          ],
          const SizedBox(height: 16),
          if (tips.isNotEmpty) Text('Ways to save', style: t.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          if (tips.isEmpty) const Text("No tips right now. Keep logging and we'll find some."),
          for (final r in tips.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: InfoCard(
                label: '${r['title']}',
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${r['body']} Saves about ${peso(d(r['peso']))}${r['stay'] == true ? ' this month' : ' a month'}.'),
                  const SizedBox(height: 8),
                  Row(children: [
                    OutlinedButton(
                      onPressed: () => run(context, () => s.tipFeedback('${r['key']}', 'HELPFUL')),
                      child: Text(r['status'] == 'HELPFUL' ? 'Marked helpful' : 'Helpful'),
                    ),
                    const SizedBox(width: 8),
                    TextButton(onPressed: () => run(context, () => s.tipFeedback('${r['key']}', 'DISMISSED')), child: const Text('Dismiss')),
                  ]),
                ]),
              ),
            ),
          FilledButton(
            key: const Key('whatIf'),
            style: FilledButton.styleFrom(backgroundColor: sun, foregroundColor: Colors.black87),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const WhatIfScreen())),
            child: const Text('What if I changed something?'),
          ),
        ]),
      ),
    ]);
  }
}
