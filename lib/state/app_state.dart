// App state (Provider). Holds what the server last returned for each screen and
// calls the API for every action. Notifications created by an action come back in
// the response ("newNotifications") and are shown at once.
import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';

class AppNotice {
  final String title;
  final String body;
  AppNotice(this.title, this.body);
}

class AppState extends ChangeNotifier {
  static const defaultServer = 'http://10.0.2.2:5000'; // the laptop, seen from the Android emulator
  final ApiClient api;
  void Function(AppNotice n)? onNotify;

  bool ready = false;
  Json? me;
  Json? home;
  Json? appliances;
  Json? usage;
  Json? save;
  Json? check;
  String usageView = 'daily';
  Timer? _ticker;

  AppState({ApiClient? client}) : api = client ?? ApiClient(baseUrl: defaultServer);

  bool get signedIn => api.token != null && me != null;
  bool get simulated => me?['simulated'] == true;
  int get unread => i(me?['unread']);

  // ---------------------------------------------------------------- session
  Future<void> init() async {
    final p = await SharedPreferences.getInstance();
    api.baseUrl = p.getString('server') ?? defaultServer;
    api.token = p.getString('token');
    if (api.token != null) {
      try {
        await refreshAll();
      } on ApiException {
        api.token = null;
      }
    }
    ready = true;
    notifyListeners();
  }

  Future<void> _saveSession() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('server', api.baseUrl);
    if (api.token == null) {
      await p.remove('token');
    } else {
      await p.setString('token', api.token!);
    }
  }

  Future<void> _signedIn(String token) async {
    api.token = token;
    await _saveSession();
    await refreshAll();
  }

  Future<void> setServer(String url) async {
    api.baseUrl = url.trim();
    await _saveSession();
  }

  Future<void> openSample() async => _signedIn(await api.demo());
  Future<void> login(String email, String password) async => _signedIn(await api.login(email, password));
  Future<void> register(Json form) async => _signedIn(await api.register(form));

  Future<void> signOut() async {
    api.token = null;
    me = home = appliances = usage = save = check = null;
    _ticker?.cancel();
    await _saveSession();
    notifyListeners();
  }

  // ---------------------------------------------------------------- loading
  Future<void> refreshAll() async {
    me = await api.get('/me');
    final r = await Future.wait([
      api.get('/dashboard'),
      api.get('/appliances'),
      api.get('/usage', query: {'view': usageView}),
      api.get('/save'),
      api.get('/check'),
    ]);
    home = r[0];
    appliances = r[1];
    usage = r[2];
    save = r[3];
    check = r[4];
    me = home; // the dashboard carries the same account fields
    _startTicker();
    notifyListeners();
  }

  void _startTicker() {
    _ticker?.cancel();
    if (simulated) return; // the sample household moves only with the demo controls
    _ticker = Timer.periodic(const Duration(minutes: 1), (_) async {
      try {
        _notices(await api.post('/tick'));
        await refreshAll();
      } catch (_) {}
    });
  }

  void _notices(Json r) {
    for (final n in list(r['newNotifications'])) {
      onNotify?.call(AppNotice('${n['title']}', '${n['body']}'));
    }
  }

  /// Runs an action, shows its notifications, and reloads every screen.
  Future<Json> act(Future<Json> Function() call) async {
    final r = await call();
    _notices(r);
    await refreshAll();
    return r;
  }

  Future<void> setUsageView(String v) async {
    usageView = v;
    usage = await api.get('/usage', query: {'view': v});
    notifyListeners();
  }

  // ---------------------------------------------------------------- actions
  Future<Json> appliance(int id) => api.get('/appliances/$id');
  Future<Json> saveAppliance(Json form, {int? id}) =>
      act(() => id == null ? api.post('/appliances', form) : api.put('/appliances/$id', form));
  Future<void> deleteAppliance(int id) => act(() => api.delete('/appliances/$id'));
  Future<Json> startTimer(int id) => act(() => api.post('/appliances/$id/start'));
  Future<Json> stopTimer(int id) => act(() => api.post('/appliances/$id/stop'));
  Future<Json> logHours(int id, String hours) => act(() => api.post('/appliances/$id/log', {'hours': hours}));
  Future<Json> logMany(Map<String, String> hours) => act(() => api.post('/log', {'hours': hours}));
  Future<void> setPlan(bool on) => act(() => api.post('/plan', {'active': on}));
  Future<void> tipFeedback(String key, String status) => act(() => api.post('/tips/$key', {'status': status}));
  Future<Json> whatIfStart() => api.get('/whatif');
  Future<Json> whatIf(Map<String, Json> changes, double saving, double extra) =>
      api.post('/whatif', {'changes': changes, 'savingPct': saving, 'extraCost': extra});
  Future<Json> parseBill(String text) => api.post('/bills/parse', {'text': text});
  Future<void> addBill(Json bill) => act(() => api.post('/bills', bill));
  Future<void> useBillRate() => act(() => api.post('/bills/use-rate'));
  Future<void> addMeterReading(String reading) => act(() => api.post('/meter', {'reading': reading}));
  Future<void> updateSettings(String rate, int cycleDay) => act(() => api.put('/settings', {'rate': rate, 'cycleDay': cycleDay}));
  Future<Json> limits() => api.get('/limits');
  Future<void> saveLimits(Json body) => act(() => api.put('/limits', body));
  Future<List<Json>> notifications() async {
    final r = list((await api.get('/notifications', query: {'markRead': '1'}))['notifications']);
    me = {...?me, 'unread': 0};
    notifyListeners();
    return r;
  }

  Future<Json> exportData() => api.get('/export');
  Future<void> deleteAccount() async {
    await api.delete('/account');
    await signOut();
  }

  // ---------------------------------------------------------------- demo controls (sample household)
  Future<void> demoAdvance(double hours) => act(() => api.post('/demo/advance', {'hours': hours}));
  Future<void> demoDay() => act(() => api.post('/demo/day'));
  Future<void> demoUse(int pct) => act(() => api.post('/demo/use', {'pct': pct}));
  Future<void> demoMeter() => act(() => api.post('/demo/meter'));
  Future<void> demoReset() => act(() => api.post('/demo/reset'));

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }
}
