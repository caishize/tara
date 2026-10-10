import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/poi.dart';
import '../bloc/guardian_bloc.dart';
import '../bloc/guardian_event.dart';
import '../bloc/guardian_state.dart';
import '../widgets/category_filter_row.dart';
import '../widgets/poi_card.dart';
import '../widgets/secretary_tip_card.dart';

/// Trip exploration page for discovering POIs
class TripExplorationPage extends StatefulWidget {
  final String? tripId;
  final String? destination;

  const TripExplorationPage({
    super.key,
    this.tripId,
    this.destination,
  });

  @override
  State<TripExplorationPage> createState() => _TripExplorationPageState();
}

class _TripExplorationPageState extends State<TripExplorationPage> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BlocBuilder<GuardianBloc, GuardianState>(
          builder: (context, state) {
            if (state is GuardianLoading) {
              return const _LoadingView();
            }

            if (state is GuardianError) {
              return _ErrorView(
                message: state.message,
                onRetry: () {
                  context.read<GuardianBloc>().add(
                        GuardianLoadRequested(
                          tripId: widget.tripId,
                          destination: widget.destination,
                        ),
                      );
                },
              );
            }

            if (state is TripExplorationLoaded) {
              return _buildContent(context, state);
            }

            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, TripExplorationLoaded state) {
    return CustomScrollView(
      slivers: [
        // Header
        SliverToBoxAdapter(
          child: _buildHeader(context),
        ),

        // Search bar
        SliverToBoxAdapter(
          child: _buildSearchBar(context),
        ),

        // Category filters
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: CategoryFilterRow(
              selectedCategory: state.selectedCategory,
              onCategorySelected: (category) {
                context
                    .read<GuardianBloc>()
                    .add(POICategoryFilterChanged(category));
              },
            ),
          ),
        ),

        // Secretary recommendations
        if (state.recommendations.isNotEmpty)
          SliverToBoxAdapter(
            child: SecretaryTipCard(
              recommendation: state.recommendations.first,
              onPOITap: (poi) => _navigateToPOIDetail(context, poi),
            ),
          ),

        // POI list header
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '推荐地点',
                  style: AppTextStyles.subtitle1.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  '${state.filteredPOIs.length}个结果',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        ),

        // POI list
        if (state.filteredPOIs.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.search_off,
                    size: 64,
                    color: AppColors.textTertiary.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    '暂无匹配的地点',
                    style: AppTextStyles.subtitle1.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          )
        else
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final poi = state.filteredPOIs[index];
                return POICard(
                  poi: poi,
                  onTap: () => _navigateToPOIDetail(context, poi),
                );
              },
              childCount: state.filteredPOIs.length,
            ),
          ),

        // Bottom padding
        const SliverToBoxAdapter(
          child: SizedBox(height: 24),
        ),
      ],
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          IconButton(
            onPressed: () => context.pop(),
            icon: const Icon(Icons.arrow_back_ios),
            color: AppColors.textPrimary,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '探索发现',
                  style: AppTextStyles.headline6.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '找到值得去的好地方',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: TextField(
        controller: _searchController,
        onChanged: (value) {
          context.read<GuardianBloc>().add(POISearchRequested(value));
        },
        decoration: InputDecoration(
          hintText: '搜索餐厅、景点、活动...',
          hintStyle: AppTextStyles.bodyText2.copyWith(
            color: AppColors.textTertiary,
          ),
          prefixIcon: const Icon(
            Icons.search,
            color: AppColors.textTertiary,
          ),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    context.read<GuardianBloc>().add(const POISearchRequested(''));
                  },
                )
              : null,
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
    );
  }

  Future<void> _navigateToPOIDetail(BuildContext context, POI poi) async {
    await context.push(Routes.poiDetail(poi.id));
    if (context.mounted) {
      context.read<GuardianBloc>().add(const GuardianLoadRequested());
    }
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: AppColors.primary),
          SizedBox(height: 16),
          Text(
            '正在加载...',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: AppColors.error,
            ),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
