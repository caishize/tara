import '../../../../core/network/api_client.dart';
import '../../../../core/utils/timezone_utils.dart';

/// Request model for creating an event
class CreateEventRequest {
  final String title;
  final DateTime startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String priority;
  final String? notes;
  final List<String> tags;

  const CreateEventRequest({
    required this.title,
    required this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    this.priority = 'normal',
    this.notes,
    this.tags = const [],
  });

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'start_time': TimezoneUtils.toApiTime(startTime),
      'end_time': endTime != null ? TimezoneUtils.toApiTime(endTime!) : null,
      'event_type': eventType,
      'location': location,
      'priority': priority,
      'notes': notes,
      'tags': tags,
    };
  }
}

/// Request model for updating an event
class UpdateEventRequest {
  final String? title;
  final DateTime? startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String? priority;
  final String? notes;
  final List<String>? tags;
  final String? status;

  const UpdateEventRequest({
    this.title,
    this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    this.priority,
    this.notes,
    this.tags,
    this.status,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{};
    if (title != null) map['title'] = title;
    if (startTime != null) map['start_time'] = TimezoneUtils.toApiTime(startTime!);
    if (endTime != null) map['end_time'] = TimezoneUtils.toApiTime(endTime!);
    if (eventType != null) map['event_type'] = eventType;
    if (location != null) map['location'] = location;
    if (priority != null) map['priority'] = priority;
    if (notes != null) map['notes'] = notes;
    if (tags != null) map['tags'] = tags;
    if (status != null) map['status'] = status;
    return map;
  }
}

/// Response model for event operations
class EventResponseModel {
  final String id;
  final String title;
  final DateTime startTime;
  final DateTime? endTime;
  final String? eventType;
  final String? location;
  final String status;
  final String priority;
  final String? notes;
  final List<String> tags;
  final List<String> sourceTypes;
  final double confidence;
  final String? tripId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const EventResponseModel({
    required this.id,
    required this.title,
    required this.startTime,
    this.endTime,
    this.eventType,
    this.location,
    required this.status,
    required this.priority,
    this.notes,
    required this.tags,
    required this.sourceTypes,
    required this.confidence,
    this.tripId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory EventResponseModel.fromJson(Map<String, dynamic> json) {
    return EventResponseModel(
      id: json['id'] as String,
      title: json['title'] as String,
      startTime: TimezoneUtils.parseApiTime(json['start_time'] as String),
      endTime: json['end_time'] != null
          ? TimezoneUtils.parseApiTime(json['end_time'] as String)
          : null,
      eventType: json['event_type'] as String?,
      location: json['location'] as String?,
      status: json['status'] as String? ?? 'pending',
      priority: json['priority'] as String? ?? 'normal',
      notes: json['notes'] as String?,
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
      sourceTypes: (json['source_types'] as List<dynamic>?)?.cast<String>() ?? [],
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      tripId: json['trip_id'] as String?,
      createdAt: TimezoneUtils.parseApiTime(json['created_at'] as String),
      updatedAt: TimezoneUtils.parseApiTime(json['updated_at'] as String),
    );
  }
}

/// Remote data source for event CRUD operations
class EventRemoteDataSource {
  final ApiClient _apiClient;

  EventRemoteDataSource({required ApiClient apiClient})
      : _apiClient = apiClient;

  /// Create a new event (auth via JWT, no query params needed)
  Future<EventResponseModel> createEvent({
    required CreateEventRequest request,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/secretary/events',
      data: request.toJson(),
    );
    return EventResponseModel.fromJson(response);
  }

  /// Update an existing event (auth via JWT)
  Future<EventResponseModel> updateEvent({
    required String eventId,
    required UpdateEventRequest request,
  }) async {
    final response = await _apiClient.patch<Map<String, dynamic>>(
      '/secretary/events/$eventId',
      data: request.toJson(),
    );
    return EventResponseModel.fromJson(response);
  }

  /// Delete (soft-delete) an event (auth via JWT)
  Future<void> deleteEvent({
    required String eventId,
  }) async {
    await _apiClient.delete<dynamic>(
      '/secretary/events/$eventId',
    );
  }

  /// List events with filters (auth via JWT)
  Future<List<EventResponseModel>> listEvents({
    String? startDate,
    String? endDate,
    String? eventType,
    String? status,
    int limit = 100,
    int offset = 0,
  }) async {
    final queryParams = <String, dynamic>{
      'limit': limit,
      'offset': offset,
    };
    if (startDate != null) queryParams['start_date'] = startDate;
    if (endDate != null) queryParams['end_date'] = endDate;
    if (eventType != null) queryParams['event_type'] = eventType;
    if (status != null) queryParams['status'] = status;

    final response = await _apiClient.get<Map<String, dynamic>>(
      '/secretary/events',
      queryParameters: queryParams,
    );

    final events = (response['events'] as List<dynamic>?)
            ?.map((e) => EventResponseModel.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    return events;
  }
}
