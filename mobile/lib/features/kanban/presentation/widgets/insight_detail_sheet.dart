import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import '../utils/insight_style.dart';
import 'action_type_registry.dart';
import 'insight_card_context.dart';

/// Bottom sheet showing full insight details with feedback and action support.
///
/// PLAN-003: Migrated from KanbanInsightModel to InsightFeedItemModel.
/// Now shows MORE information than the collapsed card: action chips,
/// related entities, context hints, feedback buttons, and full content.
class InsightDetailSheet extends StatelessWidget {
  final InsightFeedItemModel insight;
  final void Function(String feedbackType) onFeedback;
  final void Function(String actionType, Map<String, dynamic>? actionData)?
      onActionTap;
  final void Function(String eventId)? onEventTap;
  final void Function(String memberId)? onMemberTap;

  const InsightDetailSheet({
    super.key,
    required this.insight,
    required this.onFeedback,
    this.onActionTap,
    this.onEventTap,
    this.onMemberTap,
  });

  /// Show this sheet as a modal bottom sheet.
  static void show(
    BuildContext context, {
    required InsightFeedItemModel insight,
    required void Function(String feedbackType) onFeedback,
    void Function(String actionType, Map<String, dynamic>? actionData)?
        onActionTap,
    void Function(String eventId)? onEventTap,
    void Function(String memberId)? onMemberTap,
  }) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => InsightDetailSheet(
        insight: insight,
        onFeedback: (type) {
          Navigator.of(context).pop();
          onFeedback(type);
        },
        onActionTap: onActionTap != null
            ? (actionType, actionData) {
                Navigator.of(context).pop();
                onActionTap(actionType, actionData);
              }
            : null,
        onEventTap: onEventTap,
        onMemberTap: onMemberTap,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final style = InsightStyle.resolve(
      context: context,
      insightType: insight.insightType,
      urgency: insight.urgency,
      visualWeight: insight.visualWeight,
      priority: insight.priority,
    );

    final colorScheme = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return Container(
      margin: const EdgeInsets.only(top: 80),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: colorScheme.outlineVariant,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Type badge
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: style.bgGradient.first,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          style.emoji,
                          style: const TextStyle(fontSize: 13),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          style.label,
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: style.accentColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  // Title
                  Text(
                    insight.title,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: colorScheme.onSurface,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 8),
                  // Creation date
                  if (insight.createdAt != null)
                    Text(
                      DateFormat('yyyy\u5E74M\u6708d\u65E5 HH:mm')
                          .format(insight.createdAt!.toLocal()),
                      style: TextStyle(
                        fontSize: 12,
                        color: ext?.textTertiary ?? AppColors.textTertiary,
                      ),
                    ),
                  const SizedBox(height: 16),
                  // Full content
                  Text(
                    insight.content,
                    style: TextStyle(
                      fontSize: 15,
                      color: colorScheme.onSurfaceVariant,
                      height: 1.6,
                    ),
                  ),
                  // PLAN-003: Related events (rich context)
                  if (insight.relatedEvents.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: insight.relatedEvents.map((event) {
                        return GestureDetector(
                          onTap: () => onEventTap?.call(event.id),
                          child: InsightEventChip(event: event),
                        );
                      }).toList(),
                    ),
                  ],
                  // PLAN-003: Related members
                  if (insight.relatedMembers.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Row(
                      children: insight.relatedMembers.take(5).map((member) {
                        return Padding(
                          padding: const EdgeInsets.only(right: 10),
                          child: GestureDetector(
                            onTap: () => onMemberTap?.call(member.id),
                            child: InsightMemberAvatar(member: member),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                  // PLAN-003: Related trip
                  if (insight.relatedTrip != null) ...[
                    const SizedBox(height: 12),
                    InsightTripCard(trip: insight.relatedTrip!),
                  ],
                  // PLAN-003: Context hint
                  if (insight.contextHint != null) ...[
                    const SizedBox(height: 12),
                    _buildContextHint(context, insight.contextHint!),
                  ],
                  // PLAN-003: Source context
                  if (insight.sourceContext != null) ...[
                    const SizedBox(height: 8),
                    InsightSourceContextChip(
                      sourceContext: insight.sourceContext!,
                    ),
                  ],
                  // PLAN-003: Action chips (richer than collapsed state)
                  if (insight.actionOptions.isNotEmpty ||
                      insight.actionType != null) ...[
                    const SizedBox(height: 16),
                    _buildActionChips(style),
                  ],
                  const SizedBox(height: 20),
                  // View insight history link
                  GestureDetector(
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push(Routes.insightHistory);
                    },
                    child: Row(
                      children: [
                        Icon(
                          Icons.history,
                          size: 16,
                          color: ext?.insightDefault ?? AppColors.accentGreen,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '\u67E5\u770B\u6D1E\u5BDF\u5386\u53F2',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                            color: ext?.insightDefault ?? AppColors.accentGreen,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Simplified action buttons: primary CTA + defer + subtle "never" link
          Container(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(color: colorScheme.outlineVariant, width: 1),
              ),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    // Primary action (same as card CTA)
                    if (insight.actionOptions.isNotEmpty || insight.actionType != null)
                      Expanded(
                        child: _ActionButton(
                          icon: Icons.play_arrow_outlined,
                          label: insight.actionOptions.isNotEmpty
                              ? insight.actionOptions.first.label
                              : '\u6267\u884C',
                          color: style.accentColor,
                          onTap: () {
                            final actionType = insight.actionOptions.isNotEmpty
                                ? insight.actionOptions.first.actionType
                                : insight.actionType!;
                            onActionTap?.call(actionType, insight.actionData);
                          },
                        ),
                      ),
                    if (insight.actionOptions.isNotEmpty || insight.actionType != null)
                      const SizedBox(width: 10),
                    // Defer
                    Expanded(
                      child: _ActionButton(
                        icon: Icons.schedule_outlined,
                        label: '\u7A0D\u540E\u63D0\u9192',
                        color: ext?.insightObservation ?? const Color(0xFF1976D2),
                        onTap: () => onFeedback('defer'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Destructive preference — intentionally subtle text link
                GestureDetector(
                  onTap: () => _confirmNeverShow(context),
                  child: Text(
                    '\u4E0D\u518D\u63D0\u793A\u6B64\u7C7B',
                    style: TextStyle(
                      fontSize: 12,
                      color: ext?.textTertiary ?? const Color(0xFF757575),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _confirmNeverShow(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('\u786E\u8BA4\u5C4F\u853D'),
        content: const Text('\u5C4F\u853D\u540E\u5C06\u4E0D\u518D\u663E\u793A\u6B64\u7C7B\u6D1E\u5BDF\uFF0C\u786E\u5B9A\u5417\uFF1F'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('\u53D6\u6D88'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              onFeedback('never');
            },
            child: const Text('\u786E\u5B9A'),
          ),
        ],
      ),
    );
  }

  Widget _buildContextHint(BuildContext context, String hint) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: ext?.chipBackground ?? AppColors.bgMuted,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.lightbulb_outline,
            size: 14,
            color: ext?.textTertiary ?? AppColors.textTertiary,
          ),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              hint,
              style: TextStyle(
                fontSize: 13,
                color: ext?.textTertiary ?? AppColors.textSecondary,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionChips(InsightStyle style) {
    final chips = insight.actionOptions.isNotEmpty
        ? insight.actionOptions
        : (insight.actionType != null
            ? [ActionOptionModel(actionType: insight.actionType!, label: insight.actionType!)]
            : <ActionOptionModel>[]);

    if (chips.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: chips.map((option) {
        final def = ActionTypeRegistry.lookup(option.actionType);
        final label = option.label.isNotEmpty ? option.label : def.label;
        return GestureDetector(
          onTap: () => onActionTap?.call(option.actionType, insight.actionData),
          child: Container(
            height: 36,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: style.accentColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: style.accentColor.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(def.icon, size: 14, color: style.accentColor),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: style.accentColor,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minWidth: 90),
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
