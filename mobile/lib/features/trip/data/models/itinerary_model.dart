import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/itinerary.dart';

/// Helper function to safely extract a string from a dynamic value
/// Handles String, Map (extracts text/content/name field), List (joins), and other types
String? _safeString(dynamic value) {
  if (value == null) return null;
  if (value is String) return value;
  if (value is Map<String, dynamic>) {
    // Try common keys that might contain text content
    return value['text']?.toString() ??
        value['content']?.toString() ??
        value['name']?.toString() ??
        value['value']?.toString() ??
        value['description']?.toString() ??
        value.toString();
  }
  if (value is List) {
    return value.map((e) => e.toString()).join(', ');
  }
  return value.toString();
}

class ItineraryActivityModel extends ItineraryActivity {
  const ItineraryActivityModel({
    super.time,
    super.period,
    required super.activityType,
    required super.title,
    super.location,
    super.description,
    super.estimatedCost,
    super.bookingInfo,
    super.notes,
    super.professionalAdvice,
    super.alternatives,
  });

  factory ItineraryActivityModel.fromJson(Map<String, dynamic> json) {
    // Handle location which can be either a String or a Map object
    String? locationStr;
    final locationData = json['location'];
    if (locationData != null) {
      if (locationData is String) {
        locationStr = locationData;
      } else if (locationData is Map<String, dynamic>) {
        final name = locationData['name'] ?? '';
        final address = locationData['address'] ?? '';
        if (name.isNotEmpty && address.isNotEmpty) {
          locationStr = '$name ($address)';
        } else if (name.isNotEmpty) {
          locationStr = name;
        } else if (address.isNotEmpty) {
          locationStr = address;
        }
      }
    }

    // Handle estimated_cost which can be various numeric types
    double? cost;
    final costData = json['estimated_cost'];
    if (costData != null) {
      if (costData is double) {
        cost = costData;
      } else if (costData is int) {
        cost = costData.toDouble();
      } else if (costData is String) {
        cost = double.tryParse(costData);
      }
    }

    // Handle alternatives which can be List<String> or List<Map>
    List<String>? alternativesList;
    final altData = json['alternatives'] as List?;
    if (altData != null) {
      alternativesList = altData.map((a) {
        if (a is String) return a;
        if (a is Map<String, dynamic>) return a['name']?.toString() ?? '';
        return '';
      }).where((s) => s.isNotEmpty).toList();
    }

    return ItineraryActivityModel(
      time: _safeString(json['time']),
      period: json['period'] as String?,
      activityType: _parseActivityType(json['activity_type']),
      title: _safeString(json['title']) ?? '',
      location: locationStr,
      description: _safeString(json['description']),
      estimatedCost: cost,
      bookingInfo: _safeString(json['booking_info']),
      notes: _safeString(json['notes']),
      professionalAdvice: _safeString(json['professional_advice']),
      alternatives: alternativesList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'time': time,
      'period': period,
      'activity_type': activityType.name,
      'title': title,
      'location': location,
      'description': description,
      'estimated_cost': estimatedCost,
      'booking_info': bookingInfo,
      'notes': notes,
      'professional_advice': professionalAdvice,
      'alternatives': alternatives,
    };
  }

  static ActivityType _parseActivityType(String? type) {
    if (type == null) return ActivityType.other;
    return ActivityType.values.firstWhere(
      (t) => t.name.toLowerCase() == type.toLowerCase(),
      orElse: () => ActivityType.other,
    );
  }
}

class DayItineraryModel extends DayItinerary {
  const DayItineraryModel({
    required super.id,
    required super.tripId,
    required super.dayNumber,
    super.activities,
    super.packingNotes,
    required super.createdAt,
    required super.updatedAt,
  });

  factory DayItineraryModel.fromJson(Map<String, dynamic> json) {
    // Backend returns 'schedule', but we also support 'activities' for flexibility
    final activitiesList = json['activities'] as List? ?? json['schedule'] as List? ?? [];

    return DayItineraryModel(
      id: json['itinerary_id']?.toString() ?? json['id']?.toString() ?? '',
      tripId: json['trip_id']?.toString() ?? '',
      dayNumber: json['day_number'] ?? 1,
      activities: activitiesList
          .map((a) => ItineraryActivityModel.fromJson(a as Map<String, dynamic>))
          .toList(),
      packingNotes: _safeString(json['packing_notes']),
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
      updatedAt: json['updated_at'] != null
          ? TimezoneUtils.parseApiTime(json['updated_at'])
          : DateTime.now().toUtc(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'itinerary_id': id,
      'trip_id': tripId,
      'day_number': dayNumber,
      'activities': activities
          .map((a) => (a as ItineraryActivityModel).toJson())
          .toList(),
      'packing_notes': packingNotes,
    };
  }

  static DayItineraryModel fromEntity(DayItinerary itinerary) {
    return DayItineraryModel(
      id: itinerary.id,
      tripId: itinerary.tripId,
      dayNumber: itinerary.dayNumber,
      activities: itinerary.activities,
      packingNotes: itinerary.packingNotes,
      createdAt: itinerary.createdAt,
      updatedAt: itinerary.updatedAt,
    );
  }
}
