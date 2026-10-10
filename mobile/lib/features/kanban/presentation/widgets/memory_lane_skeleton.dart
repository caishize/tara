import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import 'shimmer_container.dart';

/// Shimmer loading skeleton for the memory lane tab.
///
/// Mirrors the spatial layout of the loaded memory lane content:
/// - "那年今日" section with 2 on-this-day skeleton cards
/// - "最近的故事" section with 3 story skeleton cards
///
/// Uses [ShimmerContainer] to share the same shimmer timing and colors
/// as [InsightCardSkeleton], ensuring visual consistency across both tabs.
class MemoryLaneSkeleton extends StatelessWidget {
  const MemoryLaneSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final baseColor = ext?.shimmerBase ?? AppColors.shimmerBase;

    return ShimmerContainer(
      child: CustomScrollView(
        physics: const NeverScrollableScrollPhysics(),
        slivers: [
          // 🌅 那年今日 section skeleton
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Section header skeleton
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
                  child: _SkeletonBar(
                    width: 120,
                    height: 14,
                    color: baseColor,
                  ),
                ),
                // 2 on-this-day skeleton cards
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: _OnThisDaySkeletonCard(baseColor: baseColor),
                ),
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: _OnThisDaySkeletonCard(baseColor: baseColor),
                ),
              ],
            ),
          ),
          // 📖 最近的故事 section skeleton
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Section header skeleton
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
                  child: _SkeletonBar(
                    width: 140,
                    height: 14,
                    color: baseColor,
                  ),
                ),
                // 3 story skeleton cards
                _StorySkeletonCard(baseColor: baseColor),
                const SizedBox(height: 8),
                _StorySkeletonCard(baseColor: baseColor),
                const SizedBox(height: 8),
                _StorySkeletonCard(baseColor: baseColor),
              ],
            ),
          ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
        ],
      ),
    );
  }
}

/// Skeleton card mimicking the OnThisDayCard layout.
class _OnThisDaySkeletonCard extends StatelessWidget {
  final Color baseColor;

  const _OnThisDaySkeletonCard({required this.baseColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: baseColor.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: baseColor.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Year label (e.g., "3年前的今天")
          _SkeletonBar(width: 100, height: 12, color: baseColor),
          const SizedBox(height: 8),
          // Event title
          _SkeletonBar(width: 200, height: 14, color: baseColor),
          const SizedBox(height: 6),
          // Event detail line
          _SkeletonBar(width: 150, height: 11, color: baseColor),
        ],
      ),
    );
  }
}

/// Skeleton card mimicking the StoryCard layout.
class _StorySkeletonCard extends StatelessWidget {
  final Color baseColor;

  const _StorySkeletonCard({required this.baseColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: baseColor.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: baseColor.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Story title
          _SkeletonBar(width: 180, height: 16, color: baseColor),
          const SizedBox(height: 10),
          // Date / location line
          _SkeletonBar(width: 130, height: 12, color: baseColor),
          const SizedBox(height: 8),
          // Summary lines
          _SkeletonBar(width: double.infinity, height: 12, color: baseColor),
          const SizedBox(height: 6),
          _SkeletonBar(width: 220, height: 12, color: baseColor),
        ],
      ),
    );
  }
}

/// A simple rectangular skeleton bar.
class _SkeletonBar extends StatelessWidget {
  final double width;
  final double height;
  final Color color;

  const _SkeletonBar({
    required this.width,
    required this.height,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width.isInfinite ? double.infinity : width,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }
}
