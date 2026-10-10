import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import 'shimmer_container.dart';

/// Shimmer loading skeleton that mirrors [InsightCard] spatial layout.
///
/// Renders a placeholder with accent bar, header, title, content lines,
/// and action chip placeholders — all animated with a horizontal shimmer.
///
/// PLAN-006: Refactored to use [ShimmerContainer] as shared shimmer base,
/// ensuring identical shimmer timing/colors across InsightCardSkeleton
/// and MemoryLaneSkeleton.
class InsightCardSkeleton extends StatelessWidget {
  const InsightCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final baseColor = ext?.shimmerBase ?? AppColors.shimmerBase;

    return ShimmerContainer(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: baseColor.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: baseColor.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left accent bar placeholder
            Container(
              width: 4,
              height: 120,
              decoration: BoxDecoration(
                color: baseColor,
                borderRadius: const BorderRadius.horizontal(
                  left: Radius.circular(16),
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header line (40% width)
                    _SkeletonLine(
                      width: 0.4,
                      height: 12,
                      color: baseColor,
                    ),
                    const SizedBox(height: 10),
                    // Title line (70% width)
                    _SkeletonLine(
                      width: 0.7,
                      height: 16,
                      color: baseColor,
                    ),
                    const SizedBox(height: 8),
                    // Content lines (varying widths)
                    _SkeletonLine(
                      width: 0.95,
                      height: 12,
                      color: baseColor,
                    ),
                    const SizedBox(height: 6),
                    _SkeletonLine(
                      width: 0.80,
                      height: 12,
                      color: baseColor,
                    ),
                    const SizedBox(height: 6),
                    _SkeletonLine(
                      width: 0.55,
                      height: 12,
                      color: baseColor,
                    ),
                    const SizedBox(height: 14),
                    // Action chip placeholders
                    Row(
                      children: [
                        _SkeletonChip(color: baseColor),
                        const SizedBox(width: 8),
                        _SkeletonChip(color: baseColor),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A single placeholder line with fractional width.
class _SkeletonLine extends StatelessWidget {
  final double width;
  final double height;
  final Color color;

  const _SkeletonLine({
    required this.width,
    required this.height,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: width,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

/// A placeholder chip (rounded rectangle).
class _SkeletonChip extends StatelessWidget {
  final Color color;

  const _SkeletonChip({required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 72,
      height: 32,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
      ),
    );
  }
}
