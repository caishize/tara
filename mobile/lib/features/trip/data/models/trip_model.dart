import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/trip.dart';

class TripModel extends Trip {
  const TripModel({
    required super.id,
    required super.familyId,
    super.tripName,
    required super.destination,
    required super.startDate,
    required super.endDate,
    super.category,
    super.tripType,
    super.budget,
    super.actualExpense,
    super.participants,
    super.status,
    super.notes,
    super.recommendationContext,
    required super.createdAt,
    required super.updatedAt,
  });

  factory TripModel.fromJson(Map<String, dynamic> json) {
    return TripModel(
      id: json['trip_id']?.toString() ?? json['id']?.toString() ?? '',
      familyId: json['family_id']?.toString() ?? '',
      tripName: json['trip_name'],
      destination: json['destination'] ?? '',
      startDate: TimezoneUtils.parseApiTime(json['start_date']),
      endDate: TimezoneUtils.parseApiTime(json['end_date']),
      category: _parseCategory(json['category']),
      tripType: _parseTripType(json['trip_type']),
      budget: _parseDouble(json['budget']),
      actualExpense: _parseDouble(json['actual_expense']) ?? 0.0,
      participants: (json['participants'] as List?)
          ?.map((e) => e.toString())
          .toList() ?? [],
      status: _parseStatus(json['status']),
      notes: json['notes'],
      recommendationContext: json['recommendation_context'],
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
      'trip_id': id,
      'family_id': familyId,
      'trip_name': tripName,
      'destination': destination,
      'start_date': TimezoneUtils.formatDateForApi(startDate),
      'end_date': TimezoneUtils.formatDateForApi(endDate),
      'category': category.name,
      'trip_type': _tripTypeToString(tripType),
      'budget': budget,
      'actual_expense': actualExpense,
      'participants': participants,
      'status': status.name,
      'notes': notes,
      'recommendation_context': recommendationContext,
    };
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'trip_name': tripName,
      'destination': destination,
      'start_date': TimezoneUtils.formatDateForApi(startDate),
      'end_date': TimezoneUtils.formatDateForApi(endDate),
      'category': category.name,
      'trip_type': _tripTypeToString(tripType),
      'budget': budget,
      'participants': participants,
      'notes': notes,
    };
  }

  static TripCategory _parseCategory(String? category) {
    if (category == null) return TripCategory.personal;
    return TripCategory.values.firstWhere(
      (c) => c.name.toLowerCase() == category.toLowerCase(),
      orElse: () => TripCategory.personal,
    );
  }

  static TripType _parseTripType(String? type) {
    if (type == null) return TripType.leisure;
    // Handle snake_case from backend (e.g., 'business_trip' -> 'businessTrip')
    final normalizedType = _snakeToCamel(type);
    return TripType.values.firstWhere(
      (t) => t.name.toLowerCase() == normalizedType.toLowerCase() ||
             t.name.toLowerCase() == type.toLowerCase(),
      orElse: () => TripType.leisure,
    );
  }

  static TripStatus _parseStatus(String? status) {
    if (status == null) return TripStatus.planning;
    // Handle snake_case from backend
    final normalizedStatus = status.replaceAll('_', '');
    return TripStatus.values.firstWhere(
      (s) => s.name.toLowerCase() == normalizedStatus.toLowerCase() ||
             s.name.toLowerCase() == status.toLowerCase(),
      orElse: () => TripStatus.planning,
    );
  }

  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Convert snake_case to camelCase
  static String _snakeToCamel(String text) {
    final parts = text.split('_');
    if (parts.length == 1) return text;
    return parts[0] + parts.skip(1).map((p) =>
      p.isEmpty ? '' : p[0].toUpperCase() + p.substring(1)
    ).join('');
  }

  /// Convert TripType to snake_case for API
  static String _tripTypeToString(TripType type) {
    switch (type) {
      case TripType.businessTrip:
        return 'business_trip';
      case TripType.clientVisit:
        return 'client_visit';
      default:
        return type.name;
    }
  }

  static TripModel fromEntity(Trip plan) {
    return TripModel(
      id: plan.id,
      familyId: plan.familyId,
      tripName: plan.tripName,
      destination: plan.destination,
      startDate: plan.startDate,
      endDate: plan.endDate,
      category: plan.category,
      tripType: plan.tripType,
      budget: plan.budget,
      actualExpense: plan.actualExpense,
      participants: plan.participants,
      status: plan.status,
      notes: plan.notes,
      recommendationContext: plan.recommendationContext,
      createdAt: plan.createdAt,
      updatedAt: plan.updatedAt,
    );
  }
}
