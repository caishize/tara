import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/connector_metadata_model.dart';
import '../../domain/entities/connector_metadata.dart';
import '../bloc/connection_bloc.dart';
import '../bloc/connection_event.dart';
import '../bloc/connection_state.dart' as bloc;
import '../widgets/connection_card.dart';
import '../widgets/usage_stats_card.dart';

/// Main hub page for data connections
class DataConnectionHubPage extends StatefulWidget {
  const DataConnectionHubPage({super.key});

  @override
  State<DataConnectionHubPage> createState() => _DataConnectionHubPageState();
}

class _DataConnectionHubPageState extends State<DataConnectionHubPage> {
  @override
  void initState() {
    super.initState();
    context.read<ConnectionBloc>().add(const RefreshConnectionData());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('数据连接中心'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => context.push(Routes.addConnection),
            tooltip: '添加连接',
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
          if (state is bloc.ConnectionLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is bloc.ConnectionLoaded) {
            return _buildContent(context, state);
          }

          if (state is bloc.ConnectionError && state.previousState != null) {
            return _buildContent(context, state.previousState!);
          }

          if (state is bloc.ConnectionOperationInProgress) {
            return Stack(
              children: [
                _buildContent(context, state.previousState),
                Container(
                  color: Colors.black26,
                  child: const Center(child: CircularProgressIndicator()),
                ),
              ],
            );
          }

          return _buildEmptyState(context);
        },
      ),
    );
  }

  Widget _buildContent(BuildContext context, bloc.ConnectionLoaded state) {
    return RefreshIndicator(
      onRefresh: () async {
        context.read<ConnectionBloc>().add(const RefreshConnectionData());
      },
      child: ListView(
        children: [
          // Usage Statistics
          if (state.usageSummary != null)
            UsageStatsCard(summary: state.usageSummary!),

          // Active Connections
          if (state.connections.isNotEmpty) ...[
            _buildSectionHeader(context, '已连接数据源'),
            ...state.connections.map((connection) {
              final connector = state.connectors.firstWhere(
                (c) => c.id == connection.connectorId,
                orElse: () => ConnectorMetadataModel(
                  id: connection.connectorId,
                  name: connection.connectorName,
                  displayName: connection.connectorName,
                  displayNameZh: connection.connectorName,
                  description: '',
                  descriptionZh: '',
                  icon: 'extension',
                  category: DataCategory.other,
                  authType: AuthType.oauth2,
                  capabilities: const ConnectorCapabilities(),
                  requiredScopes: const [],
                  optionalScopes: const [],
                  dataRetentionDays: 90,
                  isAvailable: true,
                  regions: const ['CN'],
                  dataUsageDescription: '',
                  dataUsageDescriptionZh: '',
                ),
              );
              return ConnectionCard(
                connection: connection,
                connectorDisplayName: connector.displayNameZh,
                connectorIcon: connector.icon,
                onTap: () async {
                  await context.push(Routes.connectionDetail(connection.id));
                  if (context.mounted) {
                    context.read<ConnectionBloc>().add(const RefreshConnectionData());
                  }
                },
                onSync: () {
                  context.read<ConnectionBloc>().add(TriggerSync(
                        connectionId: connection.id,
                      ));
                },
                onDisconnect: () => _confirmDisconnect(context, connection.id),
              );
            }),
          ],

          // Quick Add Section
          if (state.connections.isEmpty) ...[
            _buildEmptyConnectionsCard(context),
          ] else ...[
            const SizedBox(height: 16),
            _buildQuickAddSection(context, state),
          ],

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(BuildContext context, String title) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Text(
        title,
        style: theme.textTheme.titleSmall?.copyWith(
          color: AppColors.textSecondary,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.link_off,
            size: 64,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 16),
          Text(
            '暂无数据连接',
            style: TextStyle(
              fontSize: 18,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '连接外部数据源，让秘书更好地帮助您',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => context.push(Routes.addConnection),
            icon: const Icon(Icons.add),
            label: const Text('添加数据连接'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyConnectionsCard(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(
              Icons.cloud_sync,
              size: 48,
              color: AppColors.primary.withOpacity(0.5),
            ),
            const SizedBox(height: 16),
            Text(
              '连接您的数据源',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              '连接日历、邮箱等服务，让秘书能够：\n• 自动同步日程安排\n• 解析订单和行程信息\n• 生成更精准的智能建议',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.textSecondary,
                  ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => context.push(Routes.addConnection),
              icon: const Icon(Icons.add),
              label: const Text('添加数据连接'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(200, 44),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickAddSection(BuildContext context, bloc.ConnectionLoaded state) {
    final connectedIds = state.connections.map((c) => c.connectorId).toSet();
    final unconnectedConnectors = state.connectors
        .where((c) => !connectedIds.contains(c.id) && c.isAvailable)
        .take(3)
        .toList();

    if (unconnectedConnectors.isEmpty) return const SizedBox.shrink();

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '推荐连接',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                TextButton(
                  onPressed: () => context.push(Routes.addConnection),
                  child: const Text('查看全部'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...unconnectedConnectors.map((connector) {
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    _getCategoryIcon(connector.category),
                    color: AppColors.primary,
                    size: 20,
                  ),
                ),
                title: Text(connector.displayNameZh),
                subtitle: Text(
                  connector.descriptionZh,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: const Icon(Icons.add_circle_outline),
                onTap: () {
                  context.read<ConnectionBloc>().add(InitiateConnection(
                        connectorId: connector.id,
                      ));
                },
              );
            }),
          ],
        ),
      ),
    );
  }

  IconData _getCategoryIcon(DataCategory category) {
    switch (category) {
      case DataCategory.calendar:
        return Icons.calendar_today;
      case DataCategory.email:
        return Icons.email;
      case DataCategory.ecommerce:
        return Icons.shopping_cart;
      case DataCategory.social:
        return Icons.people;
      case DataCategory.health:
        return Icons.favorite;
      case DataCategory.finance:
        return Icons.account_balance;
      default:
        return Icons.extension;
    }
  }

  void _confirmDisconnect(BuildContext context, String connectionId) {
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
              context.read<ConnectionBloc>().add(DisconnectConnection(connectionId));
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('断开'),
          ),
        ],
      ),
    );
  }
}
