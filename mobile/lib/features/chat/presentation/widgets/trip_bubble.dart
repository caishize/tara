import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/chat_message.dart';
import 'card_quick_actions.dart';
import 'chat_bubble.dart' show buildQuickActionsRow;
import 'expandable_content_section.dart';
import 'message_action_bar.dart';

/// A chat bubble widget that displays trip plans as structured cards.
///
/// Handles two rendering modes:
/// - **Multi-trip list**: When query_trips returns multiple trips, each trip
///   is shown as a compact tappable card with destination, dates, and status.
/// - **Single-trip detail**: When there's one trip (or a trip_itinerary),
///   shows the enriched view with itinerary, people, and tasks.
class TripBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)?
      onFeedback;
  final Future<String?> Function(
      String messageId, Map<String, dynamic> planData)? onConfirmPlan;
  final void Function(QuickAction action)? onQuickAction;

  const TripBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onConfirmPlan,
    this.onQuickAction,
  });

  @override
  State<TripBubble> createState() => _TripBubbleState();
}

class _TripBubbleState extends State<TripBubble> {
  bool _detailsExpanded = false;
  bool _isConfirming = false;
  String? _confirmedPlanId;

  ChatMessage get message => widget.message;

  // -----------------------------------------------------------------------
  // Data helpers
  // -----------------------------------------------------------------------

  /// Extract the raw trips list from message data.
  List<Map<String, dynamic>> get _trips {
    final raw = message.data?['trips'];
    if (raw is! List) return [];
    return raw.whereType<Map<String, dynamic>>().toList();
  }

  /// Whether this is a multi-trip query result (>1 trip).
  bool get _isMultiTrip => _trips.length > 1;

  /// Returns the plan ID for the primary (or only) trip.
  String? get _planId {
    final direct = _confirmedPlanId ??
        (message.data?['plan_id'] as String?) ??
        (message.data?['trip_id'] as String?);
    if (direct != null) return direct;
    final trips = _trips;
    if (trips.isNotEmpty) {
      return trips.first['id'] as String?;
    }
    return null;
  }

  bool get _isConfirmed => _planId != null;

  /// Extract a non-empty destination from a data map.
  static String _extractDestination(Map<String, dynamic> data) {
    final tripName = (data['trip_name'] as String? ?? '').trim();
    if (tripName.isNotEmpty) return tripName;
    final title = (data['title'] as String? ?? '').trim();
    if (title.isNotEmpty) return title;
    final raw = (data['destination'] as String? ?? '').trim();
    if (raw.isNotEmpty) return raw;
    final location = (data['location'] as String? ?? '').trim();
    if (location.isNotEmpty) return location;
    return '旅行计划';
  }

  /// Resolve the effective data map for single-trip rendering.
  Map<String, dynamic> _resolveData() {
    final raw = message.data ?? {};
    if (raw.containsKey('destination') &&
        (raw['destination'] as String? ?? '').isNotEmpty) {
      return raw;
    }
    final trips = _trips;
    if (trips.isNotEmpty) {
      final first = trips.first;
      return {
        ...raw,
        'trip_name': first['title'] ?? first['trip_name'] ?? '',
        'title': first['title'] ?? first['trip_name'] ?? '',
        'destination':
            first['location'] ?? first['destination'] ?? first['title'] ?? '',
        'trip_id': first['id'],
        'start_date': first['start_date'],
        'end_date': first['end_date'],
        'status': first['status'],
      };
    }
    return raw;
  }

  // -----------------------------------------------------------------------
  // Build
  // -----------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 8),
          Flexible(
            child: _isMultiTrip
                ? _buildMultiTripView(context)
                : _buildSingleTripView(context),
          ),
        ],
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Multi-trip view (list of trip cards)
  // -----------------------------------------------------------------------

  Widget _buildMultiTripView(BuildContext context) {
    final trips = _trips;
    final totalCount = (message.data?['total_count'] as int?) ?? trips.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header
        _buildMultiTripHeader(context, totalCount),
        const SizedBox(height: 8),
        // AI analysis
        if (message.content.isNotEmpty && message.content.length > 20)
          ExpandableContentSection(content: message.content),
        // Trip cards
        ...trips.take(5).map((trip) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _buildTripCard(context, trip),
            )),
        if (trips.length > 5)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              '还有 ${trips.length - 5} 个行程...',
              style: AppTextStyles.caption.copyWith(
                color: Theme.of(context)
                    .extension<AppColorsExtension>()!
                    .textTertiary,
              ),
            ),
          ),
        ..._buildQuickActionsSection(),
        const SizedBox(height: 4),
        _buildMessageActionBar(),
      ],
    );
  }

  Widget _buildMultiTripHeader(BuildContext context, int totalCount) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF2196F3), Color(0xFF00BCD4)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(10),
            ),
            child:
                const Icon(Icons.flight_takeoff, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '旅行计划',
                  style: AppTextStyles.subtitle2.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  '共 $totalCount 个行程',
                  style: AppTextStyles.caption.copyWith(
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTripCard(BuildContext context, Map<String, dynamic> trip) {
    final tripId = trip['id'] as String?;
    final destination = _extractDestination(trip);
    final status = trip['status'] as String? ?? '';
    final startDate = trip['start_date'] as String?;
    final endDate = trip['end_date'] as String?;
    final description = trip['description'] as String?;
    final dateRange = _formatDateRange(startDate, endDate);
    final statusInfo = _getStatusInfo(status);

    return GestureDetector(
      onTap:
          tripId != null ? () => context.push(Routes.tripDetail(tripId)) : null,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        decoration: BoxDecoration(
          color:
              Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(
                  alpha: 0.04 *
                      Theme.of(context)
                          .extension<AppColorsExtension>()!
                          .shadowOpacity),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              // Status indicator dot
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: statusInfo.color,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              // Trip info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            destination,
                            style: AppTextStyles.bodyText2.copyWith(
                              fontWeight: FontWeight.w600,
                              color: Theme.of(context).colorScheme.onSurface,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: statusInfo.color.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            statusInfo.label,
                            style: AppTextStyles.overline.copyWith(
                              color: statusInfo.color,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (dateRange.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Icon(Icons.calendar_today,
                              size: 12,
                              color: Theme.of(context)
                                  .extension<AppColorsExtension>()!
                                  .textTertiary),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              dateRange,
                              style: AppTextStyles.overline.copyWith(
                                color: Theme.of(context)
                                    .extension<AppColorsExtension>()!
                                    .textTertiary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                    if (description != null && description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        description,
                        style: AppTextStyles.caption.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              if (tripId != null) ...[
                const SizedBox(width: 4),
                Icon(Icons.chevron_right,
                    size: 20,
                    color: Theme.of(context)
                        .extension<AppColorsExtension>()!
                        .textTertiary),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Single-trip view (enriched detail)
  // -----------------------------------------------------------------------

  Widget _buildSingleTripView(BuildContext context) {
    final data = _resolveData();
    final destination = _extractDestination(data);
    final durationDays =
        (data['duration_days'] as int?) ?? (data['days_saved'] as int?) ?? 0;
    final style = data['style'] as String? ?? '';
    final itinerary = (data['itinerary'] as List<dynamic>?) ?? [];
    final peopleToMeet = (data['people_to_meet'] as List<dynamic>?) ?? [];
    final tasks = (data['tasks'] as List<dynamic>?) ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeaderCard(context, destination, durationDays, style),
        const SizedBox(height: 8),
        if (message.content.isNotEmpty && message.content.length > 20)
          ExpandableContentSection(content: message.content),
        if (peopleToMeet.isNotEmpty) ...[
          _buildPeopleSection(context, peopleToMeet),
          const SizedBox(height: 8),
        ],
        if (tasks.isNotEmpty) ...[
          _buildTasksSection(context, tasks),
          const SizedBox(height: 8),
        ],
        if (itinerary.isNotEmpty) _buildItinerarySection(context, itinerary),
        const SizedBox(height: 8),
        if (_isConfirmed)
          _buildViewMoreButton(context, _planId!, destination)
        else
          _buildConfirmButton(context, data),
        ..._buildQuickActionsSection(),
        const SizedBox(height: 4),
        _buildMessageActionBar(),
      ],
    );
  }

  // -----------------------------------------------------------------------
  // Single-trip sub-widgets
  // -----------------------------------------------------------------------

  Widget _buildAvatar() {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Icon(Icons.auto_awesome, color: Colors.white, size: 18),
    );
  }

  Widget _buildHeaderCard(
    BuildContext context,
    String destination,
    int durationDays,
    String style,
  ) {
    final styleEmoji = _getStyleEmoji(style);
    final subtitle = [
      if (durationDays > 0) '$durationDays天行程',
      if (style.isNotEmpty) _getStyleLabel(style),
    ].join(' · ');

    return GestureDetector(
      onTap: _planId != null
          ? () => context.push(Routes.tripDetail(_planId!))
          : null,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF2196F3), Color(0xFF00BCD4)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Center(
                child: Text(styleEmoji, style: const TextStyle(fontSize: 22)),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    destination,
                    style: AppTextStyles.subtitle2.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (subtitle.isNotEmpty)
                    Text(
                      subtitle,
                      style: AppTextStyles.caption.copyWith(
                        color: Colors.white.withValues(alpha: 0.8),
                      ),
                    ),
                ],
              ),
            ),
            if (_planId != null)
              const Icon(Icons.chevron_right, color: Colors.white70, size: 22)
            else
              const Icon(Icons.flight_takeoff, color: Colors.white, size: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildPeopleSection(BuildContext context, List<dynamic> people) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.people, size: 16, color: Colors.orange.shade700),
              const SizedBox(width: 6),
              Text(
                '可以约见的朋友',
                style: AppTextStyles.caption.copyWith(
                  color: Colors.orange.shade700,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...people.take(3).map((person) {
            final name = person is Map
                ? (person['name'] ?? person.toString())
                : person.toString();
            final note = person is Map ? (person['note'] as String?) : null;
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: Colors.orange.shade400,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      note != null ? '$name ($note)' : name,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildTasksSection(BuildContext context, List<dynamic> tasks) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber, size: 16, color: Colors.red.shade700),
              const SizedBox(width: 6),
              Text(
                '行前提醒',
                style: AppTextStyles.caption.copyWith(
                  color: Colors.red.shade700,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...tasks.take(3).map((task) {
            final text = task is Map
                ? (task['title'] ?? task.toString())
                : task.toString();
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  Icon(Icons.check_box_outline_blank,
                      size: 14, color: Colors.red.shade400),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      text,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildItinerarySection(BuildContext context, List<dynamic> itinerary) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      decoration: BoxDecoration(
        color:
            Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(
                alpha: 0.05 *
                    Theme.of(context)
                        .extension<AppColorsExtension>()!
                        .shadowOpacity),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _detailsExpanded = !_detailsExpanded),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.calendar_today,
                      size: 16, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '每日行程 (${itinerary.length}天)',
                      style: AppTextStyles.subtitle2.copyWith(
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                  ),
                  Icon(
                    _detailsExpanded ? Icons.expand_less : Icons.expand_more,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: Container(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Column(
                children: itinerary.asMap().entries.map((entry) {
                  final day = entry.key + 1;
                  final dayData = entry.value as Map<String, dynamic>?;
                  final title = dayData?['title'] ?? '第$day天';
                  final activities =
                      dayData?['activities'] as List<dynamic>? ?? [];

                  return Container(
                    margin: const EdgeInsets.only(top: 8),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Theme.of(context).scaffoldBackgroundColor,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '第$day天: $title',
                          style: AppTextStyles.caption.copyWith(
                            color: Theme.of(context).colorScheme.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (activities.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          ...activities.take(3).map((act) => Padding(
                                padding: const EdgeInsets.only(top: 2),
                                child: Text(
                                  '• ${act.toString()}',
                                  style: AppTextStyles.caption.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                              )),
                        ],
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
            crossFadeState: _detailsExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }

  Widget _buildViewMoreButton(
      BuildContext context, String planId, String destination) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () => context.push(Routes.tripDetail(planId)),
              icon: const Icon(Icons.map, size: 16),
              label: Text('查看$destination完整行程'),
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF2196F3),
                side: BorderSide(
                    color: const Color(0xFF2196F3).withValues(alpha: 0.3)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              ),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: () => context.push('/timeline'),
            icon: const Icon(Icons.calendar_today, size: 16),
            label: const Text('查看日程'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.green,
              side: BorderSide(color: Colors.green.withValues(alpha: 0.3)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfirmButton(
      BuildContext context, Map<String, dynamic> planData) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: ElevatedButton.icon(
        onPressed: _isConfirming ? null : () => _handleConfirmPlan(planData),
        icon: _isConfirming
            ? const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Icon(Icons.check_circle_outline, size: 18),
        label: Text(_isConfirming ? '正在添加...' : '确认并加入日程'),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF4CAF50),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          elevation: 2,
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Shared widgets & actions
  // -----------------------------------------------------------------------

  List<Widget> _buildQuickActionsSection() {
    final intentKey =
        message.intent == 'plan_smart_trip' ? 'plan_smart_trip' : 'trip_itinerary';
    final actions = resolveQuickActions(message, intentKey);
    if (actions.isEmpty) return const [];
    return [
      Padding(
        padding: const EdgeInsets.only(top: 8),
        child: buildQuickActionsRow(actions, onTap: widget.onQuickAction),
      ),
    ];
  }

  Widget _buildMessageActionBar() {
    return MessageActionBar(
      createdAt: message.createdAt,
      config: MessageActionBarConfig(
        showCopy: true,
        showRegenerate: true,
        showFeedback: true,
        onCopy: () => _copyPlan(context),
        onRegenerate: widget.onRegenerate != null
            ? () => widget.onRegenerate!.call(message.id)
            : null,
        onFeedback: (isLike, reason) =>
            widget.onFeedback?.call(message.id, isLike, reason),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------

  Future<void> _handleConfirmPlan(Map<String, dynamic> planData) async {
    if (widget.onConfirmPlan == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.info_outline, color: Colors.white, size: 18),
              SizedBox(width: 8),
              Text('确认功能暂未启用'),
            ],
          ),
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          duration: const Duration(seconds: 2),
          margin: const EdgeInsets.all(16),
        ),
      );
      return;
    }

    HapticFeedback.mediumImpact();
    setState(() => _isConfirming = true);

    try {
      final newPlanId = await widget.onConfirmPlan!(message.id, planData);

      if (newPlanId != null && mounted) {
        setState(() {
          _confirmedPlanId = newPlanId;
          _isConfirming = false;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.check_circle, color: Colors.white, size: 18),
                SizedBox(width: 8),
                Expanded(child: Text('行程已添加到日程')),
              ],
            ),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            duration: const Duration(seconds: 3),
            margin: const EdgeInsets.all(16),
            action: SnackBarAction(
              label: '查看',
              textColor: Colors.white,
              onPressed: () => context.push('/timeline'),
            ),
          ),
        );
      } else if (mounted) {
        setState(() => _isConfirming = false);
        _showErrorSnackBar('添加失败，请重试');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isConfirming = false);
        _showErrorSnackBar('添加失败: $e');
      }
    }
  }

  void _showErrorSnackBar(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(msg)),
          ],
        ),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 3),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  void _copyPlan(BuildContext context) {
    HapticFeedback.lightImpact();

    if (message.content.isNotEmpty && message.content.length > 20) {
      Clipboard.setData(ClipboardData(text: message.content));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Row(
            children: [
              Icon(Icons.check_circle, color: Colors.white, size: 18),
              SizedBox(width: 8),
              Text('完整分析已复制'),
            ],
          ),
          behavior: SnackBarBehavior.floating,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          duration: const Duration(seconds: 2),
          margin: const EdgeInsets.all(16),
        ),
      );
      return;
    }

    // Build text summary from trips or single plan
    final data = message.data ?? {};
    final trips = _trips;
    final buffer = StringBuffer();

    if (trips.length > 1) {
      buffer.writeln('旅行计划 (${trips.length}个行程)\n');
      for (final trip in trips) {
        final dest = _extractDestination(trip);
        final dateRange = _formatDateRange(
          trip['start_date'] as String?,
          trip['end_date'] as String?,
        );
        buffer.writeln('• $dest${dateRange.isNotEmpty ? " ($dateRange)" : ""}');
      }
    } else {
      final destination = _extractDestination(data);
      final durationDays = data['duration_days'] as int? ?? 0;
      buffer.writeln('$destination $durationDays天行程规划\n');
      final peopleToMeet = (data['people_to_meet'] as List<dynamic>?) ?? [];
      if (peopleToMeet.isNotEmpty) {
        buffer.writeln('可约见的朋友:');
        for (final person in peopleToMeet) {
          final name = person is Map
              ? (person['name'] ?? person.toString())
              : person.toString();
          buffer.writeln('  - $name');
        }
        buffer.writeln();
      }
      final taskList = (data['tasks'] as List<dynamic>?) ?? [];
      if (taskList.isNotEmpty) {
        buffer.writeln('行前提醒:');
        for (final task in taskList) {
          final text = task is Map
              ? (task['title'] ?? task.toString())
              : task.toString();
          buffer.writeln('  - $text');
        }
      }
    }

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle, color: Colors.white, size: 18),
            SizedBox(width: 8),
            Text('行程已复制'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Formatting helpers
  // -----------------------------------------------------------------------

  String _formatDateRange(String? startDate, String? endDate) {
    if (startDate == null) return '';
    try {
      final start = DateTime.parse(startDate);
      final startStr = '${start.month}月${start.day}日';
      if (endDate == null) return startStr;
      final end = DateTime.parse(endDate);
      final days = end.difference(start).inDays + 1;
      return '$startStr - ${end.month}月${end.day}日 (${days}天)';
    } catch (_) {
      return '';
    }
  }

  ({Color color, String label}) _getStatusInfo(String status) {
    switch (status) {
      case 'planning':
        return (color: Colors.orange, label: '规划中');
      case 'confirmed':
        return (color: const Color(0xFF2196F3), label: '已确认');
      case 'in_progress':
        return (color: Colors.green, label: '进行中');
      case 'completed':
        return (
          color:
              Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
          label: '已完成'
        );
      case 'cancelled':
        return (color: Colors.red, label: '已取消');
      default:
        return (
          color:
              Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
          label: '未知'
        );
    }
  }

  String _getStyleEmoji(String style) {
    switch (style.toLowerCase()) {
      case 'cultural':
        return '🏛️';
      case 'relaxing':
        return '🏖️';
      case 'adventure':
        return '🏔️';
      case 'food':
        return '🍜';
      case 'shopping':
        return '🛍️';
      case 'business':
        return '💼';
      default:
        return '✈️';
    }
  }

  String _getStyleLabel(String style) {
    switch (style.toLowerCase()) {
      case 'cultural':
        return '文化游';
      case 'relaxing':
        return '休闲游';
      case 'adventure':
        return '探险游';
      case 'food':
        return '美食游';
      case 'shopping':
        return '购物游';
      case 'business':
        return '商务行';
      default:
        return style;
    }
  }
}
