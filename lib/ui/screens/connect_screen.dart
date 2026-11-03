import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';

/// Wireframe 1 – connect to the server, then open the sample household, sign in,
/// or create an account (REQ-ACC-1 to REQ-ACC-4, NFR-PRV-1).
class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _server = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _rate = TextEditingController();
  final _limit = TextEditingController();
  int _day = 1;
  bool _consent = false;
  bool _create = false;
  bool _busy = false;
  Map<String, String> _errors = {};

  @override
  void initState() {
    super.initState();
    _server.text = context.read<AppState>().api.baseUrl;
  }

  @override
  void dispose() {
    for (final c in [_server, _email, _password, _rate, _limit]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _go(Future<void> Function(AppState s) f) async {
    final s = context.read<AppState>();
    setState(() {
      _busy = true;
      _errors = {};
    });
    try {
      await s.setServer(_server.text);
      await f(s);
    } on ApiException catch (e) {
      if (mounted) setState(() => _errors = e.errors);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_create ? 'Create your account' : 'Electricity Regulator')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: _server,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
              labelText: 'Server address',
              helperText: 'Emulator: http://10.0.2.2:5000 · Phone on the same Wi-Fi: http://<laptop IP>:5000'),
        ),
        if (_errors['network'] != null)
          Padding(padding: const EdgeInsets.only(top: 8), child: Text(_errors['network']!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 16),
        if (!_create) ...[
          FilledButton.icon(
            onPressed: _busy ? null : () => _go((s) => s.openSample()),
            icon: const Icon(Icons.home_outlined),
            label: const Text('Open sample household'),
          ),
          const Divider(height: 32),
        ],
        TextField(controller: _email, keyboardType: TextInputType.emailAddress, decoration: InputDecoration(labelText: 'Email', errorText: _errors['email'])),
        const SizedBox(height: 12),
        TextField(controller: _password, obscureText: true, decoration: InputDecoration(labelText: 'Password', helperText: _create ? 'At least 8 characters' : null, errorText: _errors['password'])),
        if (_create) ...[
          const SizedBox(height: 12),
          TextField(controller: _rate, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: 'Electricity rate per kWh (₱, from your bill)', errorText: _errors['rate'])),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: DropdownButtonFormField<int>(
                value: _day,
                decoration: const InputDecoration(labelText: 'Billing cycle starts on day'),
                items: [for (var d = 1; d <= 31; d++) DropdownMenuItem(value: d, child: Text('$d'))],
                onChanged: (v) => setState(() => _day = v ?? 1),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(child: TextField(controller: _limit, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: 'Monthly limit (₱, optional)', errorText: _errors['limit']))),
          ]),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _consent,
            onChanged: (v) => setState(() => _consent = v ?? false),
            title: const Text('I agree to the Privacy Notice. My data is used only for this app (RA 10173).'),
            subtitle: _errors['consent'] == null ? null : Text(_errors['consent']!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        ],
        const SizedBox(height: 12),
        FilledButton.tonal(
          onPressed: _busy
              ? null
              : () => _create
                  ? _go((s) => s.register({
                        'email': _email.text,
                        'password': _password.text,
                        'rate': _rate.text,
                        'cycleDay': _day,
                        'monthlyLimit': _limit.text,
                        'consent': _consent,
                      }))
                  : _go((s) => s.login(_email.text, _password.text)),
          child: Text(_create ? 'Create account' : 'Sign in'),
        ),
        TextButton(onPressed: () => setState(() => _create = !_create), child: Text(_create ? 'I already have an account' : 'Create an account')),
      ]),
    );
  }
}
