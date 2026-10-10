import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/app_text_field.dart';
import '../../domain/entities/relationship_member.dart';
import '../bloc/relationships_bloc.dart';
import '../widgets/family_member_card.dart';
import '../widgets/network_member_card.dart';

class RelationshipsPage extends StatelessWidget {
  const RelationshipsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => getIt<RelationshipsBloc>()
        ..add(const RelationshipsLoadRequested()),
      child: const _RelationshipsPageContent(),
    );
  }
}

class _RelationshipsPageContent extends StatefulWidget {
  const _RelationshipsPageContent();

  @override
  State<_RelationshipsPageContent> createState() =>
      _RelationshipsPageContentState();
}

class _RelationshipsPageContentState extends State<_RelationshipsPageContent>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _searchController = TextEditingController();
  String _searchQuery = '';
  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(_onTabChanged);
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (_tabController.indexIsChanging) return;

    String? category;
    switch (_tabController.index) {
      case 0:
        category = null; // All
        break;
      case 1:
        category = 'family';
        break;
      case 2:
        category = 'network';
        break;
    }

    context.read<RelationshipsBloc>().add(RelationshipsCategoryChanged(category));
  }

  List<RelationshipMember> _filterMembers(List<RelationshipMember> members) {
    if (_searchQuery.isEmpty) return members;
    return members.where((m) {
      return m.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          (m.nickname?.toLowerCase().contains(_searchQuery.toLowerCase()) ??
              false) ||
          m.relationDisplay.toLowerCase().contains(_searchQuery.toLowerCase());
    }).toList();
  }

  Future<void> _makePhoneCall(String phone) async {
    final uri = Uri.parse('tel:$phone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  Future<void> _sendSms(String phone) async {
    final uri = Uri.parse('sms:$phone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildSearchAndTabs(),
            Expanded(child: _buildContent()),
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
          IconButton(
            onPressed: () => context.pop(),
            icon: const Icon(Icons.arrow_back),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('关系管理', style: AppTextStyles.headline5),
                BlocBuilder<RelationshipsBloc, RelationshipsState>(
                  builder: (context, state) {
                    if (state is RelationshipsLoaded) {
                      return Text(
                        '${state.data.summary.familyCount} 家人 \u2022 ${state.data.summary.networkCount} 人脉',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      );
                    }
                    return const SizedBox.shrink();
                  },
                ),
              ],
            ),
          ),
          // Smart groups button
          IconButton(
            onPressed: () => context.push(Routes.smartGroups),
            icon: const Icon(Icons.auto_awesome),
            tooltip: '智能分组',
          ),
          // Sort button
          IconButton(
            onPressed: _showSortOptions,
            icon: const Icon(Icons.sort),
          ),
          // More options
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (value) {
              switch (value) {
                case 'graph':
                  context.push(Routes.relationshipGraph);
                  break;
                case 'favors':
                  context.push(Routes.favorLedger);
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
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSearchAndTabs() {
    return Column(
      children: [
        // Search bar
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: AppSearchField(
            controller: _searchController,
            hint: '搜索联系人...',
            onChanged: (value) {
              setState(() => _searchQuery = value);
            },
            onClear: () {
              setState(() => _searchQuery = '');
            },
          ),
        ),

        const SizedBox(height: 12),

        // Tab bar
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 20),
          decoration: BoxDecoration(
            color: AppColors.inputBackground,
            borderRadius: BorderRadius.circular(12),
          ),
          child: TabBar(
            controller: _tabController,
            indicator: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(10),
            ),
            indicatorSize: TabBarIndicatorSize.tab,
            dividerColor: Colors.transparent,
            labelColor: Colors.white,
            unselectedLabelColor: AppColors.textSecondary,
            labelStyle: AppTextStyles.button.copyWith(fontSize: 13),
            tabs: const [
              Tab(text: '全部'),
              Tab(text: '家人'),
              Tab(text: '人脉'),
            ],
          ),
        ),

        const SizedBox(height: 8),

        // Summary stats
        BlocBuilder<RelationshipsBloc, RelationshipsState>(
          builder: (context, state) {
            if (state is RelationshipsLoaded) {
              return _buildSummaryStats(state.data.summary);
            }
            return const SizedBox.shrink();
          },
        ),
      ],
    );
  }

  Widget _buildSummaryStats(RelationshipSummary summary) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Row(
        children: [
          if (summary.needsAttention > 0)
            _buildStatChip(
              icon: Icons.warning_amber,
              label: '${summary.needsAttention} 需关注',
              color: AppColors.warning,
            ),
          const SizedBox(width: 8),
          _buildStatChip(
            icon: Icons.favorite,
            label: '平均 ${summary.averageScore.toInt()}%',
            color: AppColors.success,
          ),
        ],
      ),
    );
  }

  Widget _buildStatChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: AppTextStyles.caption.copyWith(
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return BlocBuilder<RelationshipsBloc, RelationshipsState>(
      builder: (context, state) {
        if (state is RelationshipsLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is RelationshipsError) {
          return _buildError(state.message);
        }

        if (state is RelationshipsLoaded) {
          return RefreshIndicator(
            onRefresh: () async {
              context
                  .read<RelationshipsBloc>()
                  .add(const RelationshipsRefreshRequested());
            },
            child: _buildMembersList(state.data),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildMembersList(RelationshipData data) {
    final List<RelationshipMember> membersToShow;

    switch (_tabController.index) {
      case 1: // Family
        membersToShow = _filterMembers(data.family);
        break;
      case 2: // Network
        membersToShow = _filterMembers(data.network);
        break;
      default: // All
        membersToShow = _filterMembers(data.all);
    }

    if (membersToShow.isEmpty) {
      return _buildEmptyState();
    }

    // For "All" tab, group by category
    if (_tabController.index == 0) {
      final family = membersToShow
          .where((m) => m.category == RelationshipCategory.family)
          .toList();
      final network = membersToShow
          .where((m) => m.category == RelationshipCategory.network)
          .toList();

      return CustomScrollView(
        slivers: [
          if (family.isNotEmpty) ...[
            _buildSectionHeader('家人圈', family.length),
            _buildMemberSliver(family, isFamily: true),
          ],
          if (network.isNotEmpty) ...[
            _buildSectionHeader('人脉圈', network.length),
            _buildMemberSliver(network, isFamily: false),
          ],
        ],
      );
    }

    // Single category view
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      itemCount: membersToShow.length,
      itemBuilder: (context, index) {
        final member = membersToShow[index];
        return _buildMemberCard(member);
      },
    );
  }

  Widget _buildSectionHeader(String title, int count) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
        child: Row(
          children: [
            Text(
              title,
              style: AppTextStyles.subtitle1.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.chipBackground,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$count',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMemberSliver(List<RelationshipMember> members,
      {required bool isFamily}) {
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      sliver: SliverList(
        delegate: SliverChildBuilderDelegate(
          (context, index) => _buildMemberCard(members[index]),
          childCount: members.length,
        ),
      ),
    );
  }

  Widget _buildMemberCard(RelationshipMember member) {
    if (member.isFamily) {
      return FamilyMemberCard(
        member: member,
        onTap: () => context.push(Routes.memberDetail(member.id)),
        onCall: member.phone != null ? () => _makePhoneCall(member.phone!) : null,
        onMessage:
            member.phone != null ? () => _sendSms(member.phone!) : null,
      );
    } else {
      return NetworkMemberCard(
        member: member,
        onTap: () => context.push(Routes.memberDetail(member.id)),
        onSendGift: () {
          // Navigate to gift recommendation
        },
        onMessage:
            member.phone != null ? () => _sendSms(member.phone!) : null,
      );
    }
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

  Widget _buildError(String message) {
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
          Text(message, style: AppTextStyles.bodyText2),
          const SizedBox(height: 16),
          TextButton(
            onPressed: () {
              context.read<RelationshipsBloc>().add(
                    const RelationshipsLoadRequested(),
                  );
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  void _showSortOptions() {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('排序方式', style: AppTextStyles.headline6),
            const SizedBox(height: 16),
            _buildSortOption('按健康度', 'score', Icons.favorite),
            _buildSortOption('按最近联络', 'last_contact', Icons.access_time),
            _buildSortOption('按姓名', 'name', Icons.sort_by_alpha),
          ],
        ),
      ),
    );
  }

  Widget _buildSortOption(String label, String value, IconData icon) {
    return ListTile(
      leading: Icon(icon, color: AppColors.primary),
      title: Text(label),
      onTap: () {
        Navigator.pop(context);
        context.read<RelationshipsBloc>().add(
              RelationshipsSortChanged(sortBy: value, sortOrder: 'desc'),
            );
      },
    );
  }
}
