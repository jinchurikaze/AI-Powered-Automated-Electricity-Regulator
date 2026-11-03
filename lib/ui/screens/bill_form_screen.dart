import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../services/bill_service.dart';
import '../../state/app_state.dart';
import '../format.dart';

/// Bill entry: take or choose a photo, read it on the phone with ML Kit, let the server
/// find the period, kWh, and amount, then confirm or correct the values (Feature 11).
class BillFormScreen extends StatefulWidget {
  const BillFormScreen({super.key});

  @override
  State<BillFormScreen> createState() => _BillFormScreenState();
}

class _BillFormScreenState extends State<BillFormScreen> {
  final _kwh = TextEditingController();
  final _amount = TextEditingController();
  DateTime? _start;
  DateTime? _end;
  String _src = 'MANUAL';
  Map<String, String> _errors = {};
  String? _scanMessage;
  bool _busy = false;

  @override
  void dispose() {
    _kwh.dispose();
    _amount.dispose();
    super.dispose();
  }

  Future<void> _scan(ImageSource from) async {
    final s = context.read<AppState>();
    final photo = await ImagePicker().pickImage(source: from, maxWidth: 2000);
    if (photo == null) return;
    setState(() => _busy = true);
    try {
      final text = await BillService.readText(photo.path);
      final f = await s.parseBill(text);
      setState(() {
        _src = 'SCAN';
        if (f['kwh'] != null) _kwh.text = d(f['kwh']).toStringAsFixed(0);
        if (f['amount'] != null) _amount.text = d(f['amount']).toStringAsFixed(2);
        _start = dt(f['start']) ?? _start;
        _end = dt(f['end']) ?? _end;
        final found = [f['kwh'], f['amount'], f['start']].where((x) => x != null).length;
        _scanMessage = found == 3 ? 'Read from the photo. Check the values before saving.' : 'Some values could not be read. Please fill them in.';
      });
    } on ApiException catch (e) {
      setState(() => _scanMessage = e.message);
    } catch (_) {
      setState(() => _scanMessage = 'Could not read the photo. Enter the values by hand.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickDate(bool start) async {
    final dd = await showDatePicker(
      context: context,
      initialDate: (start ? _start : _end) ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
    );
    if (dd == null) return;
    setState(() {
      if (start) {
        _start = dd;
      } else {
        _end = dd;
      }
    });
  }

  String _iso(DateTime? t) => t == null ? '' : '${t.year}-${t.month.toString().padLeft(2, '0')}-${t.day.toString().padLeft(2, '0')}';

  Future<void> _save() async {
    final s = context.read<AppState>();
    try {
      await s.addBill({'start': _iso(_start), 'end': _iso(_end), 'kwh': _kwh.text, 'amount': _amount.text, 'src': _src});
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      setState(() => _errors = e.errors);
    }
  }

  @override
  Widget build(BuildContext context) {
    final err = Theme.of(context).colorScheme.error;
    return Scaffold(
      appBar: AppBar(title: const Text('Electric bill')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Row(children: [
          Expanded(child: FilledButton.icon(onPressed: _busy ? null : () => _scan(ImageSource.camera), icon: const Icon(Icons.photo_camera_outlined), label: const Text('Take photo'))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton.icon(onPressed: _busy ? null : () => _scan(ImageSource.gallery), icon: const Icon(Icons.photo_library_outlined), label: const Text('Choose photo'))),
        ]),
        if (_busy) const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
        if (_scanMessage != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_scanMessage!)),
        const SizedBox(height: 4),
        Text('The photo is read on your phone; only the text is sent to the server.', style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 16),
        Row(children: [
          Expanded(child: OutlinedButton(onPressed: () => _pickDate(true), child: Text(_start == null ? 'Period start' : 'From ${longDate(_start!)}'))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton(onPressed: () => _pickDate(false), child: Text(_end == null ? 'Period end' : 'To ${longDate(_end!)}'))),
        ]),
        if (_errors['period'] != null) Text(_errors['period']!, style: TextStyle(color: err)),
        const SizedBox(height: 12),
        TextField(key: const Key('billKwh'), controller: _kwh, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: 'kWh used', errorText: _errors['kwh'])),
        const SizedBox(height: 12),
        TextField(key: const Key('billAmount'), controller: _amount, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: 'Total amount due (₱)', errorText: _errors['amount'])),
        const SizedBox(height: 16),
        FilledButton(onPressed: _save, child: const Text('Save bill')),
      ]),
    );
  }
}
