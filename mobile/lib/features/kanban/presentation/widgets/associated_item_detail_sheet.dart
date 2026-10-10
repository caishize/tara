import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/associated_item.dart';

/// Bottom sheet that displays full details for an AssociatedItem
/// from the insight graph.
class AssociatedItemDetailSheet extends StatelessWidget {
  final AssociatedItem item;

  const AssociatedItemDetailSheet({super.key, required this.item});

  static Future<void> show(BuildContext context, AssociatedItem item) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        maxChildSize: 0.8,
        minChildSize: 0.3,
        builder: (_, __) => AssociatedItemDetailSheet(item: item),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          _buildHandle(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              children: [
                _buildHeader(),
                const SizedBox(height: 16),
                _buildMetaRow(),
                if (item.subtitle != null) ...[
                  const SizedBox(height: 16),
                  _buildSubtitle(),
                ],
                if (item.hasContextHint) ...[
                  const SizedBox(height: 16),
                  _buildContextHint(),
                ],
                if (_hasExtraDetails) ...[
                  const SizedBox(height: 16),
                  _buildExtraDetails(),
                ],
                const SizedBox(height: 32),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey.shade300,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: _iconBgColor,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(_icon, color: _iconColor, size: 24),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.title,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                item.itemTypeDisplayName,
                style: TextStyle(
                  fontSize: 14,
                  color: _iconColor,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildMetaRow() {
    return Row(
      children: [
        _buildChip(item.priorityDisplayName, _priorityColor),
        const SizedBox(width: 8),
        _buildChip(item.itemTypeDisplayName, _iconColor),
      ],
    );
  }

  Widget _buildChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withAlpha((0.1 * 255).round()),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }

  Widget _buildSubtitle() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        item.subtitle!,
        style: const TextStyle(
          fontSize: 14,
          color: AppColors.textPrimary,
          height: 1.5,
        ),
      ),
    );
  }

  Widget _buildContextHint() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withAlpha((0.06 * 255).round()),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.auto_awesome, size: 16, color: AppColors.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              item.contextHint!,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  bool get _hasExtraDetails {
    final metadata = item.metadata ?? {};
    return metadata['description'] != null ||
        metadata['location'] != null ||
        metadata['time'] != null ||
        metadata['date'] != null ||
        metadata['note'] != null;
  }

  Widget _buildExtraDetails() {
    final metadata = item.metadata ?? {};
    final rows = <Widget>[];

    if (metadata['date'] != null || metadata['time'] != null) {
      final timeStr = [metadata['date'], metadata['time']]
          .where((v) => v != null)
          .join(' ');
      rows.add(_buildDetailRow(Icons.schedule, '时间', timeStr));
    }
    if (metadata['location'] != null) {
      rows.add(_buildDetailRow(
          Icons.location_on_outlined, '地点', metadata['location'].toString()));
    }
    if (metadata['description'] != null) {
      rows.add(_buildDetailRow(
          Icons.notes, '描述', metadata['description'].toString()));
    }
    if (metadata['note'] != null) {
      rows.add(
          _buildDetailRow(Icons.note_outlined, '备注', metadata['note'].toString()));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '详细信息',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        ...rows,
      ],
    );
  }

  Widget _buildDetailRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: AppColors.textTertiary),
          const SizedBox(width: 10),
          SizedBox(
            width: 48,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textPrimary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  IconData get _icon {
    switch (item.itemType) {
      case ItemType.person:
        return Icons.person_outline;
      case ItemType.task:
        return Icons.check_circle_outline;
      case ItemType.gift:
        return Icons.card_giftcard_outlined;
      case ItemType.place:
        return Icons.place_outlined;
      case ItemType.business:
        return Icons.business_outlined;
    }
  }

  Color get _iconBgColor {
    switch (item.itemType) {
      case ItemType.person:
        return AppColors.badgePurple;
      case ItemType.task:
        return AppColors.badgeBlue;
      case ItemType.gift:
        return AppColors.badgePink;
      case ItemType.place:
      case ItemType.business:
        return AppColors.badgeGreen;
    }
  }

  Color get _iconColor {
    switch (item.itemType) {
      case ItemType.person:
        return const Color(0xFF8B5CF6);
      case ItemType.task:
        return const Color(0xFF1976D2);
      case ItemType.gift:
        return const Color(0xFFEC4899);
      case ItemType.place:
      case ItemType.business:
        return AppColors.primary;
    }
  }

  Color get _priorityColor {
    switch (item.priority) {
      case ItemPriority.stronglyRecommend:
        return AppColors.error;
      case ItemPriority.convenient:
        return AppColors.warning;
      case ItemPriority.optional:
        return AppColors.textSecondary;
    }
  }
}
