// REST client for the Python (Flask) server (SRS 7.4.3). Every screen's data
// comes from the server; the phone keeps only the server address and the token.
import 'dart:convert';

import 'package:http/http.dart' as http;

typedef Json = Map<String, dynamic>;

class ApiException implements Exception {
  final int status;
  final Map<String, String> errors;
  ApiException(this.status, this.errors);

  String get message => errors.values.isEmpty ? 'Something went wrong (HTTP $status).' : errors.values.join(' ');

  @override
  String toString() => message;
}

class ApiClient {
  String baseUrl;
  String? token;
  final http.Client _http;

  ApiClient({required this.baseUrl, this.token, http.Client? client}) : _http = client ?? http.Client();

  Uri _uri(String path, [Map<String, String>? query]) {
    final b = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    return Uri.parse('$b/api$path').replace(queryParameters: query);
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<Json> _send(String method, String path, {Object? body, Map<String, String>? query}) async {
    final req = http.Request(method, _uri(path, query))..headers.addAll(_headers);
    if (body != null) req.body = jsonEncode(body);
    http.Response res;
    try {
      res = await http.Response.fromStream(await _http.send(req)).timeout(const Duration(seconds: 15));
    } catch (_) {
      throw ApiException(0, {'network': 'Cannot reach the server at $baseUrl. Check the address and Wi-Fi.'});
    }
    Json data = {};
    if (res.body.isNotEmpty) {
      try {
        data = jsonDecode(utf8.decode(res.bodyBytes)) as Json;
      } catch (_) {
        data = {};
      }
    }
    if (res.statusCode >= 400) {
      final e = (data['errors'] as Map?)?.map((k, v) => MapEntry('$k', '$v')) ??
          {'error': res.statusCode == 401 ? 'Please sign in again.' : 'Server error (${res.statusCode}).'};
      throw ApiException(res.statusCode, e);
    }
    return data;
  }

  Future<Json> get(String path, {Map<String, String>? query}) => _send('GET', path, query: query);
  Future<Json> post(String path, [Object? body]) => _send('POST', path, body: body ?? {});
  Future<Json> put(String path, [Object? body]) => _send('PUT', path, body: body ?? {});
  Future<Json> delete(String path) => _send('DELETE', path);

  // ---- accounts
  Future<String> demo() async => (await post('/demo'))['token'] as String;
  Future<String> login(String email, String password) async =>
      (await post('/login', {'email': email, 'password': password}))['token'] as String;
  Future<String> register(Json form) async => (await post('/register', form))['token'] as String;
}

/// Small helpers for reading JSON numbers safely.
double d(Object? v) => v is num ? v.toDouble() : 0.0;
int i(Object? v) => v is num ? v.toInt() : 0;
DateTime? dt(Object? v) => v is String ? DateTime.tryParse(v) : null;
List<Json> list(Object? v) => (v as List<dynamic>? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)).toList();
Json? obj(Object? v) => v == null ? null : Map<String, dynamic>.from(v as Map);
