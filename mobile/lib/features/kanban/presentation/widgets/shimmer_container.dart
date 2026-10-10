import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// Shared shimmer animation wrapper.
///
/// Provides a horizontal shimmer sweep effect for skeleton loading states.
/// Used by [InsightCardSkeleton] and [MemoryLaneSkeleton] to ensure
/// consistent shimmer timing, colors, and animation across both tabs.
///
/// Usage:
/// ```dart
/// ShimmerContainer(
///   child: Container(
///     width: 200,
///     height: 100,
///     color: baseColor, // shimmer replaces this color
///   ),
/// )
/// ```
class ShimmerContainer extends StatefulWidget {
  final Widget child;

  /// Duration of one full shimmer sweep. Default 1500ms.
  final Duration duration;

  const ShimmerContainer({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 1500),
  });

  @override
  State<ShimmerContainer> createState() => _ShimmerContainerState();
}

class _ShimmerContainerState extends State<ShimmerContainer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration,
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final baseColor = ext?.shimmerBase ?? AppColors.shimmerBase;
    final highlightColor = baseColor.withValues(alpha: 0.5);

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return ShaderMask(
          shaderCallback: (bounds) {
            return LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [baseColor, highlightColor, baseColor],
              stops: [
                (_controller.value - 0.3).clamp(0.0, 1.0),
                _controller.value,
                (_controller.value + 0.3).clamp(0.0, 1.0),
              ],
            ).createShader(bounds);
          },
          blendMode: BlendMode.srcATop,
          child: child!,
        );
      },
      child: widget.child,
    );
  }
}
