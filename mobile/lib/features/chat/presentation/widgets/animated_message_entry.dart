import 'package:flutter/material.dart';

/// Wraps a chat bubble with a slide + fade entrance animation.
///
/// - User messages slide in from the right.
/// - AI messages slide in from the left.
/// - Only plays once per message (controlled by [isNew]).
class AnimatedMessageEntry extends StatefulWidget {
  final bool isNew;
  final bool isUser;
  final Widget child;

  const AnimatedMessageEntry({
    super.key,
    required this.isNew,
    required this.isUser,
    required this.child,
  });

  @override
  State<AnimatedMessageEntry> createState() => _AnimatedMessageEntryState();
}

class _AnimatedMessageEntryState extends State<AnimatedMessageEntry>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<Offset> _slideAnimation;
  late final Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );

    final beginOffset = widget.isUser
        ? const Offset(0.3, 0.0)
        : const Offset(-0.3, 0.0);

    _slideAnimation = Tween<Offset>(
      begin: beginOffset,
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    ));

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    ));

    if (widget.isNew) {
      _controller.forward();
    } else {
      _controller.value = 1.0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnimation,
      child: FadeTransition(
        opacity: _fadeAnimation,
        child: widget.child,
      ),
    );
  }
}
