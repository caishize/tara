import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../data/datasources/connections_remote_datasource.dart';
import '../../data/datasources/profile_remote_datasource.dart';
import '../../data/models/connection_model.dart';

/// Data management page matching the "数据管理" prototype
class DataBackupPage extends StatelessWidget {
  const DataBackupPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const _DataBackupContent();
  }
}

class _DataBackupContent extends StatefulWidget {
  const _DataBackupContent();

  @override
  State<_DataBackupContent> createState() => _DataBackupContentState();
}

class _DataBackupContentState extends State<_DataBackupContent> {
  Map<String, dynamic> _dataStats = {};
  bool _isLoadingStats = true;
  List<UserConnection> _connections = [];
  bool _isLoadingConnections = true;

  @override
  void initState() {
    super.initState();
    _loadDataStats();
    _loadConnections();
  }

  Future<void> _loadDataStats() async {
    try {
      final dataSource = getIt<ProfileRemoteDataSource>();
      final stats = await dataSource.fetchDataStats();
      if (mounted) {
        setState(() {
          _dataStats = stats;
          _isLoadingStats = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingStats = false);
      }
    }
  }

  Future<void> _loadConnections() async {
    try {
      final dataSource = getIt<ConnectionsRemoteDataSource>();
      final connections = await dataSource.fetchConnections();
      if (mounted) {
        setState(() {
          _connections = connections;
          _isLoadingConnections = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingConnections = false);
      }
    }
  }

  double get _totalSizeMB {
    final chat = (_dataStats['chat_size_mb'] as num?)?.toDouble() ?? 3.2;
    final memory = (_dataStats['memory_size_mb'] as num?)?.toDouble() ?? 5.6;
    final insight =
        (_dataStats['insight_size_mb'] as num?)?.toDouble() ?? 1.8;
    final event = (_dataStats['event_size_mb'] as num?)?.toDouble() ?? 1.7;
    return chat + memory + insight + event;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: const CustomAppBar(title: '数据管理'),
      body: RefreshIndicator(
        onRefresh: () async {
          await Future.wait([_loadDataStats(), _loadConnections()]);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Storage card
            _buildStorageCard(),
            const SizedBox(height: 20),

            // Data connections card (matching prototype)
            _buildDataConnectionsCard(),
            const SizedBox(height: 20),

            // Data categories label
            const Text(
              '数据分类',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Color(0xFF6D6C6A),
              ),
            ),
            const SizedBox(height: 8),

            // Data category list
            _buildDataCategoryGroup(),
            const SizedBox(height: 20),

            // Danger label
            const Text(
              '危险操作',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Color(0xFFE53935),
              ),
            ),
            const SizedBox(height: 8),

            // Clear all button
            _buildClearAllButton(),
            const SizedBox(height: 12),

            // Warning text
            const Text(
              '清空所有数据将删除聊天记录、记忆、洞察和事件数据，但保留账户信息。此操作不可恢复。',
              style: TextStyle(
                fontSize: 12,
                color: Color(0xFF9C9B99),
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStorageCard() {
    if (_isLoadingStats) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.accentGreenLight,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }
    final total = _totalSizeMB;
    const maxStorage = 100.0;
    final progress = (total / maxStorage).clamp(0.0, 1.0);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.accentGreenLight,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.storage_outlined,
                  size: 20, color: AppColors.accentGreen),
              const SizedBox(width: 8),
              Text(
                '存储使用',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.accentGreen,
                ),
              ),
              const Spacer(),
              Text(
                '${total.toStringAsFixed(1)} MB / ${maxStorage.toInt()} MB',
                style: const TextStyle(
                  fontSize: 13,
                  color: Color(0xFF6D6C6A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            height: 8,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(4),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: progress,
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.accentGreen,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDataConnectionsCard() {
    final connected = _connections.where((c) => c.isConnected).toList();
    final connectedCount = connected.length;
    final totalCount = _connections.length;

    // Build dynamic chips from actual connections
    final chips = <Widget>[];
    const chipIconMap = <String, IconData>{
      'calendar': Icons.calendar_today,
      'google_calendar': Icons.calendar_today,
      'email': Icons.mail_outline,
      'imap': Icons.mail_outline,
      'contacts': Icons.contacts_outlined,
      'mcp': Icons.extension_outlined,
      'mcp_service': Icons.extension_outlined,
    };
    const chipLabelMap = <String, String>{
      'calendar': '日历',
      'google_calendar': '日历',
      'email': '邮件',
      'imap': '邮件',
      'contacts': '通讯录',
      'mcp': 'MCP',
      'mcp_service': 'MCP',
    };

    // Deduplicate by provider type, show max 3 chips
    final seenTypes = <String>{};
    for (final conn in _connections) {
      final key = conn.providerType.toLowerCase();
      if (seenTypes.contains(key)) continue;
      seenTypes.add(key);
      if (chips.length >= 3) break;

      final icon = chipIconMap[key] ?? Icons.extension_outlined;
      final label = chipLabelMap[key] ?? conn.providerType;
      chips.add(_buildChip(icon, label, isActive: conn.isConnected));
    }

    // "+N" chip if there are more types
    final remaining = seenTypes.length > 3 ? seenTypes.length - 3 : 0;
    final unseenCount = totalCount - seenTypes.length;
    final extraCount = remaining + (unseenCount > 0 ? unseenCount : 0);
    if (extraCount > 0) {
      chips.add(_buildCountChip('+$extraCount'));
    }

    return GestureDetector(
      onTap: () => context.push(Routes.connections),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                const Icon(Icons.power_outlined,
                    size: 20, color: AppColors.accentGreen),
                const SizedBox(width: 10),
                const Text(
                  '数据连接',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const Spacer(),
                const Icon(
                  Icons.chevron_right,
                  size: 18,
                  color: AppColors.textTertiary,
                ),
              ],
            ),
            const SizedBox(height: 14),
            // Description
            Text(
              connectedCount > 0
                  ? '已连接 $connectedCount 个服务，管理外部数据源和 MCP 服务'
                  : '管理外部数据源和 MCP 服务连接',
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF6D6C6A),
              ),
            ),
            if (chips.isNotEmpty) ...[
              const SizedBox(height: 14),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: chips,
              ),
            ],
            if (_isLoadingConnections) ...[
              const SizedBox(height: 14),
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildChip(IconData icon, String label, {bool isActive = false}) {
    final bgColor =
        isActive ? AppColors.accentGreenLight : const Color(0xFFEDECEA);
    final fgColor =
        isActive ? AppColors.accentGreen : const Color(0xFF6D6C6A);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fgColor),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: fgColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCountChip(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFEDECEA),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w500,
          color: AppColors.textTertiary,
        ),
      ),
    );
  }

  Widget _buildDataCategoryGroup() {
    final chatCount =
        (_dataStats['chat_messages'] as num?)?.toInt() ?? 0;
    final memoryCount = (_dataStats['memories'] as num?)?.toInt() ?? 0;
    final insightCount =
        (_dataStats['insights'] as num?)?.toInt() ?? 0;
    final eventCount = (_dataStats['events'] as num?)?.toInt() ?? 0;

    final chatSize =
        (_dataStats['chat_size_mb'] as num?)?.toDouble() ?? 3.2;
    final memorySize =
        (_dataStats['memory_size_mb'] as num?)?.toDouble() ?? 5.6;
    final insightSize =
        (_dataStats['insight_size_mb'] as num?)?.toDouble() ?? 1.8;
    final eventSize =
        (_dataStats['event_size_mb'] as num?)?.toDouble() ?? 1.7;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          _DataCategoryRow(
            icon: Icons.chat_bubble_outline,
            title: '聊天记录',
            description:
                '$chatCount 条对话 · ${chatSize.toStringAsFixed(1)} MB',
            onClear: () => _showClearConfirmation('chat', '聊天记录'),
          ),
          const _CategoryDivider(),
          _DataCategoryRow(
            icon: Icons.psychology_outlined,
            title: '家庭记忆',
            description:
                '$memoryCount 条记忆 · ${memorySize.toStringAsFixed(1)} MB',
            onClear: () => _showClearConfirmation('memories', '家庭记忆'),
          ),
          const _CategoryDivider(),
          _DataCategoryRow(
            icon: Icons.auto_awesome,
            title: '洞察记录',
            description:
                '$insightCount 条洞察 · ${insightSize.toStringAsFixed(1)} MB',
            onClear: () =>
                _showClearConfirmation('insights', '洞察记录'),
          ),
          const _CategoryDivider(),
          _DataCategoryRow(
            icon: Icons.calendar_today_outlined,
            title: '事件数据',
            description:
                '$eventCount 个事件 · ${eventSize.toStringAsFixed(1)} MB',
            onClear: () => _showClearConfirmation('events', '事件数据'),
          ),
        ],
      ),
    );
  }

  Widget _buildClearAllButton() {
    return GestureDetector(
      onTap: () => _showClearAllConfirmation(),
      child: Container(
        height: 48,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE53935)),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.delete_outline, size: 18, color: Color(0xFFE53935)),
            SizedBox(width: 8),
            Text(
              '清空所有数据',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: Color(0xFFE53935),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showClearConfirmation(String category, String label) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('清除$label'),
        content: Text('确定要清除所有$label吗？此操作不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await _performClear(category);
            },
            style:
                TextButton.styleFrom(foregroundColor: const Color(0xFFE53935)),
            child: const Text('确认清除'),
          ),
        ],
      ),
    );
  }

  void _showClearAllConfirmation() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('清空所有数据'),
        content: const Text(
          '此操作将永久删除所有聊天记录、记忆、洞察和事件数据，但保留账户信息。此操作不可恢复！',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await _performClearAll();
            },
            style:
                TextButton.styleFrom(foregroundColor: const Color(0xFFE53935)),
            child: const Text('确认清除所有'),
          ),
        ],
      ),
    );
  }

  Future<void> _performClear(String category) async {
    try {
      final dataSource = getIt<ProfileRemoteDataSource>();
      await dataSource.clearDataByCategory(category, '');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('数据已清除'),
            backgroundColor: AppColors.success,
          ),
        );
        await _loadDataStats();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('清除失败: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  Future<void> _performClearAll() async {
    try {
      final dataSource = getIt<ProfileRemoteDataSource>();
      await dataSource.clearAllData('');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('所有数据已清除'),
            backgroundColor: AppColors.success,
          ),
        );
        await _loadDataStats();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('清除失败: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }
}

class _DataCategoryRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final VoidCallback onClear;

  const _DataCategoryRow({
    required this.icon,
    required this.title,
    required this.description,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.accentGreen),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: Color(0xFF1A1918),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF9C9B99),
                  ),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: onClear,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFFEDECEA),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Text(
                '清空',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF6D6C6A),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryDivider extends StatelessWidget {
  const _CategoryDivider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(left: 48, right: 16),
      child: Divider(height: 1, thickness: 1, color: Color(0xFFE5E4E1)),
    );
  }
}
