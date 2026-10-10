import 'package:flutter/material.dart';
import '../../domain/entities/itinerary.dart';

class ActivityActionMenu extends StatelessWidget {
  final ItineraryActivity activity;
  final int activityIndex;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  final VoidCallback? onViewDetails;

  const ActivityActionMenu({
    super.key,
    required this.activity,
    required this.activityIndex,
    this.onEdit,
    this.onDelete,
    this.onViewDetails,
  });

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      icon: Icon(Icons.more_vert, color: Colors.grey[600], size: 20),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      offset: const Offset(0, 40),
      itemBuilder: (context) => [
        if (onViewDetails != null)
          PopupMenuItem<String>(
            value: 'details',
            child: Row(
              children: [
                Icon(Icons.info_outline, size: 20, color: Colors.grey[700]),
                const SizedBox(width: 12),
                const Text('查看详情'),
              ],
            ),
          ),
        if (onEdit != null)
          PopupMenuItem<String>(
            value: 'edit',
            child: Row(
              children: [
                Icon(Icons.edit_outlined, size: 20, color: Colors.grey[700]),
                const SizedBox(width: 12),
                const Text('编辑活动'),
              ],
            ),
          ),
        if (onDelete != null) ...[
          const PopupMenuDivider(),
          PopupMenuItem<String>(
            value: 'delete',
            child: Row(
              children: [
                Icon(Icons.delete_outline, size: 20, color: Colors.red[400]),
                const SizedBox(width: 12),
                Text('删除活动', style: TextStyle(color: Colors.red[400])),
              ],
            ),
          ),
        ],
      ],
      onSelected: (value) {
        switch (value) {
          case 'details':
            onViewDetails?.call();
            break;
          case 'edit':
            onEdit?.call();
            break;
          case 'delete':
            _showDeleteConfirmation(context);
            break;
        }
      },
    );
  }

  void _showDeleteConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除活动'),
        content: Text('确定要删除"${activity.title}"吗？此操作无法撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              onDelete?.call();
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }
}

class ActivityQuickActions extends StatelessWidget {
  final ItineraryActivity activity;
  final int activityIndex;
  final VoidCallback? onDelete;

  const ActivityQuickActions({
    super.key,
    required this.activity,
    required this.activityIndex,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (onDelete != null)
          IconButton(
            icon: Icon(Icons.delete_outline, size: 18, color: Colors.red[400]),
            onPressed: () => _showDeleteConfirmation(context),
            tooltip: '删除活动',
            padding: const EdgeInsets.all(4),
            constraints: const BoxConstraints(),
          ),
      ],
    );
  }

  void _showDeleteConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除活动'),
        content: Text('确定要删除"${activity.title}"吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              onDelete?.call();
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }
}

class ActivityDragHandle extends StatelessWidget {
  const ActivityDragHandle({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      child: Icon(
        Icons.drag_indicator,
        size: 20,
        color: Colors.grey[400],
      ),
    );
  }
}
