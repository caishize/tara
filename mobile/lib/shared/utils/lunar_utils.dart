import 'package:lunar/lunar.dart';

/// 农历工具类
class LunarUtils {
  /// 将公历日期转换为农历日期
  static Lunar solarToLunar(DateTime solarDate) {
    final solar = Solar.fromDate(solarDate);
    return solar.getLunar();
  }

  /// 将农历日期转换为公历日期
  /// [lunarMonth] 农历月份 (1-12)
  /// [lunarDay] 农历日期 (1-30)
  /// [year] 公历年份
  /// [isLeapMonth] 是否为闰月
  static DateTime lunarToSolar(int year, int lunarMonth, int lunarDay, {bool isLeapMonth = false}) {
    try {
      final lunar = Lunar.fromYmd(year, isLeapMonth ? -lunarMonth : lunarMonth, lunarDay);
      final solar = lunar.getSolar();
      return DateTime(solar.getYear(), solar.getMonth(), solar.getDay());
    } catch (e) {
      // 如果日期无效（如某月没有30号），返回该月最后一天
      try {
        final lunar = Lunar.fromYmd(year, isLeapMonth ? -lunarMonth : lunarMonth, lunarDay - 1);
        final solar = lunar.getSolar();
        return DateTime(solar.getYear(), solar.getMonth(), solar.getDay());
      } catch (e2) {
        return DateTime(year, lunarMonth, lunarDay);
      }
    }
  }

  /// 获取农历月份名称
  static String getLunarMonthName(int month, {bool isLeapMonth = false}) {
    const months = ['', '正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊'];
    if (month < 1 || month > 12) return '';
    return '${isLeapMonth ? '闰' : ''}${months[month]}月';
  }

  /// 获取农历日期名称
  static String getLunarDayName(int day) {
    const days = [
      '', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
      '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
      '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
    ];
    if (day < 1 || day > 30) return '';
    return days[day];
  }

  /// 获取完整的农历日期字符串
  static String getLunarDateString(DateTime solarDate) {
    final lunar = solarToLunar(solarDate);
    return '${getLunarMonthName(lunar.getMonth())}${getLunarDayName(lunar.getDay())}';
  }

  /// 获取完整的农历年月日字符串
  static String getFullLunarDateString(DateTime solarDate) {
    final lunar = solarToLunar(solarDate);
    return '农历${lunar.getYearInChinese()}年${getLunarMonthName(lunar.getMonth())}${getLunarDayName(lunar.getDay())}';
  }

  /// 获取农历年份的生肖
  static String getZodiac(DateTime solarDate) {
    final lunar = solarToLunar(solarDate);
    return lunar.getYearShengXiao();
  }

  /// 获取指定年份中某个农历日期对应的公历日期
  /// 用于计算重复农历事件的下一次日期
  static DateTime getNextLunarOccurrence(int lunarMonth, int lunarDay, {bool isLeapMonth = false}) {
    final now = DateTime.now();
    final thisYear = now.year;

    // 尝试今年的日期
    final thisYearDate = lunarToSolar(thisYear, lunarMonth, lunarDay, isLeapMonth: isLeapMonth);
    if (thisYearDate.isAfter(now) || _isSameDay(thisYearDate, now)) {
      return thisYearDate;
    }

    // 否则返回明年的日期
    return lunarToSolar(thisYear + 1, lunarMonth, lunarDay, isLeapMonth: isLeapMonth);
  }

  /// 检查指定公历日期是否匹配某个农历月日
  static bool matchesLunarDate(DateTime solarDate, int lunarMonth, int lunarDay) {
    final lunar = solarToLunar(solarDate);
    return lunar.getMonth() == lunarMonth && lunar.getDay() == lunarDay;
  }

  /// 获取某年某月的农历日期信息列表
  /// 返回该月每天对应的农历信息
  static List<LunarDayInfo> getMonthLunarInfo(int year, int month) {
    final daysInMonth = DateTime(year, month + 1, 0).day;
    final result = <LunarDayInfo>[];

    for (int day = 1; day <= daysInMonth; day++) {
      final solarDate = DateTime(year, month, day);
      final lunar = solarToLunar(solarDate);
      result.add(LunarDayInfo(
        solarDay: day,
        lunarMonth: lunar.getMonth(),
        lunarDay: lunar.getDay(),
        lunarDayName: getLunarDayName(lunar.getDay()),
        isFirstDayOfMonth: lunar.getDay() == 1,
      ));
    }

    return result;
  }

  static bool _isSameDay(DateTime a, DateTime b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }
}

/// 农历日期信息
class LunarDayInfo {
  final int solarDay;
  final int lunarMonth;
  final int lunarDay;
  final String lunarDayName;
  final bool isFirstDayOfMonth;

  LunarDayInfo({
    required this.solarDay,
    required this.lunarMonth,
    required this.lunarDay,
    required this.lunarDayName,
    required this.isFirstDayOfMonth,
  });

  /// 显示文本：如果是初一则显示月份，否则显示日期
  String get displayText => isFirstDayOfMonth
      ? LunarUtils.getLunarMonthName(lunarMonth)
      : lunarDayName;
}
