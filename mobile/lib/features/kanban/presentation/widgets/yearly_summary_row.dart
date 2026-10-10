import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/memory_lane.dart';
import 'story_card.dart';

/// Year row for the "更早" section in memory lane.
/// Shows "2025年" + stats meta + expand arrow.
/// When expanded, displays the year's stories below the header.
class YearlySummaryRow extends StatelessWidget {
  final YearlySummary summary;
  final bool isExpanded;
  final VoidCallback? onToggle;
  final ValueChanged<StoryGroup>? onStoryTap;

  const YearlySummaryRow({
    super.key,
    required this.summary,
    this.isExpanded = false,
    this.onToggle,
    this.onStoryTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Header row
        GestureDetector(
          onTap: onToggle,
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${summary.year}\u5E74',
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _buildMeta(),
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ),
                AnimatedRotation(
                  turns: isExpanded ? 0.25 : 0,
                  duration: const Duration(milliseconds: 200),
                  child: const Text(
                    '\u25B8',
                    style: TextStyle(
                      fontSize: 16,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        // Expanded stories
        if (isExpanded && summary.stories.isNotEmpty)
          ...summary.stories.map((story) => StoryCard(
                story: story,
                onTap: onStoryTap != null ? () => onStoryTap!(story) : null,
              )),
      ],
    );
  }

  String _buildMeta() {
    final parts = <String>[];

    if (summary.tripCount > 0) {
      parts.add('${summary.tripCount}\u6B21\u65C5\u884C');
    }

    if (summary.specialDayCount > 0) {
      parts.add('${summary.specialDayCount}\u4E2A\u7EAA\u5FF5\u65E5');
    }

    final memoryCount = summary.eventCount;
    if (memoryCount > 0) {
      parts.add('$memoryCount\u6761\u8BB0\u5FC6');
    }

    if (parts.isEmpty) {
      return '\u5171 ${summary.eventCount} \u4E2A\u4E8B\u4EF6';
    }

    return parts.join(' \u00B7 ');
  }
}
