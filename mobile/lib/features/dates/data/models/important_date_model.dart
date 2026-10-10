import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/important_date.dart';

class ImportantDateModel extends ImportantDate {
  const ImportantDateModel({
    required super.id,
    required super.title,
    super.description,
    required super.date,
    required super.dateType,
    super.calendarType,
    super.lunarMonth,
    super.lunarDay,
    super.isRecurring,
    super.memberId,
    super.memberName,
    super.reminderDays,
    required super.createdAt,
    super.updatedAt,
  });

  factory ImportantDateModel.fromJson(Map<String, dynamic> json) {
    // Handle different date field names from API
    final dateString = json['date'] ?? json['date_value'] ?? json['event_date'];
    DateTime parsedDate;
    try {
      parsedDate = dateString != null
          ? TimezoneUtils.parseApiTime(dateString.toString())
          : DateTime.now().toUtc();
    } catch (e) {
      parsedDate = DateTime.now().toUtc();
    }

    return ImportantDateModel(
      id: json['id']?.toString() ?? '',
      title: json['title'] ?? json['name'] ?? '',
      description: json['description'],
      date: parsedDate,
      dateType: _parseDateType(json['date_type'] ?? json['type']),
      calendarType: _parseCalendarType(json['calendar_type']),
      lunarMonth: json['lunar_month'] as int?,
      lunarDay: json['lunar_day'] as int?,
      isRecurring: json['is_recurring'] ?? true,
      memberId: json['member_id']?.toString(),
      memberName: json['member_name'],
      reminderDays: _parseReminderDays(json['reminder_days'] ?? json['reminder_offsets']),
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
      updatedAt: json['updated_at'] != null
          ? TimezoneUtils.parseApiTime(json['updated_at'])
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'notes': description,
      'solar_date': TimezoneUtils.formatDateForApi(date),
      'date_type': dateType.name,
      'is_lunar': calendarType == CalendarType.lunar,
      'lunar_month': lunarMonth,
      'lunar_day': lunarDay,
      'is_recurring': isRecurring,
      'member_id': memberId,
      'reminder_offsets': reminderDays,
    };
  }

  static DateType _parseDateType(String? type) {
    if (type == null) return DateType.custom;
    return DateType.values.firstWhere(
      (e) => e.name.toLowerCase() == type.toLowerCase(),
      orElse: () => DateType.custom,
    );
  }

  static CalendarType _parseCalendarType(String? type) {
    if (type == null) return CalendarType.solar;
    return CalendarType.values.firstWhere(
      (e) => e.name.toLowerCase() == type.toLowerCase(),
      orElse: () => CalendarType.solar,
    );
  }

  static List<int> _parseReminderDays(dynamic days) {
    if (days == null) return [0, 1, 7];
    if (days is List) {
      return days.map((e) => int.tryParse(e.toString()) ?? 0).toList();
    }
    return [0, 1, 7];
  }

  static ImportantDateModel fromEntity(ImportantDate entity) {
    return ImportantDateModel(
      id: entity.id,
      title: entity.title,
      description: entity.description,
      date: entity.date,
      dateType: entity.dateType,
      calendarType: entity.calendarType,
      lunarMonth: entity.lunarMonth,
      lunarDay: entity.lunarDay,
      isRecurring: entity.isRecurring,
      memberId: entity.memberId,
      memberName: entity.memberName,
      reminderDays: entity.reminderDays,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}
