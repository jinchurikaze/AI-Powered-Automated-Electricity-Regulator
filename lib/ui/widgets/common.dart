import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// A friendly picture for each appliance type.
String appEmoji(String type) {
  const map = {'air': '❄️', 'refrigerator': '🧊', 'fridge': '🧊', 'freezer': '🧊', 'fan': '🌀', 'television': '📺', 'tv': '📺',
    'washing': '🧺', 'rice': '🍚', 'computer': '💻', 'laptop': '💻', 'light': '💡', 'water': '🚰', 'iron': '👕', 'oven': '🍞', 'microwave': '🍞'};
  final t = type.toLowerCase();
  for (final e in map.entries) {
    if (t.contains(e.key)) return e.value;
  }
  return '🔌';
}

/// Technical details (formulas, model names) stay folded away until the user asks.
class HowCalculated extends StatelessWidget {
  final String text;
  const HowCalculated(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Theme(
      data: t.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: 8),
        expandedAlignment: Alignment.centerLeft,
        title: Text('How is this calculated?', style: TextStyle(color: t.colorScheme.primary, fontWeight: FontWeight.w800, fontSize: 14)),
        children: [Text(text, style: t.textTheme.bodySmall)],
      ),
    );
  }
}

/// Status color for a share of the budget.
Color budgetColor(double pct, {bool overForecast = false}) => pct >= 100 ? bad : (pct >= 80 || overForecast ? warn : good);

/// Round progress ring with the percentage in the middle.
class BudgetRing extends StatelessWidget {
  final double pct;
  final Color color;
  const BudgetRing({super.key, required this.pct, required this.color});

  @override
  Widget build(BuildContext context) => Semantics(
        label: '${pct.round()} percent of the monthly budget used',
        child: SizedBox(
          width: 108,
          height: 108,
          child: CustomPaint(
            painter: _RingPainter(math.min(pct, 100) / 100, color, Theme.of(context).colorScheme.surfaceContainerHighest),
            child: Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Text('${pct.round()}%', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
                const Text('used', style: TextStyle(fontSize: 12)),
              ]),
            ),
          ),
        ),
      );
}

class _RingPainter extends CustomPainter {
  final double p;
  final Color color, track;
  _RingPainter(this.p, this.color, this.track);

  @override
  void paint(Canvas canvas, Size size) {
    final r = Rect.fromLTWH(7, 7, size.width - 14, size.height - 14);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(r, 0, 2 * math.pi, false, paint..color = track);
    if (p > 0) canvas.drawArc(r, -math.pi / 2, 2 * math.pi * p, false, paint..color = color);
  }

  @override
  bool shouldRepaint(_RingPainter o) => o.p != p || o.color != color;
}

/// Colored sentence that says plainly how the month is going.
class StatusBox extends StatelessWidget {
  final String title;
  final String body;
  final Color color;
  const StatusBox({super.key, required this.title, required this.body, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(18)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 2),
          Text(body),
        ]),
      );
}

class InfoCard extends StatelessWidget {
  final String label;
  final Widget child;
  final Color? color;
  final Color? foreground;
  const InfoCard({super.key, required this.label, required this.child, this.color, this.foreground});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Card(
      color: color,
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (label.isNotEmpty) ...[
            Text(label, style: t.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800, color: foreground)),
            const SizedBox(height: 8),
          ],
          child,
        ]),
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  final String text;
  final Color color;
  const StatusChip(this.text, this.color, {super.key});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
        child: Text(text, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800)),
      );
}

/// Simple labeled bar chart; values are drawn to one scale (no chart library).
class BarChart extends StatelessWidget {
  final List<double> values;
  final List<String> labels;
  final bool dashedForecast;
  final int? highlightLast;
  const BarChart({super.key, required this.values, required this.labels, this.dashedForecast = false, this.highlightLast});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final max = values.fold<double>(0.1, (m, v) => v > m ? v : m) * 1.15;
    return SizedBox(
      height: 150,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < values.length; i++)
            Expanded(
              child: Semantics(
                label: '${labels[i]}: ${values[i].toStringAsFixed(1)} kilowatt-hours',
                child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                  Text(values[i].toStringAsFixed(1), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Container(
                    height: 100 * values[i] / max,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      color: dashedForecast
                          ? cs.primary.withValues(alpha: 0.15)
                          : (highlightLast != null && i == values.length - 1 ? sun : cs.primary),
                      border: dashedForecast ? Border.all(color: cs.primary) : null,
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(labels[i], style: const TextStyle(fontSize: 10), overflow: TextOverflow.ellipsis),
                ]),
              ),
            ),
        ],
      ),
    );
  }
}
