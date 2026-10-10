import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/future_view_models.dart';

/// Single row within the upcoming events section of the V4 future view.
///
/// Shows a colored dot, event info (emoji + title + subtitle), icon badge,
/// and countdown text.
class FutureUpcomingRow extends StatelessWidget {
  final FutureViewUpcomingModel item;
  final bool isLast;
  final VoidCallback? onTap;

  const FutureUpcomingRow({
    super.key,
    required this.item,
    this.isLast = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dotColor = item.dotColorValue;

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : const Border(
                  bottom: BorderSide(color: AppColors.divider, width: 1),
                ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: dotColor,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (item.emoji.isNotEmpty) ...[
                        Text(
                          item.emoji,
                          style: const TextStyle(fontSize: 14, height: 1.2),
                        ),
                        const SizedBox(width: 6),
                      ],
                      Expanded(
                        child: Text(
                          item.title,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                            height: 1.3,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _buildSubtitle(),
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textTertiary,
                      height: 1.3,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: dotColor.withValues(alpha: 0.07),
                borderRadius: BorderRadius.circular(100),
              ),
              child: Icon(
                _iconForDateType(item.dateType),
                size: 12,
                color: dotColor,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              '${item.daysUntil}天',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: item.daysUntil <= 14
                    ? dotColor
                    : AppColors.textTertiary,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _buildSubtitle() {
    if (item.contextHint.isNotEmpty) {
      return '${item.dateLabel} · ${item.contextHint}';
    }
    return item.dateLabel;
  }

  IconData _iconForDateType(String dateType) {
    switch (dateType) {
      case 'birthday':
        return Icons.cake_outlined;
      case 'anniversary':
        return Icons.favorite_outline;
      case 'holiday':
        return Icons.celebration_outlined;
      case 'meeting':
        return Icons.groups_outlined;
      case 'deadline':
        return Icons.flag_outlined;
      default:
        return Icons.event_outlined;
    }
  }
}
