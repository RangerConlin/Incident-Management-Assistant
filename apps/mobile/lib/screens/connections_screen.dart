import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../services/server_connection_store.dart';

/// Saved connect codes: pick which incident command post to use, add a code
/// handed out by the IC, or forget one. Works with no network.
class ConnectionsScreen extends StatefulWidget {
  const ConnectionsScreen({super.key});

  @override
  State<ConnectionsScreen> createState() => _ConnectionsScreenState();
}

class _ConnectionsScreenState extends State<ConnectionsScreen> {
  final _codeController = TextEditingController();
  final _routerController = TextEditingController();
  List<ServerConnection> _connections = const [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    _codeController.dispose();
    _routerController.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    final all = await ServerConnectionStore.loadAll();
    if (mounted) setState(() => _connections = all);
  }

  Future<void> _add() async {
    final code = ServerConnection.normalizeCode(_codeController.text);
    if (code == null) {
      setState(
        () => _errorMessage =
            'Enter the connect code from your incident commander, e.g. ABCD-1234.',
      );
      return;
    }
    final routerUrl = ServerConnection.normalizeRouterUrl(_routerController.text);
    if (routerUrl == null) {
      setState(
        () => _errorMessage =
            'The router address must be a full http(s) URL, or left blank.',
      );
      return;
    }

    await ServerConnectionStore.addAndActivate(
      ServerConnection(code: code, routerUrl: routerUrl),
    );
    _codeController.clear();
    _routerController.clear();
    setState(() => _errorMessage = null);
    await _reload();
  }

  Future<void> _select(ServerConnection connection) async {
    await ServerConnectionStore.setActive(connection.code);
    await _reload();
  }

  Future<void> _remove(ServerConnection connection) async {
    await ServerConnectionStore.remove(connection.code);
    await _reload();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final activeCode = ServerConnectionStore.active?.code;

    return Scaffold(
      appBar: AppBar(title: const Text('Connections')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Saved connections', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_connections.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('None yet. Add the connect code below.'),
            )
          else
            for (final connection in _connections)
              Card(
                child: ListTile(
                  leading: Icon(
                    connection.code == activeCode
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked,
                  ),
                  title: Text(connection.code),
                  subtitle: connection.routerUrl == AppConfig.cloudRouterBaseUrl
                      ? null
                      : Text(connection.routerUrl),
                  onTap: () => _select(connection),
                  trailing: IconButton(
                    tooltip: 'Forget ${connection.code}',
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => _remove(connection),
                  ),
                ),
              ),
          const SizedBox(height: 24),
          Text('Add a connection', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _codeController,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: 'Connect code',
              hintText: 'ABCD-1234',
            ),
            onSubmitted: (_) => _add(),
          ),
          const SizedBox(height: 4),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Advanced'),
            children: [
              TextField(
                controller: _routerController,
                keyboardType: TextInputType.url,
                decoration: InputDecoration(
                  labelText: 'Router address (optional)',
                  hintText: AppConfig.cloudRouterBaseUrl,
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
          if (_errorMessage != null) ...[
            Text(
              _errorMessage!,
              style: TextStyle(color: theme.colorScheme.error),
            ),
            const SizedBox(height: 12),
          ],
          FilledButton(onPressed: _add, child: const Text('Add and use')),
        ],
      ),
    );
  }
}
