import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/memory_item_model.dart';
import '../bloc/insight_history_bloc.dart';

/// Insight History page matching the prototype design "tOZe3" (洞察历史).
/// Shows all insights with type filters, search, and feedback buttons.
class InsightHistoryPage extends StatelessWidget {
  const InsightHistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<InsightHistoryBloc>()..add(const LoadInsightHistory()),
      child: const _InsightHistoryContent(),
    );
  }
}

class _InsightHistoryContent extends StatefulWidget {
  const _InsightHistoryContent();

  @override
  State<_InsightHistoryContent> createState() => _InsightHistoryContentState();
}

class _InsightHistoryContentState extends State<_InsightHistoryContent> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _buildHeader(context),
            // Search bar
            _buildSearchBar(),
            const SizedBox(height: 8),
            // Filter tabs
            BlocBuilder<InsightHistoryBloc, InsightHistoryState>(
              builder: (context, state) => _buildFilterTabs(context, state),
            ),
            const SizedBox(height: 4),
            // Content
            Expanded(
              child: BlocConsumer<InsightHistoryBloc, InsightHistoryState>(
                listener: (context, state) {
                  if (state is InsightHistoryError) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(state.message),
                        backgroundColor: AppColors.error,
                      ),
                    );
                  }
                },
                builder: (context, state) => _buildBody(context, state),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          GestureDetector(
            onTap: () {
              if (context.canPop()) context.pop();
            },
            child: const Icon(
              Icons.arrow_back_ios,
              color: Color(0xFF1A1918),
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          const Text(
            '洞察历史',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              color: Color(0xFF1A1918),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: TextField(
          controller: _searchController,
          decoration: InputDecoration(
            hintText: '搜索洞察...',
            hintStyle: const TextStyle(
              fontSize: 14,
              color: Color(0xFF9C9B99),
            ),
            prefixIcon: const Icon(Icons.search,
                color: Color(0xFF9C9B99), size: 18),
            suffixIcon: _searchController.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear,
                        size: 16, color: Color(0xFF9C9B99)),
                    onPressed: () {
                      _searchController.clear();
                      context
                          .read<InsightHistoryBloc>()
                          .add(const LoadInsightHistory());
                      setState(() {});
                    },
                  )
                : null,
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(vertical: 10),
          ),
          style: const TextStyle(fontSize: 14, color: Color(0xFF1A1918)),
          textInputAction: TextInputAction.search,
          onSubmitted: (query) {
            if (query.trim().isNotEmpty) {
              context
                  .read<InsightHistoryBloc>()
                  .add(SearchInsights(query.trim()));
            }
          },
          onChanged: (_) => setState(() {}),
        ),
      ),
    );
  }

  Widget _buildFilterTabs(BuildContext context, InsightHistoryState state) {
    final activeFilter =
        state is InsightHistoryLoaded ? state.activeFilter : null;

    const filters = [
      _InsightFilter(null, '全部'),
      _InsightFilter('reminder', '提醒'),
      _InsightFilter('suggestion', '建议'),
      _InsightFilter('observation', '观察'),
      _InsightFilter('connection', '关联'),
    ];

    return SizedBox(
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: filters.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final filter = filters[index];
          final isSelected = filter.type == activeFilter;
          return GestureDetector(
            onTap: () {
              context
                  .read<InsightHistoryBloc>()
                  .add(FilterInsightsByType(filter.type));
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: isSelected
                    ? AppColors.accentWarm
                    : Colors.white,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Center(
                child: Text(
                  filter.label,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight:
                        isSelected ? FontWeight.w500 : FontWeight.normal,
                    color: isSelected
                        ? Colors.white
                        : const Color(0xFF6D6C6A),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildBody(BuildContext context, InsightHistoryState state) {
    if (state is InsightHistoryLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state is InsightHistoryLoaded) {
      if (state.insights.isEmpty) {
        return _buildEmptyState(state);
      }

      return RefreshIndicator(
        onRefresh: () async {
          context
              .read<InsightHistoryBloc>()
              .add(const LoadInsightHistory());
        },
        child: ListView.separated(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          itemCount: state.insights.length,
          separatorBuilder: (_, __) => const SizedBox(height: 10),
          itemBuilder: (context, index) {
            return _InsightCard(
              insight: state.insights[index],
              onUseful: () {
                context.read<InsightHistoryBloc>().add(
                      SubmitInsightHistoryFeedback(
                        insightId: state.insights[index].id,
                        feedbackType: 'useful',
                      ),
                    );
              },
              onNotUseful: () {
                context.read<InsightHistoryBloc>().add(
                      SubmitInsightHistoryFeedback(
                        insightId: state.insights[index].id,
                        feedbackType: 'not_useful',
                      ),
                    );
              },
            );
          },
        ),
      );
    }

    if (state is InsightHistoryError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AppColors.textSecondary),
            const SizedBox(height: 16),
            Text(state.message, style: const TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () => context.read<InsightHistoryBloc>().add(const LoadInsightHistory()),
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }

    return const Center(child: CircularProgressIndicator());
  }

  Widget _buildEmptyState(InsightHistoryLoaded state) {
    final isSearch = state.searchQuery != null;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isSearch ? Icons.search_off : Icons.lightbulb_outline,
            size: 56,
            color: const Color(0xFF9C9B99),
          ),
          const SizedBox(height: 16),
          Text(
            isSearch ? '未找到相关洞察' : '还没有洞察',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: Color(0xFF6D6C6A),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            isSearch ? '试试其他关键词' : '秘书会基于你的记忆生成智能洞察',
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF9C9B99),
            ),
          ),
        ],
      ),
    );
  }
}

class _InsightFilter {
  final String? type;
  final String label;

  const _InsightFilter(this.type, this.label);
}

/// A single insight card matching the prototype design.
/// Shows type badge with icon, status badge, date, content, and feedback buttons.
class _InsightCard extends StatelessWidget {
  final InsightItem insight;
  final VoidCallback? onUseful;
  final VoidCallback? onNotUseful;

  const _InsightCard({
    required this.insight,
    this.onUseful,
    this.onNotUseful,
  });

  @override
  Widget build(BuildContext context) {
    final typeInfo = _getTypeInfo(insight.type);
    final statusInfo = _getStatusInfo(insight.status);
    final feedbackState = _getFeedbackState(insight.status);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top row: type icon + type label + status badge + date
          Row(
            children: [
              // Type icon circle
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: typeInfo.bgColor,
                  borderRadius: BorderRadius.circular(14),
                ),
                alignment: Alignment.center,
                child: Icon(
                  typeInfo.icon,
                  size: 14,
                  color: typeInfo.color,
                ),
              ),
              const SizedBox(width: 8),
              // Type label
              Text(
                typeInfo.label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: typeInfo.color,
                ),
              ),
              const SizedBox(width: 8),
              // Status badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: statusInfo.bgColor,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  statusInfo.label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: statusInfo.color,
                  ),
                ),
              ),
              const Spacer(),
              // Date
              Text(
                _formatDate(insight.createdAt),
                style: const TextStyle(
                  fontSize: 11,
                  color: Color(0xFF9C9B99),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Content
          Text(
            insight.content,
            style: const TextStyle(
              fontSize: 14,
              color: Color(0xFF1A1918),
              height: 1.5,
            ),
          ),
          const SizedBox(height: 10),

          // Feedback buttons
          Row(
            children: [
              // Useful button
              GestureDetector(
                onTap: feedbackState != 'useful' ? onUseful : null,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: feedbackState == 'useful'
                        ? AppColors.accentGreenLight
                        : const Color(0xFFF5F4F2),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.thumb_up_outlined,
                        size: 12,
                        color: feedbackState == 'useful'
                            ? AppColors.accentGreen
                            : const Color(0xFF9C9B99),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '有用',
                        style: TextStyle(
                          fontSize: 11,
                          color: feedbackState == 'useful'
                              ? AppColors.accentGreen
                              : const Color(0xFF9C9B99),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Not useful button
              GestureDetector(
                onTap: feedbackState != 'not_useful' ? onNotUseful : null,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: feedbackState == 'not_useful'
                        ? const Color(0xFFFFEBEE)
                        : const Color(0xFFF5F4F2),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.thumb_down_outlined,
                        size: 12,
                        color: feedbackState == 'not_useful'
                            ? const Color(0xFFE53935)
                            : const Color(0xFF9C9B99),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '没用',
                        style: TextStyle(
                          fontSize: 11,
                          color: feedbackState == 'not_useful'
                              ? const Color(0xFFE53935)
                              : const Color(0xFF9C9B99),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.month}月${local.day}日';
  }

  /// Determine feedback visual state from insight status.
  /// Returns 'useful', 'not_useful', or null (no feedback yet).
  String? _getFeedbackState(String status) {
    if (status == 'acted') return 'useful';
    if (status == 'dismissed') return 'not_useful';
    return null;
  }

  static _TypeInfo _getTypeInfo(String type) {
    switch (type) {
      case 'reminder':
        return const _TypeInfo(
          label: '提醒',
          icon: Icons.notifications_outlined,
          color: Color(0xFFE65100),
          bgColor: Color(0xFFFFF3E0),
        );
      case 'suggestion':
        return const _TypeInfo(
          label: '建议',
          icon: Icons.gps_fixed,
          color: Color(0xFF3D8A5A),
          bgColor: Color(0xFFE8F5E9),
        );
      case 'observation':
        return const _TypeInfo(
          label: '观察',
          icon: Icons.visibility_outlined,
          color: Color(0xFF1976D2),
          bgColor: Color(0xFFE3F2FD),
        );
      case 'connection':
        return const _TypeInfo(
          label: '关联',
          icon: Icons.device_hub,
          color: Color(0xFF7B1FA2),
          bgColor: Color(0xFFF3E5F5),
        );
      default:
        return const _TypeInfo(
          label: '洞察',
          icon: Icons.lightbulb_outline,
          color: Color(0xFFE65100),
          bgColor: Color(0xFFFFF3E0),
        );
    }
  }

  static _StatusInfo _getStatusInfo(String status) {
    switch (status) {
      case 'acted':
        return const _StatusInfo(
          label: '已执行',
          color: Color(0xFF3D8A5A),
          bgColor: Color(0xFFE8F5E9),
        );
      case 'pending':
        return const _StatusInfo(
          label: '待查看',
          color: Color(0xFFE65100),
          bgColor: Color(0xFFFFF3E0),
        );
      case 'dismissed':
        return const _StatusInfo(
          label: '已忽略',
          color: Color(0xFF9C9B99),
          bgColor: Color(0xFFF5F4F2),
        );
      case 'shown':
        return const _StatusInfo(
          label: '已查看',
          color: Color(0xFF3D8A5A),
          bgColor: Color(0xFFE8F5E9),
        );
      default:
        return const _StatusInfo(
          label: '待查看',
          color: Color(0xFFE65100),
          bgColor: Color(0xFFFFF3E0),
        );
    }
  }
}

class _TypeInfo {
  final String label;
  final IconData icon;
  final Color color;
  final Color bgColor;

  const _TypeInfo({
    required this.label,
    required this.icon,
    required this.color,
    required this.bgColor,
  });
}

class _StatusInfo {
  final String label;
  final Color color;
  final Color bgColor;

  const _StatusInfo({
    required this.label,
    required this.color,
    required this.bgColor,
  });
}
