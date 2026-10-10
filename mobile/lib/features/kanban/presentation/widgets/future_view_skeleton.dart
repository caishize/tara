import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import 'shimmer_container.dart';

/// Loading skeleton for V4 future timeline view.
///
/// Shows placeholder shapes for 1 trip card, 2 suggestion cards,
/// 3 upcoming rows, and 2 family member rows, all wrapped in shimmer.
class FutureViewSkeleton extends StatelessWidget {
  const FutureViewSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final baseColor = ext?.shimmerBase ?? AppColors.shimmerBase;

    return ShimmerContainer(
      child: SingleChildScrollView(
        physics: const NeverScrollableScrollPhysics(),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 16),
            _SectionHeaderSkeleton(color: baseColor),
            const SizedBox(height: 12),
            _TripCardSkeleton(color: baseColor),
            const SizedBox(height: 24),
            _SectionHeaderSkeleton(color: baseColor),
            const SizedBox(height: 12),
            _SuggestionCardSkeleton(color: baseColor),
            const SizedBox(height: 8),
            _SuggestionCardSkeleton(color: baseColor),
            const SizedBox(height: 24),
            _SectionHeaderSkeleton(color: baseColor),
            const SizedBox(height: 12),
            _UpcomingCardSkeleton(color: baseColor),
            const SizedBox(height: 24),
            _SectionHeaderSkeleton(color: baseColor),
            const SizedBox(height: 12),
            _MemberRowSkeleton(color: baseColor),
            const SizedBox(height: 12),
            _MemberRowSkeleton(color: baseColor),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionHeaderSkeleton extends StatelessWidget {
  final Color color;
  const _SectionHeaderSkeleton({required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 18, height: 18,
          decoration: BoxDecoration(
            color: color, borderRadius: BorderRadius.circular(4),
          ),
        ),
        const SizedBox(width: 6),
        Container(
          width: 80, height: 16,
          decoration: BoxDecoration(
            color: color, borderRadius: BorderRadius.circular(4),
          ),
        ),
      ],
    );
  }
}

class _TripCardSkeleton extends StatelessWidget {
  final Color color;
  const _TripCardSkeleton({required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header area
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _rect(color, 140, 18),
                    const Spacer(),
                    _rect(color, 48, 22, radius: 100),
                  ],
                ),
                const SizedBox(height: 10),
                _rect(color, 120, 12),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _rect(color, 60, 16, radius: 100),
                    const SizedBox(width: 4),
                    _rect(color, 60, 16, radius: 100),
                  ],
                ),
              ],
            ),
          ),
          // Task rows
          for (int i = 0; i < 3; i++) ...[
            Container(
              height: 1,
              color: color.withValues(alpha: 0.2),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  Container(
                    width: 20, height: 20,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: color, width: 2),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _rect(color, 120, 14),
                        const SizedBox(height: 4),
                        _rect(color, 80, 10),
                      ],
                    ),
                  ),
                  _rect(color, 48, 24, radius: 8),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SuggestionCardSkeleton extends StatelessWidget {
  final Color color;
  const _SuggestionCardSkeleton({required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _rect(color, 60, 12),
                const SizedBox(height: 6),
                _rect(color, 160, 14),
                const SizedBox(height: 4),
                _rect(color, 120, 10),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            children: [
              _rect(color, 48, 24, radius: 8),
              const SizedBox(height: 6),
              _rect(color, 48, 24, radius: 8),
            ],
          ),
        ],
      ),
    );
  }
}

class _UpcomingCardSkeleton extends StatelessWidget {
  final Color color;
  const _UpcomingCardSkeleton({required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: List.generate(3, (i) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              border: i < 2
                  ? Border(
                      bottom: BorderSide(
                          color: color.withValues(alpha: 0.2)),
                    )
                  : null,
            ),
            child: Row(
              children: [
                Container(
                  width: 10, height: 10,
                  decoration: BoxDecoration(
                    color: color, shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _rect(color, 120, 14),
                      const SizedBox(height: 4),
                      _rect(color, 80, 10),
                    ],
                  ),
                ),
                _rect(color, 28, 18, radius: 100),
                const SizedBox(width: 6),
                _rect(color, 30, 12),
              ],
            ),
          );
        }),
      ),
    );
  }
}

class _MemberRowSkeleton extends StatelessWidget {
  final Color color;
  const _MemberRowSkeleton({required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: color, shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _rect(color, 100, 14),
              const SizedBox(height: 4),
              _rect(color, 140, 10),
            ],
          ),
        ),
        _rect(color, 16, 16, radius: 4),
      ],
    );
  }
}

/// Helper to build a rounded rectangle skeleton block.
Widget _rect(Color color, double width, double height, {double radius = 4}) {
  return Container(
    width: width,
    height: height,
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(radius),
    ),
  );
}
