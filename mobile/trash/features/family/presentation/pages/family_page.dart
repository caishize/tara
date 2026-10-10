import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../../shared/widgets/avatar_with_initials.dart';
import '../../../../shared/widgets/section_card.dart';
import '../../../shopping/presentation/bloc/shopping_list_bloc.dart';
import '../../../shopping/domain/entities/shopping_list.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../schedule/presentation/bloc/schedule_bloc.dart';
import '../../../schedule/presentation/bloc/schedule_event.dart';
import '../../../schedule/presentation/bloc/schedule_state.dart';
import '../../../schedule/domain/entities/unified_event.dart';

/// Family Helper page (家庭助手).
/// Family dashboard with shopping, maintenance, and family activities.
class FamilyPage extends StatefulWidget {
  const FamilyPage({super.key});

  @override
  State<FamilyPage> createState() => _FamilyPageState();
}

class _FamilyPageState extends State<FamilyPage> {
  late ShoppingListBloc _shoppingBloc;
  late MembersBloc _membersBloc;
  late ScheduleBloc _scheduleBloc;

  @override
  void initState() {
    super.initState();
    _shoppingBloc = getIt<ShoppingListBloc>();
    _membersBloc = getIt<MembersBloc>();
    _scheduleBloc = getIt<ScheduleBloc>();

    // Load shopping lists, members, and schedule
    _shoppingBloc.add(const ShoppingListsLoadRequested());
    _membersBloc.add(const MembersLoadRequested());
    _scheduleBloc.add(const ScheduleLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: _shoppingBloc),
        BlocProvider.value(value: _membersBloc),
        BlocProvider.value(value: _scheduleBloc),
      ],
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(context),
                const SizedBox(height: 16),
                _buildShortcuts(context),
                const SizedBox(height: 16),
                _buildPendingTasks(context),
                const SizedBox(height: 16),
                _buildShoppingList(context),
                const SizedBox(height: 16),
                _buildFamilyActivities(context),
                const SizedBox(height: 16),
                _buildHealthSection(context),
                const SizedBox(height: 16),
                _buildChildGrowthSection(context),
                const SizedBox(height: 16),
                _buildMoreServices(context),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '家庭助手',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              SizedBox(height: 4),
              Text(
                '守护家的每一个细节',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          GestureDetector(
            onTap: () => _showAddOptionsSheet(context),
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

  void _showAddOptionsSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 8),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.divider,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                '添加内容',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 16),
              _buildAddOption(
                context,
                icon: Icons.shopping_cart_outlined,
                label: '购物清单',
                subtitle: '创建新的购物清单',
                onTap: () {
                  Navigator.pop(context);
                  context.push(Routes.shopping);
                },
              ),
              _buildAddOption(
                context,
                icon: Icons.inventory_2_outlined,
                label: '家庭库存',
                subtitle: '管理家庭物品库存',
                onTap: () {
                  Navigator.pop(context);
                  context.push(Routes.inventory);
                },
              ),
              _buildAddOption(
                context,
                icon: Icons.person_add_outlined,
                label: '添加家人',
                subtitle: '添加新的家庭成员',
                onTap: () {
                  Navigator.pop(context);
                  context.push(Routes.memberForm);
                },
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAddOption(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppColors.chipBackground,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: AppColors.primary, size: 22),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildShortcuts(BuildContext context) {
    return BlocBuilder<ShoppingListBloc, ShoppingListState>(
      builder: (context, state) {
        int pendingItems = 0;
        if (state is ShoppingListLoaded) {
          // Count unpurchased items across all lists
          pendingItems = state.lists.fold(0, (sum, list) => sum + (list.totalItems - list.purchasedItems));
        }

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: _buildShortcutCard(
                      icon: Icons.shopping_cart_outlined,
                      label: '购物清单',
                      badge: pendingItems > 0 ? '$pendingItems项' : null,
                      badgeColor: AppColors.primary,
                      onTap: () => context.push(Routes.shopping),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildShortcutCard(
                      icon: Icons.inventory_2_outlined,
                      label: '家庭库存',
                      badge: null,
                      onTap: () => context.push(Routes.inventory),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _buildShortcutCard(
                      icon: Icons.family_restroom_outlined,
                      label: '家人管理',
                      badge: null,
                      onTap: () => context.push(Routes.familyMembers),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildShortcutCard(
                      icon: Icons.build_outlined,
                      label: '家庭维护',
                      badge: null,
                      onTap: () => context.push(Routes.housing),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildShortcutCard({
    required IconData icon,
    required String label,
    String? badge,
    Color? badgeColor,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppColors.cardShadow,
        ),
        child: Column(
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                IconAvatar(
                  icon: icon,
                  size: 56,
                  backgroundColor: AppColors.chipBackground,
                  iconColor: AppColors.primary,
                  borderRadius: 16,
                ),
                if (badge != null)
                  Positioned(
                    top: -4,
                    right: -4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: badgeColor ?? AppColors.primary,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        badge,
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPendingTasks(BuildContext context) {
    return BlocBuilder<ScheduleBloc, ScheduleState>(
      builder: (context, scheduleState) {
        return BlocBuilder<ShoppingListBloc, ShoppingListState>(
          builder: (context, shoppingState) {
            final tasks = <_PendingTask>[];

            // Add upcoming family events from schedule
            // Only show family-relevant events (family tasks and important dates like birthdays)
            // Exclude travel plans, external calendars, etc. which belong to other sections
            if (scheduleState is ScheduleLoaded) {
              final todayEvents = scheduleState.eventsByPeriod[TimePeriod.today] ?? [];
              final tomorrowEvents = scheduleState.eventsByPeriod[TimePeriod.tomorrow] ?? [];

              // Filter to only show family-relevant sources
              final familyRelevantSources = {
                EventSource.familyTask,
                EventSource.importantDate,
              };

              final familyEvents = [...todayEvents, ...tomorrowEvents]
                  .where((event) => familyRelevantSources.contains(event.source))
                  .take(2)
                  .toList();

              for (final event in familyEvents) {
                tasks.add(_PendingTask(
                  title: event.title,
                  subtitle: event.location ?? event.description ?? '今日事项',
                  icon: Icons.event_outlined,
                  isUrgent: event.isToday,
                  onPrimary: () => context.push(Routes.timeline),
                ));
              }
            }

            // Add pending shopping lists
            if (shoppingState is ShoppingListLoaded) {
              final pendingLists = shoppingState.lists
                  .where((list) => list.totalItems > list.purchasedItems)
                  .take(2)
                  .toList();

              for (final list in pendingLists) {
                final remaining = list.totalItems - list.purchasedItems;
                tasks.add(_PendingTask(
                  title: list.listName,
                  subtitle: '还有 $remaining 项待购买',
                  icon: Icons.shopping_cart_outlined,
                  isUrgent: list.listType == ListType.urgent,
                  onPrimary: () => context.push(Routes.shopping),
                ));
              }
            }

            final taskCount = tasks.length;

            return SectionCard(
              title: '待处理事项',
              trailing: taskCount > 0
                  ? Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.badgeOrange,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '$taskCount项待办',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFFE65100),
                        ),
                      ),
                    )
                  : null,
              child: tasks.isEmpty
                  ? _buildEmptyPendingTasks()
                  : Column(
                      children: tasks.take(3).map((task) => _buildPendingTaskItem(
                            title: task.title,
                            subtitle: task.subtitle,
                            icon: task.icon,
                            isUrgent: task.isUrgent,
                            onPrimary: task.onPrimary,
                          )).toList(),
                    ),
            );
          },
        );
      },
    );
  }

  Widget _buildEmptyPendingTasks() {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Center(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.check_circle_outline,
              size: 20,
              color: AppColors.success,
            ),
            const SizedBox(width: 8),
            const Text(
              '太棒了！暂无待处理事项',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPendingTaskItem({
    required String title,
    required String subtitle,
    IconData icon = Icons.warning_amber_outlined,
    bool isUrgent = false,
    VoidCallback? onPrimary,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isUrgent ? AppColors.badgeOrange.withValues(alpha: 0.3) : AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: isUrgent ? const Color(0xFFE65100).withValues(alpha: 0.2) : AppColors.divider,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              icon,
              size: 18,
              color: isUrgent ? const Color(0xFFE65100) : AppColors.textSecondary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textSecondary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: onPrimary,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Text(
                '查看',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildShoppingList(BuildContext context) {
    return BlocBuilder<ShoppingListBloc, ShoppingListState>(
      builder: (context, state) {
        if (state is ShoppingListLoading) {
          return const SectionCard(
            title: '购物清单',
            child: Center(child: CircularProgressIndicator()),
          );
        }

        if (state is ShoppingListLoaded) {
          // Show shopping lists overview
          final activeLists = state.lists
              .where((list) => list.status == ListStatus.active)
              .take(4)
              .toList();

          return SectionCard(
            title: '购物清单',
            trailing: GestureDetector(
              onTap: () => context.push(Routes.shopping),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.add,
                    size: 16,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '添加',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.primary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            child: activeLists.isEmpty
                ? _buildEmptyShoppingList()
                : Column(
                    children: activeLists.map((list) {
                      final remaining = list.totalItems - list.purchasedItems;
                      final progress = list.totalItems > 0
                          ? list.purchasedItems / list.totalItems
                          : 0.0;

                      return GestureDetector(
                        onTap: () => context.push(Routes.shopping),
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.chipBackground,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 36,
                                height: 36,
                                decoration: BoxDecoration(
                                  color: _getListTypeColor(list.listType).withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Icon(
                                  _getListTypeIcon(list.listType),
                                  size: 18,
                                  color: _getListTypeColor(list.listType),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      list.listName,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.textPrimary,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    const SizedBox(height: 4),
                                    Row(
                                      children: [
                                        Expanded(
                                          child: ClipRRect(
                                            borderRadius: BorderRadius.circular(2),
                                            child: LinearProgressIndicator(
                                              value: progress,
                                              backgroundColor: AppColors.divider,
                                              valueColor: AlwaysStoppedAnimation<Color>(
                                                progress == 1.0 ? AppColors.success : AppColors.primary,
                                              ),
                                              minHeight: 4,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Text(
                                          remaining > 0 ? '剩余$remaining项' : '已完成',
                                          style: TextStyle(
                                            fontSize: 11,
                                            color: remaining > 0
                                                ? AppColors.textSecondary
                                                : AppColors.success,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                              const Icon(
                                Icons.chevron_right,
                                color: AppColors.textTertiary,
                                size: 20,
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
          );
        }

        return SectionCard(
          title: '购物清单',
          child: _buildEmptyShoppingList(),
        );
      },
    );
  }

  Color _getListTypeColor(ListType type) {
    switch (type) {
      case ListType.regular:
        return AppColors.primary;
      case ListType.urgent:
        return const Color(0xFFE65100);
      case ListType.replenishment:
        return AppColors.badgeBlue;
      case ListType.seasonal:
        return AppColors.badgePink;
      case ListType.bulk:
        return AppColors.badgeGreen;
    }
  }

  IconData _getListTypeIcon(ListType type) {
    switch (type) {
      case ListType.regular:
        return Icons.shopping_cart_outlined;
      case ListType.urgent:
        return Icons.priority_high;
      case ListType.replenishment:
        return Icons.autorenew;
      case ListType.seasonal:
        return Icons.wb_sunny_outlined;
      case ListType.bulk:
        return Icons.inventory_2_outlined;
    }
  }

  Widget _buildEmptyShoppingList() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.shopping_cart_outlined,
              size: 40,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 12),
            const Text(
              '暂无购物清单',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () => context.push(Routes.shopping),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  border: Border.all(color: AppColors.primary),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.add, color: AppColors.primary, size: 16),
                    const SizedBox(width: 4),
                    Text(
                      '创建清单',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFamilyActivities(BuildContext context) {
    return BlocBuilder<MembersBloc, MembersState>(
      builder: (context, state) {
        if (state is MembersLoading) {
          return const SectionCard(
            title: '家人动态',
            child: Center(child: CircularProgressIndicator()),
          );
        }

        if (state is MembersLoaded) {
          // Get family members (those with relation 'spouse', 'child', etc.)
          final familyMembers = state.members.where((m) =>
              m.relation == 'spouse' ||
              m.relation == 'child' ||
              m.relation == 'parent' ||
              m.relation == 'grandchild' ||
              m.relation == 'sibling' ||
              m.relation == 'self').toList();

          if (familyMembers.isEmpty) {
            return SectionCard(
              title: '家人圈',
              child: _buildEmptyFamilyActivities(),
            );
          }

          // Build family activity items
          final activities = <_FamilyActivity>[];

          for (final member in familyMembers.take(4)) {
            // Check for upcoming birthdays
            if (member.birthDate != null && member.birthDate!.isNotEmpty) {
              try {
                final birthDate = DateTime.parse(member.birthDate!);
                final now = DateTime.now();
                final thisYearBirthday = DateTime(
                  now.year,
                  birthDate.month,
                  birthDate.day,
                );
                final nextBirthday = thisYearBirthday.isBefore(now)
                    ? DateTime(now.year + 1, birthDate.month, birthDate.day)
                    : thisYearBirthday;
                final daysUntil = nextBirthday.difference(now).inDays;

                if (daysUntil <= 30) {
                  activities.add(_FamilyActivity(
                    member: member,
                    activityType: _ActivityType.birthday,
                    description: daysUntil == 0
                        ? '今天生日！'
                        : daysUntil == 1
                            ? '明天生日'
                            : '$daysUntil天后生日',
                    isUrgent: daysUntil <= 3,
                  ));
                }
              } catch (_) {
                // Invalid date format, skip birthday check
              }
            }

            // Add member if no specific activity
            if (!activities.any((a) => a.member.id == member.id)) {
              activities.add(_FamilyActivity(
                member: member,
                activityType: _ActivityType.member,
                description: member.relationText,
                isUrgent: false,
              ));
            }
          }

          return SectionCard(
            title: '家人圈',
            trailing: GestureDetector(
              onTap: () async {
                await context.push(Routes.familyMembers);
                if (context.mounted) {
                  _membersBloc.add(const MembersLoadRequested());
                }
              },
              child: Text(
                '全部 ${familyMembers.length}人',
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.primary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            child: Column(
              children: [
                // Horizontal scrollable avatar list
                SizedBox(
                  height: 90,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    itemCount: familyMembers.take(6).length,
                    itemBuilder: (context, index) {
                      final member = familyMembers[index];
                      final activity = activities.firstWhere(
                        (a) => a.member.id == member.id,
                        orElse: () => _FamilyActivity(
                          member: member,
                          activityType: _ActivityType.member,
                          description: member.relationText,
                          isUrgent: false,
                        ),
                      );

                      return GestureDetector(
                        onTap: () async {
                          await context.push(Routes.memberDetail(member.id));
                          if (context.mounted) {
                            _membersBloc.add(const MembersLoadRequested());
                          }
                        },
                        child: Container(
                          width: 72,
                          margin: EdgeInsets.only(right: index < 5 ? 12 : 0),
                          child: Column(
                            children: [
                              Stack(
                                children: [
                                  AvatarWithInitials(
                                    name: member.displayName,
                                    size: 52,
                                    backgroundColor: _getAvatarColor(member.relation),
                                  ),
                                  if (activity.activityType == _ActivityType.birthday)
                                    Positioned(
                                      right: 0,
                                      bottom: 0,
                                      child: Container(
                                        width: 20,
                                        height: 20,
                                        decoration: BoxDecoration(
                                          color: activity.isUrgent ? AppColors.error : AppColors.badgePink,
                                          shape: BoxShape.circle,
                                          border: Border.all(color: Colors.white, width: 2),
                                        ),
                                        child: const Icon(
                                          Icons.cake,
                                          size: 10,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                member.displayName,
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                  color: AppColors.textPrimary,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                textAlign: TextAlign.center,
                              ),
                              Text(
                                activity.activityType == _ActivityType.birthday
                                    ? activity.description
                                    : member.relationText,
                                style: TextStyle(
                                  fontSize: 10,
                                  color: activity.isUrgent
                                      ? AppColors.error
                                      : AppColors.textTertiary,
                                  fontWeight: activity.isUrgent ? FontWeight.w600 : FontWeight.normal,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          );
        }

        return SectionCard(
          title: '家人圈',
          child: _buildEmptyFamilyActivities(),
        );
      },
    );
  }

  Color _getAvatarColor(String relation) {
    switch (relation) {
      case 'spouse':
        return AppColors.badgePink;
      case 'child':
        return AppColors.badgeBlue;
      case 'parent':
        return AppColors.badgeGreen;
      case 'grandchild':
        return AppColors.badgeOrange;
      default:
        return AppColors.chipBackground;
    }
  }

  Widget _buildEmptyFamilyActivities() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.family_restroom_outlined,
              size: 48,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 12),
            const Text(
              '还没有添加家人',
              style: TextStyle(
                fontSize: 15,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              '添加家人后可以追踪生日、纪念日等重要日期',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            GestureDetector(
              onTap: () => context.push(Routes.memberForm),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.person_add_outlined, color: Colors.white, size: 18),
                    SizedBox(width: 8),
                    Text(
                      '添加第一位家人',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHealthSection(BuildContext context) {
    return SectionCard(
      title: '家庭健康',
      trailing: GestureDetector(
        onTap: () => context.push(Routes.health),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '查看全部',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(width: 4),
            Icon(Icons.chevron_right, color: AppColors.primary, size: 16),
          ],
        ),
      ),
      child: Column(
        children: [
          // Health quick actions
          Row(
            children: [
              Expanded(
                child: _buildHealthQuickAction(
                  context,
                  icon: Icons.assignment_outlined,
                  label: '体检记录',
                  color: AppColors.badgeBlue,
                  onTap: () => context.push(Routes.checkups),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildHealthQuickAction(
                  context,
                  icon: Icons.medication_outlined,
                  label: '用药提醒',
                  color: AppColors.badgePink,
                  onTap: () => context.push(Routes.medications),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildHealthQuickAction(
                  context,
                  icon: Icons.monitor_heart_outlined,
                  label: '健康数据',
                  color: AppColors.badgeGreen,
                  onTap: () => context.push(Routes.vitalSigns),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Health reminder preview
          _buildHealthReminder(
            title: '定期体检提醒',
            subtitle: '建议每年进行一次全面体检',
            icon: Icons.event_available,
            color: AppColors.primary,
            onTap: () => context.push(Routes.health),
          ),
        ],
      ),
    );
  }

  Widget _buildHealthQuickAction(
    BuildContext context, {
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHealthReminder({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: AppColors.textTertiary, size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildChildGrowthSection(BuildContext context) {
    return BlocBuilder<MembersBloc, MembersState>(
      builder: (context, state) {
        // Find child members
        List<dynamic> children = [];
        if (state is MembersLoaded) {
          children = state.members
              .where((m) => m.relation == 'child' || m.relation == 'grandchild')
              .toList();
        }

        // Don't show section if no children
        if (children.isEmpty) {
          return const SizedBox.shrink();
        }

        return SectionCard(
          title: '宝宝成长',
          trailing: GestureDetector(
            onTap: () => context.push(Routes.child),
            child: Text(
              '查看全部',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          child: Column(
            children: [
              // Child cards
              ...children.take(2).map((child) => _buildChildCard(context, child)),
              const SizedBox(height: 12),
              // Quick actions
              Row(
                children: [
                  Expanded(
                    child: _buildChildQuickAction(
                      context,
                      icon: Icons.straighten,
                      label: '成长记录',
                      onTap: () {
                        if (children.isNotEmpty) {
                          context.push(Routes.childGrowth(children.first.id));
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildChildQuickAction(
                      context,
                      icon: Icons.emoji_events_outlined,
                      label: '成长里程碑',
                      onTap: () {
                        if (children.isNotEmpty) {
                          context.push(Routes.childMilestones(children.first.id));
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildChildQuickAction(
                      context,
                      icon: Icons.vaccines_outlined,
                      label: '疫苗接种',
                      onTap: () {
                        if (children.isNotEmpty) {
                          context.push(Routes.childVaccines(children.first.id));
                        }
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildChildCard(BuildContext context, dynamic child) {
    return GestureDetector(
      onTap: () async {
        await context.push(Routes.memberDetail(child.id));
        if (context.mounted) {
          _membersBloc.add(const MembersLoadRequested());
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppColors.badgePink.withValues(alpha: 0.3),
              AppColors.badgeBlue.withValues(alpha: 0.2),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.child_care, color: AppColors.primary, size: 24),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    child.displayName,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Text(
                    child.age != null ? '${child.age}岁' : child.relationText,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textTertiary, size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildChildQuickAction(
    BuildContext context, {
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.chipBackground,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          children: [
            Icon(icon, color: AppColors.primary, size: 20),
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMoreServices(BuildContext context) {
    return SectionCard(
      title: '更多服务',
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildServiceItem(
                  context,
                  icon: Icons.account_balance_wallet_outlined,
                  label: '家庭财务',
                  color: AppColors.badgeGreen,
                  onTap: () => context.push(Routes.finance),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildServiceItem(
                  context,
                  icon: Icons.home_outlined,
                  label: '房产管理',
                  color: AppColors.badgeBlue,
                  onTap: () => context.push(Routes.housing),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildServiceItem(
                  context,
                  icon: Icons.card_giftcard_outlined,
                  label: '礼物推荐',
                  color: AppColors.badgePink,
                  onTap: () => context.push(Routes.gifts),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildServiceItem(
                  context,
                  icon: Icons.auto_graph_outlined,
                  label: '目标追踪',
                  color: AppColors.badgeOrange,
                  onTap: () => context.push(Routes.goals),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildServiceItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: AppColors.textPrimary,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

/// Helper class for pending tasks
class _PendingTask {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool isUrgent;
  final VoidCallback? onPrimary;

  const _PendingTask({
    required this.title,
    required this.subtitle,
    this.icon = Icons.task_outlined,
    this.isUrgent = false,
    this.onPrimary,
  });
}

/// Helper class for family activities
class _FamilyActivity {
  final dynamic member; // Member type
  final _ActivityType activityType;
  final String description;
  final bool isUrgent;

  const _FamilyActivity({
    required this.member,
    required this.activityType,
    required this.description,
    this.isUrgent = false,
  });
}

enum _ActivityType {
  birthday,
  member,
}
