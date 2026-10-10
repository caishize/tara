import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Scrollable Cursor-style progress log container.
///
/// Displays real-time progress messages during tool execution with
/// auto-scrolling to the latest entry.
class ProgressLogContainer extends StatelessWidget {
  final List<String> entries;
  final double maxHeight;

  const ProgressLogContainer({
    super.key,
    required this.entries,
    this.maxHeight = 120,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      constraints: BoxConstraints(maxHeight: maxHeight),
      width: double.infinity,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.12),
        ),
      ),
      child: _ProgressLogListView(entries: entries),
    );
  }
}

/// Auto-scrolling list view for progress log entries.
class _ProgressLogListView extends StatefulWidget {
  final List<String> entries;

  const _ProgressLogListView({required this.entries});

  @override
  State<_ProgressLogListView> createState() => _ProgressLogListViewState();
}

class _ProgressLogListViewState extends State<_ProgressLogListView> {
  final ScrollController _scrollController = ScrollController();

  @override
  void didUpdateWidget(_ProgressLogListView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.entries.length > oldWidget.entries.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 150),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      shrinkWrap: true,
      itemCount: widget.entries.length,
      itemBuilder: (context, index) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 1.5),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '›',
                style: TextStyle(
                  fontSize: 11,
                  fontFamily: 'monospace',
                  color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                  height: 1.4,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  widget.entries[index],
                  style: TextStyle(
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
