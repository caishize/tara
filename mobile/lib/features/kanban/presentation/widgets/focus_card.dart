import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/kanban_models.dart';

/// Compact focus card for "本周重点" horizontal scroll.
/// 152×110, vertical layout: icon → title → subtitle → status badge.
class FocusCard extends StatelessWidget {
  final KanbanEventModel event;
  final VoidCallback? onTap;

  const FocusCard({
    super.key,
    required this.event,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final typeColor = Color(event.eventType?.colorValue ?? 0xFF78909C);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 152,
        height: 110,
        margin: const EdgeInsets.only(right: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderSubtle, width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon
            Text(
              event.eventType?.icon ?? '',
              style: const TextStyle(fontSize: 20),
            ),
            const SizedBox(height: 6),
            // Title
            Text(
              event.title,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            // Subtitle (date or location)
            Text(
              _subtitle,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: AppColors.textTertiary,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const Spacer(),
            // Status badge
            _buildStatusBadge(typeColor),
          ],
        ),
      ),
    );
  }

  String get _subtitle {
    if (event.startTime != null) {
      return DateFormat('M月d日 EEEE', 'zh_CN')
          .format(event.startTime!.toLocal());
    }
    return event.location ?? '';
  }

  Widget _buildStatusBadge(Color typeColor) {
    // Life-context badges: show what matters, not just status
    if (event.hasPendingPrep) {
      final pending = event.prepTotalCount - event.prepDoneCount;
      return _badge(
        '$pending\u9879\u5f85\u5907',
        AppColors.alertOrange,
        AppColors.alertOrangeLight,
      );
    }

    if (event.isFocusEvent) {
      return _badge(
        '\u91CD\u70B9',
        AppColors.accentWarm,
        AppColors.accentWarmLight,
      );
    }

    if (event.status == 'confirmed' || event.allPrepDone) {
      return _badge(
        '\u5DF2\u5B89\u6392',
        AppColors.accentGreen,
        AppColors.accentGreenLight,
      );
    }

    // Show countdown for upcoming events instead of generic "未准备"
    if (event.startTime != null) {
      final eventDate = DateUtils.dateOnly(event.startTime!.toLocal());
      final today = DateUtils.dateOnly(DateTime.now());
      final daysUntil = eventDate.difference(today).inDays;
      final label = _countdownLabel(daysUntil);
      if (label != null) {
        return _badge(
          label,
          AppColors.accentGreen,
          AppColors.accentGreenLight,
        );
      }
    }

    return _badge(
      '\u5F85\u5B89\u6392',
      AppColors.alertOrange,
      AppColors.alertOrangeLight,
    );
  }

  /// Returns a short countdown label for events within 3 days, or null.
  static String? _countdownLabel(int daysUntil) {
    if (daysUntil < 0 || daysUntil > 3) return null;
    switch (daysUntil) {
      case 0:
        return '\u4ECA\u5929';
      case 1:
        return '\u660E\u5929';
      case 2:
        return '\u540E\u5929';
      default:
        return null;
    }
  }

  Widget _badge(String text, Color fg, Color bg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: fg,
        ),
      ),
    );
  }
}
