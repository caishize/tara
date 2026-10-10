import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../domain/entities/memory_lane.dart';

/// Story card for memory lane — flat white card matching design system.
/// Shows emoji + title, date/meta subtitle, and italic quote summary.
class StoryCard extends StatelessWidget {
  final StoryGroup story;
  final VoidCallback? onTap;

  const StoryCard({
    super.key,
    required this.story,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(
          horizontal: AppDimensions.cardMarginH,
          vertical: 5,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: colorScheme.surface,
          borderRadius: BorderRadius.circular(AppDimensions.cardRadiusSmall),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: emoji + title + subtitle
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  story.typeIcon,
                  style: const TextStyle(fontSize: 18),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              story.title,
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: colorScheme.onSurface,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (story.emotionalTag != null) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 1,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.accentWarmLight,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                story.emotionalTag!,
                                style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w500,
                                  color: AppColors.accentWarm,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 1),
                      Text(
                        _buildSubtitle(),
                        style: TextStyle(
                          fontSize: 12,
                          color: colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ],
            ),

            // Summary quote
            if (story.memorySummaries.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                story.memorySummaries.first,
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: colorScheme.onSurfaceVariant,
                  height: 1.4,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _buildSubtitle() {
    final parts = <String>[];

    if (story.startDate != null) {
      parts.add(DateFormat('yyyy\u5E74M\u6708').format(story.startDate!));
    }

    if (story.participantCount > 0) {
      parts.add('${story.participantCount}\u4EBA');
    }

    if (story.durationDays > 1) {
      parts.add('${story.durationDays}\u5929');
    }

    return parts.join(' \u00B7 ');
  }
}
