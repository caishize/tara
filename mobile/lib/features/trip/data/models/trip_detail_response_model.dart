/// Aggregated response model for the trip detail endpoint.
///
/// Combines trip plan, itineraries, expenses, budget status, context,
/// and event associations into a single response parsed from
/// `GET /trips/plans/{tripId}/detail`.
library;

import 'trip_model.dart';
import 'itinerary_model.dart';
import 'trip_expense_model.dart';
import 'trip_context_model.dart';
import 'association_summary_model.dart';
import 'related_memory_model.dart';

class TripDetailResponseModel {
  final TripModel plan;
  final List<DayItineraryModel> itinerary;
  final List<TripExpenseModel> expenses;
  final int expenseTotal;
  final BudgetStatusModel? budgetStatus;
  final TripContextModel? context;
  final List<AssociationSummaryModel> associations;
  final List<RelatedMemoryModel> relatedMemories;

  const TripDetailResponseModel({
    required this.plan,
    this.itinerary = const [],
    this.expenses = const [],
    this.expenseTotal = 0,
    this.budgetStatus,
    this.context,
    this.associations = const [],
    this.relatedMemories = const [],
  });

  factory TripDetailResponseModel.fromJson(Map<String, dynamic> json) {
    return TripDetailResponseModel(
      plan: TripModel.fromJson(json['plan'] as Map<String, dynamic>),
      itinerary: (json['itinerary'] as List<dynamic>?)
              ?.map(
                  (e) => DayItineraryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      expenses: (json['expenses'] as List<dynamic>?)
              ?.map(
                  (e) => TripExpenseModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      expenseTotal: (json['expense_total'] as num?)?.toInt() ?? 0,
      budgetStatus: json['budget_status'] != null
          ? BudgetStatusModel.fromJson(
              json['budget_status'] as Map<String, dynamic>)
          : null,
      context: json['context'] != null
          ? TripContextModel.fromJson(
              json['context'] as Map<String, dynamic>)
          : null,
      associations: (json['associations'] as List<dynamic>?)
              ?.map((e) => AssociationSummaryModel.fromJson(
                  e as Map<String, dynamic>))
              .toList() ??
          const [],
      relatedMemories: (json['related_memories'] as List<dynamic>?)
              ?.map((e) =>
                  RelatedMemoryModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}
