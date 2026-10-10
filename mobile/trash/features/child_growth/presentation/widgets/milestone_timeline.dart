import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/milestone.dart';

class MilestoneTimeline extends StatefulWidget {
  final List<Milestone> milestones;
  final VoidCallback onAddMilestone;

  const MilestoneTimeline({
    super.key,
    required this.milestones,
    required this.onAddMilestone,
  });

  @override
  State<MilestoneTimeline> createState() => _MilestoneTimelineState();
}

class _MilestoneTimelineState extends State<MilestoneTimeline> {
  MilestoneType? _selectedType;

  @override
  Widget build(BuildContext context) {
    final filteredMilestones = _selectedType == null
        ? widget.milestones
        : widget.milestones.where((m) => m.type == _selectedType).toList();

    return Column(
      children: [
        _buildTypeFilter(),
        Expanded(
          child: filteredMilestones.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  padding: const EdgeInsets.all(20),
                  itemCount: filteredMilestones.length,
                  itemBuilder: (context, index) {
                    return _buildTimelineItem(
                      filteredMilestones[index],
                      isFirst: index == 0,
                      isLast: index == filteredMilestones.length - 1,
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildTypeFilter() {
    return Container(
      height: 50,
      margin: const EdgeInsets.only(top: 8),
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          _buildTypeChip(null, '全部', '🎯'),
          ...MilestoneType.values.map((type) => _buildTypeChip(
            type,
            _getTypeName(type),
            _getTypeIcon(type),
          )),
        ],
      ),
    );
  }

  Widget _buildTypeChip(MilestoneType? type, String label, String icon) {
    final isSelected = _selectedType == type;
    final count = type == null
        ? widget.milestones.length
        : widget.milestones.where((m) => m.type == type).length;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: GestureDetector(
        onTap: () => setState(() => _selectedType = type),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? _getTypeColor(type) : Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isSelected ? _getTypeColor(type) : AppColors.divider,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(icon, style: const TextStyle(fontSize: 14)),
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
                        : _getTypeColor(type).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '$count',
                    style: AppTextStyles.caption.copyWith(
                      fontSize: 10,
                      color: isSelected ? Colors.white : _getTypeColor(type),
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

  Widget _buildTimelineItem(Milestone milestone, {bool isFirst = false, bool isLast = false}) {
    final color = Color(milestone.typeColorValue);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 时间线
          SizedBox(
            width: 60,
            child: Column(
              children: [
                if (!isFirst)
                  Expanded(
                    child: Container(width: 2, color: AppColors.divider),
                  ),
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                    border: Border.all(color: color, width: 2),
                  ),
                  child: Center(
                    child: Text(
                      milestone.typeIcon,
                      style: const TextStyle(fontSize: 18),
                    ),
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(width: 2, color: AppColors.divider),
                  ),
              ],
            ),
          ),

          // 卡片内容
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [AppColors.shadowLight],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          milestone.title,
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
                          milestone.typeName,
                          style: AppTextStyles.caption.copyWith(
                            color: color,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Icon(Icons.calendar_today, size: 14, color: AppColors.textTertiary),
                      const SizedBox(width: 4),
                      Text(
                        _formatDate(milestone.achievedDate),
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      if (milestone.ageMonths != null) ...[
                        const SizedBox(width: 12),
                        const Icon(Icons.child_care, size: 14, color: AppColors.textTertiary),
                        const SizedBox(width: 4),
                        Text(
                          milestone.ageDisplay,
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ],
                  ),
                  if (milestone.description?.isNotEmpty ?? false) ...[
                    const SizedBox(height: 8),
                    Text(
                      milestone.description!,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                  if (milestone.developmentStatus != '已达成') ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: milestone.developmentStatus == '提前发育'
                            ? AppColors.success.withValues(alpha: 0.1)
                            : AppColors.warning.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        milestone.developmentStatus,
                        style: AppTextStyles.caption.copyWith(
                          color: milestone.developmentStatus == '提前发育'
                              ? AppColors.success
                              : AppColors.warning,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                  if (milestone.notes?.isNotEmpty ?? false) ...[
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppColors.inputBackground,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.sticky_note_2, size: 14, color: AppColors.textTertiary),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              milestone.notes!,
                              style: AppTextStyles.caption.copyWith(
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
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
          const Icon(Icons.emoji_events_outlined, size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text('暂无里程碑记录', style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            '记录宝宝的每一个成长瞬间',
            style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: widget.onAddMilestone,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            icon: const Icon(Icons.add),
            label: const Text('添加第一个里程碑'),
          ),
        ],
      ),
    );
  }

  String _getTypeName(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return '运动';
      case MilestoneType.cognitive:
        return '认知';
      case MilestoneType.language:
        return '语言';
      case MilestoneType.social:
        return '社交';
      case MilestoneType.emotional:
        return '情感';
    }
  }

  String _getTypeIcon(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return '🏃';
      case MilestoneType.cognitive:
        return '🧠';
      case MilestoneType.language:
        return '🗣️';
      case MilestoneType.social:
        return '👋';
      case MilestoneType.emotional:
        return '💕';
    }
  }

  Color _getTypeColor(MilestoneType? type) {
    if (type == null) return AppColors.primary;
    switch (type) {
      case MilestoneType.physical:
        return const Color(0xFF4CAF50);
      case MilestoneType.cognitive:
        return const Color(0xFF2196F3);
      case MilestoneType.language:
        return const Color(0xFFFF9800);
      case MilestoneType.social:
        return const Color(0xFF9C27B0);
      case MilestoneType.emotional:
        return const Color(0xFFE91E63);
    }
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }
}
