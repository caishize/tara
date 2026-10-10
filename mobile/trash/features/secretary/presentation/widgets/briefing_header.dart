import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/daily_briefing.dart';

/// Header widget for the daily briefing page.
class BriefingHeader extends StatelessWidget {
  final DailyBriefing briefing;

  const BriefingHeader({
    super.key,
    required this.briefing,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(24),
          bottomRight: Radius.circular(24),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top bar with title and date
            Row(
              children: [
                const Text(
                  '今日简报',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: Colors.white70,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    briefing.formattedDate,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
                  ),
                ),
                const Spacer(),
                _buildTimeIcon(),
              ],
            ),
            const SizedBox(height: 24),

            // Greeting
            Text(
              briefing.greeting,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w600,
                color: Colors.white,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 16),

            // PRD-style categorized overview: 📋 今日必做, 💝 人情提醒, 🏠 家庭状况
            _buildCategorizedOverview(),
          ],
        ),
      ),
    );
  }

  /// PRD-style categorized overview with 📋 今日必做, 💝 人情提醒, 🏠 家庭状况
  Widget _buildCategorizedOverview() {
    // Categorize events
    final todoEvents = briefing.todayEvents.where((e) =>
        e.eventType == 'meeting' ||
        e.eventType == 'work' ||
        e.eventType == 'task' ||
        e.eventType == 'general').toList();

    final favorEvents = briefing.todayEvents.where((e) =>
        e.eventType == 'birthday' ||
        e.eventType == 'anniversary' ||
        e.eventType == 'wedding_anniversary' ||
        e.eventType == 'gift').toList();

    final familyEvents = briefing.todayEvents.where((e) =>
        e.eventType == 'family' ||
        e.eventType == 'household' ||
        e.eventType == 'health' ||
        e.eventType == 'vaccine' ||
        e.eventType == 'checkup').toList();

    // Count reminders for favor category
    final favorReminders = briefing.preparationReminders.where((r) =>
        r.contains('生日') ||
        r.contains('礼物') ||
        r.contains('纪念日') ||
        r.contains('约') ||
        r.contains('见面')).length;

    // Count reminders for family category
    final familyReminders = briefing.preparationReminders.where((r) =>
        r.contains('家') ||
        r.contains('滤芯') ||
        r.contains('维修') ||
        r.contains('孩子') ||
        r.contains('老人')).length;

    final todoCount = todoEvents.length + (briefing.todayEventCount - todoEvents.length - favorEvents.length - familyEvents.length).clamp(0, 99);
    final favorCount = favorEvents.length + favorReminders;
    final familyCount = familyEvents.length + familyReminders;

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        if (todoCount > 0)
          _buildCategoryChip('📋', '今日必做', todoCount),
        if (favorCount > 0)
          _buildCategoryChip('💝', '人情提醒', favorCount),
        if (familyCount > 0)
          _buildCategoryChip('🏠', '家庭状况', familyCount),
        if (todoCount == 0 && favorCount == 0 && familyCount == 0)
          _buildCategoryChip('🌴', '今日轻松', 0, showCount: false),
      ],
    );
  }

  Widget _buildCategoryChip(String emoji, String label, int count, {bool showCount = true}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 16)),
          const SizedBox(width: 6),
          Text(
            showCount ? '$label$count项' : label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimeIcon() {
    final hour = DateTime.now().hour;
    IconData icon;
    if (hour < 6 || hour >= 20) {
      icon = Icons.nightlight_round;
    } else if (hour < 12) {
      icon = Icons.wb_sunny;
    } else if (hour < 18) {
      icon = Icons.wb_sunny_outlined;
    } else {
      icon = Icons.nights_stay;
    }
    return Icon(icon, color: Colors.white70, size: 24);
  }
}
