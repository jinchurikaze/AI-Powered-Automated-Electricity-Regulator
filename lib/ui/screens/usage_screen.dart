import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'app_shell.dart';

/// Wireframe 6 – Usage (REQ-DSH-1 to 4, REQ-CST-1 to 4, REQ-HCA-1 to 3).
class UsageScreen extends StatelessWidget {
  const UsageScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final t = Theme.of(context).textTheme;
    final u = s.usage ?? {};
    final bars = list(u['bars']);
    final change = u['change'] == null ? null : d(u['change']);
    final shares = list(u['shares']);
    final rate = d(s.me?['rate']);
    return ListView(padding: const EdgeInsets.only(bottom: 24), children: [
      const PageHeader('Usage'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SegmentedButton<String>(
            segments: const [ButtonSegment(value: 'daily', label: Text('Daily')), ButtonSegment(value: 'monthly', label: Text('Monthly'))],
            selected: {s.usageView},
            onSelectionChanged: (v) => s.setUsageView(v.first),
          ),
          const SizedBox(height: 12),
          InfoCard(
            label: s.usageView == 'daily' ? 'Last 7 days' : 'Past months',
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Electricity used, in kWh', style: t.bodySmall),
              const SizedBox(height: 8),
              BarChart(values: [for (final b in bars) d(b['kwh'])], labels: [for (final b in bars) '${b['label']}'], highlightLast: 1),
            ]),
          ),
          const SizedBox(height: 12),
          InfoCard(
            label: '',
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('This month so far', style: t.bodySmall),
              Text(peso(d(u['cycleCost'])), style: t.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              if (change != null) Text('${change.abs().toStringAsFixed(0)}% ${change >= 0 ? 'more' : 'less'} than last month at this point.'),
              const Text('See your expected bill on the Save tab.'),
              HowCalculated('A simple average: if every day were like the days so far, the month would cost ${peso(d(u['projCost']))}.\n'
                  '(${kwh(d(u['cycleKwh']), decimals: 1)} ÷ ${i(u['dayIndex'])} days) × ${i(u['cycleDays'])} days × ${peso(rate)}\n'
                  'The Save tab gives a better estimate because it also looks at the weather and recent days.'),
            ]),
          ),
          const SizedBox(height: 12),
          InfoCard(
            label: 'What uses the most',
            child: Column(children: [
              if (shares.isEmpty) const Text('No usage yet this month.'),
              for (final r in shares)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Expanded(child: Text('${appEmoji('${r['type']}')} ${r['type']}')),
                      if (r['aboveUsual'] == true) const StatusChip('Above usual', warn),
                      const SizedBox(width: 8),
                      Text(peso(d(r['cost'])), style: const TextStyle(fontWeight: FontWeight.w800)),
                    ]),
                    const SizedBox(height: 6),
                    ClipRRect(borderRadius: BorderRadius.circular(6), child: LinearProgressIndicator(value: d(r['share']) / 100, minHeight: 10)),
                  ]),
                ),
            ]),
          ),
          const SizedBox(height: 8),
          Text('Costs are estimates. Compare them with your real bill on the Check tab.', style: t.bodySmall, textAlign: TextAlign.center),
        ]),
      ),
    ]);
  }
}
