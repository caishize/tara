import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/connector_metadata_model.dart';
import '../../data/models/data_connection_model.dart';
import '../../domain/entities/connector_metadata.dart';
import '../../domain/entities/data_connection.dart';
import '../bloc/connection_bloc.dart';
import '../bloc/connection_event.dart';
import '../bloc/connection_state.dart' as bloc;
import '../widgets/permission_toggle.dart';

/// Detail page for a specific connection
class ConnectionDetailPage extends StatefulWidget {
  final String connectionId;

  const ConnectionDetailPage({
    super.key,
    required this.connectionId,
  });

  @override
  State<ConnectionDetailPage> createState() => _ConnectionDetailPageState();
}

class _ConnectionDetailPageState extends State<ConnectionDetailPage> {
  DataConnectionModel? _connection;
  ConnectorMetadataModel? _connector;
  UsagePermissions? _editedPermissions;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_connector?.displayNameZh ?? '连接详情'),
        actions: [
          IconButton(
            icon: const Icon(Icons.sync),
            onPressed: _connection?.isConnected == true
                ? () => context.read<ConnectionBloc>().add(
                      TriggerSync(connectionId: widget.connectionId),
                    )
                : null,
            tooltip: '同步数据',
          ),
        ],
      ),
      body: BlocConsumer<ConnectionBloc, bloc.DataConnectionState>(
        listener: (context, state) {
          if (state is bloc.ConnectionError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.red,
              ),
            );
          } else if (state is bloc.ConnectionOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.green,
              ),
            );
            if (state.message == '已断开连接') {
              context.pop();
            }
          } else if (state is bloc.ConnectionSyncComplete) {
            final result = state.result;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  result.success
                      ? '同步完成: ${result.totalRecords}条数据'
                      : '同步失败: ${result.errorMessage}',
                ),
                backgroundColor: result.success ? Colors.green : Colors.red,
              ),
            );
          }
        },
        builder: (context, state) {
          bloc.ConnectionLoaded? loadedState;
          if (state is bloc.ConnectionLoaded) {
            loadedState = state;
          } else if (state is bloc.ConnectionError && state.previousState != null) {
            loadedState = state.previousState;
          } else if (state is bloc.ConnectionOperationInProgress) {
            loadedState = state.previousState;
          } else if (state is bloc.ConnectionSyncComplete) {
            loadedState = state.currentState;
          }

          if (loadedState != null) {
            _connection = loadedState.connections.firstWhere(
              (c) => c.id == widget.connectionId,
              orElse: () => loadedState!.connections.first,
            );
            _connector = loadedState.connectors.firstWhere(
              (c) => c.id == _connection?.connectorId,
              orElse: () => loadedState!.connectors.first,
            );
            _editedPermissions ??= _connection?.usagePermissions;
          }

          if (_connection == null) {
            return const Center(child: CircularProgressIndicator());
          }

          return Stack(
            children: [
              _buildContent(context),
              if (state is bloc.ConnectionOperationInProgress)
                Container(
                  color: Colors.black26,
                  child: const Center(child: CircularProgressIndicator()),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildContent(BuildContext context) {
    final theme = Theme.of(context);
    final connection = _connection!;
    final connector = _connector;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Status Card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: (connection.isConnected
                                ? Colors.green
                                : Colors.grey)
                            .withOpacity(0.1),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Icon(
                        Icons.extension,
                        color: connection.isConnected ? Colors.green : Colors.grey,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            connector?.displayNameZh ?? connection.connectorName,
                            style: theme.textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          _buildStatusBadge(connection.status),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Divider(),
                const SizedBox(height: 16),
                _buildInfoRow(
                  context,
                  icon: Icons.calendar_today,
                  label: '连接时间',
                  value: connection.connectedAt != null
                      ? _formatDate(connection.connectedAt!)
                      : '-',
                ),
                _buildInfoRow(
                  context,
                  icon: Icons.sync,
                  label: '上次同步',
                  value: connection.lastSyncAt != null
                      ? _formatDateTime(connection.lastSyncAt!)
                      : '从未同步',
                ),
                _buildInfoRow(
                  context,
                  icon: Icons.schedule,
                  label: '下次同步',
                  value: connection.nextSyncAt != null
                      ? _formatDateTime(connection.nextSyncAt!)
                      : '-',
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Sync Settings Card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '同步设置',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('自动同步'),
                    Switch(
                      value: connection.syncEnabled,
                      onChanged: (value) {
                        context.read<ConnectionBloc>().add(
                              UpdateConnectionSettings(
                                connectionId: widget.connectionId,
                                syncEnabled: value,
                              ),
                            );
                      },
                      activeColor: AppColors.primary,
                    ),
                  ],
                ),
                const Divider(),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('同步频率'),
                  trailing: DropdownButton<SyncFrequency>(
                    value: connection.syncFrequency,
                    underline: const SizedBox.shrink(),
                    onChanged: (value) {
                      if (value != null) {
                        context.read<ConnectionBloc>().add(
                              UpdateConnectionSettings(
                                connectionId: widget.connectionId,
                                syncFrequency: value,
                              ),
                            );
                      }
                    },
                    items: SyncFrequency.values.map((freq) {
                      return DropdownMenuItem(
                        value: freq,
                        child: Text(freq.displayName),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Permission Settings Card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                PermissionToggle(
                  permissions: _editedPermissions ?? connection.usagePermissions,
                  onChanged: (permissions) {
                    setState(() {
                      _editedPermissions = permissions;
                    });
                    context.read<ConnectionBloc>().add(
                          UpdateConnectionSettings(
                            connectionId: widget.connectionId,
                            usagePermissions: permissions,
                          ),
                        );
                  },
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 24),

        // Error Info
        if (connection.hasError && connection.errorMessage != null)
          Card(
            color: Colors.red.withOpacity(0.1),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: Colors.red),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '连接错误',
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: Colors.red,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          connection.errorMessage!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: Colors.red.shade700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

        const SizedBox(height: 24),

        // Disconnect Button
        OutlinedButton.icon(
          onPressed: () => _confirmDisconnect(context),
          icon: const Icon(Icons.link_off, color: Colors.red),
          label: const Text('断开连接'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.red,
            side: const BorderSide(color: Colors.red),
            padding: const EdgeInsets.symmetric(vertical: 16),
          ),
        ),

        const SizedBox(height: 32),
      ],
    );
  }

  Widget _buildStatusBadge(ConnectionStatus status) {
    Color color;
    String text;

    switch (status) {
      case ConnectionStatus.connected:
        color = Colors.green;
        text = '已连接';
        break;
      case ConnectionStatus.syncing:
        color = Colors.blue;
        text = '同步中';
        break;
      case ConnectionStatus.error:
        color = Colors.red;
        text = '错误';
        break;
      case ConnectionStatus.expired:
        color = Colors.orange;
        text = '已过期';
        break;
      case ConnectionStatus.connecting:
        color = Colors.blue;
        text = '连接中';
        break;
      default:
        color = Colors.grey;
        text = '未连接';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildInfoRow(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.textSecondary),
          const SizedBox(width: 12),
          Text(
            label,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.textSecondary,
                ),
          ),
          const Spacer(),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}/${dt.month}/${dt.day}';
  }

  String _formatDateTime(DateTime dt) {
    return '${dt.month}/${dt.day} ${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
  }

  void _confirmDisconnect(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('断开连接'),
        content: const Text('确定要断开此数据连接吗？断开后将停止同步数据。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              context
                  .read<ConnectionBloc>()
                  .add(DisconnectConnection(widget.connectionId));
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('断开'),
          ),
        ],
      ),
    );
  }
}
