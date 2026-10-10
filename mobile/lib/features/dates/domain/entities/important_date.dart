import 'package:equatable/equatable.dart';
import '../../../../shared/utils/lunar_utils.dart';

enum DateType {
  birthday,      // 生日
  anniversary,   // 纪念日
  holiday,       // 节日
  memorial,      // 祭日
  custom,        // 自定义
}

enum CalendarType {
  solar,         // 公历
  lunar,         // 农历
}

class ImportantDate extends Equatable {
  final String id;
  final String title;
  final String? description;
  final DateTime date;           // 公历日期（用于存储和排序）
  final DateType dateType;
  final CalendarType calendarType;
  final int? lunarMonth;         // 农历月份（仅当 calendarType 为 lunar 时有效）
  final int? lunarDay;           // 农历日期（仅当 calendarType 为 lunar 时有效）
  final bool isRecurring;
  final String? memberId;
  final String? memberName;
  final List<int> reminderDays;  // 提前多少天提醒
  final DateTime createdAt;
  final DateTime? updatedAt;

  const ImportantDate({
    required this.id,
    required this.title,
    this.description,
    required this.date,
    required this.dateType,
    this.calendarType = CalendarType.solar,
    this.lunarMonth,
    this.lunarDay,
    this.isRecurring = true,
    this.memberId,
    this.memberName,
    this.reminderDays = const [0, 1, 7],
    required this.createdAt,
    this.updatedAt,
  });

  /// 获取下次日期
  DateTime get nextOccurrence {
    // 农历日期需要特殊处理，即使不是周期性的也要计算正确的公历日期
    // 因为数据库中可能存储了多年的农历节日记录，每条记录的 solar_date 不同
    if (calendarType == CalendarType.lunar) {
      // If lunar month/day are available, use them directly
      if (lunarMonth != null && lunarDay != null) {
        return LunarUtils.getNextLunarOccurrence(lunarMonth!, lunarDay!);
      }
      // Otherwise, derive lunar date from the stored solar date
      // This handles cases where the database stores lunar holidays without lunar_month/lunar_day
      final derivedLunarMonth = effectiveLunarMonth;
      final derivedLunarDay = effectiveLunarDay;
      return LunarUtils.getNextLunarOccurrence(derivedLunarMonth, derivedLunarDay);
    }

    // Convert stored date to local time to extract correct date components
    // This is important because the API may return UTC times (e.g., 2026-02-03T16:00:00Z)
    // which in UTC+8 would be Feb 4 00:00 local, not Feb 3
    final localDate = date.toLocal();

    if (!isRecurring) return localDate;

    final now = DateTime.now();

    // 公历日期 - use local date components
    var next = DateTime(now.year, localDate.month, localDate.day);
    if (next.isBefore(now)) {
      next = DateTime(now.year + 1, localDate.month, localDate.day);
    }

    return next;
  }

  /// 获取农历月份（如果是农历日期）
  int get effectiveLunarMonth {
    if (calendarType == CalendarType.lunar && lunarMonth != null) {
      return lunarMonth!;
    }
    // 如果是公历，转换为农历
    // Convert to local time first to ensure correct date for lunar conversion
    final lunar = LunarUtils.solarToLunar(date.toLocal());
    return lunar.getMonth();
  }

  /// 获取农历日期（如果是农历日期）
  int get effectiveLunarDay {
    if (calendarType == CalendarType.lunar && lunarDay != null) {
      return lunarDay!;
    }
    // 如果是公历，转换为农历
    // Convert to local time first to ensure correct date for lunar conversion
    final lunar = LunarUtils.solarToLunar(date.toLocal());
    return lunar.getDay();
  }

  /// 获取日期显示字符串
  String get dateDisplayString {
    if (calendarType == CalendarType.lunar) {
      final monthName = LunarUtils.getLunarMonthName(effectiveLunarMonth);
      final dayName = LunarUtils.getLunarDayName(effectiveLunarDay);
      return '农历$monthName$dayName';
    }
    // Convert to local time before extracting date components
    final localDate = date.toLocal();
    return '${localDate.month}月${localDate.day}日';
  }

  /// 检查给定的公历日期是否匹配此事件
  bool matchesDate(DateTime solarDate) {
    if (calendarType == CalendarType.lunar) {
      // 农历匹配：使用 effectiveLunarMonth/Day（如果原始值为null会自动从date转换）
      return LunarUtils.matchesLunarDate(solarDate, effectiveLunarMonth, effectiveLunarDay);
    }
    // Convert to local time before extracting date components
    final localDate = date.toLocal();
    // 公历匹配
    if (isRecurring) {
      return solarDate.month == localDate.month && solarDate.day == localDate.day;
    }
    return solarDate.year == localDate.year &&
        solarDate.month == localDate.month &&
        solarDate.day == localDate.day;
  }

  /// 距离下次还有多少天
  int get daysUntilNext {
    final now = DateTime.now();
    final todayStart = DateTime(now.year, now.month, now.day);
    return nextOccurrence.difference(todayStart).inDays;
  }

  /// 是否是今天
  bool get isToday => daysUntilNext == 0;

  /// 是否即将到来(7天内)
  bool get isUpcoming => daysUntilNext > 0 && daysUntilNext <= 7;

  /// 获取日期类型显示名称
  String get dateTypeName {
    switch (dateType) {
      case DateType.birthday:
        return '生日';
      case DateType.anniversary:
        return '纪念日';
      case DateType.holiday:
        return '节日';
      case DateType.memorial:
        return '祭日';
      case DateType.custom:
        return '自定义';
    }
  }

  /// 获取日期类型图标
  String get dateTypeIcon {
    switch (dateType) {
      case DateType.birthday:
        return '🎂';
      case DateType.anniversary:
        return '💑';
      case DateType.holiday:
        return '🎉';
      case DateType.memorial:
        return '🕯️';
      case DateType.custom:
        return '📅';
    }
  }

  ImportantDate copyWith({
    String? id,
    String? title,
    String? description,
    DateTime? date,
    DateType? dateType,
    CalendarType? calendarType,
    int? lunarMonth,
    int? lunarDay,
    bool? isRecurring,
    String? memberId,
    String? memberName,
    List<int>? reminderDays,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ImportantDate(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      date: date ?? this.date,
      dateType: dateType ?? this.dateType,
      lunarMonth: lunarMonth ?? this.lunarMonth,
      lunarDay: lunarDay ?? this.lunarDay,
      calendarType: calendarType ?? this.calendarType,
      isRecurring: isRecurring ?? this.isRecurring,
      memberId: memberId ?? this.memberId,
      memberName: memberName ?? this.memberName,
      reminderDays: reminderDays ?? this.reminderDays,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, title, description, date, dateType, calendarType,
    lunarMonth, lunarDay, isRecurring, memberId, memberName,
    reminderDays, createdAt, updatedAt,
  ];
}
