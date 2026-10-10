import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/insight_feed_models.dart';

/// PLAN-011: AI-generated memory reflection highlights.
///
/// Displays a horizontally scrollable list of AI insight cards at the top
/// of the Memory Lane page. Each card shows a memory_reflection insight
/// with a soft gradient background and italic AI-generated text.
class AiMemoryHighlights extends StatelessWidget {
  final List<InsightFeedItemModel> highlights;

  const AiMemoryHighlights({super.key, required this.highlights});

  @override
  Widget build(BuildContext context) {
    if (highlights.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 10),
          child: Row(
            children: [
              Text(
                '\u2728',
                style: TextStyle(fontSize: 14),
              ),
              SizedBox(width: 6),
              Text(
                'AI \u56DE\u5FC6\u7CBE\u534E',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ),
        SizedBox(
          height: 140,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: highlights.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (context, index) =>
                _HighlightCard(insight: highlights[index]),
          ),
        ),
      ],
    );
  }
}

class _HighlightCard extends StatelessWidget {
  final InsightFeedItemModel insight;

  const _HighlightCard({required this.insight});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      width: 240,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            colorScheme.primaryContainer.withValues(alpha: 0.4),
            colorScheme.tertiaryContainer.withValues(alpha: 0.3),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: colorScheme.primary.withValues(alpha: 0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            insight.title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: colorScheme.onSurface,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),
          // Content — italic AI reflection style
          Expanded(
            child: Text(
              insight.content,
              style: TextStyle(
                fontSize: 12,
                fontStyle: FontStyle.italic,
                color: colorScheme.onSurfaceVariant,
                height: 1.5,
              ),
              maxLines: 4,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // Source context hint
          if (insight.contextHint != null) ...[
            const SizedBox(height: 6),
            Text(
              insight.contextHint!,
              style: TextStyle(
                fontSize: 10,
                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.6),
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }
}
