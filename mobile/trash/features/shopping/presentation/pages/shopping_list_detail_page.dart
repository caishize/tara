import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_list.dart';
import '../../domain/entities/shopping_item.dart';
import '../bloc/shopping_list_bloc.dart';
import '../widgets/shopping_item_tile.dart';
import '../widgets/category_filter_chips.dart';
import '../widgets/bundle_suggestion_card.dart';
import '../widgets/add_item_sheet.dart';
import '../widgets/add_item_bottom_sheet.dart';
import '../widgets/assignee_selector.dart';
import 'shopping_item_detail_page.dart';

/// 购物清单详情页面
class ShoppingListDetailPage extends StatefulWidget {
  final String listId;

  const ShoppingListDetailPage({
    super.key,
    required this.listId,
  });

  @override
  State<ShoppingListDetailPage> createState() => _ShoppingListDetailPageState();
}

class _ShoppingListDetailPageState extends State<ShoppingListDetailPage>
    with SingleTickerProviderStateMixin {
  ItemCategory? _selectedCategory;
  bool _showPurchased = true;
  late TabController _tabController;
  int _selectedTabIndex = 0; // 0: All, 1: To Buy, 2: Completed

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() => _selectedTabIndex = _tabController.index);
      }
    });
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _loadData() {
    context.read<ShoppingListBloc>().add(ShoppingListSelected(widget.listId));
    context.read<ShoppingListBloc>().add(BundleOpportunitiesLoadRequested(widget.listId));
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ShoppingListBloc, ShoppingListState>(
      builder: (context, state) {
        if (state is ShoppingListLoading) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        if (state is ShoppingListError) {
          return Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 48),
                  const SizedBox(height: 16),
                  Text(state.message),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: _loadData,
                    child: const Text('重试'),
                  ),
                ],
              ),
            ),
          );
        }

        if (state is ShoppingListLoaded && state.selectedList != null) {
          return _buildContent(state);
        }

        return const Scaffold(
          body: Center(child: Text('清单不存在')),
        );
      },
    );
  }

  Widget _buildContent(ShoppingListLoaded state) {
    final list = state.selectedList!;
    final items = state.items;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(list),
            _buildProgress(state),
            _buildFilters(),
            Expanded(
              child: _buildItemsList(state, items),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddItemSheet(context),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      bottomNavigationBar: items.isNotEmpty ? _buildBottomBar(state) : null,
    );
  }

  Widget _buildHeader(ShoppingList list) {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [AppColors.shadowLight],
              ),
              child: const Icon(Icons.arrow_back_ios_new, size: 18),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(list.listTypeIcon, style: const TextStyle(fontSize: 20)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        list.listName,
                        style: AppTextStyles.headline5,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _buildStatusBadge(list.status),
                    const SizedBox(width: 8),
                    Text(
                      list.listTypeName,
                      style: AppTextStyles.caption,
                    ),
                    if (list.dueDate != null) ...[
                      const SizedBox(width: 8),
                      const Icon(Icons.schedule, size: 12, color: AppColors.textTertiary),
                      const SizedBox(width: 4),
                      Text(
                        '${list.dueDate!.month}/${list.dueDate!.day}',
                        style: AppTextStyles.caption,
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          PopupMenuButton(
            icon: const Icon(Icons.more_vert),
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'edit',
                child: Row(
                  children: [
                    Icon(Icons.edit_outlined, size: 20),
                    SizedBox(width: 12),
                    Text('编辑清单'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'share',
                child: Row(
                  children: [
                    Icon(Icons.share_outlined, size: 20),
                    SizedBox(width: 12),
                    Text('分享清单'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'complete',
                child: Row(
                  children: [
                    Icon(Icons.check_circle_outline, size: 20),
                    SizedBox(width: 12),
                    Text('标记完成'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'ai_add',
                child: Row(
                  children: [
                    Icon(Icons.auto_awesome, size: 20, color: AppColors.accent3),
                    SizedBox(width: 12),
                    Text('AI添加商品'),
                  ],
                ),
              ),
            ],
            onSelected: (value) => _handleMenuAction(value, list),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(ListStatus status) {
    Color color;
    String label;
    switch (status) {
      case ListStatus.active:
        color = AppColors.info;
        label = '待采购';
        break;
      case ListStatus.inProgress:
        color = AppColors.warning;
        label = '采购中';
        break;
      case ListStatus.completed:
        color = AppColors.success;
        label = '已完成';
        break;
      case ListStatus.archived:
        color = AppColors.textTertiary;
        label = '已归档';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: AppTextStyles.overline.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildProgress(ShoppingListLoaded state) {
    final progress = state.selectedList!.completionRate;
    final purchased = state.purchasedItems.length;
    final total = state.items.length;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.check_circle_outline, size: 18, color: AppColors.success),
                  const SizedBox(width: 8),
                  Text(
                    '已完成 $purchased / $total 项',
                    style: AppTextStyles.subtitle2,
                  ),
                ],
              ),
              Text(
                '${(progress * 100).toInt()}%',
                style: AppTextStyles.headline6.copyWith(
                  color: AppColors.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: AppColors.divider,
              valueColor: AlwaysStoppedAnimation<Color>(
                progress == 1.0 ? AppColors.success : AppColors.primary,
              ),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStat('预估', '¥${state.totalEstimatedPrice.toStringAsFixed(0)}'),
              _buildStat('实际', '¥${state.totalActualPrice.toStringAsFixed(0)}'),
              _buildStat(
                '差额',
                '${state.totalActualPrice - state.totalEstimatedPrice >= 0 ? '+' : ''}¥${(state.totalActualPrice - state.totalEstimatedPrice).toStringAsFixed(0)}',
                color: state.totalActualPrice > state.totalEstimatedPrice
                    ? AppColors.error
                    : AppColors.success,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStat(String label, String value, {Color? color}) {
    return Column(
      children: [
        Text(label, style: AppTextStyles.caption),
        const SizedBox(height: 2),
        Text(
          value,
          style: AppTextStyles.subtitle2.copyWith(
            color: color ?? AppColors.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildFilters() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      child: _buildStatusTabs(),
    );
  }

  /// 状态筛选标签（匹配原型：全部、待购买、已完成）
  Widget _buildStatusTabs() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: [
          _buildTabItem(0, '全部'),
          _buildTabItem(1, '待购买'),
          _buildTabItem(2, '已完成'),
        ],
      ),
    );
  }

  Widget _buildTabItem(int index, String label) {
    final isSelected = _selectedTabIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() => _selectedTabIndex = index);
          _tabController.animateTo(index);
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? Colors.white : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.05),
                      blurRadius: 4,
                      offset: const Offset(0, 1),
                    ),
                  ]
                : null,
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isSelected ? AppColors.primary : AppColors.textTertiary,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildItemsList(ShoppingListLoaded state, List<ShoppingItem> items) {
    // Filter items based on selected tab
    var filteredItems = items.where((item) {
      // Tab filter: 0=All, 1=To Buy (pending/ordered), 2=Completed (delivered)
      switch (_selectedTabIndex) {
        case 1: // 待购买
          if (item.itemStatus == ItemStatus.delivered ||
              item.itemStatus == ItemStatus.cancelled) {
            return false;
          }
          break;
        case 2: // 已完成
          if (item.itemStatus != ItemStatus.delivered) {
            return false;
          }
          break;
      }
      // Category filter
      if (_selectedCategory != null && item.category != _selectedCategory) {
        return false;
      }
      return true;
    }).toList();

    // Sort: by item status, then by priority
    filteredItems.sort((a, b) {
      // Delivered items last
      if (a.itemStatus == ItemStatus.delivered &&
          b.itemStatus != ItemStatus.delivered) {
        return 1;
      }
      if (b.itemStatus == ItemStatus.delivered &&
          a.itemStatus != ItemStatus.delivered) {
        return -1;
      }
      // Then by priority
      return a.priority.compareTo(b.priority);
    });

    if (filteredItems.isEmpty && items.isEmpty) {
      return EmptyItemsPlaceholder(
        onAddItem: () => _showAddItemSheet(context),
      );
    }

    return RefreshIndicator(
      onRefresh: () async => _loadData(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
        children: [
          // Bundle suggestions
          if (state.bundleOpportunities.isNotEmpty)
            BundleSuggestionList(
              bundles: state.bundleOpportunities,
              onBundleTap: (bundle) {
                // TODO: Handle bundle tap
              },
            ),
          // Items
          ...filteredItems.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: ShoppingItemTile(
              item: item,
              onTap: () => _showItemDetail(item),
              onTogglePurchased: () => _toggleItemPurchased(item),
              onDelete: () => _deleteItem(item),
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildBottomBar(ShoppingListLoaded state) {
    final unpurchased = state.unpurchasedItems.length;

    return Container(
      padding: EdgeInsets.fromLTRB(
        20, 16, 20, 16 + MediaQuery.of(context).padding.bottom,
      ),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '剩余 $unpurchased 项待购',
                  style: AppTextStyles.subtitle2,
                ),
                Text(
                  '预估 ¥${state.totalEstimatedPrice.toStringAsFixed(0)}',
                  style: AppTextStyles.caption,
                ),
              ],
            ),
          ),
          ElevatedButton.icon(
            onPressed: unpurchased == 0
                ? () => _completeList(state.selectedList!)
                : () => _startShopping(state.selectedList!),
            icon: Icon(unpurchased == 0 ? Icons.check : Icons.shopping_cart),
            label: Text(unpurchased == 0 ? '完成采购' : '开始采购'),
            style: ElevatedButton.styleFrom(
              backgroundColor: unpurchased == 0 ? AppColors.success : AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showAddItemSheet(BuildContext context) {
    showAddItemSheet(
      context,
      onSubmit: (productName, category, quantity, unit, priority, estimatedPrice, notes) {
        context.read<ShoppingListBloc>().add(ShoppingItemAddRequested(
          listId: widget.listId,
          productName: productName,
          category: category?.name,
          quantity: quantity,
          unit: unit,
          priority: priority,
          estimatedPrice: estimatedPrice,
          notes: notes,
        ));
      },
      onAIGenerate: () {
        Navigator.pop(context);
        _navigateToAIAssistant();
      },
    );
  }

  void _handleMenuAction(String action, ShoppingList list) {
    switch (action) {
      case 'edit':
        // TODO: Navigate to edit
        break;
      case 'share':
        // TODO: Share list
        break;
      case 'complete':
        context.read<ShoppingListBloc>().add(ShoppingListCompleted(list.id));
        break;
      case 'ai_add':
        _navigateToAIAssistant();
        break;
    }
  }

  void _toggleItemPurchased(ShoppingItem item) {
    if (item.isPurchased) {
      // Unmark as purchased
      context.read<ShoppingListBloc>().add(ShoppingItemUpdateRequested(
        listId: widget.listId,
        itemId: item.id,
      ));
    } else {
      // Show purchase dialog
      _showPurchaseDialog(item);
    }
  }

  void _showPurchaseDialog(ShoppingItem item) {
    final priceController = TextEditingController(
      text: item.estimatedPrice?.toStringAsFixed(0) ?? '',
    );
    final merchantController = TextEditingController();
    final bloc = context.read<ShoppingListBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('购买 ${item.productName}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: priceController,
              decoration: const InputDecoration(
                labelText: '实际价格',
                prefixText: '¥ ',
              ),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: merchantController,
              decoration: const InputDecoration(
                labelText: '购买渠道（可选）',
                hintText: '例如：盒马、京东',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              bloc.add(ShoppingItemPurchased(
                listId: widget.listId,
                itemId: item.id,
                actualPrice: double.tryParse(priceController.text),
                merchant: merchantController.text.isEmpty ? null : merchantController.text,
              ));
            },
            child: const Text('确认'),
          ),
        ],
      ),
    );
  }

  void _deleteItem(ShoppingItem item) {
    final bloc = context.read<ShoppingListBloc>();
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('删除商品'),
        content: Text('确定要删除「${item.productName}」吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              bloc.add(ShoppingItemDeleted(
                listId: widget.listId,
                itemId: item.id,
              ));
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  void _showItemDetail(ShoppingItem item) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ShoppingItemDetailPage(
          item: item,
          onCancel: () {
            Navigator.pop(context);
            context.read<ShoppingListBloc>().add(ShoppingItemStatusUpdateRequested(
              listId: widget.listId,
              itemId: item.id,
              itemStatus: ItemStatus.cancelled,
            ));
          },
          onMarkComplete: () {
            Navigator.pop(context);
            context.read<ShoppingListBloc>().add(ShoppingItemStatusUpdateRequested(
              listId: widget.listId,
              itemId: item.id,
              itemStatus: ItemStatus.delivered,
            ));
          },
          onEdit: () {
            Navigator.pop(context);
            // TODO: Show edit sheet
          },
        ),
      ),
    );
  }

  void _startShopping(ShoppingList list) {
    context.read<ShoppingListBloc>().add(ShoppingListUpdateRequested(
      listId: list.id,
      status: ListStatus.inProgress,
    ));
  }

  void _completeList(ShoppingList list) {
    context.read<ShoppingListBloc>().add(ShoppingListCompleted(list.id));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('采购完成！')),
    );
  }

  void _navigateToAIAssistant() {
    context.go('/conversation');
  }
}
