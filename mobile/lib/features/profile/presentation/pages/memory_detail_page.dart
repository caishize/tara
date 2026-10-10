import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../data/datasources/memory_browser_remote_datasource.dart';
import '../../data/models/memory_item_model.dart';
import '../bloc/memory_browser_bloc.dart';

class MemoryDetailPage extends StatefulWidget {
  final String memoryId;
  final MemoryItem? memory;

  const MemoryDetailPage({
    super.key,
    required this.memoryId,
    this.memory,
  });

  @override
  State<MemoryDetailPage> createState() => _MemoryDetailPageState();
}

class _MemoryDetailPageState extends State<MemoryDetailPage> {
  MemoryItem? _memory;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _memory = widget.memory;
    if (_memory == null) {
      _fetchMemory();
    }
  }

  Future<void> _fetchMemory() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final ds = getIt<MemoryBrowserRemoteDataSource>();
      final mem = await ds.fetchMemoryById(widget.memoryId);
      if (mounted) {
        setState(() {
          _memory = mem;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '加载记忆失败';
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: const CustomAppBar(title: '记忆详情'),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null || _memory == null) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: const CustomAppBar(title: '记忆详情'),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(_error ?? '记忆不存在'),
              const SizedBox(height: 12),
              TextButton(
                onPressed: _fetchMemory,
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      );
    }

    return _MemoryDetailContent(memory: _memory!);
  }
}

class _MemoryDetailContent extends StatelessWidget {
  final MemoryItem memory;

  const _MemoryDetailContent({required this.memory});

  @override
  Widget build(BuildContext context) {
    final badge = _getTypeBadge(memory.type);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: CustomAppBar(
        title: '记忆详情',
        backgroundColor: AppColors.background,
        actions: [
          IconButton(
            icon: const Icon(Icons.more_horiz,
                color: Color(0xFF6D6C6A), size: 22),
            onPressed: () => _showMoreMenu(context),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Type badge + date
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: badge.bgColor,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(badge.icon, size: 12, color: badge.color),
                    const SizedBox(width: 4),
                    Text(
                      badge.label,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                        color: badge.color,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '${_formatDate(memory.createdAt)} 提取',
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFF9C9B99),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Content card
          _buildContentCard(),
          const SizedBox(height: 12),

          // Person entities card
          if (memory.personEntities.isNotEmpty) ...[
            _buildPersonEntitiesCard(),
            const SizedBox(height: 12),
          ],

          // Context entities card (location, time, etc.)
          if (memory.contextEntities.isNotEmpty) ...[
            _buildContextEntitiesCard(),
            const SizedBox(height: 12),
          ],

          // Source card
          _buildSourceCard(context),
          const SizedBox(height: 20),

          // Action buttons
          _buildActionButtons(context),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildContentCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '记忆内容',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF6D6C6A),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            memory.content,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF1A1918),
              height: 1.6,
            ),
          ),
          const SizedBox(height: 14),
          // Importance stars
          Row(
            children: [
              const Text(
                '重要程度',
                style: TextStyle(
                  fontSize: 12,
                  color: Color(0xFF9C9B99),
                ),
              ),
              const SizedBox(width: 8),
              ...List.generate(5, (i) {
                return Padding(
                  padding: EdgeInsets.only(right: i < 4 ? 2 : 0),
                  child: Icon(
                    Icons.star,
                    size: 16,
                    color: i < memory.importance
                        ? AppColors.accentWarm
                        : const Color(0xFFE5E4E1),
                  ),
                );
              }),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPersonEntitiesCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '关联人物',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF6D6C6A),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: memory.personEntities.map((entity) {
              return Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F5E9),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.person_outline,
                        size: 14, color: Color(0xFF3D8A5A)),
                    const SizedBox(width: 4),
                    Text(
                      entity.name,
                      style: const TextStyle(
                        fontSize: 13,
                        color: Color(0xFF3D8A5A),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildContextEntitiesCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '相关信息',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Color(0xFF6D6C6A),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: memory.contextEntities.map((entity) {
              final badge = _getEntityBadge(entity.type ?? '');
              return Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: badge.bgColor,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(badge.icon, size: 14, color: badge.color),
                    const SizedBox(width: 4),
                    Text(
                      entity.name,
                      style: TextStyle(
                        fontSize: 13,
                        color: badge.color,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  static _TypeBadgeData _getEntityBadge(String type) {
    // Normalize: destination, trip_location → location
    if (type == 'destination' || type.contains('location')) {
      return _TypeBadgeData(
        label: '',
        icon: Icons.location_on_outlined,
        color: const Color(0xFF1976D2),
        bgColor: const Color(0xFFE3F2FD),
      );
    }
    // Normalize: start_date, end_date, time_hint, date, time, etc.
    if (type.contains('date') || type.contains('time')) {
      return _TypeBadgeData(
        label: '',
        icon: Icons.schedule_outlined,
        color: const Color(0xFF7B1FA2),
        bgColor: const Color(0xFFF3E5F5),
      );
    }
    // Trip/travel name
    if (type.contains('trip') || type.contains('travel')) {
      return _TypeBadgeData(
        label: '',
        icon: Icons.flight_outlined,
        color: const Color(0xFF00838F),
        bgColor: const Color(0xFFE0F7FA),
      );
    }
    switch (type) {
      case 'location':
        return _TypeBadgeData(
          label: '',
          icon: Icons.location_on_outlined,
          color: const Color(0xFF1976D2),
          bgColor: const Color(0xFFE3F2FD),
        );
      case 'emotion':
        return _TypeBadgeData(
          label: '',
          icon: Icons.mood_outlined,
          color: const Color(0xFFE65100),
          bgColor: const Color(0xFFFFF3E0),
        );
      case 'event':
        return _TypeBadgeData(
          label: '',
          icon: Icons.event_outlined,
          color: const Color(0xFF00695C),
          bgColor: const Color(0xFFE0F2F1),
        );
      case 'relationship':
        return _TypeBadgeData(
          label: '',
          icon: Icons.people_outline,
          color: const Color(0xFF5D4037),
          bgColor: const Color(0xFFEFEBE9),
        );
      case 'item':
        return _TypeBadgeData(
          label: '',
          icon: Icons.inventory_2_outlined,
          color: const Color(0xFF4527A0),
          bgColor: const Color(0xFFEDE7F6),
        );
      case 'amount':
        return _TypeBadgeData(
          label: '',
          icon: Icons.payments_outlined,
          color: const Color(0xFF2E7D32),
          bgColor: const Color(0xFFE8F5E9),
        );
      default:
        return _TypeBadgeData(
          label: '',
          icon: Icons.info_outline,
          color: const Color(0xFF455A64),
          bgColor: const Color(0xFFECEFF1),
        );
    }
  }

  Widget _buildSourceCard(BuildContext context) {
    final hasSource = memory.sourceSessionId != null;

    return GestureDetector(
      onTap: hasSource
          ? () {
              // Navigate to conversation tab
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('正在跳转到来源对话...'),
                  duration: Duration(seconds: 1),
                ),
              );
              context.go(Routes.conversation);
            }
          : null,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: const Color(0xFFEDECEA),
                borderRadius: BorderRadius.circular(8),
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.chat_bubble_outline,
                  size: 16, color: Color(0xFF6D6C6A)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '来源对话',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF1A1918),
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    hasSource
                        ? '${_formatDate(memory.createdAt)} 的对话中提取'
                        : '来源对话不可用',
                    style: TextStyle(
                      fontSize: 12,
                      color: hasSource
                          ? const Color(0xFF9C9B99)
                          : const Color(0xFFBDBDBD),
                    ),
                  ),
                ],
              ),
            ),
            if (hasSource)
              const Icon(Icons.chevron_right,
                  size: 18, color: Color(0xFF9C9B99))
            else
              const Icon(Icons.link_off,
                  size: 16, color: Color(0xFFBDBDBD)),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButtons(BuildContext context) {
    return Row(
      children: [
        // Edit button
        Expanded(
          child: GestureDetector(
            onTap: () {
              // Edit memory
            },
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.edit_outlined, size: 16, color: Colors.white),
                  SizedBox(width: 6),
                  Text(
                    '编辑',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        // Archive button
        Expanded(
          child: GestureDetector(
            onTap: () => _handleArchive(context),
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: const Color(0xFFEDECEA),
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.archive_outlined,
                      size: 16, color: Color(0xFF6D6C6A)),
                  SizedBox(width: 6),
                  Text(
                    '归档',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF6D6C6A),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        // Delete button
        Expanded(
          child: GestureDetector(
            onTap: () => _handleDelete(context),
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: const Color(0xFFFFEBEE),
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.delete_outline,
                      size: 16, color: Color(0xFFE53935)),
                  SizedBox(width: 6),
                  Text(
                    '删除',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFFE53935),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _showMoreMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFE5E4E1),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.share_outlined,
                  color: Color(0xFF6D6C6A)),
              title: const Text('分享'),
              onTap: () => Navigator.pop(ctx),
            ),
            ListTile(
              leading: const Icon(Icons.copy_outlined,
                  color: Color(0xFF6D6C6A)),
              title: const Text('复制内容'),
              onTap: () => Navigator.pop(ctx),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  void _handleArchive(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('归档记忆'),
        content: const Text('确定要归档这条记忆吗？归档后可在归档列表中查看。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              try {
                context
                    .read<MemoryBrowserBloc>()
                    .add(ArchiveMemory(memory.id));
              } catch (_) {
                // BLoC may not be in the tree if navigated directly
              }
              context.pop();
            },
            child: const Text('确认归档'),
          ),
        ],
      ),
    );
  }

  void _handleDelete(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除记忆'),
        content: const Text('确定要删除这条记忆吗？此操作不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              try {
                context
                    .read<MemoryBrowserBloc>()
                    .add(DeleteMemory(memory.id));
              } catch (_) {
                // BLoC may not be in the tree if navigated directly
              }
              context.pop();
            },
            style: TextButton.styleFrom(
                foregroundColor: const Color(0xFFE53935)),
            child: const Text('确认删除'),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}年${local.month}月${local.day}日';
  }

  static _TypeBadgeData _getTypeBadge(String type) {
    switch (type) {
      case 'preference':
        return _TypeBadgeData(
          label: '偏好',
          icon: Icons.favorite_outline,
          color: const Color(0xFF3D8A5A),
          bgColor: const Color(0xFFE8F5E9),
        );
      case 'general':
        return _TypeBadgeData(
          label: '事实',
          icon: Icons.bookmark_outline,
          color: const Color(0xFF1976D2),
          bgColor: const Color(0xFFE3F2FD),
        );
      case 'relationship':
        return _TypeBadgeData(
          label: '关系',
          icon: Icons.people_outline,
          color: const Color(0xFFE65100),
          bgColor: const Color(0xFFFFF3E0),
        );
      case 'life_event':
        return _TypeBadgeData(
          label: '事件',
          icon: Icons.calendar_today_outlined,
          color: const Color(0xFF7B1FA2),
          bgColor: const Color(0xFFF3E5F5),
        );
      case 'emotion':
        return _TypeBadgeData(
          label: '观点',
          icon: Icons.lightbulb_outline,
          color: const Color(0xFFE65100),
          bgColor: const Color(0xFFFFF3E0),
        );
      default:
        return _TypeBadgeData(
          label: '记忆',
          icon: Icons.psychology_outlined,
          color: const Color(0xFF3D8A5A),
          bgColor: const Color(0xFFE8F5E9),
        );
    }
  }
}

class _TypeBadgeData {
  final String label;
  final IconData icon;
  final Color color;
  final Color bgColor;

  const _TypeBadgeData({
    required this.label,
    required this.icon,
    required this.color,
    required this.bgColor,
  });
}
