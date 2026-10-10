import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../../../kanban/data/models/insight_feed_models.dart';
import '../../../kanban/domain/repositories/insight_feed_repository.dart';
import '../../../kanban/presentation/widgets/insight_section.dart';
import '../../domain/entities/trip.dart';
import '../../domain/entities/itinerary.dart';
import '../../domain/entities/trip_expense.dart';
import '../../data/models/trip_context_model.dart';
import '../../data/models/association_summary_model.dart';
import '../../data/models/related_memory_model.dart';

/// Callback signature for toggling a preparation item.
typedef PrepToggleCallback = void Function(
  String curatedEventId,
  String itemKey,
  bool done,
);

/// Overview tab for Trip Detail V2.
///
/// All text content comes from the backend — the frontend only displays it.
/// Sections: AI insight, weather alert, recommendation highlights,
/// budget, people, side activities, related memories, prep checklist, CTA.
class TripOverviewTab extends StatefulWidget {
  final Trip trip;
  final List<DayItinerary> itinerary;
  final BudgetStatus? budgetStatus;
  final TripContextModel? tripContext;
  final List<AssociationSummaryModel> associations;
  final List<RelatedMemoryModel> relatedMemories;
  final String? currentUserId;
  final VoidCallback? onChatContinue;
  final PrepToggleCallback? onTogglePrepItem;
  final VoidCallback? onManageParticipants;

  const TripOverviewTab({
    super.key,
    required this.trip,
    this.itinerary = const [],
    this.budgetStatus,
    this.tripContext,
    this.associations = const [],
    this.relatedMemories = const [],
    this.currentUserId,
    this.onChatContinue,
    this.onTogglePrepItem,
    this.onManageParticipants,
  });

  @override
  State<TripOverviewTab> createState() => _TripOverviewTabState();
}

class _TripOverviewTabState extends State<TripOverviewTab> {
  List<InsightFeedItemModel>? _tripInsights;
  bool _insightsLoaded = false;

  Trip get trip => widget.trip;
  List<DayItinerary> get itinerary => widget.itinerary;
  BudgetStatus? get budgetStatus => widget.budgetStatus;
  TripContextModel? get tripContext => widget.tripContext;
  List<AssociationSummaryModel> get associations => widget.associations;
  List<RelatedMemoryModel> get relatedMemories => widget.relatedMemories;
  String? get currentUserId => widget.currentUserId;
  VoidCallback? get onChatContinue => widget.onChatContinue;
  PrepToggleCallback? get onTogglePrepItem => widget.onTogglePrepItem;
  VoidCallback? get onManageParticipants => widget.onManageParticipants;

  @override
  void initState() {
    super.initState();
    _fetchTripInsights();
  }

  Future<void> _fetchTripInsights() async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      final result = await repository.getTripInsights(tripId: trip.id);
      if (!mounted) return;
      result.fold(
        (_) => setState(() => _insightsLoaded = true),
        (insights) => setState(() {
          _tripInsights = insights;
          _insightsLoaded = true;
        }),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _insightsLoaded = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        // Structured AI insights (from unified insight API)
        if (_hasStructuredInsights)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: InsightSection(
              insights: _tripInsights!,
              title: 'AI \u667A\u80FD\u63D0\u9192',
              maxVisible: 3,
              showActions: true,
              onInsightActionTap: _handleInsightAction,
              onInsightDismiss: _handleInsightDismiss,
            ),
          )
        // Fallback: plain text insight card
        else if (_hasInsightText)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: GestureDetector(
              onTap: () => _showInsightDetail(context),
              child: _buildAiInsightCard(),
            ),
          ),

        // Weather alert
        if (tripContext?.weather != null && tripContext!.weather!.hasAlert)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: _buildWeatherAlertCard(tripContext!.weather!),
          ),

        // Recommendation highlights (from backend AI planning)
        if (_hasRecommendationHighlights)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildRecommendationSection(),
          ),

        // Budget summary
        if (trip.budget != null && trip.budget! > 0)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildBudgetSummaryCard(),
          ),

        // People section
        if (_hasParticipants)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildPeopleSection(context),
          ),

        // "顺便做的事情" — from backend side_activities
        if (_hasSideActivities)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildSideActivitiesSection(context),
          ),

        // Related memories
        if (relatedMemories.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildRelatedMemoriesSection(),
          ),

        // Prep checklist
        if (_hasPrepItems)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: _buildPrepChecklist(),
          ),

        // CTA buttons
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
          child: _buildCtaSection(),
        ),

        const SizedBox(height: 24),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Data helpers
  // ---------------------------------------------------------------------------

  void _handleInsightAction(
    InsightFeedItemModel insight,
    String actionType,
    Map<String, dynamic>? payload,
  ) {
    final repository = GetIt.instance<InsightFeedRepository>();
    if (actionType == 'adopt' || actionType == 'create_pending_action') {
      repository.adoptInsight(insightId: insight.id, tripId: trip.id);
      _fetchTripInsights();
    } else {
      repository.submitInsightFeedback(
        insightId: insight.id,
        feedbackType: 'acknowledged',
      );
      _fetchTripInsights();
    }
  }

  Future<bool> _handleInsightDismiss(InsightFeedItemModel insight) async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      await repository.submitInsightFeedback(
        insightId: insight.id,
        feedbackType: 'not_useful',
      );
      setState(() {
        _tripInsights = _tripInsights?.where((i) => i.id != insight.id).toList();
      });
      return true;
    } catch (e) {
      debugPrint('Error dismissing insight: $e');
      return false;
    }
  }

  bool get _hasStructuredInsights =>
      _insightsLoaded &&
      _tripInsights != null &&
      _tripInsights!.isNotEmpty;

  bool get _hasInsightText =>
      tripContext?.insightText != null && tripContext!.insightText!.isNotEmpty;

  bool get _hasParticipants {
    if (tripContext == null) return false;
    return tripContext!.participants.isNotEmpty;
  }

  bool get _hasPrepItems =>
      tripContext != null && tripContext!.preparationItems.isNotEmpty;

  List<TripPrepItemModel> get _prepItems =>
      tripContext?.preparationItems ?? const [];

  bool get _hasRecommendationHighlights =>
      tripContext != null && tripContext!.recommendationHighlights.isNotEmpty;

  bool get _hasSideActivities =>
      tripContext != null && tripContext!.sideActivities.isNotEmpty;

  // ---------------------------------------------------------------------------
  // AI Insight Card — displays server-provided insight_text directly
  // ---------------------------------------------------------------------------

  Widget _buildAiInsightCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFD4EDDA), Color(0xFFF5F4F1)],
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, size: 14, color: Color(0xFF2D7A46)),
              SizedBox(width: 6),
              Text(
                'AI 智能提醒',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF2D7A46),
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            tripContext!.insightText!,
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF1A3D2A),
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Weather Alert
  // ---------------------------------------------------------------------------

  Widget _buildWeatherAlertCard(WeatherAlertModel weather) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF3E0), AppColors.background],
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: 20,
            color: AppColors.alertOrange,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (weather.alertMessage != null)
                  Text(
                    weather.alertMessage!,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFFBF360C),
                    ),
                  ),
                if (weather.advice != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    weather.advice!,
                    style: const TextStyle(
                      fontSize: 13,
                      color: Color(0xFFE65100),
                      height: 1.45,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Recommendation Highlights (server-provided)
  // ---------------------------------------------------------------------------

  Widget _buildRecommendationSection() {
    final items = tripContext!.recommendationHighlights;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.lightbulb_outline,
                size: 16, color: AppColors.accentGreen),
            SizedBox(width: 6),
            Text(
              '行程规划',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderSubtle, width: 1),
          ),
          child: Column(
            children: items.asMap().entries.map((entry) {
              final item = entry.value;
              final isLast = entry.key == items.length - 1;
              final color = _iconColorForCategory(item.category);

              return Padding(
                padding: EdgeInsets.only(bottom: isLast ? 0 : 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        _iconDataForName(item.icon),
                        size: 16,
                        color: color,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.label,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          if (item.detail.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              item.detail,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.textSecondary,
                                height: 1.4,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Color _iconColorForCategory(String category) {
    switch (category) {
      case 'people':
        return const Color(0xFF5C6BC0);
      case 'accommodation':
        return AppColors.accentGreen;
      case 'budget':
        return AppColors.accent1;
      case 'tip':
        return AppColors.accentBlue;
      case 'rationale':
        return AppColors.primary;
      default:
        return AppColors.accentGreen;
    }
  }

  IconData _iconDataForName(String iconName) {
    switch (iconName) {
      case 'user':
        return Icons.person_outline;
      case 'hotel':
        return Icons.hotel_outlined;
      case 'wallet':
        return Icons.account_balance_wallet_outlined;
      case 'lightbulb':
        return Icons.lightbulb_outline;
      case 'sparkles':
        return Icons.auto_awesome;
      default:
        return Icons.info_outline;
    }
  }

  // ---------------------------------------------------------------------------
  // People Section
  // ---------------------------------------------------------------------------

  Widget _buildPeopleSection(BuildContext context) {
    final participants = tripContext!.participants.toList();

    if (participants.isEmpty) return const SizedBox.shrink();

    const avatarColors = [
      AppColors.accentGreen,
      Color(0xFF5C6BC0),
      Color(0xFFEF6C00),
      AppColors.avatarGold,
      AppColors.avatarPink,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.group_outlined,
                size: 16, color: AppColors.accentGreen),
            const SizedBox(width: 6),
            const Text(
              '参与成员',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${participants.length}',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
            const Spacer(),
            if (onManageParticipants != null)
              TextButton.icon(
                onPressed: onManageParticipants,
                icon: const Icon(Icons.edit_outlined, size: 14),
                label: const Text('编辑成员'),
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  foregroundColor: AppColors.accentGreen,
                ),
              ),
          ],
        ),
        const SizedBox(height: 10),
        ...participants.asMap().entries.map((entry) {
          final index = entry.key;
          final p = entry.value;
          final color = avatarColors[index % avatarColors.length];
          final isMe = p.id == currentUserId;
          final displayName =
              isMe ? '我（${p.displayName}）' : p.displayName;
          final relationLabel = p.relation != null && p.relation!.isNotEmpty
              ? RelationUtils.getRelationLabel(p.relation!)
              : (p.isChild ? '儿童' : null);

          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Material(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(14),
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => context.push(Routes.memberDetail(p.id)),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    border:
                        Border.all(color: AppColors.borderSubtle, width: 1),
                  ),
                  child: Row(
                    children: [
                      // Avatar
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [
                              color,
                              color.withValues(alpha: 0.75),
                            ],
                          ),
                          shape: BoxShape.circle,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          p.displayName.isNotEmpty
                              ? p.displayName.substring(0, 1)
                              : '',
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      // Info column — takes all remaining space
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Row 1: Name + age + relation chip
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    displayName,
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.textPrimary,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (p.age != null) ...[
                                  const SizedBox(width: 6),
                                  Text(
                                    '${p.age}岁',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: AppColors.textTertiary,
                                    ),
                                  ),
                                ],
                                if (relationLabel != null) ...[
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: color.withValues(alpha: 0.10),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      relationLabel,
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w500,
                                        color: color,
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                            // Row 2: Context label (AI suggestion)
                            if (p.contextLabel != null &&
                                p.contextLabel!.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Icon(Icons.lightbulb_outline,
                                      size: 13,
                                      color: AppColors.accent1
                                          .withValues(alpha: 0.7)),
                                  const SizedBox(width: 4),
                                  Expanded(
                                    child: Text(
                                      p.contextLabel!,
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textSecondary
                                            .withValues(alpha: 0.85),
                                        height: 1.3,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                            // Row 3: Action tags
                            if (p.actionTags.isNotEmpty) ...[
                              const SizedBox(height: 6),
                              Wrap(
                                spacing: 6,
                                runSpacing: 4,
                                children: p.actionTags.map((tag) {
                                  return Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: AppColors.primary
                                          .withValues(alpha: 0.08),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      tag,
                                      style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w500,
                                        color: AppColors.primary,
                                      ),
                                    ),
                                  );
                                }).toList(),
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(width: 4),
                      // Chevron — navigation hint
                      const Icon(
                        Icons.chevron_right_rounded,
                        size: 20,
                        color: AppColors.textHint,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Side Activities — "顺便做的事情" (server-provided)
  // ---------------------------------------------------------------------------

  Widget _buildSideActivitiesSection(BuildContext context) {
    final items = tripContext!.sideActivities;

    const priorityColors = <String, Color>{
      'high': Color(0xFFE53935),
      'medium': Color(0xFFEF6C00),
      'low': AppColors.accentGreen,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.explore_outlined,
                size: 16, color: AppColors.accentGreen),
            const SizedBox(width: 6),
            const Text(
              '顺便做的事情',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${items.length}',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        ...items.asMap().entries.map((entry) {
          final item = entry.value;
          final isLast = entry.key == items.length - 1;
          final accentColor =
              priorityColors[item.priority] ?? AppColors.accentGreen;

          return Padding(
            padding: EdgeInsets.only(bottom: isLast ? 0 : 8),
            child: GestureDetector(
              onTap: () => _showSideActivityDetail(context, item, accentColor),
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.borderSubtle, width: 1),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 4,
                      height: 56,
                      decoration: BoxDecoration(
                        color: accentColor,
                        borderRadius: const BorderRadius.horizontal(
                            left: Radius.circular(14)),
                      ),
                    ),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 10),
                        child: Row(
                          children: [
                            Icon(
                              _sideActivityIcon(item.targetType),
                              size: 22,
                              color: accentColor,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(item.title,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.textPrimary,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis),
                                  if (item.reason != null) ...[
                                    const SizedBox(height: 2),
                                    Text(item.reason!,
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: AppColors.textSecondary,
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis),
                                  ],
                                ],
                              ),
                            ),
                            const Icon(Icons.chevron_right,
                                size: 18, color: AppColors.textTertiary),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ],
    );
  }

  IconData _sideActivityIcon(String targetType) {
    switch (targetType) {
      case 'task':
        return Icons.assignment_outlined;
      case 'place':
        return Icons.place_outlined;
      case 'date':
        return Icons.event_outlined;
      case 'memory':
        return Icons.psychology_outlined;
      default:
        return Icons.link;
    }
  }

  // ---------------------------------------------------------------------------
  // Related Memories
  // ---------------------------------------------------------------------------

  Widget _buildRelatedMemoriesSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.psychology_outlined,
                size: 16, color: AppColors.accentGreen),
            SizedBox(width: 6),
            Text(
              '相关记忆',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 90,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: relatedMemories.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final mem = relatedMemories[index];
              return GestureDetector(
                onTap: () => context.push(Routes.memoryDetail(mem.id)),
                child: Container(
                  width: 200,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.chipBackground,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.borderSubtle, width: 1),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(mem.categoryIcon,
                              style: const TextStyle(fontSize: 14)),
                          const SizedBox(width: 6),
                          Text(mem.categoryLabel,
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textTertiary,
                              )),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Expanded(
                        child: Text(mem.summary,
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.textSecondary,
                              height: 1.4,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Preparation Checklist
  // ---------------------------------------------------------------------------

  Widget _buildPrepChecklist() {
    final items = _prepItems;
    final doneCount = items.where((i) => i.done).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.checklist_outlined,
                size: 16, color: AppColors.accentGreen),
            const SizedBox(width: 6),
            const Text('准备清单',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                )),
            const SizedBox(width: 8),
            Text('$doneCount/${items.length}',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.accentGreen,
                )),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderSubtle, width: 1),
          ),
          child: Column(
            children: items.asMap().entries.map((entry) {
              final item = entry.value;
              final isLast = entry.key == items.length - 1;

              return Padding(
                padding: EdgeInsets.only(bottom: isLast ? 0 : 10),
                child: Row(
                  children: [
                    GestureDetector(
                      onTap: () {
                        final eventId = tripContext?.curatedEventId;
                        if (eventId != null && onTogglePrepItem != null) {
                          onTogglePrepItem!(eventId, item.key, !item.done);
                        }
                      },
                      child: Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          color: item.done
                              ? AppColors.accentGreen
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(6),
                          border: item.done
                              ? null
                              : Border.all(color: AppColors.error, width: 1.5),
                        ),
                        child: item.done
                            ? const Icon(Icons.check,
                                size: 14, color: Colors.white)
                            : null,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(item.text,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight:
                                item.done ? FontWeight.w400 : FontWeight.w600,
                            color: item.done
                                ? AppColors.textSecondary
                                : AppColors.error,
                            decoration:
                                item.done ? TextDecoration.lineThrough : null,
                          )),
                    ),
                    if (!item.done && item.actionLabel != null)
                      GestureDetector(
                        onTap: () {
                          final eventId = tripContext?.curatedEventId;
                          if (eventId != null && onTogglePrepItem != null) {
                            onTogglePrepItem!(eventId, item.key, true);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppColors.accentGreen,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(item.actionLabel!,
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              )),
                        ),
                      ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Budget Summary
  // ---------------------------------------------------------------------------

  Widget _buildBudgetSummaryCard() {
    final budget = trip.budget!;
    final spent = trip.actualExpense;
    final remaining = budget - spent;
    final percentage = budget > 0 ? (spent / budget).clamp(0.0, 1.5) : 0.0;
    final isOver = remaining < 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.account_balance_wallet_outlined,
                size: 14, color: AppColors.accentGreen),
            SizedBox(width: 6),
            Text('预算概览',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                  letterSpacing: 0.5,
                )),
          ],
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderSubtle, width: 1),
          ),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                      child: _budgetColumn(
                          '总预算',
                          '\u00A5${budget.toStringAsFixed(0)}',
                          AppColors.textPrimary)),
                  Container(
                      width: 1, height: 32, color: AppColors.borderSubtle),
                  const SizedBox(width: 16),
                  Expanded(
                      child: _budgetColumn(
                          '已支出',
                          '\u00A5${spent.toStringAsFixed(0)}',
                          isOver ? AppColors.error : AppColors.accentGreen)),
                  Expanded(
                      child: _budgetColumn(
                          isOver ? '超支' : '剩余',
                          '\u00A5${remaining.abs().toStringAsFixed(0)}',
                          isOver ? AppColors.error : AppColors.textSecondary)),
                ],
              ),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: LinearProgressIndicator(
                  value: percentage,
                  minHeight: 6,
                  backgroundColor: AppColors.bgMuted,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    isOver ? AppColors.error : AppColors.accentGreen,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  '${(percentage * 100).toStringAsFixed(0)}%',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: isOver ? AppColors.error : AppColors.accentGreen,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _budgetColumn(String label, String value, Color valueColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style:
                const TextStyle(fontSize: 11, color: AppColors.textTertiary)),
        const SizedBox(height: 2),
        Text(value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: valueColor,
            )),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // CTA Section
  // ---------------------------------------------------------------------------

  Widget _buildCtaSection() {
    final undoneItems = _prepItems.where((item) => !item.done).toList();

    return Column(
      children: [
        if (undoneItems.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GestureDetector(
              onTap: onChatContinue,
              child: Container(
                width: double.infinity,
                height: 48,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    colors: [Color(0xFF2D7A46), Color(0xFF3D8A5A)],
                  ),
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF3D8A5A).withValues(alpha: 0.25),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.arrow_forward_rounded,
                        size: 18, color: Colors.white),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        undoneItems.first.actionLabel != null
                            ? '${undoneItems.first.text} \u00B7 ${undoneItems.first.actionLabel}'
                            : undoneItems.first.text,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        GestureDetector(
          onTap: onChatContinue,
          child: Container(
            width: double.infinity,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.borderSubtle, width: 1),
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.chat_bubble_outline,
                    size: 16, color: AppColors.textSecondary),
                SizedBox(width: 8),
                Text('在对话中继续',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textSecondary,
                    )),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // Detail sheets
  // ---------------------------------------------------------------------------

  void _showSideActivityDetail(
    BuildContext context,
    SideActivityModel item,
    Color accentColor,
  ) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        margin: const EdgeInsets.only(top: 120),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              margin: const EdgeInsets.only(top: 12),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Type badge
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: accentColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _sideActivityIcon(item.targetType),
                          size: 14,
                          color: accentColor,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _sideActivityTypeLabel(item.targetType),
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: accentColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  // Title
                  Text(
                    item.title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      height: 1.3,
                    ),
                  ),
                  if (item.reason != null && item.reason!.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      item.reason!,
                      style: const TextStyle(
                        fontSize: 15,
                        color: AppColors.textSecondary,
                        height: 1.6,
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  // Priority badge
                  Row(
                    children: [
                      const Icon(Icons.flag_outlined,
                          size: 14, color: AppColors.textTertiary),
                      const SizedBox(width: 6),
                      Text(
                        _priorityLabel(item.priority),
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _sideActivityTypeLabel(String targetType) {
    switch (targetType) {
      case 'person':
        return '联系人';
      case 'task':
        return '待办';
      case 'place':
        return '地点';
      case 'date':
        return '日期';
      case 'memory':
        return '记忆';
      default:
        return '关联';
    }
  }

  String _priorityLabel(String priority) {
    switch (priority) {
      case 'high':
        return '强烈推荐';
      case 'medium':
        return '顺路可做';
      case 'low':
        return '可选';
      default:
        return '建议';
    }
  }

  void _showInsightDetail(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        margin: const EdgeInsets.only(top: 120),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              margin: const EdgeInsets.only(top: 12),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F5ED),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome,
                            size: 14, color: Color(0xFF2D7A46)),
                        SizedBox(width: 4),
                        Text(
                          'AI 智能提醒',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF2D7A46),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    '${trip.destination} · ${trip.tripTypeName}',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    tripContext!.insightText!,
                    style: const TextStyle(
                      fontSize: 15,
                      color: AppColors.textSecondary,
                      height: 1.6,
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
}
