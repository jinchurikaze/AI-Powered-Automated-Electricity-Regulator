// Philippine number and date formats (NFR-LOC-2, NFR-LOC-3).
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

String _group(String digits) {
  final b = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) b.write(',');
    b.write(digits[i]);
  }
  return b.toString();
}

String number(double v, {int decimals = 2}) {
  final neg = v < 0 && v.abs().toStringAsFixed(decimals) != (0).toStringAsFixed(decimals);
  final parts = v.abs().toStringAsFixed(decimals).split('.');
  final s = _group(parts[0]) + (decimals > 0 ? '.${parts[1]}' : '');
  return neg ? '−$s' : s; // Unicode minus
}

String peso(double v) => v < 0 ? '−₱${number(-v)}' : '₱${number(v)}';
String signedPeso(double v) => v > 0 ? '+${peso(v)}' : peso(v);
String kwh(double v, {int decimals = 2}) => '${number(v, decimals: decimals)} kWh';
String watts(double v) => '${number(v, decimals: 0)} W';
String hours(double h) {
  final m = (h * 60).round();
  if (m < 60) return '$m min';
  return m % 60 == 0 ? '${m ~/ 60} h' : '${m ~/ 60} h ${m % 60} min';
}

String shortDate(DateTime t) => '${_months[t.month - 1]} ${t.day}';
String longDate(DateTime t) => '${_months[t.month - 1]} ${t.day}, ${t.year}';
String time(DateTime t) {
  final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
  final ap = t.hour >= 12 ? 'PM' : 'AM';
  return '$h:${t.minute.toString().padLeft(2, '0')} $ap';
}

String dateTime(DateTime t) => '${longDate(t)}, ${time(t)}';
