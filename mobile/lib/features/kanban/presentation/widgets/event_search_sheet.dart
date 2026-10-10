import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/kanban_models.dart';
import '../bloc/kanban_bloc.dart';
import '../bloc/kanban_event.dart';
import '../bloc/kanban_state.dart';
import 'compact_event_row.dart';

/// Bottom sheet for searching family events.
class EventSearchSheet extends StatefulWidget {
  final KanbanBloc kanbanBloc;
  final void Function(KanbanEventModel event)? onEventTap;

  const EventSearchSheet({
    super.key,
    required this.kanbanBloc,
    this.onEventTap,
  });

  static Future<void> show(
    BuildContext context, {
    required KanbanBloc kanbanBloc,
    void Function(KanbanEventModel event)? onEventTap,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => BlocProvider.value(
        value: kanbanBloc,
        child: DraggableScrollableSheet(
          initialChildSize: 0.85,
          maxChildSize: 0.95,
          minChildSize: 0.4,
          builder: (_, scrollController) => EventSearchSheet(
            kanbanBloc: kanbanBloc,
            onEventTap: onEventTap,
          ),
        ),
      ),
    );
  }

  @override
  State<EventSearchSheet> createState() => _EventSearchSheetState();
}

class _EventSearchSheetState extends State<EventSearchSheet> {
  final _searchController = TextEditingController();
  final _focusNode = FocusNode();
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _focusNode.requestFocus();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _focusNode.dispose();
    // Restore kanban view when sheet closes
    widget.kanbanBloc.add(const ClearSearch());
    super.dispose();
  }

  void _onQueryChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (query.trim().isEmpty) {
        widget.kanbanBloc.add(const ClearSearch());
      } else {
        widget.kanbanBloc.add(SearchEvents(query: query.trim()));
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          // Drag handle
          Container(
            margin: const EdgeInsets.only(top: 8),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.divider,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          // Search bar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: TextField(
              controller: _searchController,
              focusNode: _focusNode,
              onChanged: _onQueryChanged,
              decoration: InputDecoration(
                hintText: '搜索家庭事件...',
                hintStyle: const TextStyle(
                  color: AppColors.textTertiary,
                  fontSize: 15,
                ),
                prefixIcon: const Icon(
                  Icons.search,
                  color: AppColors.textSecondary,
                ),
                suffixIcon: ValueListenableBuilder<TextEditingValue>(
                  valueListenable: _searchController,
                  builder: (_, value, __) {
                    if (value.text.isEmpty) return const SizedBox.shrink();
                    return IconButton(
                      icon: const Icon(Icons.close,
                          size: 20, color: AppColors.textSecondary),
                      onPressed: () {
                        _searchController.clear();
                        widget.kanbanBloc.add(const ClearSearch());
                      },
                    );
                  },
                ),
                filled: true,
                fillColor: AppColors.chipBackground,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
          ),
          // Results
          Expanded(
            child: BlocBuilder<KanbanBloc, KanbanState>(
              builder: (context, state) {
                if (state is KanbanSearchResults) {
                  return _buildSearchResults(state);
                }
                // Not searching yet — show placeholder
                return _buildPlaceholder();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPlaceholder() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.search, size: 48, color: AppColors.textTertiary),
          SizedBox(height: 12),
          Text(
            '输入关键词搜索事件',
            style: TextStyle(
              fontSize: 15,
              color: AppColors.textSecondary,
            ),
          ),
          SizedBox(height: 4),
          Text(
            '支持搜索标题、地点、备注等',
            style: TextStyle(
              fontSize: 13,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchResults(KanbanSearchResults state) {
    if (state.isSearching) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.results.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.search_off,
                size: 48, color: AppColors.textTertiary),
            const SizedBox(height: 12),
            Text(
              '未找到相关事件',
              style: const TextStyle(
                fontSize: 15,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '"${state.query}"',
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Text(
            state.total > state.results.length
                ? '找到 ${state.total} 个结果（显示前 ${state.results.length} 条）'
                : '找到 ${state.total} 个结果',
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.only(bottom: 20),
            itemCount: state.results.length,
            itemBuilder: (_, i) {
              final event = state.results[i];
              return CompactEventRow(
                event: event,
                onTap: () {
                  Navigator.pop(context);
                  widget.onEventTap?.call(event);
                },
              );
            },
          ),
        ),
      ],
    );
  }
}
