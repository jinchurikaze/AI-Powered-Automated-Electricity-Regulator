import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../theme.dart';
import '../widgets/actions.dart';
import '../widgets/common.dart';
import 'app_shell.dart';
import 'log_sheet_screen.dart';

/// Wireframe 2 – Home (REQ-MON-1, REQ-DSH-1, REQ-CST-2, REQ-HCA-2).
/// Three things only: this month's budget, what is on right now, and one tip.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final h = s.home ?? {};
    final t = Theme.of(context).textTheme;
    final running = list(h['running']);
    final lim = obj(h['limit']);
    final limitPeso = h['limitPeso'] == null ? null : d(h['limitPeso']);
    final fcCost = d(h['forecastCost']);
    final plan = obj(h['plan']);
    final tip = obj(h['tip']);
    final notLogged = i(h['notLogged']);
    final pct = lim == null ? 0.0 : d(lim['pct']);
    final over = limitPeso != null && fcCost > limitPeso;
    final isPeso = lim?['unit'] == 'PESO';
    final color = budgetColor(pct, overForecast: over);

    return ListView(padding: const EdgeInsets.only(bottom: 24), children: [
      const PageHeader('Home'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (lim != null) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Row(children: [
                  BudgetRing(pct: pct, color: color),
                  const SizedBox(width: 18),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Used so far · day ${i(h['dayIndex'])} of ${i(h['cycleDays'])}', style: t.bodySmall),
                      Text(isPeso ? peso(d(lim['used'])) : kwh(d(lim['used']), decimals: 1),
                          style: t.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                      Text('of your ${isPeso ? peso(d(lim['limit'])) : kwh(d(lim['limit']), decimals: 0)} budget', style: t.bodySmall),
                    ]),
                  ),
                ]),
              ),
            ),
            const SizedBox(height: 12),
            if (pct >= 100)
              const StatusBox(title: 'Budget reached.', body: 'Only essential appliances fit the plan for the rest of the month.', color: bad)
            else if (over)
              StatusBox(title: 'Above limit at this pace.', body: 'You may reach ${peso(fcCost)} by the end of the month. See the Save tab for ways to cut back.', color: warn)
            else
              StatusBox(title: 'Within limit.', body: "At this pace you'll spend about ${peso(fcCost)} this month.", color: good),
          ] else
            const InfoCard(label: 'Set a monthly budget', child: Text("Tell us how much you want to spend and we'll warn you before you go over. Tap the gear icon above.")),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(color: sun.withOpacity(0.22), borderRadius: BorderRadius.circular(22)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('On right now', style: t.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
              if (running.isEmpty) const Padding(padding: EdgeInsets.only(top: 4), child: Text('Nothing is running. Tap Start on an appliance when you turn it on.')),
              for (final a in running)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Row(children: [
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${appEmoji('${a['type']}')} ${a['type']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                        Text(hours(d(a['elapsedH'])), style: t.titleLarge?.copyWith(fontWeight: FontWeight.w800, color: warn)),
                      ]),
                    ),
                    OutlinedButton(onPressed: () => run(context, () => s.stopTimer(i(a['id']))), child: const Text('Stop')),
                  ]),
                ),
            ]),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: InfoCard(label: '', child: _Money('Today', peso(d(h['todayCost'])), kwh(d(h['todayKwh']))))),
            const SizedBox(width: 12),
            Expanded(child: InfoCard(label: '', child: _Money('This month', peso(d(h['cycleCost'])), kwh(d(h['cycleKwh']), decimals: 1)))),
          ]),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const LogSheetScreen())),
            child: Text(notLogged > 0 ? "Log today's hours ($notLogged to go)" : "Log today's hours"),
          ),
          if (plan != null) ...[
            const SizedBox(height: 12),
            InfoCard(
              label: "Today's plan",
              child: Column(children: [
                for (final it in list(plan['items']))
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(children: [
                      Expanded(child: Text('${appEmoji('${it['type']}')} ${it['type']}')),
                      Text(d(it['leftH']) > 0 ? '${hours(d(it['leftH']))} left' : 'Used up',
                          style: TextStyle(fontWeight: FontWeight.w800, color: d(it['leftH']) > 0 ? null : bad)),
                    ]),
                  ),
              ]),
            ),
          ],
          if (tip != null) ...[
            const SizedBox(height: 12),
            InfoCard(
              label: '💡 Tip',
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${tip['title']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                Text('Saves about ${peso(d(tip['peso']))}${tip['stay'] == true ? ' this month' : ' a month'}.'),
              ]),
            ),
          ],
          const SizedBox(height: 12),
          Text('All amounts are estimates. Check them against your bill on the Check tab.', style: t.bodySmall, textAlign: TextAlign.center),
        ]),
      ),
    ]);
  }
}

class _Money extends StatelessWidget {
  final String label, pesos, energy;
  const _Money(this.label, this.pesos, this.energy);

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: t.bodySmall),
      Text(pesos, style: t.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
      Text(energy, style: t.bodySmall),
    ]);
  }
}
