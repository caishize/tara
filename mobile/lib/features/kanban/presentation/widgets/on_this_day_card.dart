import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../domain/entities/memory_lane.dart';

/// Warm-toned "On This Day" card matching the design system.
/// Flat accentWarmLight background, no gradient.
class OnThisDayCard extends StatelessWidget {
  final List<OnThisDayItem> items;
  final ValueChanged<String>? onDismiss;
  final ValueChanged<OnThisDayItem>? onViewDetail;

  const OnThisDayCard({
    super.key,
    required this.items,
    this.onDismiss,
    this.onViewDetail,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    if (items.length == 1) {
      return _buildCard(items.first);
    }

    // Multiple items: horizontal PageView
    return SizedBox(
      height: 380,
      child: PageView.builder(
        itemCount: items.length,
        controller: PageController(viewportFraction: 0.92),
        itemBuilder: (context, index) {
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _buildCard(items[index]),
          );
        },
      ),
    );
  }

  Widget _buildCard(OnThisDayItem item) {
    return Builder(builder: (context) {
    final colorScheme = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return Container(
      padding: const EdgeInsets.all(AppDimensions.cardPaddingH),
      decoration: BoxDecoration(
        color: ext?.chipBackground ?? AppColors.accentWarmLight,
        borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // "X年前的今天" label
          Row(
            children: [
              Text(
                '${item.yearsAgo}年前的今天',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.accentWarm,
                ),
              ),
              const Spacer(),
              if (onDismiss != null)
                GestureDetector(
                  onTap: () => onDismiss!(item.id),
                  child: Icon(
                    Icons.close,
                    size: 16,
                    color: ext?.textTertiary ?? AppColors.textTertiary,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),

          // Title with type emoji
          Text(
            '${item.typeIcon} ${item.title}',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: colorScheme.onSurface,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),

          // Metadata line
          ..._buildMetadata(item),

          const SizedBox(height: 10),

          // Cover image / placeholder
          _buildCoverImage(item),

          // Memory quotes
          ..._buildQuotes(item),

          const SizedBox(height: 10),

          // CTA button
          SizedBox(
            width: double.infinity,
            height: 36,
            child: ElevatedButton(
              onPressed:
                  onViewDetail != null ? () => onViewDetail!(item) : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accentWarm,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
                elevation: 0,
                padding: EdgeInsets.zero,
              ),
              child: const Text(
                '回顾这次旅行 →',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
    });
  }

  List<Widget> _buildMetadata(OnThisDayItem item) {
    final parts = <String>[];
    if (item.location != null && item.location!.isNotEmpty) {
      parts.add('\u2708\uFE0F ${item.location!}');
    }
    if (item.participantCount > 0) {
      parts.add('\u5168\u5BB6${item.participantCount}\u4EBA');
    }
    if (item.durationDays > 1) {
      final nights = item.durationDays - 1;
      parts.add('${item.durationDays}\u5929$nights\u665A');
    }

    if (parts.isEmpty) return [];

    return [
      const SizedBox(height: 6),
      Builder(builder: (context) {
        final colorScheme = Theme.of(context).colorScheme;
        return Text(
          parts.join(' \u00B7 '),
          style: TextStyle(
            fontSize: 12,
            color: colorScheme.onSurfaceVariant,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        );
      }),
    ];
  }

  Widget _buildCoverImage(OnThisDayItem item) {
    if (item.coverImageUrl != null && item.coverImageUrl!.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(AppDimensions.cardRadiusSmall),
        child: Image.network(
          item.coverImageUrl!,
          height: 120,
          width: double.infinity,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => _buildPlaceholder(item),
        ),
      );
    }
    return _buildPlaceholder(item);
  }

  Widget _buildPlaceholder(OnThisDayItem item) {
    final label = item.location ?? item.title;
    return Container(
      height: 120,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFFD4B5A0),
        borderRadius: BorderRadius.circular(AppDimensions.cardRadiusSmall),
      ),
      alignment: Alignment.center,
      child: Text(
        '\uD83C\uDF05 $label',
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
    );
  }

  List<Widget> _buildQuotes(OnThisDayItem item) {
    if (item.memorySummaries.isEmpty) return [];

    return [
      const SizedBox(height: 8),
      ...item.memorySummaries.take(2).map(
            (quote) => Builder(builder: (context) {
              final colorScheme = Theme.of(context).colorScheme;
              return Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  '\u300C$quote\u300D',
                  style: TextStyle(
                    fontSize: 12,
                    fontStyle: FontStyle.italic,
                    color: colorScheme.onSurfaceVariant,
                    height: 1.4,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }),
          ),
    ];
  }
}
