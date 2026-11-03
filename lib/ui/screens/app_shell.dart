import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/app_state.dart';
import '../format.dart';
import 'appliances_screen.dart';
import 'check_screen.dart';
import 'home_screen.dart';
import 'save_screen.dart';
import 'settings_screen.dart';
import 'usage_screen.dart';

/// Five-tab navigation (SRS Section 3.1): Home, Appliances, Usage, Save, Check.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    // In-app banner for alerts and plan reminders (a release build can also post a local notification).
    context.read<AppState>().onNotify = (AppNotice n) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 5),
        content: Text('${n.title}\n${n.body}'),
      ));
    };
  }

  @override
  Widget build(BuildContext context) {
    const pages = [HomeScreen(), AppliancesScreen(), UsageScreen(), SaveScreen(), CheckScreen()];
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(onRefresh: context.read<AppState>().refreshAll, child: pages[_tab]),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.power_outlined), selectedIcon: Icon(Icons.power), label: 'Appliances'),
          NavigationDestination(icon: Icon(Icons.bar_chart_outlined), selectedIcon: Icon(Icons.bar_chart), label: 'Usage'),
          NavigationDestination(icon: Icon(Icons.lightbulb_outline), selectedIcon: Icon(Icons.lightbulb), label: 'Save'),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), selectedIcon: Icon(Icons.fact_check), label: 'Check'),
        ],
      ),
    );
  }
}

/// Shared page header with the notifications and settings buttons.
class PageHeader extends StatelessWidget {
  final String title;
  const PageHeader(this.title, {super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    void go(Widget w) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => w));
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 4, 8),
      child: Row(children: [
        Expanded(child: Text(title, style: Theme.of(context).textTheme.headlineSmall)),
        IconButton(
          tooltip: 'Notifications',
          icon: Badge(isLabelVisible: s.unread > 0, label: Text('${s.unread}'), child: const Icon(Icons.notifications_outlined)),
          onPressed: () => go(const NotificationsScreen()),
        ),
        IconButton(tooltip: 'Settings', icon: const Icon(Icons.settings_outlined), onPressed: () => go(const SettingsScreen())),
      ]),
    );
  }
}

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: FutureBuilder<List<Json>>(
        future: context.read<AppState>().notifications(),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final items = snap.data!;
          if (items.isEmpty) return const Center(child: Text('No notifications yet.'));
          return ListView(padding: const EdgeInsets.all(16), children: [
            for (final n in items)
              Card(
                child: ListTile(
                  title: Text('${n['title']}'),
                  subtitle: Text('${n['body']}\n${shortDate(DateTime.parse('${n['ts']}'.replaceFirst(' ', 'T')))}, '
                      '${time(DateTime.parse('${n['ts']}'.replaceFirst(' ', 'T')))}'),
                  isThreeLine: true,
                ),
              ),
          ]);
        },
      ),
    );
  }
}
