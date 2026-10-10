import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/vaccine.dart';

class VaccineSchedule extends StatefulWidget {
  final List<VaccineRecord> vaccines;
  final Function(VaccineRecord vaccine, VaccineStatus status) onUpdateStatus;

  const VaccineSchedule({
    super.key,
    required this.vaccines,
    required this.onUpdateStatus,
  });

  @override
  State<VaccineSchedule> createState() => _VaccineScheduleState();
}

class _VaccineScheduleState extends State<VaccineSchedule> {
  VaccineStatus? _selectedStatus;

  @override
  Widget build(BuildContext context) {
    final filteredVaccines = _selectedStatus == null
        ? widget.vaccines
        : widget.vaccines.where((v) => v.status == _selectedStatus).toList();

    // 按状态排序：过期 > 待接种 > 已完成
    filteredVaccines.sort((a, b) {
      final statusOrder = {
        VaccineStatus.overdue: 0,
        VaccineStatus.scheduled: 1,
        VaccineStatus.completed: 2,
        VaccineStatus.skipped: 3,
      };
      final orderCompare = statusOrder[a.status]!.compareTo(statusOrder[b.status]!);
      if (orderCompare != 0) return orderCompare;
      return a.scheduledDate.compareTo(b.scheduledDate);
    });

    return Column(
      children: [
        _buildStatusFilter(),
        _buildSummaryBar(),
        Expanded(
          child: filteredVaccines.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  padding: const EdgeInsets.all(20),
                  itemCount: filteredVaccines.length,
                  itemBuilder: (context, index) {
                    return _buildVaccineCard(filteredVaccines[index]);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildStatusFilter() {
    return Container(
      height: 50,
      margin: const EdgeInsets.only(top: 8),
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          _buildStatusChip(null, '全部', Icons.list),
          _buildStatusChip(VaccineStatus.scheduled, '待接种', Icons.schedule),
          _buildStatusChip(VaccineStatus.completed, '已完成', Icons.check_circle),
          _buildStatusChip(VaccineStatus.overdue, '已过期', Icons.warning),
        ],
      ),
    );
  }

  Widget _buildStatusChip(VaccineStatus? status, String label, IconData icon) {
    final isSelected = _selectedStatus == status;
    final count = status == null
        ? widget.vaccines.length
        : widget.vaccines.where((v) => v.status == status).length;
    final color = _getStatusColor(status);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: GestureDetector(
        onTap: () => setState(() => _selectedStatus = status),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? color : Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isSelected ? color : AppColors.divider,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                size: 16,
                color: isSelected ? Colors.white : color,
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: AppTextStyles.caption.copyWith(
                  color: isSelected ? Colors.white : AppColors.textPrimary,
                ),
              ),
              if (count > 0) ...[
                const SizedBox(width: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? Colors.white.withValues(alpha: 0.2)
                        : color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '$count',
                    style: AppTextStyles.caption.copyWith(
                      fontSize: 10,
                      color: isSelected ? Colors.white : color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryBar() {
    final scheduled = widget.vaccines.where((v) => v.status == VaccineStatus.scheduled).length;
    final completed = widget.vaccines.where((v) => v.status == VaccineStatus.completed).length;
    final overdue = widget.vaccines.where((v) => v.status == VaccineStatus.overdue).length;
    final total = widget.vaccines.length;

    if (total == 0) return const SizedBox.shrink();

    final completionRate = total > 0 ? (completed / total * 100).toInt() : 0;

    return Container(
      margin: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Text('接种进度', style: AppTextStyles.bodyText2),
              const Spacer(),
              Text(
                '$completionRate%',
                style: AppTextStyles.subtitle1.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: completed / total,
              backgroundColor: AppColors.inputBackground,
              valueColor: const AlwaysStoppedAnimation<Color>(AppColors.success),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildSummaryItem('待接种', scheduled, AppColors.primary),
              _buildSummaryItem('已完成', completed, AppColors.success),
              if (overdue > 0) _buildSummaryItem('已过期', overdue, AppColors.error),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryItem(String label, int count, Color color) {
    return Column(
      children: [
        Text(
          '$count',
          style: AppTextStyles.headline5.copyWith(
            color: color,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }

  Widget _buildVaccineCard(VaccineRecord vaccine) {
    final color = Color(vaccine.statusColorValue);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: vaccine.isOverdue
            ? Border.all(color: AppColors.error.withValues(alpha: 0.5), width: 1.5)
            : null,
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      vaccine.statusIcon,
                      style: const TextStyle(fontSize: 24),
                    ),
                  ),
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
                              vaccine.vaccineName,
                              style: AppTextStyles.subtitle1.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              vaccine.statusName,
                              style: AppTextStyles.caption.copyWith(
                                color: color,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '第${vaccine.doseNumber}针 · ${_formatDate(vaccine.scheduledDate)}',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      if (vaccine.isScheduled || vaccine.isOverdue) ...[
                        const SizedBox(height: 4),
                        Text(
                          vaccine.daysUntilDisplay,
                          style: AppTextStyles.caption.copyWith(
                            color: vaccine.isOverdue ? AppColors.error : AppColors.primary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),

          // 操作按钮
          if (vaccine.isScheduled || vaccine.isOverdue)
            Container(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => _showCompleteDialog(vaccine),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.success,
                        side: const BorderSide(color: AppColors.success),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      child: const Text('标记已接种'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  OutlinedButton(
                    onPressed: () => widget.onUpdateStatus(vaccine, VaccineStatus.skipped),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.textSecondary,
                      side: const BorderSide(color: AppColors.divider),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    child: const Text('跳过'),
                  ),
                ],
              ),
            ),

          // 已完成信息
          if (vaccine.isCompleted && vaccine.actualDate != null)
            Container(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Row(
                children: [
                  const Icon(Icons.check_circle, size: 16, color: AppColors.success),
                  const SizedBox(width: 6),
                  Text(
                    '已于 ${_formatDate(vaccine.actualDate!)} 接种',
                    style: AppTextStyles.caption.copyWith(color: AppColors.success),
                  ),
                  if (vaccine.location?.isNotEmpty ?? false) ...[
                    const SizedBox(width: 12),
                    const Icon(Icons.location_on, size: 14, color: AppColors.textTertiary),
                    const SizedBox(width: 4),
                    Text(
                      vaccine.location!,
                      style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.vaccines_outlined, size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text('暂无疫苗记录', style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            '疫苗信息将从后台同步',
            style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  void _showCompleteDialog(VaccineRecord vaccine) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('确认接种'),
        content: Text('确认 ${vaccine.fullName} 已完成接种？'),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              widget.onUpdateStatus(vaccine, VaccineStatus.completed);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.success,
              foregroundColor: Colors.white,
            ),
            child: const Text('确认'),
          ),
        ],
      ),
    );
  }

  Color _getStatusColor(VaccineStatus? status) {
    if (status == null) return AppColors.primary;
    switch (status) {
      case VaccineStatus.scheduled:
        return AppColors.primary;
      case VaccineStatus.completed:
        return AppColors.success;
      case VaccineStatus.overdue:
        return AppColors.error;
      case VaccineStatus.skipped:
        return AppColors.textSecondary;
    }
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }
}
