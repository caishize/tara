import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/unified_event.dart';

/// Bottom sheet that displays full details for a UnifiedEvent
/// when no dedicated detail page is available.
class EventDetailSheet extends StatelessWidget {
  final UnifiedEvent event;

  const EventDetailSheet({super.key, required this.event});

  static Future<void> show(BuildContext context, UnifiedEvent event) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.55,
        maxChildSize: 0.85,
        minChildSize: 0.3,
        builder: (_, __) => EventDetailSheet(event: event),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          _buildHandle(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              children: [
                _buildHeader(),
                const SizedBox(height: 16),
                _buildInfoSection(),
                if (event.description != null) ...[
                  const SizedBox(height: 16),
                  _buildDescription(),
                ],
                if (event.aiInsights.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _buildAiInsights(),
                ],
                if (event.sourceData.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _buildSourceDetails(),
                ],
                const SizedBox(height: 32),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey.shade300,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: event.color.withAlpha((0.1 * 255).round()),
            borderRadius: BorderRadius.circular(12),
          ),
          alignment: Alignment.center,
          child: Text(
            event.icon,
            style: const TextStyle(fontSize: 24),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                event.title,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: event.color.withAlpha((0.1 * 255).round()),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  event.sourceName,
                  style: TextStyle(
                    fontSize: 12,
                    color: event.color,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: _countdownColor.withAlpha((0.1 * 255).round()),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Text(
            event.countdownDisplay,
            style: AppTextStyles.caption.copyWith(
              color: _countdownColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoSection() {
    return Column(
      children: [
        if (event.dateTime != null)
          _buildInfoRow(Icons.schedule, '时间', _formatDateRange()),
        if (event.durationDays != null && event.durationDays! > 1)
          _buildInfoRow(Icons.timelapse, '时长', '${event.durationDays}天'),
        if (event.location != null)
          _buildInfoRow(Icons.location_on_outlined, '地点', event.location!),
        if (event.memberName != null)
          _buildInfoRow(Icons.person_outline, '相关人', event.memberName!),
      ],
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.textTertiary),
          const SizedBox(width: 10),
          SizedBox(
            width: 48,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDescription() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        event.description!,
        style: const TextStyle(
          fontSize: 14,
          color: AppColors.textPrimary,
          height: 1.5,
        ),
      ),
    );
  }

  Widget _buildAiInsights() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withAlpha((0.06 * 255).round()),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, size: 16, color: AppColors.primary),
              SizedBox(width: 6),
              Text(
                'AI 洞察',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...event.aiInsights.map(
            (insight) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• ', style: TextStyle(color: AppColors.textSecondary)),
                  Expanded(
                    child: Text(
                      insight,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                        height: 1.5,
                      ),
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

  Widget _buildSourceDetails() {
    final details = <MapEntry<String, String>>[];

    final sourceData = event.sourceData;
    // Extract human-readable details from sourceData
    if (sourceData['note'] != null) {
      details.add(MapEntry('备注', sourceData['note'].toString()));
    }
    if (sourceData['category'] != null) {
      details.add(MapEntry('分类', sourceData['category'].toString()));
    }
    if (sourceData['provider'] != null) {
      details.add(MapEntry('来源', sourceData['provider'].toString()));
    }
    if (sourceData['confirmation_number'] != null) {
      details.add(MapEntry('确认号', sourceData['confirmation_number'].toString()));
    }

    if (details.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '详细信息',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        ...details.map(
          (entry) => _buildInfoRow(
            Icons.info_outline,
            entry.key,
            entry.value,
          ),
        ),
      ],
    );
  }

  String _formatDateRange() {
    if (event.dateTime == null) return '';
    final dateFormat = DateFormat('M月d日 HH:mm');
    final dateOnlyFormat = DateFormat('M月d日');
    final localStart = event.dateTime!.toLocal();

    if (event.endDateTime != null &&
        event.endDateTime!.difference(event.dateTime!).inDays > 0) {
      final localEnd = event.endDateTime!.toLocal();
      return '${dateOnlyFormat.format(localStart)} - ${dateOnlyFormat.format(localEnd)}';
    }

    if (event.isAllDay) {
      return dateOnlyFormat.format(localStart);
    }

    return dateFormat.format(localStart);
  }

  Color get _countdownColor {
    if (event.isOverdue) return AppColors.textTertiary;
    if (event.isToday) return AppColors.error;
    if (event.daysUntil <= 7) return AppColors.warning;
    return AppColors.primary;
  }
}
