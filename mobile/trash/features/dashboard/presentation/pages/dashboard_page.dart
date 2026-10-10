import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../dates/presentation/bloc/dates_bloc.dart';
import '../../../dates/domain/entities/important_date.dart' show DateType;
import '../../../secretary/presentation/bloc/secretary_bloc.dart';
import '../../../secretary/domain/entities/smart_suggestion.dart'
    show SuggestionType;
import '../bloc/dashboard_bloc.dart';
import '../widgets/weather_chip.dart';
import '../widgets/daily_snapshot_section.dart';
import '../widgets/opportunity_alerts_section.dart';
import '../widgets/relationship_health_section.dart';

/// Redesigned Dashboard Page following demo design.
///
/// Structure:
/// 1. Header - Greeting + Date + Weather + Avatar
/// 2. Daily Snapshot - Today's key items with priority
/// 3. Opportunity Alerts - Travel, reconnect, gift opportunities
/// 4. Relationship Health - Key relationships status
class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  @override
  void initState() {
    super.initState();

    // Load data when dashboard is initialized
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<DatesBloc>().add(const DatesLoadRequested());
      context.read<SecretaryBloc>().add(const LoadSuggestions(limit: 10));

      // Load dashboard-specific data if bloc is available
      try {
        final dashboardBloc = context.read<DashboardBloc>();
        dashboardBloc.add(const LoadDashboardData());
      } catch (_) {
        // DashboardBloc not provided, use fallback data
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _onRefresh,
          color: AppColors.primary,
          child: CustomScrollView(
            physics: const BouncingScrollPhysics(
              parent: AlwaysScrollableScrollPhysics(),
            ),
            slivers: [
              // Header with greeting, date, weather
              SliverToBoxAdapter(
                child: _buildHeader(context),
              ),

              // Daily Snapshot section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: _buildDailySnapshot(context),
                ),
              ),

              // PRD-style Smart Widgets: [📅 今日3项] [🎁 人情2项] [🏠 家庭1项]
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: _buildSmartWidgets(context),
                ),
              ),

              // Quick actions
              SliverToBoxAdapter(
                child: _buildQuickActions(context),
              ),

              // Opportunity Alerts section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.only(top: 24),
                  child: _buildOpportunityAlerts(context),
                ),
              ),

              // Relationship Health section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.only(top: 24),
                  child: _buildRelationshipHealth(context),
                ),
              ),

              // Bottom padding for FAB
              const SliverPadding(padding: EdgeInsets.only(bottom: 100)),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go(Routes.conversation),
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.auto_awesome, color: Colors.white),
        label: const Text(
          'AI 助理',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  Future<void> _onRefresh() async {
    HapticFeedback.mediumImpact();
    context.read<DatesBloc>().add(const DatesLoadRequested());
    context.read<SecretaryBloc>().add(const LoadSuggestions(limit: 10));

    try {
      final dashboardBloc = context.read<DashboardBloc>();
      dashboardBloc.add(const RefreshDashboardData());
    } catch (_) {
      // DashboardBloc not provided
    }

    await Future.delayed(const Duration(milliseconds: 500));
  }

  /// PRD-style smart widgets: [📅 今日3项] [🎁 人情2项] [🏠 家庭1项]
  Widget _buildSmartWidgets(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      child: Row(
        children: [
          // 📅 今日事项
          Expanded(
            child: BlocBuilder<DatesBloc, DatesState>(
              builder: (context, state) {
                int todayCount = 0;
                if (state is DatesLoaded) {
                  todayCount = state.dates.where((d) => d.daysUntilNext == 0).length;
                }
                return _buildSmartWidgetChip(
                  context,
                  emoji: '📅',
                  label: '今日',
                  count: todayCount,
                  color: AppColors.primary,
                  onTap: () => context.push(Routes.schedule),
                );
              },
            ),
          ),
          const SizedBox(width: 8),
          // 🎁 人情提醒
          Expanded(
            child: BlocBuilder<SecretaryBloc, SecretaryState>(
              builder: (context, state) {
                int favorCount = 0;
                if (state is SecretaryLoaded) {
                  favorCount = state.suggestions.where((s) =>
                    s.type == SuggestionType.giftReminder ||
                    s.type == SuggestionType.anniversaryReminder ||
                    s.type == SuggestionType.meetupSuggestion ||
                    s.type == SuggestionType.personCorrelation
                  ).length;
                }
                return _buildSmartWidgetChip(
                  context,
                  emoji: '🎁',
                  label: '人情',
                  count: favorCount,
                  color: AppColors.accent1,
                  onTap: () => context.push(Routes.favorLedger),
                );
              },
            ),
          ),
          const SizedBox(width: 8),
          // 🏠 家庭事项
          Expanded(
            child: BlocBuilder<DatesBloc, DatesState>(
              builder: (context, state) {
                int familyCount = 0;
                if (state is DatesLoaded) {
                  // Count upcoming dates within 7 days (family reminders)
                  familyCount = state.upcomingDates
                      .where((d) => d.daysUntilNext <= 7 && d.daysUntilNext > 0)
                      .length;
                }
                return _buildSmartWidgetChip(
                  context,
                  emoji: '🏠',
                  label: '家庭',
                  count: familyCount,
                  color: AppColors.secondary,
                  onTap: () => context.push(Routes.members),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSmartWidgetChip(
    BuildContext context, {
    required String emoji,
    required String label,
    required int count,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: color.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 16)),
            const SizedBox(width: 6),
            Text(
              '$label$count项',
              style: AppTextStyles.caption.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context) {
    final actions = [
      (icon: Icons.person_add_outlined, label: '添加成员', color: AppColors.primary, route: Routes.memberForm),
      (icon: Icons.event_outlined, label: '添加日期', color: AppColors.secondary, route: Routes.dates),
      (icon: Icons.card_giftcard_outlined, label: '礼物推荐', color: AppColors.accent1, route: Routes.giftEntry),
      (icon: Icons.flight_outlined, label: '旅行计划', color: AppColors.accent2, route: Routes.travel),
      (icon: Icons.search, label: '研究搜索', color: const Color(0xFF10B981), route: Routes.research),
      (icon: Icons.menu_book_outlined, label: '知识库', color: const Color(0xFF6366F1), route: Routes.notebooks),
    ];

    return SizedBox(
      height: 100,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: actions.length,
        itemBuilder: (context, index) {
          final action = actions[index];
          return GestureDetector(
            onTap: () => context.push(action.route),
            child: Container(
              width: 72,
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: AppColors.cardShadow,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: action.color.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      action.icon,
                      color: action.color,
                      size: 20,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    action.label,
                    style: AppTextStyles.caption.copyWith(
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                      fontSize: 11,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  /// Build header with greeting, date, weather, and avatar.
  Widget _buildHeader(BuildContext context) {
    final now = DateTime.now();
    final greeting = _getGreeting(now.hour);
    final dateStr = _formatDateFull(now);

    return Container(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          // User avatar
          BlocBuilder<AuthBloc, AuthState>(
            builder: (context, state) {
              // User entity doesn't have avatarUrl yet - use placeholder
              const String? avatarUrl = null;
              return GestureDetector(
                onTap: () => context.push(Routes.profile),
                child: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: AppColors.primary.withValues(alpha: 0.3),
                      width: 2,
                    ),
                    image: avatarUrl != null
                        ? DecorationImage(
                            image: NetworkImage(avatarUrl),
                            fit: BoxFit.cover,
                          )
                        : null,
                  ),
                  child: avatarUrl == null
                      ? Container(
                          decoration: BoxDecoration(
                            gradient: AppColors.primaryGradient,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(
                            Icons.person,
                            color: Colors.white,
                            size: 24,
                          ),
                        )
                      : null,
                ),
              );
            },
          ),
          const SizedBox(width: 12),
          // Greeting and date
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                BlocBuilder<AuthBloc, AuthState>(
                  builder: (context, state) {
                    String name = '主人';
                    if (state is AuthAuthenticated) {
                      name = state.user.username;
                    }
                    return Text(
                      '$greeting，$name',
                      style: AppTextStyles.headline5.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    );
                  },
                ),
                const SizedBox(height: 2),
                Text(
                  dateStr,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          // Weather chip - try to get from DashboardBloc or show default
          _buildWeatherChip(),
        ],
      ),
    );
  }

  Widget _buildWeatherChip() {
    try {
      return BlocBuilder<DashboardBloc, DashboardState>(
        builder: (context, state) {
          if (state is DashboardLoaded && state.weather != null) {
            return WeatherChip(
              temperature: '${state.weather!.temperature}°',
              condition: state.weather!.condition,
              onTap: () => _showWeatherDetail(context, state.weather!),
            );
          }
          // Show default weather
          return const WeatherChip(
            temperature: '5°',
            condition: 'sunny',
          );
        },
      );
    } catch (_) {
      // DashboardBloc not provided, show default
      return const WeatherChip(
        temperature: '5°',
        condition: 'sunny',
      );
    }
  }

  String _getGreeting(int hour) {
    if (hour < 6) return '夜深了';
    if (hour < 12) return '早上好';
    if (hour < 14) return '中午好';
    if (hour < 18) return '下午好';
    if (hour < 22) return '晚上好';
    return '夜深了';
  }

  String _formatDateFull(DateTime date) {
    final weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    final weekday = weekdays[date.weekday - 1];
    return '$weekday，${date.month}月${date.day}日';
  }

  void _showWeatherDetail(BuildContext context, WeatherInfo weather) {
    HapticFeedback.lightImpact();
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '今日天气',
                style: AppTextStyles.headline6,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text(
                    '${weather.temperature}°',
                    style: AppTextStyles.headline2.copyWith(
                      fontWeight: FontWeight.w300,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        weather.condition,
                        style: AppTextStyles.subtitle1,
                      ),
                      if (weather.highTemp != null && weather.lowTemp != null)
                        Text(
                          '${weather.highTemp}° / ${weather.lowTemp}°',
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 20),
            ],
          ),
        );
      },
    );
  }

  /// Build Daily Snapshot section.
  Widget _buildDailySnapshot(BuildContext context) {
    return BlocBuilder<SecretaryBloc, SecretaryState>(
      builder: (context, secretaryState) {
        return BlocBuilder<DatesBloc, DatesState>(
          builder: (context, datesState) {
            final items = _buildSnapshotItems(secretaryState, datesState);

            return DailySnapshotSection(
              items: items,
              onViewAll: () => context.push(Routes.dailyBriefing),
              onItemToggle: (itemId, completed) {
                HapticFeedback.lightImpact();
                // Handle item completion
              },
            );
          },
        );
      },
    );
  }

  List<SnapshotItem> _buildSnapshotItems(
    SecretaryState secretaryState,
    DatesState datesState,
  ) {
    final items = <SnapshotItem>[];

    // Get today's dates
    if (datesState is DatesLoaded) {
      final todayDates = datesState.dates
          .where((d) => d.daysUntilNext == 0)
          .toList();

      // Aggregate custom/holiday dates as events
      final events = todayDates
          .where((d) => d.dateType == DateType.custom || d.dateType == DateType.holiday)
          .toList();

      if (events.length > 1) {
        items.add(SnapshotItem(
          id: 'events_aggregate',
          title: '${events.length} 个事项',
          subtitle: '下一个: ${events.first.title}',
          icon: '📅',
          type: SnapshotItemType.meeting,
          priority: SnapshotPriority.normal,
          onTap: () => context.push(Routes.schedule),
        ));
      } else if (events.length == 1) {
        items.add(SnapshotItem(
          id: events.first.id,
          title: events.first.title,
          subtitle: events.first.description ?? '今日事项',
          icon: '📅',
          type: SnapshotItemType.meeting,
          priority: SnapshotPriority.normal,
          onTap: () => context.push(Routes.schedule),
        ));
      }

      // Add birthdays and anniversaries with urgent priority
      for (final date in todayDates) {
        if (date.dateType == DateType.birthday) {
          items.add(SnapshotItem(
            id: date.id,
            title: date.title,
            subtitle: '今日需要行动',
            icon: '🎂',
            type: SnapshotItemType.birthday,
            priority: SnapshotPriority.urgent,
            actionLabel: '查看',
            onAction: () => context.push(Routes.giftEntry),
            onTap: () => context.push(Routes.dates),
          ));
        } else if (date.dateType == DateType.anniversary) {
          items.add(SnapshotItem(
            id: date.id,
            title: date.title,
            subtitle: '今日需要行动',
            icon: '💝',
            type: SnapshotItemType.gift,
            priority: SnapshotPriority.urgent,
            actionLabel: '查看',
            onAction: () => context.push(Routes.giftEntry),
            onTap: () => context.push(Routes.dates),
          ));
        }
      }
    }

    // Get gift suggestions
    if (secretaryState is SecretaryLoaded) {
      for (final suggestion in secretaryState.suggestions.take(2)) {
        if (suggestion.type == SuggestionType.giftReminder &&
            !items.any((i) => i.id == suggestion.id)) {
          items.add(SnapshotItem(
            id: suggestion.id,
            title: suggestion.title,
            subtitle: suggestion.content,
            icon: '🎁',
            type: SnapshotItemType.gift,
            priority: suggestion.isHighUrgency
                ? SnapshotPriority.urgent
                : SnapshotPriority.normal,
            actionLabel: '查看',
            onAction: () => context.push(Routes.giftEntry),
          ));
        }
      }
    }

    return items;
  }

  /// Build Opportunity Alerts section.
  Widget _buildOpportunityAlerts(BuildContext context) {
    return BlocBuilder<SecretaryBloc, SecretaryState>(
      builder: (context, state) {
        final items = _buildOpportunityItems(state);

        if (items.isEmpty) {
          return const SizedBox.shrink();
        }

        return OpportunityAlertsSection(
          items: items,
          onViewAll: () => context.push(Routes.dailyBriefing),
        );
      },
    );
  }

  List<OpportunityItem> _buildOpportunityItems(SecretaryState state) {
    final items = <OpportunityItem>[];

    if (state is SecretaryLoaded) {
      for (final suggestion in state.suggestions) {
        // Travel suggestions
        if (suggestion.type == SuggestionType.preparationReminder ||
            suggestion.relatedTravelIds.isNotEmpty) {
          // Calculate days until from expiresAt
          final daysUntil = suggestion.expiresAt != null
              ? suggestion.expiresAt!.difference(DateTime.now()).inDays
              : 2;
          items.add(OpportunityItem(
            id: suggestion.id,
            title: suggestion.title,
            subtitle: suggestion.content,
            type: OpportunityType.travel,
            metadata: {
              'days_until': daysUntil,
              'duration': 4,
            },
            onTap: () => context.push(Routes.travel),
          ));
        }
        // Reconnect suggestions
        else if (suggestion.type == SuggestionType.meetupSuggestion ||
            suggestion.type == SuggestionType.personCorrelation) {
          items.add(OpportunityItem(
            id: suggestion.id,
            title: suggestion.title,
            subtitle: suggestion.content,
            type: OpportunityType.reconnect,
            onAction: () {
              // Open messaging
            },
            onTap: () => context.push(Routes.members),
          ));
        }
        // Gift suggestions
        else if (suggestion.type == SuggestionType.giftReminder ||
            suggestion.type == SuggestionType.anniversaryReminder) {
          items.add(OpportunityItem(
            id: suggestion.id,
            title: suggestion.title,
            subtitle: suggestion.content,
            type: OpportunityType.gift,
            actionLabel: 'Review',
            onAction: () => context.push(Routes.giftEntry),
            onTap: () => context.push(Routes.gifts),
          ));
        }
      }
    }

    return items.take(5).toList();
  }

  /// Build Relationship Health section.
  Widget _buildRelationshipHealth(BuildContext context) {
    // Try to get data from DashboardBloc if available
    try {
      return BlocBuilder<DashboardBloc, DashboardState>(
        builder: (context, state) {
          List<RelationshipHealthItem> items = [];
          bool isLoading = false;

          if (state is DashboardLoading) {
            isLoading = true;
          } else if (state is DashboardLoaded) {
            items = state.relationshipHealth.map((r) {
              return RelationshipHealthItem(
                id: r.memberId,
                name: r.name,
                type: _mapRelationType(r.relationType),
                healthScore: r.healthScore,
                suggestion: r.suggestion,
                avatarUrl: r.avatarUrl,
                daysSinceContact: r.daysSinceContact,
                onTap: () => context.push(Routes.memberDetail(r.memberId)),
              );
            }).toList();
          }

          return RelationshipHealthSection(
            items: items,
            isLoading: isLoading,
            onViewAll: () => context.push(Routes.relationships),
          );
        },
      );
    } catch (_) {
      // DashboardBloc not provided, show empty state
      return RelationshipHealthSection(
        items: const [],
        onViewAll: () => context.push(Routes.relationships),
      );
    }
  }

  RelationshipType _mapRelationType(String? type) {
    switch (type) {
      case 'partner':
      case 'spouse':
        return RelationshipType.partner;
      case 'parent':
      case 'father':
      case 'mother':
        return RelationshipType.parent;
      case 'child':
      case 'son':
      case 'daughter':
        return RelationshipType.child;
      case 'sibling':
      case 'brother':
      case 'sister':
        return RelationshipType.sibling;
      case 'friend':
        return RelationshipType.friend;
      case 'colleague':
        return RelationshipType.colleague;
      default:
        return RelationshipType.other;
    }
  }
}

/// Weather information model.
class WeatherInfo {
  final int temperature;
  final String condition;
  final int? highTemp;
  final int? lowTemp;
  final String? humidity;
  final String? location;

  const WeatherInfo({
    required this.temperature,
    required this.condition,
    this.highTemp,
    this.lowTemp,
    this.humidity,
    this.location,
  });
}

/// Relationship health data model.
class RelationshipHealthData {
  final String memberId;
  final String name;
  final String? relationType;
  final int healthScore;
  final String suggestion;
  final String? avatarUrl;
  final int? daysSinceContact;

  const RelationshipHealthData({
    required this.memberId,
    required this.name,
    this.relationType,
    required this.healthScore,
    required this.suggestion,
    this.avatarUrl,
    this.daysSinceContact,
  });
}
