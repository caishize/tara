import 'package:flutter/material.dart';

/// Trigger widget for loading more chat history when scrolled into view.
///
/// Place this widget at the top of a reversed message list. When [hasMore] is
/// true and [isLoading] is false, [onTrigger] is fired via a post-frame
/// callback once the widget is built (i.e., scrolled into the viewport by
/// ListView.builder's lazy rendering).
///
/// IMPORTANT: When [hasMore] is false, the widget renders as an empty [SizedBox]
/// to prevent infinite triggering.
class HistoryLoadTrigger extends StatefulWidget {
  final bool hasMore;
  final bool isLoading;
  final VoidCallback onTrigger;

  const HistoryLoadTrigger({
    super.key,
    required this.hasMore,
    required this.isLoading,
    required this.onTrigger,
  });

  @override
  State<HistoryLoadTrigger> createState() => _HistoryLoadTriggerState();
}

class _HistoryLoadTriggerState extends State<HistoryLoadTrigger> {
  @override
  void initState() {
    super.initState();
    if (widget.hasMore && !widget.isLoading) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && widget.hasMore && !widget.isLoading) {
          widget.onTrigger();
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.hasMore) return const SizedBox.shrink();

    if (widget.isLoading) {
      return const SizedBox(
        height: 48,
        child: Center(
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    // Invisible sentinel — rendered by ListView.builder when near the top,
    // which fires the post-frame callback in initState.
    return const SizedBox(height: 1);
  }
}
