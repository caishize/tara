import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/property.dart';
import '../bloc/housing_bloc.dart';
import '../widgets/add_property_sheet.dart';
import '../widgets/add_appliance_sheet.dart';

class HousingPage extends StatelessWidget {
  const HousingPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/family');
            }
          },
        ),
        title: Text('房产管理', style: AppTextStyles.headline5),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: AppColors.textPrimary),
            onPressed: () {
              context.read<HousingBloc>().add(const HousingLoadRequested());
            },
          ),
        ],
      ),
      body: BlocConsumer<HousingBloc, HousingState>(
        listener: (context, state) {
          if (state is HousingError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          } else if (state is HousingOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.success,
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is HousingLoading || state is HousingInitial) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is HousingError) {
            return _buildErrorState(context, state.message);
          }

          if (state is HousingLoaded) {
            if (state.properties.isEmpty) {
              return _buildEmptyState(context);
            }
            return _buildContent(context, state);
          }

          return const SizedBox.shrink();
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddPropertySheet(context),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: AppColors.error.withValues(alpha: 0.5)),
            const SizedBox(height: 16),
            Text(
              '加载失败',
              style: AppTextStyles.headline6,
            ),
            const SizedBox(height: 8),
            Text(
              message,
              style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () {
                context.read<HousingBloc>().add(const HousingLoadRequested());
              },
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.home_outlined, size: 80, color: AppColors.primary.withValues(alpha: 0.3)),
            const SizedBox(height: 20),
            Text('还没有添加房产', style: AppTextStyles.headline6),
            const SizedBox(height: 8),
            Text(
              '点击下方按钮添加您的第一处房产',
              style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _showAddPropertySheet(context),
              icon: const Icon(Icons.add),
              label: const Text('添加房产'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, HousingLoaded state) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        // Property selector if multiple properties
        if (state.properties.length > 1)
          _buildPropertySelector(context, state),

        // Selected property card
        if (state.selectedProperty != null) ...[
          _buildPropertyCard(context, state.selectedProperty!),
          const SizedBox(height: 20),

          // Mortgage info (if applicable)
          if (state.selectedProperty!.mortgageAmount != null)
            _buildMortgageInfo(state.selectedProperty!),
          if (state.selectedProperty!.mortgageAmount != null)
            const SizedBox(height: 20),

          // Property fee info (if applicable)
          if (state.selectedProperty!.propertyFeeAmount != null)
            _buildPropertyFeeInfo(state.selectedProperty!),
          if (state.selectedProperty!.propertyFeeAmount != null)
            const SizedBox(height: 20),

          // Appliances section
          _buildAppliancesSection(context, state),
        ],
      ],
    );
  }

  Widget _buildPropertySelector(BuildContext context, HousingLoaded state) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: state.properties.map((property) {
            final isSelected = property.id == state.selectedProperty?.id;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(
                  property.address.length > 20
                      ? '${property.address.substring(0, 20)}...'
                      : property.address,
                ),
                selected: isSelected,
                onSelected: (selected) {
                  if (selected) {
                    context.read<HousingBloc>().add(PropertySelected(property.id));
                  }
                },
                selectedColor: AppColors.primary.withValues(alpha: 0.2),
                labelStyle: TextStyle(
                  color: isSelected ? AppColors.primary : AppColors.textSecondary,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildPropertyCard(BuildContext context, Property property) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [AppColors.shadowLight],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            height: 140,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Stack(
              children: [
                const Center(
                  child: Icon(Icons.home, color: Colors.white, size: 56),
                ),
                Positioned(
                  top: 8,
                  right: 8,
                  child: PopupMenuButton<String>(
                    icon: const Icon(Icons.more_vert, color: Colors.white),
                    onSelected: (value) {
                      if (value == 'delete') {
                        _showDeleteConfirmation(context, property);
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'delete',
                        child: Row(
                          children: [
                            Icon(Icons.delete_outline, color: AppColors.error),
                            SizedBox(width: 8),
                            Text('删除房产'),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        property.address,
                        style: AppTextStyles.subtitle1,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    if (property.areaSqm != null)
                      _buildPropertyInfo('面积', '${property.areaSqm!.toStringAsFixed(0)}㎡'),
                    if (property.purchaseDate != null)
                      _buildPropertyInfo('入住', property.purchaseDate!.year.toString()),
                    if (property.mortgageBank != null)
                      _buildPropertyInfo('贷款银行', property.mortgageBank!),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPropertyInfo(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: AppTextStyles.bodyText1.copyWith(
              fontWeight: FontWeight.w600,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          Text(
            label,
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMortgageInfo(Property property) {
    final mortgageDay = property.mortgageDay ?? 1;
    final now = DateTime.now();
    final nextPaymentDate = DateTime(
      now.day > mortgageDay ? now.year + (now.month == 12 ? 1 : 0) : now.year,
      now.day > mortgageDay ? (now.month == 12 ? 1 : now.month + 1) : now.month,
      mortgageDay,
    );
    final formattedDate = '${nextPaymentDate.year}-${nextPaymentDate.month.toString().padLeft(2, '0')}-${nextPaymentDate.day.toString().padLeft(2, '0')}';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_balance, size: 20, color: AppColors.primary),
              const SizedBox(width: 8),
              Text('贷款信息', style: AppTextStyles.subtitle1),
              const Spacer(),
              if (property.mortgageBank != null)
                Text(
                  property.mortgageBank!,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildMortgageMetric(
                  '贷款金额',
                  property.displayMortgageAmount,
                  '',
                  AppColors.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMortgageMetric(
                  '还款日',
                  '每月$mortgageDay日',
                  '',
                  AppColors.secondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '下次还款: $formattedDate',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPropertyFeeInfo(Property property) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.receipt_long, size: 20, color: AppColors.warning),
              const SizedBox(width: 8),
              Text('物业费', style: AppTextStyles.subtitle1),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildMortgageMetric(
                  '费用金额',
                  property.displayPropertyFee,
                  '',
                  AppColors.warning,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMortgageMetric(
                  '缴费周期',
                  property.displayFeeCycle,
                  '',
                  AppColors.info,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMortgageMetric(
    String label,
    String value,
    String unit,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: AppTextStyles.caption.copyWith(color: color),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Text(
                  value,
                  style: AppTextStyles.bodyText1.copyWith(
                    color: color,
                    fontWeight: FontWeight.bold,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (unit.isNotEmpty)
                Text(
                  unit,
                  style: AppTextStyles.caption.copyWith(color: color),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAppliancesSection(BuildContext context, HousingLoaded state) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.devices_other, size: 20, color: AppColors.secondary),
              const SizedBox(width: 8),
              Text('家电设备', style: AppTextStyles.subtitle1),
              const Spacer(),
              TextButton.icon(
                onPressed: () => _showAddApplianceSheet(context, state.selectedProperty!.id),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (state.appliances.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    Icon(Icons.devices_other, size: 48, color: AppColors.textSecondary.withValues(alpha: 0.3)),
                    const SizedBox(height: 8),
                    Text(
                      '暂无家电设备',
                      style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            )
          else
            ...state.appliances.map((appliance) => _buildApplianceItem(appliance)),
        ],
      ),
    );
  }

  Widget _buildApplianceItem(Appliance appliance) {
    final bool needsMaintenance = appliance.needsMaintenance;
    final bool warrantyExpired = appliance.warrantyExpired;

    Color statusColor;
    String statusText;

    if (needsMaintenance) {
      statusColor = AppColors.error;
      statusText = '需维护';
    } else if (warrantyExpired) {
      statusColor = AppColors.warning;
      statusText = '保修已过';
    } else {
      statusColor = AppColors.success;
      statusText = '正常';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.devices, color: statusColor, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        appliance.name,
                        style: AppTextStyles.bodyText2,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (appliance.brand != null)
                      Text(
                        appliance.brand!,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    if (appliance.lastMaintenanceDate != null)
                      Text(
                        '上次维护: ${_formatDate(appliance.lastMaintenanceDate!)}',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      )
                    else if (appliance.purchaseDate != null)
                      Text(
                        '购买: ${_formatDate(appliance.purchaseDate!)}',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              statusText,
              style: AppTextStyles.caption.copyWith(
                color: statusColor,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  void _showAddPropertySheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<HousingBloc>(),
        child: const AddPropertySheet(),
      ),
    );
  }

  void _showAddApplianceSheet(BuildContext context, String propertyId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<HousingBloc>(),
        child: AddApplianceSheet(propertyId: propertyId),
      ),
    );
  }

  void _showDeleteConfirmation(BuildContext context, Property property) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除"${property.address}"吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              context.read<HousingBloc>().add(PropertyDeleteRequested(property.id));
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }
}
