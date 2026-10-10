import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/gift.dart';
import '../bloc/gifts_bloc.dart';

class GiftsPage extends StatefulWidget {
  const GiftsPage({super.key});

  @override
  State<GiftsPage> createState() => _GiftsPageState();
}

class _GiftsPageState extends State<GiftsPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    context.read<GiftsBloc>().add(const GiftsLoadRequested());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
        onPressed: () => _navigateToConversationForGifts(),
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.auto_awesome, color: Colors.white),
        label: const Text('AI推荐', style: TextStyle(color: Colors.white)),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Text('礼物记录', style: AppTextStyles.headline4),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.bookmark_outline),
            onPressed: () => _tabController.animateTo(1),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
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
        unselectedLabelStyle: AppTextStyles.bodyText2.copyWith(
          fontWeight: FontWeight.w500,
          fontSize: 13,
        ),
        dividerColor: Colors.transparent,
        splashBorderRadius: BorderRadius.circular(12),
        overlayColor: WidgetStateProperty.all(Colors.transparent),
        tabs: [
          _buildTab(Icons.history_rounded, '推荐历史'),
          _buildTab(Icons.bookmark_rounded, '已收藏'),
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
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        if (state is GiftsLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is GiftsError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
                const SizedBox(height: 16),
                Text(state.message, style: AppTextStyles.bodyText2),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    context.read<GiftsBloc>().add(const GiftsLoadRequested());
                  },
                  child: const Text('重试'),
                ),
              ],
            ),
          );
        }

        if (state is GiftsLoaded) {
          return TabBarView(
            controller: _tabController,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              _buildHistoryList(state.history),
              _buildSavedGiftsList(state.savedGifts),
            ],
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildSavedGiftsList(List<Gift> gifts) {
    if (gifts.isEmpty) {
      return _buildEmptyState(
        '暂无收藏',
        '在对话中收到礼物推荐时，点击收藏即可保存',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: gifts.length,
      itemBuilder: (context, index) {
        final gift = gifts[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            leading: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text(gift.categoryIcon, style: const TextStyle(fontSize: 24)),
              ),
            ),
            title: Text(gift.name, style: AppTextStyles.subtitle1),
            subtitle: gift.price > 0
                ? Text(
                    '¥${gift.price.toStringAsFixed(0)}',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.error,
                      fontWeight: FontWeight.bold,
                    ),
                  )
                : null,
            trailing: const Icon(Icons.chevron_right, color: AppColors.textTertiary),
            onTap: () => _openGiftUrl(context, gift),
          ),
        );
      },
    );
  }

  Future<void> _openGiftUrl(BuildContext context, Gift gift) async {
    final url = gift.purchaseUrl;
    if (url == null || url.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${gift.name} 暂无购买链接'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: AppColors.textSecondary,
          duration: const Duration(seconds: 2),
        ),
      );
      return;
    }

    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('无法打开链接: $url'),
            behavior: SnackBarBehavior.floating,
            backgroundColor: AppColors.error,
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
  }

  Widget _buildHistoryList(List<GiftRecommendation> history) {
    if (history.isEmpty) {
      return _buildEmptyState(
        '暂无推荐记录',
        '点击右下角按钮，让AI帮你挑选礼物',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: history.length,
      itemBuilder: (context, index) {
        final rec = history[index];
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: ExpansionTile(
            leading: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                gradient: AppColors.primaryGradient,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.auto_awesome, color: Colors.white),
            ),
            title: Text(rec.memberName, style: AppTextStyles.subtitle1),
            subtitle: Text(
              '${_getOccasionName(rec.occasion)} · 预算¥${rec.budget}',
              style: AppTextStyles.caption,
            ),
            children: rec.gifts.map((gift) => ListTile(
              leading: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(gift.categoryIcon, style: const TextStyle(fontSize: 20)),
                ),
              ),
              title: Text(gift.name, style: AppTextStyles.bodyText2),
              trailing: Text(
                '¥${gift.price.toStringAsFixed(0)}',
                style: AppTextStyles.bodyText1.copyWith(
                  color: AppColors.error,
                  fontWeight: FontWeight.bold,
                ),
              ),
            )).toList(),
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(String title, String subtitle) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.card_giftcard_outlined, size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  String _getOccasionName(GiftOccasion occasion) {
    switch (occasion) {
      case GiftOccasion.birthday:
        return '生日';
      case GiftOccasion.anniversary:
        return '纪念日';
      case GiftOccasion.holiday:
        return '节日';
      case GiftOccasion.graduation:
        return '毕业';
      case GiftOccasion.wedding:
        return '婚礼';
      case GiftOccasion.babyShower:
        return '满月';
      case GiftOccasion.housewarming:
        return '乔迁';
      case GiftOccasion.thankyou:
        return '感谢';
      case GiftOccasion.other:
        return '其他';
    }
  }

  void _navigateToConversationForGifts() {
    context.go(Routes.conversation);
  }
}
