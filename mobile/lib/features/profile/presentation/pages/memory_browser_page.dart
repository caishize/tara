import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/widgets/custom_app_bar.dart';
import '../../data/models/memory_item_model.dart';
import '../bloc/memory_browser_bloc.dart';

class MemoryBrowserPage extends StatelessWidget {
  const MemoryBrowserPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<MemoryBrowserBloc>()..add(const LoadMemories()),
      child: const _MemoryBrowserContent(),
    );
  }
}

class _MemoryBrowserContent extends StatefulWidget {
  const _MemoryBrowserContent();

  @override
  State<_MemoryBrowserContent> createState() => _MemoryBrowserContentState();
}

class _MemoryBrowserContentState extends State<_MemoryBrowserContent> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      context.read<MemoryBrowserBloc>().add(const LoadMoreMemories());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: CustomAppBar(
        title: '记忆管理',
        backgroundColor: AppColors.background,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios,
              color: Color(0xFF1A1918), size: 20),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            }
          },
        ),
      ),
      body: BlocConsumer<MemoryBrowserBloc, MemoryBrowserState>(
        listener: (context, state) {
          if (state is MemoryBrowserError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        builder: (context, state) {
          return Column(
            children: [
              // Search bar
              _buildSearchBar(),
              const SizedBox(height: 12),

              // Filter tabs
              _buildFilterTabs(state),
              const SizedBox(height: 4),

              // Content
              Expanded(child: _buildBody(state)),
            ],
          );
        },
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: TextField(
          controller: _searchController,
          decoration: InputDecoration(
            hintText: '搜索记忆...',
            hintStyle: const TextStyle(
              fontSize: 14,
              color: Color(0xFF9C9B99),
            ),
            prefixIcon: const Icon(Icons.search,
                color: Color(0xFF9C9B99), size: 20),
            suffixIcon: _searchController.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear,
                        size: 16, color: Color(0xFF9C9B99)),
                    onPressed: () {
                      _searchController.clear();
                      context
                          .read<MemoryBrowserBloc>()
                          .add(const LoadMemories());
                      setState(() {});
                    },
                  )
                : null,
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 0,
              vertical: 10,
            ),
          ),
          style: const TextStyle(
            fontSize: 14,
            color: Color(0xFF1A1918),
          ),
          textInputAction: TextInputAction.search,
          onSubmitted: (query) {
            if (query.trim().isNotEmpty) {
              context
                  .read<MemoryBrowserBloc>()
                  .add(SearchMemories(query.trim()));
            }
          },
          onChanged: (_) => setState(() {}),
        ),
      ),
    );
  }

  Widget _buildFilterTabs(MemoryBrowserState state) {
    final activeFilter =
        state is MemoryBrowserLoaded ? state.activeFilter : null;

    const filters = [
      _FilterOption(null, '全部'),
      _FilterOption('preference', '偏好'),
      _FilterOption('general', '事实'),
      _FilterOption('life_event', '事件'),
      _FilterOption('relationship', '关系'),
      _FilterOption('emotion', '观点'),
    ];

    return SizedBox(
      height: 40,
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
                  .read<MemoryBrowserBloc>()
                  .add(FilterByType(filter.type));
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: isSelected
                    ? AppColors.accentGreen
                    : Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                filter.label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected
                      ? Colors.white
                      : const Color(0xFF6D6C6A),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildBody(MemoryBrowserState state) {
    if (state is MemoryBrowserLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state is MemoryBrowserLoaded) {
      if (state.memories.isEmpty) {
        return _buildEmptyState(state);
      }

      return RefreshIndicator(
        onRefresh: () async {
          context.read<MemoryBrowserBloc>().add(const LoadMemories());
        },
        child: ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.all(16),
          itemCount: state.memories.length + (state.isLoadingMore ? 1 : 0),
          itemBuilder: (context, index) {
            if (index >= state.memories.length) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Center(
                    child: CircularProgressIndicator(strokeWidth: 2)),
              );
            }
            return Padding(
              padding: EdgeInsets.only(bottom: index < state.memories.length - 1 ? 12 : 0),
              child: _MemoryCard(
                memory: state.memories[index],
                onTap: () {
                  context.push(
                    Routes.memoryDetail(state.memories[index].id),
                    extra: state.memories[index],
                  );
                },
              ),
            );
          },
        ),
      );
    }

    return const Center(child: CircularProgressIndicator());
  }

  Widget _buildEmptyState(MemoryBrowserLoaded state) {
    final isSearch = state.searchQuery != null;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isSearch ? Icons.search_off : Icons.psychology_outlined,
            size: 56,
            color: const Color(0xFF9C9B99),
          ),
          const SizedBox(height: 16),
          Text(
            isSearch ? '未找到相关记忆' : '还没有记忆',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: Color(0xFF6D6C6A),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            isSearch ? '试试其他关键词' : '和助手聊天后，记忆会自动积累',
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

class _FilterOption {
  final String? type;
  final String label;

  const _FilterOption(this.type, this.label);
}

class _MemoryCard extends StatelessWidget {
  final MemoryItem memory;
  final VoidCallback? onTap;

  const _MemoryCard({
    required this.memory,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final badge = _getTypeBadge(memory.type);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Type badge + date row
            Row(
              children: [
                // Type badge
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
                const Spacer(),
                // Date
                Text(
                  _formatDate(memory.createdAt),
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF9C9B99),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),

            // Content
            Text(
              memory.content,
              style: const TextStyle(
                fontSize: 14,
                color: Color(0xFF1A1918),
                height: 1.5,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),

            // Person tags
            if (memory.entities.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: memory.entities.map((entity) {
                  return Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEDECEA),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.person_outline,
                            size: 12, color: Color(0xFF6D6C6A)),
                        const SizedBox(width: 4),
                        Text(
                          entity.name,
                          style: const TextStyle(
                            fontSize: 11,
                            color: Color(0xFF6D6C6A),
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ],

            // Star ratings
            if (memory.importance > 0) ...[
              const SizedBox(height: 10),
              Row(
                children: List.generate(5, (i) {
                  return Padding(
                    padding: EdgeInsets.only(right: i < 4 ? 2 : 0),
                    child: Icon(
                      Icons.star,
                      size: 14,
                      color: i < memory.importance
                          ? AppColors.accentWarm
                          : const Color(0xFFE5E4E1),
                    ),
                  );
                }),
              ),
            ],
          ],
        ),
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
