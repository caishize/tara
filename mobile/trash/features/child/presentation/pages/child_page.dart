import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

class ChildPage extends StatelessWidget {
  const ChildPage({super.key});

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
              context.go('/dashboard');
            }
          },
        ),
        title: Text('宝宝成长', style: AppTextStyles.headline5),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildBabyProfile(),
          const SizedBox(height: 20),
          _buildGrowthRecord(),
          const SizedBox(height: 20),
          _buildMilestones(),
          const SizedBox(height: 20),
          _buildVaccinationSchedule(),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add_a_photo, color: Colors.white),
      ),
    );
  }

  Widget _buildBabyProfile() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFF9A9E), Color(0xFFFECFEF)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(Icons.child_care, color: Colors.white, size: 40),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '小宝宝',
                  style: AppTextStyles.headline5.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  '18个月 · 女宝宝',
                  style: AppTextStyles.bodyText2.copyWith(
                    color: Colors.white.withValues(alpha: 0.9),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '生日: 2023-06-15',
                  style: AppTextStyles.caption.copyWith(
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.edit, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
    );
  }

  Widget _buildGrowthRecord() {
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
              Text('成长记录', style: AppTextStyles.subtitle1),
              const Spacer(),
              TextButton(
                onPressed: () {},
                child: const Text('添加记录'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _buildGrowthMetric('身高', '82', 'cm', AppColors.primary)),
              const SizedBox(width: 12),
              Expanded(child: _buildGrowthMetric('体重', '10.5', 'kg', AppColors.secondary)),
              const SizedBox(width: 12),
              Expanded(child: _buildGrowthMetric('头围', '46', 'cm', AppColors.accent1)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildGrowthMetric(String label, String value, String unit, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: AppTextStyles.caption.copyWith(color: color),
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                value,
                style: AppTextStyles.headline5.copyWith(
                  color: color,
                  fontWeight: FontWeight.bold,
                ),
              ),
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

  Widget _buildMilestones() {
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
          Text('成长里程碑', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          _buildMilestoneItem('第一次微笑', '2023-07-20', true),
          _buildMilestoneItem('第一次翻身', '2023-10-15', true),
          _buildMilestoneItem('第一次坐稳', '2023-12-01', true),
          _buildMilestoneItem('第一次走路', '2024-08-20', true),
          _buildMilestoneItem('第一次说话', '2024-10-15', true),
        ],
      ),
    );
  }

  Widget _buildMilestoneItem(String title, String date, bool achieved) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: achieved ? AppColors.success : AppColors.textTertiary,
              shape: BoxShape.circle,
            ),
            child: Icon(
              achieved ? Icons.check : Icons.circle_outlined,
              color: Colors.white,
              size: 14,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(title, style: AppTextStyles.bodyText2),
          ),
          Text(
            date,
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVaccinationSchedule() {
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
              Text('疫苗接种', style: AppTextStyles.subtitle1),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '已接种 12/15',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.success,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _buildVaccineItem('麻腮风疫苗', '待接种', '2025-01-15', false),
          _buildVaccineItem('乙肝疫苗加强针', '待接种', '2025-03-20', false),
          _buildVaccineItem('水痘疫苗', '待接种', '2025-06-15', false),
        ],
      ),
    );
  }

  Widget _buildVaccineItem(String name, String status, String date, bool completed) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: completed
            ? AppColors.success.withValues(alpha: 0.05)
            : AppColors.warning.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            completed ? Icons.check_circle : Icons.schedule,
            color: completed ? AppColors.success : AppColors.warning,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: AppTextStyles.bodyText2),
                Text(
                  '预约: $date',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Text(
            status,
            style: AppTextStyles.caption.copyWith(
              color: completed ? AppColors.success : AppColors.warning,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
