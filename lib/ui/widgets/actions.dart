import 'package:flutter/material.dart';

import '../../api/api_client.dart';

/// Runs a server call and shows its error (if any) as a snackbar. Returns true on success.
Future<bool> run(BuildContext context, Future<void> Function() call, {String? done}) async {
  try {
    await call();
    if (done != null && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(done)));
    }
    return true;
  } on ApiException catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
    return false;
  }
}
