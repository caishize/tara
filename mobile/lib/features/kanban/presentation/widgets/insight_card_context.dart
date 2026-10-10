import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';
import 'insight_card_parts.dart';

/// Context and entity display widgets used by [InsightCard].
///
/// Contains related-event chips, member avatars, trip cards, and
/// source-context chips — all focused on showing linked entity context.

// =============================================================================
// Related event chip — shows type emoji, title, relative time, and location
// =============================================================================

class InsightEventChip extends StatelessWidget {
  final InsightRelatedEventModel event;

  const InsightEventChip({super.key, required this.event});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Related event: ${event.title}',
      child: _buildContent(context),
    );
  }

  Widget _buildContent(BuildContext context) {
    final emoji = _eventTypeEmoji(event.eventType);
    final timeLabel = event.startTime != null
        ? InsightCardParts.formatRelativeTime(event.startTime!)
        : null;
    final chipBg = Theme.of(context).colorScheme.surfaceContainerHighest;

    return Container(
      constraints: const BoxConstraints(maxWidth: 180),
      height: 32,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: chipBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 12)),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              event.title,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
            ),
          ),
          if (timeLabel != null) ...[
            const SizedBox(width: 4),
            Text(
              timeLabel,
              style: const TextStyle(
                fontSize: 10,
                color: AppColors.textTertiary,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
          if (event.location != null) ...[
            const SizedBox(width: 3),
            const Icon(
              Icons.place_outlined,
              size: 10,
              color: AppColors.textTertiary,
            ),
          ],
        ],
      ),
    );
  }

  static String _eventTypeEmoji(String? eventType) {
    switch (eventType) {
      case 'birthday':
        return '\u{1F382}';
      case 'holiday':
        return '\u{1F389}';
      case 'appointment':
        return '\u{1F4C5}';
      case 'travel':
      case 'trip':
        return '\u2708\uFE0F';
      case 'meeting':
        return '\u{1F91D}';
      default:
        return '\u{1F4CC}';
    }
  }
}

// =============================================================================
// Related member avatar — network image + relationship label
// =============================================================================

class InsightMemberAvatar extends StatelessWidget {
  final InsightRelatedMemberModel member;

  const InsightMemberAvatar({super.key, required this.member});

  @override
  Widget build(BuildContext context) {
    final initial =
        member.name.isNotEmpty ? member.name[0].toUpperCase() : '?';
    final hasAvatar = member.avatarUrl != null && member.avatarUrl!.isNotEmpty;

    return Column(
      children: [
        CircleAvatar(
          radius: 14,
          backgroundColor: AppColors.primary.withValues(alpha: 0.15),
          backgroundImage:
              hasAvatar ? NetworkImage(member.avatarUrl!) : null,
          child: hasAvatar
              ? null
              : Text(
                  initial,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppColors.primary,
                  ),
                ),
        ),
        const SizedBox(height: 2),
        Text(
          member.name.length > 4
              ? member.name.substring(0, 4)
              : member.name,
          style: const TextStyle(
            fontSize: 11,
            color: AppColors.textTertiary,
          ),
        ),
        if (member.relationship != null)
          Text(
            member.relationship!,
            style: const TextStyle(
              fontSize: 9,
              color: AppColors.textTertiary,
              fontWeight: FontWeight.w400,
            ),
          ),
      ],
    );
  }
}

// =============================================================================
// Trip card (shown in expanded detail)
// =============================================================================

class InsightTripCard extends StatelessWidget {
  final InsightRelatedTripModel trip;

  const InsightTripCard({super.key, required this.trip});

  @override
  Widget build(BuildContext context) {
    final dateRange = _formatDateRange(trip.startDate, trip.endDate);
    final chipBg = Theme.of(context).colorScheme.surfaceContainerHighest;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: chipBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Row(
        children: [
          const Text('\u2708\uFE0F', style: TextStyle(fontSize: 16)),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  trip.name,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (dateRange != null)
                  Text(
                    dateRange,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
              ],
            ),
          ),
          if (trip.status != null) _TripStatusBadge(status: trip.status!),
        ],
      ),
    );
  }

  static String? _formatDateRange(DateTime? start, DateTime? end) {
    if (start == null) return null;
    final s = '${start.month}/${start.day}';
    if (end == null) return s;
    return '$s \u2013 ${end.month}/${end.day}';
  }
}

class _TripStatusBadge extends StatelessWidget {
  final String status;

  const _TripStatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      'planning' => ('\u8BA1\u5212\u4E2D', AppColors.accentBlue),
      'confirmed' => ('\u5DF2\u786E\u8BA4', AppColors.success),
      'ongoing' => ('\u8FDB\u884C\u4E2D', AppColors.primary),
      'completed' => ('\u5DF2\u5B8C\u6210', AppColors.textTertiary),
      _ => (status, AppColors.textTertiary),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

// =============================================================================
// PLAN-006: One-line action context summary for collapsed cards
// =============================================================================

/// Builds a compact context summary string from an insight's entities.
///
/// Example: "妈妈 · 周六" (first member + first event date).
/// Returns null when no entities are available.
class InsightActionContext {
  const InsightActionContext._();

  static String? buildSummary(InsightFeedItemModel insight) {
    final parts = <String>[];

    // First related member name
    if (insight.relatedMembers.isNotEmpty) {
      parts.add(insight.relatedMembers.first.name);
    }

    // First related event date
    if (insight.relatedEvents.isNotEmpty) {
      final event = insight.relatedEvents.first;
      if (event.startTime != null) {
        parts.add(InsightCardParts.formatRelativeTime(event.startTime!));
      } else {
        parts.add(event.title);
      }
    }

    // Related trip
    if (parts.isEmpty && insight.relatedTrip != null) {
      parts.add(insight.relatedTrip!.name);
    }

    if (parts.isEmpty) return null;
    return parts.join(' \u00B7 ');
  }
}

// =============================================================================
// PLAN-006: Compact context — 1 member avatar + 1 event chip for compact cards
// =============================================================================

/// Small inline avatar shown in compact card context row.
class CompactMemberAvatar extends StatelessWidget {
  final InsightRelatedMemberModel member;

  const CompactMemberAvatar({super.key, required this.member});

  @override
  Widget build(BuildContext context) {
    final initial =
        member.name.isNotEmpty ? member.name[0].toUpperCase() : '?';
    final hasAvatar = member.avatarUrl != null && member.avatarUrl!.isNotEmpty;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircleAvatar(
          radius: 10,
          backgroundColor: AppColors.primary.withValues(alpha: 0.15),
          backgroundImage: hasAvatar ? NetworkImage(member.avatarUrl!) : null,
          child: hasAvatar
              ? null
              : Text(
                  initial,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    color: AppColors.primary,
                  ),
                ),
        ),
        const SizedBox(width: 4),
        Text(
          member.name.length > 3 ? member.name.substring(0, 3) : member.name,
          style: const TextStyle(
            fontSize: 11,
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

/// Compact event chip showing type + days-until for compact card context row.
/// Example: "生日 in 5天"
class CompactEventChip extends StatelessWidget {
  final InsightRelatedEventModel event;
  final Color accentColor;

  const CompactEventChip({
    super.key,
    required this.event,
    required this.accentColor,
  });

  @override
  Widget build(BuildContext context) {
    final emoji = InsightEventChip._eventTypeEmoji(event.eventType);
    final timeLabel = event.startTime != null
        ? InsightCardParts.formatRelativeTime(event.startTime!)
        : null;

    return Container(
      height: 24,
      padding: const EdgeInsets.symmetric(horizontal: 6),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 10)),
          const SizedBox(width: 3),
          Flexible(
            child: Text(
              timeLabel != null
                  ? '${event.title} · $timeLabel'
                  : event.title,
              style: TextStyle(
                fontSize: 11,
                color: accentColor,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
            ),
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// Source context chip — shows where the insight came from
// =============================================================================

class InsightSourceContextChip extends StatelessWidget {
  final String sourceContext;

  const InsightSourceContextChip({super.key, required this.sourceContext});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.bgMuted,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.auto_awesome,
            size: 11,
            color: AppColors.textTertiary,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              sourceContext,
              style: const TextStyle(
                fontSize: 11,
                color: AppColors.textTertiary,
                fontStyle: FontStyle.italic,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
