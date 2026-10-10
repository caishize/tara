import 'package:flutter/material.dart';
import '../../../../core/utils/timezone_utils.dart';

import '../../../../core/network/api_client.dart';
import '../../domain/entities/curated_event.dart' as domain;
import '../../domain/entities/memory_lane.dart';
import '../../domain/entities/unified_event.dart';
import '../models/kanban_models.dart';
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
      '/kanban/curated-timeline',
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
      '/kanban/request-curation',
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
  final List<CuratedEventDto> events;
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
          .map((e) => CuratedEventDto.fromJson(e as Map<String, dynamic>))
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

/// A curated event DTO from the AI secretary service (data layer only).
/// Use [domain.CuratedEvent] for domain/presentation layer.
class CuratedEventDto {
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
  final List<String> originalEventIds; // Original source IDs for navigation

  CuratedEventDto({
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

  factory CuratedEventDto.fromJson(Map<String, dynamic> json) {
    final timelineItemsJson = json['timeline_items'] as List<dynamic>? ?? [];
    final sourceTypesJson = json['source_types'] as List<dynamic>? ?? [];
    final originalIdsJson = json['original_event_ids'] as List<dynamic>? ?? [];

    return CuratedEventDto(
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
    final originalId =
        originalEventIds.isNotEmpty ? originalEventIds.first : null;

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

// ===== Types used by CuratedTimelineRepository =====

/// Direction for directional timeline fetch
enum TimelineDirection { past, future }

/// Status of a curation job
class CurationJobStatus {
  final String jobId;
  final bool isCompleted;

  const CurationJobStatus({required this.jobId, required this.isCompleted});

  factory CurationJobStatus.fromJson(Map<String, dynamic> json) {
    final status = json['status'] as String? ?? 'pending';
    return CurationJobStatus(
      jobId: json['job_id'] as String? ?? '',
      isCompleted: status == 'completed',
    );
  }
}

/// A single event within a day group
class DayGroupEvent {
  final String id;
  final String title;
  final DateTime startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String? tripId;

  const DayGroupEvent({
    required this.id,
    required this.title,
    required this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    this.tripId,
  });

  factory DayGroupEvent.fromJson(Map<String, dynamic> json) {
    return DayGroupEvent(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : DateTime.now().toUtc(),
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      eventType: json['event_type'] as String?,
      location: json['location'] as String?,
      tripId: json['trip_id'] as String?,
    );
  }
}

/// A group of events for a single day
class DayGroup {
  final DateTime date;
  final List<DayGroupEvent> events;

  const DayGroup({required this.date, required this.events});

  factory DayGroup.fromJson(Map<String, dynamic> json) {
    final eventsJson = json['events'] as List<dynamic>? ?? [];
    return DayGroup(
      date: json['date'] != null
          ? DateTime.parse(json['date'] as String)
          : DateTime.now(),
      events: eventsJson
          .map((e) => DayGroupEvent.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// Response from directional timeline API
class DirectionalTimelineResponse {
  final List<DayGroup> dayGroups;
  final String? nextCursor;
  final bool hasMore;

  const DirectionalTimelineResponse({
    required this.dayGroups,
    this.nextCursor,
    this.hasMore = false,
  });

  factory DirectionalTimelineResponse.fromJson(Map<String, dynamic> json) {
    final groupsJson = json['day_groups'] as List<dynamic>? ?? [];
    return DirectionalTimelineResponse(
      dayGroups: groupsJson
          .map((g) => DayGroup.fromJson(g as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
      hasMore: json['has_more'] as bool? ?? false,
    );
  }
}

/// Response from event search API
class EventSearchResponse {
  final List<KanbanEventModel> results;
  final int total;

  const EventSearchResponse({required this.results, this.total = 0});

  factory EventSearchResponse.fromJson(Map<String, dynamic> json) {
    final resultsJson = json['results'] as List<dynamic>? ?? [];
    return EventSearchResponse(
      results: resultsJson
          .map((e) => KanbanEventModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int? ?? 0,
    );
  }
}

/// Abstract interface for curated timeline remote data source
abstract class CuratedTimelineRemoteDataSource {
  Future<domain.CuratedTimeline> fetchCuratedTimeline({
    DateTime? startDate,
    DateTime? endDate,
  });

  Future<CurationJobStatus> requestCuration({
    DateTime? startDate,
    DateTime? endDate,
  });

  Future<CurationJobStatus> getCurationJobStatus(String jobId);

  Future<DirectionalTimelineResponse> fetchDirectionalTimeline({
    required TimelineDirection direction,
    int days,
    String? cursor,
  });

  Future<bool> updateEventStatus({
    required String eventId,
    required String status,
  });

  Future<bool> cancelEvent({
    required String eventId,
    required String eventTitle,
  });

  Future<void> createEvent({
    required String title,
    required DateTime startTime,
    DateTime? endTime,
    String? eventType,
    String? location,
    String priority,
    String? notes,
    List<String> tags,
  });

  Future<KanbanResponseModel> fetchKanban();

  Future<List<PreparationItemModel>> togglePreparationItem({
    required String eventId,
    required int itemIndex,
    String? itemKey,
    required bool done,
  });

  Future<MemoryLaneResponse> fetchMemoryLane({int? year});

  Future<OnThisDayResponse> fetchOnThisDay();

  Future<EventSearchResponse> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit,
  });
}

/// Implementation of CuratedTimelineRemoteDataSource
class CuratedTimelineRemoteDataSourceImpl
    implements CuratedTimelineRemoteDataSource {
  final ApiClient apiClient;

  CuratedTimelineRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<domain.CuratedTimeline> fetchCuratedTimeline({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParams = <String, dynamic>{};
    if (startDate != null) queryParams['start_date'] = _formatDate(startDate);
    if (endDate != null) queryParams['end_date'] = _formatDate(endDate);

    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/curated-timeline',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    final eventsJson = response['events'] as List<dynamic>? ?? [];
    return domain.CuratedTimeline(
      events: eventsJson
          .map((e) => _parseCuratedEvent(e as Map<String, dynamic>))
          .toList(),
      lastCuratedAt: response['last_curated_at'] != null
          ? TimezoneUtils.parseApiTime(response['last_curated_at'] as String)
          : null,
      hasUnconfirmed: response['has_unconfirmed'] as bool? ?? false,
      unconfirmedCount: response['unconfirmed_count'] as int? ?? 0,
    );
  }

  @override
  Future<CurationJobStatus> requestCuration({
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final body = <String, dynamic>{};
    if (startDate != null) body['start_date'] = _formatDate(startDate);
    if (endDate != null) body['end_date'] = _formatDate(endDate);

    final response = await apiClient.post<Map<String, dynamic>>(
      '/kanban/request-curation',
      data: body.isNotEmpty ? body : null,
    );

    return CurationJobStatus.fromJson(response);
  }

  @override
  Future<CurationJobStatus> getCurationJobStatus(String jobId) async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/curation-status/$jobId',
    );
    return CurationJobStatus.fromJson(response);
  }

  @override
  Future<DirectionalTimelineResponse> fetchDirectionalTimeline({
    required TimelineDirection direction,
    int days = 14,
    String? cursor,
  }) async {
    final queryParams = <String, dynamic>{
      'direction': direction == TimelineDirection.past ? 'past' : 'future',
      'days': days.toString(),
    };
    if (cursor != null) queryParams['cursor'] = cursor;

    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/directional-timeline',
      queryParameters: queryParams,
    );

    return DirectionalTimelineResponse.fromJson(response);
  }

  @override
  Future<bool> updateEventStatus({
    required String eventId,
    required String status,
  }) async {
    await apiClient.patch<Map<String, dynamic>>(
      '/kanban/events/$eventId/status',
      data: {'status': status},
    );
    return true;
  }

  @override
  Future<bool> cancelEvent({
    required String eventId,
    required String eventTitle,
  }) async {
    await apiClient.delete<Map<String, dynamic>>(
      '/kanban/events/$eventId',
    );
    return true;
  }

  @override
  Future<void> createEvent({
    required String title,
    required DateTime startTime,
    DateTime? endTime,
    String? eventType,
    String? location,
    String priority = 'normal',
    String? notes,
    List<String> tags = const [],
  }) async {
    await apiClient.post<Map<String, dynamic>>(
      '/kanban/events',
      data: {
        'title': title,
        'start_time': TimezoneUtils.toApiTime(startTime),
        if (endTime != null) 'end_time': TimezoneUtils.toApiTime(endTime),
        if (eventType != null) 'event_type': eventType,
        if (location != null) 'location': location,
        'priority': priority,
        if (notes != null) 'notes': notes,
        if (tags.isNotEmpty) 'tags': tags,
      },
    );
  }

  @override
  Future<KanbanResponseModel> fetchKanban() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban',
    );
    return KanbanResponseModel.fromJson(response);
  }

  @override
  Future<List<PreparationItemModel>> togglePreparationItem({
    required String eventId,
    required int itemIndex,
    String? itemKey,
    required bool done,
  }) async {
    final response = await apiClient.patch<Map<String, dynamic>>(
      '/kanban/events/$eventId/preparation',
      data: {
        'done': done,
        'item_index': itemIndex,
        if (itemKey != null) 'item_key': itemKey,
      },
    );
    final items = (response['preparation_items'] as List<dynamic>?) ??
        (response['items'] as List<dynamic>?) ??
        [];
    return items
        .map((i) => PreparationItemModel.fromJson(i as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<MemoryLaneResponse> fetchMemoryLane({int? year}) async {
    final queryParams = <String, dynamic>{};
    if (year != null) queryParams['year'] = year.toString();

    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/memory-lane',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return _parseMemoryLaneResponse(response);
  }

  @override
  Future<OnThisDayResponse> fetchOnThisDay() async {
    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/on-this-day',
    );
    return _parseOnThisDayResponse(response);
  }

  @override
  Future<EventSearchResponse> searchEvents({
    required String query,
    List<String>? eventTypes,
    int limit = 20,
  }) async {
    final queryParams = <String, dynamic>{
      'q': query,
      'limit': limit.toString(),
    };
    if (eventTypes != null && eventTypes.isNotEmpty) {
      queryParams['event_types'] = eventTypes.join(',');
    }

    final response = await apiClient.get<Map<String, dynamic>>(
      '/kanban/events/search',
      queryParameters: queryParams,
    );

    return EventSearchResponse.fromJson(response);
  }

  MemoryLaneResponse _parseMemoryLaneResponse(Map<String, dynamic> json) {
    final yearsJson = json['years'] as List<dynamic>? ?? [];
    final years = yearsJson.map((y) {
      final yearMap = y as Map<String, dynamic>;
      final storiesJson = yearMap['stories'] as List<dynamic>? ?? [];
      final stories = storiesJson.map((s) {
        final storyMap = s as Map<String, dynamic>;
        final eventsJson = storyMap['events'] as List<dynamic>? ?? [];
        return StoryGroup(
          tripId: storyMap['trip_id'] as String?,
          title: storyMap['title'] as String? ?? '',
          events: eventsJson.map((e) {
            final em = e as Map<String, dynamic>;
            return StoryEvent(
              id: em['id'] as String? ?? '',
              title: em['title'] as String? ?? '',
              eventType: em['event_type'] as String?,
              startTime: em['start_time'] != null
                  ? TimezoneUtils.parseApiTime(em['start_time'] as String)
                  : null,
              endTime: em['end_time'] != null
                  ? TimezoneUtils.parseApiTime(em['end_time'] as String)
                  : null,
              location: em['location'] as String?,
              status: em['status'] as String?,
              priority: em['priority'] as String?,
              notes: em['notes'] as String?,
              tripId: em['trip_id'] as String?,
              tripName: em['trip_name'] as String?,
            );
          }).toList(),
          memorySummaries: (storyMap['memory_summaries'] as List<dynamic>?)
                  ?.map((m) => m.toString())
                  .toList() ??
              [],
          startDate: storyMap['start_date'] != null
              ? DateTime.parse(storyMap['start_date'] as String)
              : null,
          endDate: storyMap['end_date'] != null
              ? DateTime.parse(storyMap['end_date'] as String)
              : null,
          emotionalTag: storyMap['emotional_tag'] as String?,
        );
      }).toList();
      return YearlySummary(
        year: yearMap['year'] as int? ?? 0,
        stories: stories,
        eventCount: yearMap['event_count'] as int? ?? 0,
      );
    }).toList();
    return MemoryLaneResponse(
      years: years,
      totalEvents: json['total_events'] as int? ?? 0,
    );
  }

  OnThisDayResponse _parseOnThisDayResponse(Map<String, dynamic> json) {
    final itemsJson = json['items'] as List<dynamic>? ?? [];
    return OnThisDayResponse(
      items: itemsJson.map((i) {
        final im = i as Map<String, dynamic>;
        return OnThisDayItem(
          id: im['id'] as String? ?? '',
          title: im['title'] as String? ?? '',
          eventType: im['event_type'] as String?,
          year: im['year'] as int? ?? 0,
          startTime: im['start_time'] != null
              ? TimezoneUtils.parseApiTime(im['start_time'] as String)
              : null,
          location: im['location'] as String?,
          notes: im['notes'] as String?,
          tripName: im['trip_name'] as String?,
        );
      }).toList(),
      month: json['month'] as int? ?? DateTime.now().month,
      day: json['day'] as int? ?? DateTime.now().day,
    );
  }

  domain.CuratedEvent _parseCuratedEvent(Map<String, dynamic> json) {
    final timelineItemsJson = json['timeline_items'] as List<dynamic>? ?? [];
    final sourceTypesJson = json['source_types'] as List<dynamic>? ?? [];
    final originalIdsJson = json['original_event_ids'] as List<dynamic>? ?? [];
    final conflictWithJson = json['conflict_with'] as List<dynamic>? ?? [];

    return domain.CuratedEvent(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      eventType:
          domain.CuratedEventType.fromString(json['event_type'] as String?),
      startTime: json['start_time'] != null
          ? TimezoneUtils.parseApiTime(json['start_time'] as String)
          : DateTime.now().toUtc(),
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      location: json['location'] as String?,
      notes: json['notes'] as String?,
      priority: json['priority'] as String?,
      timelineItems: timelineItemsJson
          .map((e) => domain.TimelineItem(
                time: (e as Map<String, dynamic>)['time'] as String? ?? '',
                item: e['item'] as String? ?? '',
                confirmed: e['confirmed'] as bool? ?? true,
                note: e['note'] as String?,
              ))
          .toList(),
      sourceTypes: sourceTypesJson.map((e) => e.toString()).toList(),
      mergedCount: json['merged_count'] as int? ?? 1,
      dedupReason: json['dedup_reason'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.8,
      originalEventIds: originalIdsJson.map((e) => e.toString()).toList(),
      enrichments: json['enrichments'] as Map<String, dynamic>?,
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      tripDayLabel: json['trip_day_label'] as String?,
      hasConflict: json['has_conflict'] as bool? ?? false,
      conflictWith: conflictWithJson.map((e) => e.toString()).toList(),
      sequenceOfDay: json['sequence_of_day'] as int?,
    );
  }

  String _formatDate(DateTime date) {
    return TimezoneUtils.formatDateForApi(date);
  }
}
