import 'package:flutter/material.dart';
import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/unified_event.dart';
import '../../../dates/domain/entities/important_date.dart';
import '../../../trip/domain/entities/trip.dart';

/// Model class for converting between different source entities and UnifiedEvent
class UnifiedEventModel extends UnifiedEvent {
  const UnifiedEventModel({
    required super.id,
    required super.source,
    required super.title,
    super.dateTime,
    super.endDateTime,
    super.location,
    super.relatedMemberId,
    super.memberName,
    super.aiInsights,
    super.sourceData,
    required super.icon,
    required super.color,
    super.isAllDay,
    super.description,
  });

  /// Create from ImportantDate
  factory UnifiedEventModel.fromImportantDate(ImportantDate date) {
    return UnifiedEventModel(
      id: 'date_${date.id}',
      source: EventSource.importantDate,
      title: date.title,
      dateTime: date.nextOccurrence,
      location: null,
      relatedMemberId: date.memberId,
      memberName: date.memberName,
      aiInsights: [],
      sourceData: {
        'dateId': date.id,
        'originalId': date.id,
        'dateType': date.dateType.name,
        'calendarType': date.calendarType.name,
        'isRecurring': date.isRecurring,
        // Store lunar date info for deduplication
        'lunarMonth': date.lunarMonth,
        'lunarDay': date.lunarDay,
      },
      icon: date.dateTypeIcon,
      color: _getColorForDateType(date.dateType),
      isAllDay: true,
      description: date.description,
    );
  }

  /// Create from Trip
  factory UnifiedEventModel.fromTrip(Trip plan) {
    return UnifiedEventModel(
      id: 'travel_${plan.id}',
      source: EventSource.travelPlan,
      title: plan.tripName ?? '${plan.destination}之旅',
      dateTime: plan.startDate,
      endDateTime: plan.endDate,
      location: plan.destination,
      relatedMemberId: null,
      memberName: plan.participants.isNotEmpty ? plan.participants.join(', ') : null,
      aiInsights: [],
      sourceData: {
        'tripId': plan.id,
        'originalId': plan.id,
        'tripType': plan.tripType.name,
        'status': plan.status.name,
        'budget': plan.budget,
      },
      icon: plan.tripTypeIcon,
      color: Color(plan.statusColorValue),
      isAllDay: true,
      description: plan.notes,
    );
  }

  /// Create from extracted schedule (from Secretary module)
  factory UnifiedEventModel.fromExtractedSchedule(Map<String, dynamic> data) {
    return UnifiedEventModel(
      id: 'schedule_${data['id']}',
      source: EventSource.extractedSchedule,
      title: data['title'] ?? '',
      dateTime: data['dateTime'] != null ? TimezoneUtils.parseApiTime(data['dateTime']) : null,
      endDateTime: data['endDateTime'] != null ? TimezoneUtils.parseApiTime(data['endDateTime']) : null,
      location: data['location'],
      relatedMemberId: data['memberId'],
      memberName: data['memberName'],
      aiInsights: List<String>.from(data['insights'] ?? []),
      sourceData: data,
      icon: data['icon'] ?? '📋',
      color: Color(data['color'] ?? 0xFF6366F1),
      isAllDay: data['isAllDay'] ?? false,
      description: data['description'],
    );
  }

  /// Create from extracted plan (from Secretary module)
  factory UnifiedEventModel.fromExtractedPlan(Map<String, dynamic> data) {
    return UnifiedEventModel(
      id: 'plan_${data['id']}',
      source: EventSource.extractedPlan,
      title: data['title'] ?? '',
      dateTime: data['dateTime'] != null ? TimezoneUtils.parseApiTime(data['dateTime']) : null,
      endDateTime: data['endDateTime'] != null ? TimezoneUtils.parseApiTime(data['endDateTime']) : null,
      location: data['location'],
      relatedMemberId: data['memberId'],
      memberName: data['memberName'],
      aiInsights: List<String>.from(data['insights'] ?? []),
      sourceData: data,
      icon: data['icon'] ?? '📝',
      color: Color(data['color'] ?? 0xFF14B8A6),
      isAllDay: data['isAllDay'] ?? true,
      description: data['description'],
    );
  }

  /// Create from external calendar event (Google Calendar, Outlook)
  factory UnifiedEventModel.fromExternalCalendar(Map<String, dynamic> data) {
    return UnifiedEventModel(
      id: 'ext_cal_${data['id']}',
      source: EventSource.externalCalendar,
      title: data['title'] ?? data['summary'] ?? '',
      dateTime: _parseDateTime(data['start_time'] ?? data['start']),
      endDateTime: _parseDateTime(data['end_time'] ?? data['end']),
      location: data['location'],
      relatedMemberId: null,
      memberName: data['organizer'],
      aiInsights: [],
      sourceData: data,
      icon: data['icon'] ?? '📅',
      color: const Color(0xFF009688), // Teal for external calendar
      isAllDay: data['is_all_day'] ?? data['all_day'] ?? false,
      description: data['description'],
    );
  }

  /// Create from external travel booking (flights, hotels from parsed emails)
  factory UnifiedEventModel.fromExternalTravel(Map<String, dynamic> data) {
    final bookingType = data['booking_type'] ?? data['type'] ?? 'travel';
    String icon;
    String title;

    if (bookingType == 'flight') {
      icon = '✈️';
      final flightNo = data['flight_number'] ?? '';
      final departure = data['departure_city'] ?? '';
      final arrival = data['arrival_city'] ?? '';
      title = flightNo.isNotEmpty
          ? '$flightNo: $departure → $arrival'
          : '$departure → $arrival';
    } else if (bookingType == 'hotel') {
      icon = '🏨';
      title = data['hotel_name'] ?? data['title'] ?? '酒店预订';
    } else if (bookingType == 'train') {
      icon = '🚄';
      title = data['train_number'] ?? data['title'] ?? '火车票';
    } else {
      icon = '🎫';
      title = data['title'] ?? '行程预订';
    }

    return UnifiedEventModel(
      id: 'ext_travel_${data['id']}',
      source: EventSource.externalTravel,
      title: title,
      dateTime: _parseDateTime(data['start_time'] ?? data['departure_time'] ?? data['check_in']),
      endDateTime: _parseDateTime(data['end_time'] ?? data['arrival_time'] ?? data['check_out']),
      location: data['location'] ?? data['departure_city'] ?? data['hotel_name'],
      relatedMemberId: null,
      memberName: data['passenger'] ?? data['guest_name'],
      aiInsights: [],
      sourceData: data,
      icon: icon,
      color: const Color(0xFFFF9800), // Orange for external travel
      isAllDay: data['is_all_day'] ?? false,
      description: data['description'] ?? data['confirmation_number'],
    );
  }

  /// Parse DateTime from various formats
  static DateTime? _parseDateTime(dynamic value) {
    if (value == null) return null;
    if (value is DateTime) return value.toUtc();
    if (value is String) {
      try {
        return TimezoneUtils.parseApiTime(value);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  static Color _getColorForDateType(DateType type) {
    switch (type) {
      case DateType.birthday:
        return const Color(0xFFE91E63); // Pink
      case DateType.anniversary:
        return const Color(0xFFE53935); // Red
      case DateType.holiday:
        return const Color(0xFFFF9800); // Orange
      case DateType.memorial:
        return const Color(0xFF607D8B); // Blue Grey
      case DateType.custom:
        return const Color(0xFF6366F1); // Primary
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'source': source.name,
      'title': title,
      'dateTime': dateTime != null ? TimezoneUtils.toApiTime(dateTime!) : null,
      'endDateTime': endDateTime != null ? TimezoneUtils.toApiTime(endDateTime!) : null,
      'location': location,
      'relatedMemberId': relatedMemberId,
      'memberName': memberName,
      'aiInsights': aiInsights,
      'sourceData': sourceData,
      'icon': icon,
      'color': color.value,
      'isAllDay': isAllDay,
      'description': description,
    };
  }
}
