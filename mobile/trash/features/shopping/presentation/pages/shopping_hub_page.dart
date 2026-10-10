import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_list.dart';
import '../bloc/shopping_list_bloc.dart';
import '../bloc/inventory_bloc.dart';
import '../widgets/shopping_list_card.dart';
import '../widgets/category_filter_chips.dart';
import '../widgets/inventory_stats_card.dart';
import '../widgets/product_recommendation_card.dart';
import '../widgets/create_list_sheet.dart';

/// 购物功能主页面
class ShoppingHubPage extends StatefulWidget {
  final int initialTab;

  const ShoppingHubPage({super.key, this.initialTab = 0});

  @override
  State<ShoppingHubPage> createState() => _ShoppingHubPageState();
}

class _ShoppingHubPageState extends State<ShoppingHubPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  String? _selectedStatus;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: 3,
      vsync: this,
      initialIndex: widget.initialTab,
    );
    _loadData();
  }

  void _loadData() {
    context.read<ShoppingListBloc>().add(const ShoppingListsLoadRequested());
    context.read<InventoryBloc>().add(const InventoryLoadRequested());
    context.read<InventoryBloc>().add(const InventorySummaryLoadRequested());
    context.read<ShoppingListBloc>().add(const ProductRecommendationsLoadRequested());
    context.read<ShoppingListBloc>().add(const SeasonalRecommendationsLoadRequested());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<ShoppingListBloc, ShoppingListState>(
      listener: (context, state) {
        // When shopping list is deleted, show success message
        if (state is ShoppingListDeleteSuccess) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('已删除「${state.listName}」')),
          );
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildTabBar(),
              Expanded(child: _buildContent()),
            ],
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => _showCreateListSheet(context),
          backgroundColor: AppColors.primary,
          icon: const Icon(Icons.add, color: Colors.white),
          label: const Text('新建清单', style: TextStyle(color: Colors.white)),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
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
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('购物清单', style: AppTextStyles.headline4),
              Text(
                '家庭采买助手',
                style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
              ),
            ],
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: Navigate to search
            },
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.15),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelColor: AppColors.primary,
        unselectedLabelColor: AppColors.textTertiary,
        labelStyle: AppTextStyles.bodyText2.copyWith(
          fontWeight: FontWeight.w600,
          fontSize: 13,
        ),
        dividerColor: Colors.transparent,
        tabs: [
          _buildTab(Icons.list_alt_rounded, '清单'),
          _buildTab(Icons.inventory_2_outlined, '库存'),
          _buildTab(Icons.recommend_outlined, '推荐'),
        ],
      ),
    );
  }

  Widget _buildTab(IconData icon, String label) {
    return Tab(
      height: 42,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16),
          const SizedBox(width: 6),
          Text(label),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return TabBarView(
      controller: _tabController,
      children: [
        _buildListsTab(),
        _buildInventoryTab(),
        _buildRecommendationsTab(),
      ],
    );
  }

  Widget _buildListsTab() {
    return Column(
      children: [
        const SizedBox(height: 16),
        ListStatusFilterChips(
          selectedStatus: _selectedStatus,
          onStatusChanged: (status) {
            setState(() => _selectedStatus = status);
            context.read<ShoppingListBloc>().add(ShoppingListsLoadRequested(
              statusFilter: _parseStatus(status),
            ));
          },
        ),
        Expanded(
          child: BlocBuilder<ShoppingListBloc, ShoppingListState>(
            builder: (context, state) {
              if (state is ShoppingListLoading) {
                return const Center(child: CircularProgressIndicator());
              }

              if (state is ShoppingListError) {
                return _buildError(state.message, _loadData);
              }

              if (state is ShoppingListLoaded) {
                if (state.lists.isEmpty) {
                  return _buildEmptyLists();
                }

                return RefreshIndicator(
                  onRefresh: () async => _loadData(),
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: state.lists.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      final list = state.lists[index];
                      return ShoppingListCard(
                        shoppingList: list,
                        onTap: () => _navigateToListDetail(list),
                        onLongPress: () => _showListOptions(list),
                      );
                    },
                  ),
                );
              }

              return const SizedBox.shrink();
            },
          ),
        ),
      ],
    );
  }

  Widget _buildInventoryTab() {
    return BlocBuilder<InventoryBloc, InventoryState>(
      builder: (context, state) {
        if (state is InventoryLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is InventoryError) {
          return _buildError(state.message, () {
            context.read<InventoryBloc>().add(const InventoryLoadRequested());
          });
        }

        if (state is InventoryLoaded) {
          return RefreshIndicator(
            onRefresh: () async {
              context.read<InventoryBloc>().add(const InventoryLoadRequested());
              context.read<InventoryBloc>().add(const InventorySummaryLoadRequested());
            },
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (state.summary != null)
                  InventoryStatsCard(
                    summary: state.summary!,
                    onTap: () => _navigateToInventory(),
                    onLowStockTap: () => _navigateToLowStock(),
                  ),
                if (state.replenishmentSuggestions.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  _buildReplenishmentSection(state),
                ],
                if (state.inventoryItems.isEmpty && state.summary == null)
                  _buildEmptyInventory(),
              ],
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildReplenishmentSection(InventoryLoaded state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Row(
            children: [
              const Icon(Icons.shopping_bag_outlined, size: 20, color: AppColors.warning),
              const SizedBox(width: 8),
              Text('补货建议', style: AppTextStyles.headline6),
              const Spacer(),
              Text(
                '${state.replenishmentSuggestions.length}件',
                style: AppTextStyles.caption,
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 140,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: state.replenishmentSuggestions.length,
            itemBuilder: (context, index) {
              final item = state.replenishmentSuggestions[index];
              return ReplenishmentSuggestionCard(
                item: item,
                onAddToList: () => _addToShoppingList(item.productName),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildRecommendationsTab() {
    return BlocBuilder<ShoppingListBloc, ShoppingListState>(
      builder: (context, state) {
        if (state is ShoppingListLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is ShoppingListLoaded) {
          if (state.productRecommendations.isEmpty && state.seasonalRecommendations.isEmpty) {
            return _buildEmptyRecommendations();
          }

          return RefreshIndicator(
            onRefresh: () async {
              context.read<ShoppingListBloc>().add(const ProductRecommendationsLoadRequested());
              context.read<ShoppingListBloc>().add(const SeasonalRecommendationsLoadRequested());
            },
            child: ListView(
              children: [
                if (state.productRecommendations.isNotEmpty)
                  RecommendationSection(
                    title: '为你推荐',
                    recommendations: state.productRecommendations,
                    onItemTap: (rec) => _showRecommendationDetail(rec),
                    onAddToList: (rec) => _addToShoppingList(rec.productName),
                  ),
                if (state.seasonalRecommendations.isNotEmpty)
                  RecommendationSection(
                    title: '应季好物',
                    recommendations: state.seasonalRecommendations,
                    onItemTap: (rec) => _showRecommendationDetail(rec),
                    onAddToList: (rec) => _addToShoppingList(rec.productName),
                  ),
              ],
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildEmptyLists() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.shopping_cart_outlined,
              size: 40,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 16),
          Text('暂无购物清单', style: AppTextStyles.headline6),
          const SizedBox(height: 8),
          Text(
            '点击右下角按钮创建新清单',
            style: AppTextStyles.caption,
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyInventory() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.secondary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.inventory_2_outlined,
                size: 40,
                color: AppColors.secondary,
              ),
            ),
            const SizedBox(height: 16),
            Text('暂无库存记录', style: AppTextStyles.headline6),
            const SizedBox(height: 8),
            Text(
              '完成购物后会自动记录库存',
              style: AppTextStyles.caption,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyRecommendations() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.accent1.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.recommend_outlined,
              size: 40,
              color: AppColors.accent1,
            ),
          ),
          const SizedBox(height: 16),
          Text('暂无推荐', style: AppTextStyles.headline6),
          const SizedBox(height: 8),
          Text(
            '根据您的购买习惯生成推荐',
            style: AppTextStyles.caption,
          ),
        ],
      ),
    );
  }

  Widget _buildError(String message, VoidCallback onRetry) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(message, style: AppTextStyles.bodyText2),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: onRetry,
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  void _showCreateListSheet(BuildContext context) {
    showCreateListSheet(
      context,
      onSubmit: (listName, listType, dueDate) {
        context.read<ShoppingListBloc>().add(ShoppingListCreateRequested(
          listName: listName,
          listType: listType,
          dueDate: dueDate,
        ));
      },
      onAIGenerate: () {
        Navigator.pop(context);
        _navigateToAIAssistant();
      },
    );
  }

  Future<void> _navigateToListDetail(ShoppingList list) async {
    context.read<ShoppingListBloc>().add(ShoppingListSelected(list.id));
    await context.push('${Routes.shopping}/list/${list.id}');
    if (mounted) {
      context.read<ShoppingListBloc>().add(const ShoppingListsLoadRequested());
    }
  }

  void _showListOptions(ShoppingList list) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: const Text('编辑清单'),
              onTap: () {
                Navigator.pop(context);
                // TODO: Navigate to edit
              },
            ),
            ListTile(
              leading: const Icon(Icons.check_circle_outline),
              title: const Text('标记完成'),
              onTap: () {
                Navigator.pop(context);
                context.read<ShoppingListBloc>().add(
                  ShoppingListCompleted(list.id),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: AppColors.error),
              title: const Text('删除清单', style: TextStyle(color: AppColors.error)),
              onTap: () {
                Navigator.pop(context);
                _confirmDeleteList(list);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _confirmDeleteList(ShoppingList list) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除清单'),
        content: Text('确定要删除「${list.listName}」吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<ShoppingListBloc>().add(
                ShoppingListDeleted(list.id),
              );
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  void _navigateToInventory() {
    // Switch to inventory tab
    _tabController.animateTo(1);
  }

  void _navigateToLowStock() {
    // Switch to inventory tab and trigger low stock filter
    _tabController.animateTo(1);
    context.read<InventoryBloc>().add(const InventoryLoadRequested(lowStockOnly: true));
  }

  void _navigateToAIAssistant() {
    context.go('/conversation');
  }

  void _addToShoppingList(String productName) {
    // TODO: Show list selection dialog and add item
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('已添加「$productName」到清单'),
        action: SnackBarAction(
          label: '撤销',
          onPressed: () {},
        ),
      ),
    );
  }

  void _showRecommendationDetail(rec) {
    // TODO: Show recommendation detail
  }

  ListStatus? _parseStatus(String? status) {
    switch (status) {
      case 'active':
        return ListStatus.active;
      case 'in_progress':
        return ListStatus.inProgress;
      case 'completed':
        return ListStatus.completed;
      default:
        return null;
    }
  }
}
