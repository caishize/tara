import 'package:flutter/material.dart';
import '../../../../core/utils/timezone_utils.dart';

import '../../../../core/network/api_client.dart';
import '../../domain/entities/unified_event.dart';
import '../models/unified_event_model.dart';

/// Curated timeline data source - fetches AI-curated and deduplicated events
class CuratedTimelineDataSource {
  final ApiClient _apiClient;

  CuratedTimelineDataSource(this._apiClient);

  /// Fetch curated timeline from AI secretary service
  Future<CuratedTimelineResponse> fetchCuratedTimeline({
    DateTime? startDate,
    DateTime? endDate,
    int limit = 100,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };

    if (startDate != null) {
      queryParams['start_date'] = _formatDate(startDate);
    }
    if (endDate != null) {
      queryParams['end_date'] = _formatDate(endDate);
    }

    final response = await _apiClient.get<Map<String, dynamic>>(
      '/secretary/curated-timeline',
      queryParameters: queryParams,
    );

    return CuratedTimelineResponse.fromJson(response);
  }

  /// Trigger manual curation
  Future<CurationJobResponse> triggerCuration({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParams = <String, dynamic>{};

    if (startDate != null) {
      queryParams['start_date'] = _formatDate(startDate);
    }
    if (endDate != null) {
      queryParams['end_date'] = _formatDate(endDate);
    }

    final response = await _apiClient.post<Map<String, dynamic>>(
      '/secretary/request-curation',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return CurationJobResponse.fromJson(response);
  }

  String _formatDate(DateTime date) {
    return TimezoneUtils.formatDateForApi(date);
  }
}

/// Response from curated timeline API
class CuratedTimelineResponse {
  final List<CuratedEvent> events;
  final DateTime? lastCuratedAt;
  final bool hasUnconfirmed;
  final int unconfirmedCount;
  // Pagination info
  final int total;
  final int limit;
  final int offset;
  final bool hasMore;

  CuratedTimelineResponse({
    required this.events,
    this.lastCuratedAt,
    this.hasUnconfirmed = false,
    this.unconfirmedCount = 0,
    this.total = 0,
    this.limit = 100,
    this.offset = 0,
    this.hasMore = false,
  });

  factory CuratedTimelineResponse.fromJson(Map<String, dynamic> json) {
    final eventsJson = json['events'] as List<dynamic>? ?? [];
    return CuratedTimelineResponse(
      events: eventsJson
          .map((e) => CuratedEvent.fromJson(e as Map<String, dynamic>))
          .toList(),
      lastCuratedAt: json['last_curated_at'] != null
          ? TimezoneUtils.parseApiTime(json['last_curated_at'] as String)
          : null,
      hasUnconfirmed: json['has_unconfirmed'] as bool? ?? false,
      unconfirmedCount: json['unconfirmed_count'] as int? ?? 0,
      total: json['total'] as int? ?? 0,
      limit: json['limit'] as int? ?? 100,
      offset: json['offset'] as int? ?? 0,
      hasMore: json['has_more'] as bool? ?? false,
    );
  }

  /// Convert curated events to unified events for display
  List<UnifiedEvent> toUnifiedEvents() {
    return events.map((e) => e.toUnifiedEvent()).toList();
  }
}

/// A curated event from the AI secretary service
class CuratedEvent {
  final String id;
  final String title;
  final String? eventType;
  final DateTime startTime;
  final DateTime? endTime;
  final String? location;
  final List<TimelineItem> timelineItems;
  final List<String> sourceTypes;
  final int mergedCount;
  final String? dedupReason;
  final double confidence;
  final List<String> originalEventIds;  // Original source IDs for navigation

  CuratedEvent({
    required this.id,
    required this.title,
    this.eventType,
    required this.startTime,
    this.endTime,
    this.location,
    this.timelineItems = const [],
    this.sourceTypes = const [],
    this.mergedCount = 1,
    this.dedupReason,
    this.confidence = 0.8,
    this.originalEventIds = const [],
  });

  factory CuratedEvent.fromJson(Map<String, dynamic> json) {
    final timelineItemsJson = json['timeline_items'] as List<dynamic>? ?? [];
    final sourceTypesJson = json['source_types'] as List<dynamic>? ?? [];
    final originalIdsJson = json['original_event_ids'] as List<dynamic>? ?? [];

    return CuratedEvent(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType: json['event_type'] as String?,
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : DateTime.now().toUtc(),
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      location: json['location'] as String?,
      timelineItems: timelineItemsJson
          .map((e) => TimelineItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      sourceTypes: sourceTypesJson.map((e) => e.toString()).toList(),
      mergedCount: json['merged_count'] as int? ?? 1,
      dedupReason: json['dedup_reason'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      originalEventIds: originalIdsJson.map((e) => e.toString()).toList(),
    );
  }

  /// Convert to UnifiedEvent for display in schedule page
  UnifiedEvent toUnifiedEvent() {
    // Map event type to EventSource
    EventSource source = EventSource.extractedSchedule;
    if (sourceTypes.contains('travel_plan')) {
      source = EventSource.travelPlan;
    } else if (sourceTypes.contains('important_date')) {
      source = EventSource.importantDate;
    } else if (sourceTypes.contains('extracted_schedule')) {
      source = EventSource.extractedSchedule;
    }

    // Build description from timeline items or dedup reason
    String? description;
    if (timelineItems.isNotEmpty) {
      final confirmedItems = timelineItems.where((t) => t.confirmed).length;
      final unconfirmedItems = timelineItems.length - confirmedItems;
      if (unconfirmedItems > 0) {
        description = '$unconfirmedItems项待确认';
      } else if (mergedCount > 1) {
        description = '合并自$mergedCount个来源';
      }
    } else if (dedupReason != null && dedupReason!.isNotEmpty) {
      description = dedupReason;
    }

    // Get icon based on event type
    String icon = _getIconForEventType(eventType);
    Color color = _getColorForEventType(eventType, source);

    // Use first original ID for navigation (most events have single source)
    final originalId = originalEventIds.isNotEmpty ? originalEventIds.first : null;

    return UnifiedEventModel(
      id: id,
      title: title,
      dateTime: startTime,
      endDateTime: endTime,
      location: location,
      source: source,
      icon: icon,
      color: color,
      description: description,
      sourceData: {
        'curated': true,
        'eventType': eventType,
        'timelineItems': timelineItems.map((t) => t.toJson()).toList(),
        'sourceTypes': sourceTypes,
        'mergedCount': mergedCount,
        'dedupReason': dedupReason,
        'confidence': confidence,
        'originalEventIds': originalEventIds,
        'originalId': originalId,
        // Populate source-specific IDs so navigation works for curated events
        if (source == EventSource.travelPlan && originalId != null)
          'tripId': originalId,
        if (source == EventSource.importantDate && originalId != null)
          'dateId': originalId,
      },
    );
  }

  /// Get icon string for event type
  String _getIconForEventType(String? eventType) {
    switch (eventType) {
      case 'business_trip':
        return '💼';
      case 'travel':
        return '✈️';
      case 'meeting':
        return '🤝';
      case 'birthday':
        return '🎂';
      case 'anniversary':
        return '💕';
      case 'holiday':
        return '🎉';
      case 'reminder':
        return '⏰';
      case 'appointment':
        return '📅';
      default:
        return '📌';
    }
  }

  /// Get color for event type
  Color _getColorForEventType(String? eventType, EventSource source) {
    switch (eventType) {
      case 'business_trip':
        return Colors.blue;
      case 'travel':
        return Colors.teal;
      case 'meeting':
        return Colors.indigo;
      case 'birthday':
        return Colors.pink;
      case 'anniversary':
        return Colors.red;
      case 'holiday':
        return Colors.orange;
      case 'reminder':
        return Colors.amber;
      default:
        return source.color;
    }
  }
}

/// A timeline item within a curated event (for multi-day events)
class TimelineItem {
  final String time;
  final String item;
  final bool confirmed;
  final String? note;

  TimelineItem({
    required this.time,
    required this.item,
    this.confirmed = true,
    this.note,
  });

  factory TimelineItem.fromJson(Map<String, dynamic> json) {
    return TimelineItem(
      time: json['time'] as String? ?? '',
      item: json['item'] as String? ?? '',
      confirmed: json['confirmed'] as bool? ?? true,
      note: json['note'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'time': time,
      'item': item,
      'confirmed': confirmed,
      if (note != null) 'note': note,
    };
  }
}

/// Response from curation job API
class CurationJobResponse {
  final String jobId;
  final String status;
  final String message;

  CurationJobResponse({
    required this.jobId,
    required this.status,
    required this.message,
  });

  factory CurationJobResponse.fromJson(Map<String, dynamic> json) {
    return CurationJobResponse(
      jobId: json['job_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      message: json['message'] as String? ?? '',
    );
  }

  bool get isCompleted => status == 'completed';
  bool get isFailed => status == 'failed';
  bool get isRunning => status == 'running' || status == 'pending';
}
