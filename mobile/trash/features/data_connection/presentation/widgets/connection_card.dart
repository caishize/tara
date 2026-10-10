import 'package:flutter/material.dart';

import '../../domain/entities/data_connection.dart';
import '../../../../app/theme/app_colors.dart';

/// Card displaying a data connection status
class ConnectionCard extends StatelessWidget {
  final DataConnection connection;
  final String? connectorDisplayName;
  final String? connectorIcon;
  final VoidCallback? onTap;
  final VoidCallback? onSync;
  final VoidCallback? onDisconnect;

  const ConnectionCard({
    super.key,
    required this.connection,
    this.connectorDisplayName,
    this.connectorIcon,
    this.onTap,
    this.onSync,
    this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _buildIcon(context),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          connectorDisplayName ?? connection.connectorName,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 2),
                        _buildStatusBadge(context),
                      ],
                    ),
                  ),
                  if (connection.isConnected) ...[
                    IconButton(
                      icon: const Icon(Icons.sync, size: 20),
                      onPressed: onSync,
                      tooltip: '同步',
                    ),
                  ],
                  PopupMenuButton<String>(
                    icon: const Icon(Icons.more_vert, size: 20),
                    onSelected: (value) {
                      if (value == 'disconnect') {
                        onDisconnect?.call();
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'disconnect',
                        child: Row(
                          children: [
                            Icon(Icons.link_off, size: 18, color: Colors.red),
                            SizedBox(width: 8),
                            Text('断开连接', style: TextStyle(color: Colors.red)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              if (connection.lastSyncAt != null) ...[
                const SizedBox(height: 8),
                Text(
                  '上次同步: ${_formatDateTime(connection.lastSyncAt!)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
              if (connection.hasError && connection.errorMessage != null) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, size: 16, color: Colors.red),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          connection.errorMessage!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: Colors.red,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIcon(BuildContext context) {
    IconData iconData;
    switch (connectorIcon) {
      case 'google':
        iconData = Icons.g_mobiledata;
        break;
      case 'microsoft':
        iconData = Icons.window;
        break;
      case 'calendar_today':
        iconData = Icons.calendar_today;
        break;
      case 'email':
        iconData = Icons.email;
        break;
      default:
        iconData = Icons.extension;
    }

    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: connection.isConnected
            ? AppColors.primary.withOpacity(0.1)
            : Colors.grey.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        iconData,
        color: connection.isConnected ? AppColors.primary : Colors.grey,
        size: 24,
      ),
    );
  }

  Widget _buildStatusBadge(BuildContext context) {
    Color color;
    String text;

    switch (connection.status) {
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
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  String _formatDateTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);

    if (diff.inMinutes < 1) {
      return '刚刚';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}分钟前';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}小时前';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}天前';
    } else {
      return '${dt.month}/${dt.day} ${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
    }
  }
}
