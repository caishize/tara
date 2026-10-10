import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/shopping_item.dart';
import '../widgets/item_tag_selector.dart';

/// 购物商品详情页面
/// 匹配原型设计右侧面板
class ShoppingItemDetailPage extends StatelessWidget {
  final ShoppingItem item;
  final VoidCallback? onCancel;
  final VoidCallback? onMarkComplete;
  final VoidCallback? onEdit;

  const ShoppingItemDetailPage({
    super.key,
    required this.item,
    this.onCancel,
    this.onMarkComplete,
    this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildMainCard(context),
                  const SizedBox(height: 16),
                  _buildNotesSection(context),
                  const SizedBox(height: 16),
                  if (item.trackingUpdates.isNotEmpty) _buildTrackingSection(context),
                ],
              ),
            ),
            _buildActionBar(context),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      color: Colors.white,
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios),
            onPressed: () => Navigator.of(context).pop(),
          ),
          Expanded(
            child: Text(
              '购物项详情',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.more_horiz),
            onPressed: () => _showMoreOptions(context),
          ),
        ],
      ),
    );
  }

  Widget _buildMainCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题和状态
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  item.productName,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ),
              const SizedBox(width: 12),
              _buildOrderStatusBadge(context),
            ],
          ),
          const SizedBox(height: 12),
          // 配送状态标签
          _buildStatusTags(context),
          const SizedBox(height: 20),
          const Divider(height: 1),
          const SizedBox(height: 16),
          // 信息列表
          _buildInfoRow(context, '购买人', item.assignedToName ?? '我', isHighlight: true),
          const SizedBox(height: 12),
          _buildInfoRow(
            context,
            '创建时间',
            DateFormat('yyyy年M月d日').format(item.createdAt),
          ),
          if (item.expectedDeliveryDate != null) ...[
            const SizedBox(height: 12),
            _buildInfoRow(
              context,
              '预计送达',
              DateFormat('yyyy年M月d日').format(item.expectedDeliveryDate!),
            ),
          ],
          // 关联事件（匹配原型图设计）
          if (item.hasLinkedEvent) ...[
            const SizedBox(height: 12),
            _buildLinkedEventRow(context),
          ],
        ],
      ),
    );
  }

  /// 构建关联事件行（匹配原型图设计：关联事件 - 岳父生日）
  Widget _buildLinkedEventRow(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          '关联事件',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey.shade600,
              ),
        ),
        GestureDetector(
          onTap: () => _navigateToLinkedEvent(context),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                item.linkedEventIcon ?? Icons.event,
                size: 16,
                color: Theme.of(context).primaryColor,
              ),
              const SizedBox(width: 4),
              Text(
                item.linkedEventDisplay ?? '',
                style: TextStyle(
                  color: Theme.of(context).primaryColor,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// 跳转到关联事件
  void _navigateToLinkedEvent(BuildContext context) {
    if (item.eventId == null || item.eventType == null) return;

    // 根据事件类型跳转到不同页面
    String? route;
    switch (item.eventType) {
      case 'date':
        route = '/dates/${item.eventId}';
        break;
      case 'travel':
        route = '/travel/${item.eventId}';
        break;
      case 'gift':
        route = '/gifts/${item.eventId}';
        break;
    }

    if (route != null) {
      Navigator.of(context).pushNamed(route);
    }
  }

  Widget _buildOrderStatusBadge(BuildContext context) {
    Color bgColor;
    String text;

    switch (item.itemStatus) {
      case ItemStatus.ordered:
        bgColor = const Color(0xFF4CAF50).withOpacity(0.1);
        text = '已下单';
        break;
      case ItemStatus.inTransit:
        bgColor = const Color(0xFF2196F3).withOpacity(0.1);
        text = '配送中';
        break;
      case ItemStatus.delivered:
        bgColor = const Color(0xFF4CAF50).withOpacity(0.1);
        text = '已送达';
        break;
      case ItemStatus.cancelled:
        bgColor = const Color(0xFFE57373).withOpacity(0.1);
        text = '已取消';
        break;
      default:
        bgColor = const Color(0xFFFFA726).withOpacity(0.1);
        text = '待购买';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: item.itemStatusColor.withOpacity(0.3)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: item.itemStatusColor,
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildStatusTags(BuildContext context) {
    final List<Widget> tags = [];

    // 配送状态
    if (item.itemStatus == ItemStatus.inTransit) {
      tags.add(_buildTag('配送中', const Color(0xFF4CAF50)));
    }

    // 预计送达
    final deliveryText = item.deliveryText;
    if (deliveryText != null && item.itemStatus != ItemStatus.delivered) {
      tags.add(_buildTag(deliveryText, const Color(0xFF2196F3)));
    }

    // 商品标签
    for (final tag in item.tags) {
      tags.add(_buildTag(getTagLabel(tag), getTagColor(tag)));
    }

    if (tags.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: tags,
    );
  }

  Widget _buildTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildInfoRow(BuildContext context, String label, String value, {bool isHighlight = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey.shade600,
              ),
        ),
        Row(
          children: [
            if (isHighlight)
              Container(
                margin: const EdgeInsets.only(right: 6),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF4CAF50).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '我',
                  style: TextStyle(
                    color: const Color(0xFF4CAF50),
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            Text(
              value,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildNotesSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '备注',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              TextButton(
                onPressed: onEdit,
                child: Text(
                  '编辑',
                  style: TextStyle(
                    color: Theme.of(context).primaryColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            item.notes ?? '暂无备注',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: item.notes != null ? Colors.black87 : Colors.grey,
                  height: 1.5,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrackingSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '物流追踪',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              TextButton(
                onPressed: () {
                  // TODO: 显示完整物流详情
                },
                child: Text(
                  '查看详情',
                  style: TextStyle(
                    color: Theme.of(context).primaryColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...item.trackingUpdates.reversed.take(3).map((update) => _buildTrackingItem(context, update)).toList(),
        ],
      ),
    );
  }

  Widget _buildTrackingItem(BuildContext context, TrackingUpdate update) {
    final isFirst = item.trackingUpdates.isNotEmpty && item.trackingUpdates.last == update;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 时间线
          Column(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: isFirst ? const Color(0xFF4CAF50) : Colors.grey.shade300,
                  shape: BoxShape.circle,
                ),
              ),
              if (!isFirst)
                Container(
                  width: 2,
                  height: 40,
                  color: Colors.grey.shade200,
                ),
            ],
          ),
          const SizedBox(width: 12),
          // 内容
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  update.status,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: isFirst ? FontWeight.w600 : FontWeight.normal,
                        color: isFirst ? Colors.black87 : Colors.grey.shade600,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  DateFormat('yyyy-MM-dd HH:mm').format(update.timestamp),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey,
                      ),
                ),
                if (update.location != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    update.location!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.grey.shade600,
                        ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionBar(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    return Container(
      padding: EdgeInsets.fromLTRB(20, 16, 20, 16 + bottomPadding),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          if (item.canCancel) ...[
            Expanded(
              child: OutlinedButton.icon(
                onPressed: onCancel,
                icon: const Icon(Icons.close, size: 18),
                label: const Text('取消订单'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.grey.shade700,
                  side: BorderSide(color: Colors.grey.shade300),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
            flex: item.canCancel ? 1 : 2,
            child: ElevatedButton.icon(
              onPressed: item.canMarkComplete ? onMarkComplete : null,
              icon: const Icon(Icons.check, size: 18),
              label: const Text('标记完成'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4CAF50),
                foregroundColor: Colors.white,
                disabledBackgroundColor: Colors.grey.shade300,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showMoreOptions(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.edit),
                title: const Text('编辑'),
                onTap: () {
                  Navigator.pop(context);
                  onEdit?.call();
                },
              ),
              ListTile(
                leading: const Icon(Icons.share),
                title: const Text('分享'),
                onTap: () {
                  Navigator.pop(context);
                  // TODO: 分享功能
                },
              ),
              ListTile(
                leading: const Icon(Icons.delete, color: Colors.red),
                title: const Text('删除', style: TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.pop(context);
                  // TODO: 删除功能
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
