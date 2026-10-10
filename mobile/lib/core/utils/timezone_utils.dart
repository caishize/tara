/// Timezone utilities for the Secretary mobile application.
///
/// All timestamps from API are in UTC (ISO 8601 with Z suffix).
/// User-facing display uses device's local timezone.
///
/// Usage:
/// ```dart
/// import 'package:secretary/core/utils/timezone_utils.dart';
///
/// // Parse UTC time from API
/// final utcTime = TimezoneUtils.parseApiTime('2026-01-28T00:00:00Z');
///
/// // Convert to local for display
/// final localTime = TimezoneUtils.toLocal(utcTime);
///
/// // Get local date for grouping
/// final localDate = TimezoneUtils.toLocalDate(utcTime);
///
/// // Convert local time to UTC for API
/// final apiString = TimezoneUtils.toApiTime(localTime);
/// ```
class TimezoneUtils {
  TimezoneUtils._();

  /// Parse an ISO 8601 datetime string from API.
  ///
  /// API returns UTC times with 'Z' suffix.
  /// Returns a UTC DateTime object.
  static DateTime parseApiTime(String isoString) {
    // DateTime.parse handles ISO 8601 and 'Z' suffix correctly
    return DateTime.parse(isoString).toUtc();
  }

  /// Parse an ISO 8601 datetime string and convert to local timezone.
  ///
  /// Convenience method combining parseApiTime and toLocal.
  static DateTime parseApiTimeToLocal(String isoString) {
    return parseApiTime(isoString).toLocal();
  }

  /// Convert UTC datetime to local timezone for display.
  static DateTime toLocal(DateTime utcTime) {
    return utcTime.toLocal();
  }

  /// Convert local datetime to UTC for API calls.
  static DateTime toUtc(DateTime localTime) {
    return localTime.toUtc();
  }

  /// Convert UTC datetime to local date for grouping.
  ///
  /// Use this instead of `utcTime.toLocal().day` to get
  /// the correct local date accounting for timezone offset.
  static DateTime toLocalDate(DateTime utcTime) {
    final local = utcTime.toLocal();
    return DateTime(local.year, local.month, local.day);
  }

  /// Format a UTC datetime as ISO 8601 string for API calls.
  ///
  /// Returns format: "2026-01-28T00:00:00Z"
  static String toApiTime(DateTime time) {
    final utc = time.toUtc();
    return utc.toIso8601String();
  }

  /// Parse a date-only string from API (e.g. "2026-03-01").
  ///
  /// Returns a local DateTime at midnight. No UTC conversion is performed
  /// because dates are calendar dates, not points in time.
  /// Use this for fields like trip start_date / end_date that are
  /// stored as Date (not DateTime) in the database.
  static DateTime parseDate(String dateString) {
    final parts = dateString.split('-');
    return DateTime(
      int.parse(parts[0]),
      int.parse(parts[1]),
      int.parse(parts[2]),
    );
  }

  /// Format a local date as YYYY-MM-DD string for API queries.
  static String formatDateForApi(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  /// Get today's date in local timezone.
  static DateTime localToday() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  /// Get current UTC time.
  static DateTime utcNow() {
    return DateTime.now().toUtc();
  }

  /// Check if two datetimes are on the same local day.
  static bool isSameLocalDay(DateTime a, DateTime b) {
    final localA = a.toLocal();
    final localB = b.toLocal();
    return localA.year == localB.year &&
        localA.month == localB.month &&
        localA.day == localB.day;
  }

  /// Get the start of the local day in UTC.
  ///
  /// Useful for database queries that need the UTC equivalent
  /// of the start of a local day.
  static DateTime startOfLocalDayInUtc(DateTime localDate) {
    final startOfDay = DateTime(localDate.year, localDate.month, localDate.day);
    return startOfDay.toUtc();
  }

  /// Get the end of the local day in UTC.
  ///
  /// Useful for database queries that need the UTC equivalent
  /// of the end of a local day (23:59:59.999).
  static DateTime endOfLocalDayInUtc(DateTime localDate) {
    final endOfDay = DateTime(
      localDate.year,
      localDate.month,
      localDate.day,
      23,
      59,
      59,
      999,
    );
    return endOfDay.toUtc();
  }

  /// Check if a UTC datetime is in the future (compared to now).
  static bool isFuture(DateTime utcTime) {
    return utcTime.isAfter(DateTime.now().toUtc());
  }

  /// Check if a UTC datetime is in the past (compared to now).
  static bool isPast(DateTime utcTime) {
    return utcTime.isBefore(DateTime.now().toUtc());
  }

  /// Check if a UTC datetime is today in local timezone.
  static bool isToday(DateTime utcTime) {
    return isSameLocalDay(utcTime, DateTime.now());
  }

  /// Get the difference in days between a UTC datetime and today.
  ///
  /// Positive = future, Negative = past.
  static int daysFromToday(DateTime utcTime) {
    final localDate = toLocalDate(utcTime);
    final today = localToday();
    return localDate.difference(today).inDays;
  }
}
