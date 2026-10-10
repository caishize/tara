import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../core/auth/oauth_handler.dart';
import '../../domain/entities/connector_metadata.dart';
import '../bloc/connection_bloc.dart';
import '../bloc/connection_event.dart';
import '../bloc/connection_state.dart' as bloc;
import '../widgets/connector_tile.dart';

/// Page for adding new data connections
class AddConnectionPage extends StatefulWidget {
  const AddConnectionPage({super.key});

  @override
  State<AddConnectionPage> createState() => _AddConnectionPageState();
}

class _AddConnectionPageState extends State<AddConnectionPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  DataCategory? _selectedCategory;
  final OAuthHandler _oauthHandler = OAuthHandler();
  bool _isOAuthInProgress = false;

  final List<DataCategory> _categories = [
    DataCategory.calendar,
    DataCategory.email,
    DataCategory.ecommerce,
    DataCategory.foodDelivery,
    DataCategory.travel,
    DataCategory.finance,
    DataCategory.social,
    DataCategory.productivity,
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _categories.length + 1, vsync: this);
    _tabController.addListener(() {
      setState(() {
        if (_tabController.index == 0) {
          _selectedCategory = null;
        } else {
          _selectedCategory = _categories[_tabController.index - 1];
        }
      });
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _oauthHandler.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('添加数据连接'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: [
            const Tab(text: '全部'),
            ..._categories.map((c) => Tab(text: c.displayName)),
          ],
        ),
      ),
      body: BlocConsumer<ConnectionBloc, bloc.DataConnectionState>(
        listener: (context, state) {
          if (state is bloc.ConnectionAuthRequired) {
            _launchOAuth(context, state.authUrl, state.connectionId);
          } else if (state is bloc.ConnectionError) {
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
            context.pop();
          }
        },
        builder: (context, state) {
          if (state is bloc.ConnectionLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          bloc.ConnectionLoaded? loadedState;
          if (state is bloc.ConnectionLoaded) {
            loadedState = state;
          } else if (state is bloc.ConnectionError && state.previousState != null) {
            loadedState = state.previousState;
          } else if (state is bloc.ConnectionOperationInProgress) {
            loadedState = state.previousState;
          } else if (state is bloc.ConnectionAuthRequired && state.previousState != null) {
            loadedState = state.previousState;
          }

          if (loadedState == null) {
            return const Center(child: Text('加载中...'));
          }

          return Stack(
            children: [
              _buildConnectorList(context, loadedState),
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

  Widget _buildConnectorList(BuildContext context, bloc.ConnectionLoaded state) {
    final connectedIds = state.connections.map((c) => c.connectorId).toSet();

    List<ConnectorMetadata> filteredConnectors;
    if (_selectedCategory == null) {
      filteredConnectors = state.connectors;
    } else {
      filteredConnectors = state.connectors
          .where((c) => c.category == _selectedCategory)
          .toList();
    }

    if (filteredConnectors.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.extension_off, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              '暂无可用连接器',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      );
    }

    // Group by category if showing all
    if (_selectedCategory == null) {
      return ListView(
        children: [
          const SizedBox(height: 8),
          _buildInfoCard(context),
          ...DataCategory.values.where((c) => c != DataCategory.other).map((category) {
            final categoryConnectors =
                filteredConnectors.where((c) => c.category == category).toList();
            if (categoryConnectors.isEmpty) return const SizedBox.shrink();

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildCategoryHeader(context, category),
                ...categoryConnectors.map((connector) {
                  return ConnectorTile(
                    connector: connector,
                    isConnected: connectedIds.contains(connector.id),
                    onTap: () => _initiateConnection(context, connector),
                  );
                }),
              ],
            );
          }),
          const SizedBox(height: 32),
        ],
      );
    }

    return ListView(
      children: [
        const SizedBox(height: 8),
        _buildInfoCard(context),
        ...filteredConnectors.map((connector) {
          return ConnectorTile(
            connector: connector,
            isConnected: connectedIds.contains(connector.id),
            onTap: () => _initiateConnection(context, connector),
          );
        }),
        const SizedBox(height: 32),
      ],
    );
  }

  Widget _buildInfoCard(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(16),
      color: AppColors.primary.withOpacity(0.05),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.info_outline, color: AppColors.primary, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '数据安全承诺',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '您的数据将被加密存储，仅在您授权的范围内使用，您可以随时断开连接。',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryHeader(BuildContext context, DataCategory category) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          Icon(
            _getCategoryIcon(category),
            size: 18,
            color: AppColors.textSecondary,
          ),
          const SizedBox(width: 8),
          Text(
            category.displayName,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: AppColors.textSecondary,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ],
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
      case DataCategory.foodDelivery:
        return Icons.restaurant;
      case DataCategory.social:
        return Icons.people;
      case DataCategory.health:
        return Icons.favorite;
      case DataCategory.finance:
        return Icons.account_balance;
      case DataCategory.location:
        return Icons.location_on;
      case DataCategory.travel:
        return Icons.flight;
      case DataCategory.productivity:
        return Icons.construction;
      case DataCategory.other:
        return Icons.extension;
    }
  }

  void _initiateConnection(BuildContext context, ConnectorMetadata connector) {
    // Check if connector is available
    if (!connector.isAvailable) {
      // Show coming soon dialog
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(connector.displayNameZh),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.schedule, color: AppColors.primary),
                  const SizedBox(width: 8),
                  const Text('即将上线'),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                '${connector.displayNameZh} 连接功能正在开发中，敬请期待！',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppColors.textSecondary,
                    ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('好的'),
            ),
          ],
        ),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _ConnectorConfirmSheet(
        connector: connector,
        onConfirm: () {
          Navigator.of(ctx).pop();
          context.read<ConnectionBloc>().add(InitiateConnection(
                connectorId: connector.id,
              ));
        },
      ),
    );
  }

  Future<void> _launchOAuth(
    BuildContext context,
    String authUrl,
    String connectionId,
  ) async {
    if (_isOAuthInProgress) return;

    setState(() {
      _isOAuthInProgress = true;
    });

    try {
      // Show loading indicator
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Row(
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                ),
                SizedBox(width: 16),
                Text('正在打开授权页面...'),
              ],
            ),
            duration: Duration(seconds: 2),
          ),
        );
      }

      // Perform OAuth authentication
      final result = await _oauthHandler.authorize(authUrl);

      if (!context.mounted) return;

      if (result.success && result.code != null) {
        // Complete the connection with the received code
        context.read<ConnectionBloc>().add(CompleteConnection(
              connectionId: connectionId,
              code: result.code!,
              state: result.state,
            ));
      } else if (result.error == 'cancelled') {
        // User cancelled - no need to show error
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('授权已取消'),
            backgroundColor: Colors.orange,
          ),
        );
      } else {
        // Show error message
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result.errorDescription ?? '授权失败：${result.error}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('授权过程出错：$e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isOAuthInProgress = false;
        });
      }
    }
  }
}

/// Bottom sheet for confirming connector setup
class _ConnectorConfirmSheet extends StatelessWidget {
  final ConnectorMetadata connector;
  final VoidCallback onConfirm;

  const _ConnectorConfirmSheet({
    required this.connector,
    required this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.extension,
                  color: AppColors.primary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      connector.displayNameZh,
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      connector.category.displayName,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Text(
            '权限说明',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            connector.dataUsageDescriptionZh.isNotEmpty
                ? connector.dataUsageDescriptionZh
                : '我们将请求以下权限来同步您的数据：',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 12),
          ...connector.requiredScopes.map((scope) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  const Icon(Icons.check_circle, color: Colors.green, size: 18),
                  const SizedBox(width: 8),
                  Expanded(child: Text(scope)),
                ],
              ),
            );
          }),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Icon(Icons.shield, color: Colors.blue, size: 20),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '您的数据将被安全加密存储，您可以随时断开连接并删除数据。',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: onConfirm,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: const Text('授权连接'),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('取消'),
            ),
          ),
          SizedBox(height: MediaQuery.of(context).viewInsets.bottom),
        ],
      ),
    );
  }
}
