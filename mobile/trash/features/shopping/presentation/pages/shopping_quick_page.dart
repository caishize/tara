import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_item.dart';
import '../bloc/shopping_list_bloc.dart';
import '../widgets/shopping_item_tile.dart';
import '../widgets/add_item_bottom_sheet.dart';
import '../widgets/assignee_selector.dart';
import 'shopping_item_detail_page.dart';

/// 购物清单快捷入口页面
/// 匹配原型图设计：两级结构（商品列表 → 商品详情）
/// 直接显示所有商品，支持全部/待购买/已完成筛选
class ShoppingQuickPage extends StatefulWidget {
  const ShoppingQuickPage({super.key});

  @override
  State<ShoppingQuickPage> createState() => _ShoppingQuickPageState();
}

class _ShoppingQuickPageState extends State<ShoppingQuickPage> {
  int _selectedTabIndex = 0; // 0: 全部, 1: 待购买, 2: 已完成

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    // 加载所有清单的商品
    context.read<ShoppingListBloc>().add(const ShoppingListsLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            _buildFilterTabs(),
            Expanded(child: _buildItemsList()),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddItemSheet(context),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
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
          Text('购物清单', style: AppTextStyles.headline4),
          const Spacer(),
          // 添加按钮（匹配原型图右上角的"+ 添加"）
          GestureDetector(
            onTap: () => _showAddItemSheet(context),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.add, size: 16, color: Colors.white),
                  const SizedBox(width: 4),
                  Text(
                    '添加',
                    style: AppTextStyles.bodyText2.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 筛选标签（匹配原型图：全部、待购买、已完成）
  Widget _buildFilterTabs() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
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
      ),
    );
  }

  Widget _buildTabItem(int index, String label) {
    final isSelected = _selectedTabIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedTabIndex = index),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
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

  Widget _buildItemsList() {
    return BlocBuilder<ShoppingListBloc, ShoppingListState>(
      builder: (context, state) {
        if (state is ShoppingListLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is ShoppingListError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
                const SizedBox(height: 16),
                Text(state.message, style: AppTextStyles.bodyText2),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _loadData,
                  child: const Text('重试'),
                ),
              ],
            ),
          );
        }

        if (state is ShoppingListLoaded) {
          // 收集所有清单中的商品
          final allItems = _collectAllItems(state);

          // 根据选中的 Tab 筛选
          final filteredItems = _filterItems(allItems);

          if (filteredItems.isEmpty) {
            return _buildEmptyState();
          }

          return RefreshIndicator(
            onRefresh: () async => _loadData(),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: filteredItems.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final item = filteredItems[index];
                return ShoppingItemTile(
                  item: item,
                  onTap: () => _showItemDetail(item),
                  onTogglePurchased: () => _toggleItemPurchased(item),
                  onDelete: () => _deleteItem(item),
                );
              },
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  /// 收集所有清单中的商品
  List<ShoppingItem> _collectAllItems(ShoppingListLoaded state) {
    // 如果有选中的清单，返回其商品；否则需要加载所有清单的商品
    if (state.items.isNotEmpty) {
      return state.items;
    }
    // 这里可以扩展为从所有清单收集商品
    return [];
  }

  /// 根据 Tab 筛选商品
  List<ShoppingItem> _filterItems(List<ShoppingItem> items) {
    switch (_selectedTabIndex) {
      case 1: // 待购买
        return items
            .where((item) =>
                item.itemStatus != ItemStatus.delivered &&
                item.itemStatus != ItemStatus.cancelled)
            .toList();
      case 2: // 已完成
        return items
            .where((item) => item.itemStatus == ItemStatus.delivered)
            .toList();
      default: // 全部
        return items;
    }
  }

  Widget _buildEmptyState() {
    String message;
    switch (_selectedTabIndex) {
      case 1:
        message = '没有待购买的商品';
        break;
      case 2:
        message = '没有已完成的商品';
        break;
      default:
        message = '购物清单是空的';
    }

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.shopping_cart_outlined,
              size: 40,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 16),
          Text(message, style: AppTextStyles.headline6),
          const SizedBox(height: 8),
          Text(
            '点击右上角添加商品',
            style: AppTextStyles.caption,
          ),
        ],
      ),
    );
  }

  void _showAddItemSheet(BuildContext context) {
    showAddItemBottomSheet(
      context,
      onSubmit: (productName, notes, tags, assignedTo) {
        // 添加到默认清单或让用户选择清单
        final state = context.read<ShoppingListBloc>().state;
        if (state is ShoppingListLoaded && state.lists.isNotEmpty) {
          final defaultList = state.lists.first;
          context.read<ShoppingListBloc>().add(ShoppingItemAddRequested(
            listId: defaultList.id,
            productName: productName,
            notes: notes,
            // TODO: 后续添加 tags 和 assignedTo 支持到 ShoppingItemAddRequested
          ));
        }
      },
      familyMembers: const [], // TODO: 从状态获取家庭成员
      currentUserId: '', // TODO: 从认证状态获取当前用户ID
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
              listId: item.listId,
              itemId: item.id,
              itemStatus: ItemStatus.cancelled,
            ));
          },
          onMarkComplete: () {
            Navigator.pop(context);
            context.read<ShoppingListBloc>().add(ShoppingItemStatusUpdateRequested(
              listId: item.listId,
              itemId: item.id,
              itemStatus: ItemStatus.delivered,
            ));
          },
          onEdit: () {
            Navigator.pop(context);
            // TODO: 显示编辑弹窗
          },
        ),
      ),
    );
  }

  void _toggleItemPurchased(ShoppingItem item) {
    if (item.isPurchased) {
      // 取消购买标记
      context.read<ShoppingListBloc>().add(ShoppingItemUpdateRequested(
        listId: item.listId,
        itemId: item.id,
      ));
    } else {
      // 标记为已购买
      context.read<ShoppingListBloc>().add(ShoppingItemPurchased(
        listId: item.listId,
        itemId: item.id,
      ));
    }
  }

  void _deleteItem(ShoppingItem item) {
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
              context.read<ShoppingListBloc>().add(ShoppingItemDeleted(
                listId: item.listId,
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
}
