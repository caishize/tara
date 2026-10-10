import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../../domain/entities/member.dart';
import '../bloc/members_bloc.dart';
import '../widgets/network_member_card.dart';

/// Filter type for network members
enum NetworkFilter {
  all,
  mostCritical,
  business,
  family,
  friend,
  other,
}

class MembersPage extends StatelessWidget {
  final String? initialFilter;

  const MembersPage({super.key, this.initialFilter});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => getIt<MembersBloc>()..add(const MembersLoadRequested()),
      child: _MembersPageContent(initialFilter: initialFilter),
    );
  }
}

class _MembersPageContent extends StatefulWidget {
  final String? initialFilter;

  const _MembersPageContent({this.initialFilter});

  @override
  State<_MembersPageContent> createState() => _MembersPageContentState();
}

class _MembersPageContentState extends State<_MembersPageContent> {
  final _searchController = TextEditingController();
  String _searchQuery = '';
  late NetworkFilter _selectedFilter;

  @override
  void initState() {
    super.initState();
    _selectedFilter = _parseFilter(widget.initialFilter);
  }

  NetworkFilter _parseFilter(String? filter) {
    switch (filter) {
      case 'business':
        return NetworkFilter.business;
      case 'family':
        return NetworkFilter.family;
      case 'friend':
        return NetworkFilter.friend;
      case 'other':
        return NetworkFilter.other;
      default:
        return NetworkFilter.all;
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<Member> _filterMembers(List<Member> members) {
    var filtered = members;

    // Apply search filter
    if (_searchQuery.isNotEmpty) {
      filtered = filtered.where((m) {
        return m.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
            (m.nickname?.toLowerCase().contains(_searchQuery.toLowerCase()) ??
                false);
      }).toList();
    }

    // Apply category filter using centralized RelationUtils
    switch (_selectedFilter) {
      case NetworkFilter.mostCritical:
        // Filter to members needing attention: >90 days since last interaction AND importance >= 5
        filtered = filtered.where((m) {
          if (m.importance < 5) return false;
          if (m.lastMentionedAt == null) return m.importance >= 5;
          final lastDate = DateTime.tryParse(m.lastMentionedAt!);
          if (lastDate == null) return false;
          return DateTime.now().difference(lastDate).inDays > 90;
        }).toList();
        // Sort by importance DESC, then recency ASC (oldest first)
        filtered.sort((a, b) {
          final cmp = b.importance.compareTo(a.importance);
          if (cmp != 0) return cmp;
          final aDate = a.lastMentionedAt ?? '';
          final bDate = b.lastMentionedAt ?? '';
          return aDate.compareTo(bDate);
        });
        break;
      case NetworkFilter.business:
        filtered = filtered
            .where((m) => RelationUtils.isWork(m.relation))
            .toList();
        break;
      case NetworkFilter.family:
        filtered = filtered
            .where((m) => RelationUtils.isFamily(m.relation))
            .toList();
        break;
      case NetworkFilter.friend:
        filtered = filtered
            .where((m) => RelationUtils.isFriend(m.relation))
            .toList();
        break;
      case NetworkFilter.other:
        filtered = filtered
            .where((m) => RelationUtils.getRelationCategory(m.relation) == 'other')
            .toList();
        break;
      case NetworkFilter.all:
        break;
    }

    return filtered;
  }

  NetworkMemberData _convertToNetworkData(Member member, int index) {
    // Health score from profile completion (real data)
    final healthScore = member.profileCompletion > 0
        ? member.profileCompletion
        : 50; // Default if no data

    // Determine category using centralized RelationUtils
    NetworkCategory category;
    final relationCategory = RelationUtils.getRelationCategory(member.relation);
    switch (relationCategory) {
      case 'work':
        category = NetworkCategory.business;
        break;
      case 'friend':
        category = NetworkCategory.friend;
        break;
      default:
        category = NetworkCategory.family;
    }

    // PersonProfile data from API
    final favorBalance = member.favorBalance.round();

    // Parse lastMentionedAt ISO string to DateTime
    DateTime? lastInteractionDate;
    if (member.lastMentionedAt != null) {
      lastInteractionDate = DateTime.tryParse(member.lastMentionedAt!);
    }

    // Compute status badge from importance and recency
    String? statusBadge;
    if (member.importance >= 5 && lastInteractionDate != null) {
      final daysSince = DateTime.now().difference(lastInteractionDate).inDays;
      if (daysSince > 90) {
        statusBadge = '需关注';
      } else if (daysSince <= 30) {
        statusBadge = '活跃';
      }
    }

    // Add insight for first member with low health score
    NetworkInsight? insight;
    if (index == 0 && healthScore < 70) {
      insight = NetworkInsight(
        id: 'insight_${member.id}',
        message:
            '${member.displayName} 的资料完整度较低，建议补充更多信息以便更好地维护关系。',
        actionLabel: '完善资料',
        onAction: () => context.push(Routes.memberDetail(member.id)),
        onDismiss: () {},
        timestamp: DateTime.now(),
      );
    }

    return NetworkMemberData(
      id: member.id,
      name: member.displayName,
      title: member.profile?.occupation,
      company: member.organization ?? member.currentCompany ?? member.relationText,
      healthScore: healthScore.clamp(0, 100),
      category: category,
      favorBalance: favorBalance,
      lastInteractionDate: lastInteractionDate,
      statusBadge: statusBadge,
      insight: insight,
      isOnline: false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _buildHeader(),

            // Search bar
            _buildSearchBar(),

            // Filter tabs
            _buildFilterTabs(),

            // Section header
            _buildSectionHeader(),

            // Members list
            Expanded(
              child: BlocBuilder<MembersBloc, MembersState>(
                builder: (context, state) {
                  if (state is MembersLoading) {
                    return const Center(
                      child: CircularProgressIndicator(),
                    );
                  }

                  if (state is MembersError) {
                    return _buildErrorState(state.message);
                  }

                  if (state is MembersLoaded) {
                    final filtered = _filterMembers(state.members);

                    if (filtered.isEmpty) {
                      return _buildEmptyState();
                    }

                    return RefreshIndicator(
                      onRefresh: () async {
                        context
                            .read<MembersBloc>()
                            .add(const MemberRefreshRequested());
                      },
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final member = filtered[index];
                          final networkData =
                              _convertToNetworkData(member, index);
                          return NetworkMemberCard(
                            member: networkData,
                            onTap: () async {
                              await context.push(Routes.memberDetail(member.id));
                              if (context.mounted) {
                                context.read<MembersBloc>().add(const MembersLoadRequested());
                              }
                            },
                          );
                        },
                      ),
                    );
                  }

                  return const SizedBox.shrink();
                },
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push(Routes.memberForm),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('关系管理', style: AppTextStyles.headline4),
                const SizedBox(height: 4),
                BlocBuilder<MembersBloc, MembersState>(
                  builder: (context, state) {
                    int count = 0;
                    if (state is MembersLoaded) {
                      count = state.members.length;
                    }
                    return Text(
                      '共 $count 位联系人',
                      style: AppTextStyles.bodyText2,
                    );
                  },
                ),
              ],
            ),
          ),
          // Smart groups button
          IconButton(
            onPressed: () => context.push(Routes.smartGroups),
            icon: const Icon(Icons.auto_awesome),
            color: AppColors.textSecondary,
            tooltip: '智能分组',
          ),
          // More options menu
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: AppColors.textSecondary),
            onSelected: (value) {
              switch (value) {
                case 'graph':
                  context.push(Routes.relationshipGraph);
                  break;
                case 'favors':
                  context.push(Routes.favorLedger);
                  break;
                case 'notifications':
                  // Show notifications
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'graph',
                child: Row(
                  children: [
                    Icon(Icons.hub, size: 20),
                    SizedBox(width: 12),
                    Text('关系图谱'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'favors',
                child: Row(
                  children: [
                    Icon(Icons.account_balance_wallet, size: 20),
                    SizedBox(width: 12),
                    Text('人情账本'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'notifications',
                child: Row(
                  children: [
                    Icon(Icons.notifications_outlined, size: 20),
                    SizedBox(width: 12),
                    Text('通知'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.inputBackground,
          borderRadius: BorderRadius.circular(12),
        ),
        child: TextField(
          controller: _searchController,
          style: AppTextStyles.bodyText1,
          decoration: InputDecoration(
            hintText: '搜索联系人...',
            hintStyle: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textTertiary,
            ),
            prefixIcon: Icon(Icons.search, color: AppColors.textTertiary),
            suffixIcon: _searchQuery.isNotEmpty
                ? IconButton(
                    icon: Icon(Icons.clear, color: AppColors.textTertiary),
                    onPressed: () {
                      _searchController.clear();
                      setState(() => _searchQuery = '');
                    },
                  )
                : null,
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 14,
            ),
          ),
          onChanged: (value) {
            setState(() => _searchQuery = value);
          },
        ),
      ),
    );
  }

  Widget _buildFilterTabs() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Row(
        children: [
          _buildFilterChip('全部', NetworkFilter.all),
          const SizedBox(width: 8),
          _buildFilterChip('需关注', NetworkFilter.mostCritical),
          const SizedBox(width: 8),
          _buildFilterChip('家人', NetworkFilter.family),
          const SizedBox(width: 8),
          _buildFilterChip('商务', NetworkFilter.business),
          const SizedBox(width: 8),
          _buildFilterChip('亲友', NetworkFilter.friend),
          const SizedBox(width: 8),
          _buildFilterChip('其他', NetworkFilter.other),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, NetworkFilter filter) {
    final isSelected = _selectedFilter == filter;
    return GestureDetector(
      onTap: () {
        setState(() => _selectedFilter = filter);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : AppColors.chipBackground,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : AppColors.textSecondary,
            fontSize: 13,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildSectionHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            '我的人脉',
            style: AppTextStyles.subtitle1,
          ),
          Text(
            '按健康度排序',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 48,
            color: AppColors.error.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: AppTextStyles.bodyText2,
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: () {
              context.read<MembersBloc>().add(const MembersLoadRequested());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _searchQuery.isEmpty ? Icons.people_outline : Icons.search_off,
            size: 64,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            _searchQuery.isEmpty ? '暂无联系人' : '未找到匹配的联系人',
            style: AppTextStyles.subtitle1.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          if (_searchQuery.isEmpty) ...[
            const SizedBox(height: 8),
            Text(
              '点击右下角添加第一位联系人',
              style: AppTextStyles.bodyText2,
            ),
          ],
        ],
      ),
    );
  }
}
