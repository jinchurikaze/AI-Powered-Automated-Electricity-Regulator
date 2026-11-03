import 'dart:convert';

import 'package:electricity_regulator/api/api_client.dart';
import 'package:electricity_regulator/ui/format.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('ApiClient', () {
    test('sends the bearer token and decodes JSON', () async {
      late http.Request seen;
      final api = ApiClient(
        baseUrl: 'http://server:5000/',
        token: 'abc',
        client: MockClient((req) async {
          seen = req;
          return http.Response(jsonEncode({'todayKwh': 6.57, 'running': []}), 200);
        }),
      );
      final r = await api.get('/dashboard');
      expect(seen.url.toString(), 'http://server:5000/api/dashboard');
      expect(seen.headers['Authorization'], 'Bearer abc');
      expect(d(r['todayKwh']), 6.57);
    });

    test('login returns the token', () async {
      final api = ApiClient(
        baseUrl: 'http://s',
        client: MockClient((req) async {
          expect(jsonDecode(req.body), {'email': 'a@b.co', 'password': 'longenough1'});
          return http.Response(jsonEncode({'token': 't1'}), 200);
        }),
      );
      expect(await api.login('a@b.co', 'longenough1'), 't1');
    });

    test('validation errors become an ApiException with field messages (US-03)', () async {
      final api = ApiClient(
        baseUrl: 'http://s',
        client: MockClient((_) async => http.Response(
            jsonEncode({'error': 'validation', 'errors': {'watt': 'Enter a wattage from 1 to 10,000 W.'}}), 400)),
      );
      expect(
        () => api.post('/appliances', {'type': 'Other', 'watt': '0'}),
        throwsA(isA<ApiException>()
            .having((e) => e.status, 'status', 400)
            .having((e) => e.errors['watt'], 'watt', 'Enter a wattage from 1 to 10,000 W.')),
      );
    });

    test('an unreachable server gives a clear message', () async {
      final api = ApiClient(baseUrl: 'http://s', client: MockClient((_) async => throw Exception('no route')));
      expect(() => api.get('/me'), throwsA(isA<ApiException>().having((e) => e.status, 'status', 0)));
    });
  });

  group('JSON helpers', () {
    test('numbers, dates, lists', () {
      expect(d(null), 0.0);
      expect(i(3.0), 3);
      expect(dt('2026-10-31T09:40:00'), DateTime(2026, 10, 31, 9, 40));
      expect(list([{'a': 1}]).first['a'], 1);
    });
  });

  group('Philippine formats (NFR-LOC-2, NFR-LOC-3)', () {
    test('pesos, kWh, hours, dates', () {
      expect(peso(4068.37), '₱4,068.37');
      expect(peso(-375), '−₱375.00');
      expect(signedPeso(-375), '−₱375.00');
      expect(kwh(119.349, decimals: 1), '119.3 kWh');
      expect(hours(70 / 60), '1 h 10 min');
      expect(hours(0.25), '15 min');
      expect(longDate(DateTime(2026, 10, 31)), 'Oct 31, 2026');
      expect(time(DateTime(2026, 10, 31, 13, 5)), '1:05 PM');
    });
  });
}
