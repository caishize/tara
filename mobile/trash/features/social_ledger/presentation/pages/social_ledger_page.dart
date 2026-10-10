import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../relationships/presentation/bloc/relationships_bloc.dart';
import '../../../relationships/domain/entities/relationship_member.dart';
import '../widgets/contact_card.dart';

/// Social Ledger page (人情账本).
/// Contact management with relationship health tracking.
class SocialLedgerPage extends StatefulWidget {
  const SocialLedgerPage({super.key});

  @override
  State<SocialLedgerPage> createState() => _SocialLedgerPageState();
}

class _SocialLedgerPageState extends State<SocialLedgerPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  late RelationshipsBloc _relationshipsBloc;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _relationshipsBloc = getIt<RelationshipsBloc>();
    _relationshipsBloc.add(const RelationshipsLoadRequested());
    _searchController.addListener(_onSearchChanged);
  }

  void _onSearchChanged() {
    setState(() {
      _searchQuery = _searchController.text.toLowerCase();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.removeListener(_onSearchChanged);
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: _relationshipsBloc,
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildSearchBar(),
              _buildTabs(),
              Expanded(
                child: BlocBuilder<RelationshipsBloc, RelationshipsState>(
                  builder: (context, state) {
                    if (state is RelationshipsLoading) {
                      return const Center(
                        child: CircularProgressIndicator(),
                      );
                    }

                    if (state is RelationshipsError) {
                      return _buildErrorState(state.message);
                    }

                    if (state is RelationshipsLoaded) {
                      return TabBarView(
                        controller: _tabController,
                        children: [
                          _buildContactList(_getAllContacts(state.data)),
                          _buildContactList(_getPendingThankContacts(state.data)),
                          _buildContactList(_getPendingContactContacts(state.data)),
                        ],
                      );
                    }

                    return _buildEmptyState();
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '人情账本',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              SizedBox(height: 4),
              Text(
                '管理你的社交资产',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          GestureDetector(
            onTap: () => context.push(Routes.memberForm),
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.add,
                color: Colors.white,
                size: 24,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Container(
        height: 44,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
        ),
        child: TextField(
          controller: _searchController,
          decoration: InputDecoration(
            hintText: '搜索联系人...',
            hintStyle: const TextStyle(
              color: AppColors.textHint,
              fontSize: 14,
            ),
            prefixIcon: const Icon(
              Icons.search,
              color: AppColors.textTertiary,
              size: 20,
            ),
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          ),
        ),
      ),
    );
  }

  Widget _buildTabs() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          boxShadow: [AppColors.shadowLight],
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        indicatorPadding: const EdgeInsets.all(4),
        dividerColor: Colors.transparent,
        labelColor: AppColors.primary,
        unselectedLabelColor: AppColors.textSecondary,
        labelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        tabs: const [
          Tab(text: '全部'),
          Tab(text: '待回谢'),
          Tab(text: '待联络'),
        ],
      ),
    );
  }

  Widget _buildContactList(List<ContactData> contacts) {
    if (contacts.isEmpty) {
      return _buildEmptyState();
    }

    // Group contacts by category
    final groupedContacts = <String, List<ContactData>>{};
    for (final contact in contacts) {
      final category = contact.category ?? '其他';
      groupedContacts.putIfAbsent(category, () => []).add(contact);
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: groupedContacts.length,
      itemBuilder: (context, index) {
        final category = groupedContacts.keys.elementAt(index);
        final categoryContacts = groupedContacts[category]!;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 12, top: 8),
              child: Row(
                children: [
                  Text(
                    category,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textSecondary,
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
                      '${categoryContacts.length}人',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            ...categoryContacts.map((contact) => ContactCard(
                  name: contact.name,
                  imageUrl: contact.imageUrl,
                  relationship: contact.relationship,
                  healthPercentage: contact.healthPercentage,
                  recentActivities: contact.recentActivities,
                  suggestion: contact.suggestion,
                  onTap: () => context.push(Routes.memberDetail(contact.id)),
                )),
          ],
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.people_outline,
            size: 64,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          const Text(
            '暂无联系人',
            style: TextStyle(
              fontSize: 16,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () => context.push(Routes.memberForm),
            child: Text(
              '添加第一个联系人',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
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
            size: 64,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: const TextStyle(
              fontSize: 16,
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              _relationshipsBloc.add(const RelationshipsRefreshRequested());
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
            ),
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  /// Convert RelationshipData to ContactData list with search filtering
  List<ContactData> _getAllContacts(RelationshipData data) {
    final allMembers = data.all;
    return _filterAndConvertMembers(allMembers);
  }

  /// Get contacts needing thanks (those who have given us favors)
  List<ContactData> _getPendingThankContacts(RelationshipData data) {
    final allMembers = data.all.where((m) {
      // Need to thank if favor balance is negative (they gave more)
      final balance = m.favorBalance ?? 0;
      return balance < 0;
    }).toList();
    return _filterAndConvertMembers(allMembers);
  }

  /// Get contacts needing outreach (relationship health below threshold)
  List<ContactData> _getPendingContactContacts(RelationshipData data) {
    final allMembers = data.all.where((m) {
      // Need contact if health score is below 70 or overdue
      return m.score.total < 70 || m.isOverdue;
    }).toList();
    return _filterAndConvertMembers(allMembers);
  }

  /// Filter by search query and convert to ContactData
  List<ContactData> _filterAndConvertMembers(List<RelationshipMember> members) {
    var filtered = members;

    // Apply search filter
    if (_searchQuery.isNotEmpty) {
      filtered = members.where((m) {
        return m.displayName.toLowerCase().contains(_searchQuery) ||
            m.relationDisplay.toLowerCase().contains(_searchQuery) ||
            (m.occupation?.toLowerCase().contains(_searchQuery) ?? false);
      }).toList();
    }

    return filtered.map((member) => _convertToContactData(member)).toList();
  }

  /// Convert RelationshipMember to ContactData for display
  ContactData _convertToContactData(RelationshipMember member) {
    // Build recent activities from suggested actions and upcoming dates
    final activities = <ActivityItem>[];

    // Add last interaction info
    if (member.lastInteraction != null) {
      activities.add(ActivityItem(
        date: member.lastContactText,
        content: '最近联络',
      ));
    }

    // Add upcoming dates
    for (final date in member.upcomingDates.take(2)) {
      activities.add(ActivityItem(
        date: '${date.daysUntil}天后',
        content: date.title,
      ));
    }

    // Get first suggestion if any
    String? suggestion;
    if (member.suggestedActions.isNotEmpty) {
      suggestion = member.suggestedActions.first.title;
    }

    // Determine category based on relationship type
    String category;
    if (member.isFamily) {
      category = '家人';
    } else if (member.occupation != null) {
      category = '工作伙伴';
    } else {
      category = '人脉圈';
    }

    return ContactData(
      id: member.id,
      name: member.displayName,
      imageUrl: member.avatarUrl,
      relationship: member.relationDisplay,
      category: category,
      healthPercentage: member.score.total.toDouble(),
      recentActivities: activities,
      suggestion: suggestion,
    );
  }
}

/// Contact data model for display.
class ContactData {
  final String id;
  final String name;
  final String? imageUrl;
  final String relationship;
  final String? category;
  final double healthPercentage;
  final List<ActivityItem> recentActivities;
  final String? suggestion;

  const ContactData({
    required this.id,
    required this.name,
    this.imageUrl,
    required this.relationship,
    this.category,
    required this.healthPercentage,
    this.recentActivities = const [],
    this.suggestion,
  });
}
