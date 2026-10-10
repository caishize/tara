import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/gift.dart';

abstract class GiftRepository {
  Future<Either<Failure, List<Gift>>> getPopularGifts({
    GiftCategory? category,
    int? limit,
  });

  Future<Either<Failure, List<Gift>>> searchGifts({
    required String query,
    GiftCategory? category,
    double? minPrice,
    double? maxPrice,
  });

  /// Generate AI gift recommendations for a member
  Future<Either<Failure, GiftRecommendation>> generateRecommendation({
    required String memberId,
    required GiftOccasion occasion,
    int? budgetMin,
    int? budgetMax,
    String? urgency,
  });

  /// Get recommendation history, optionally filtered by member
  Future<Either<Failure, List<GiftRecommendation>>> getRecommendationHistory({
    String? memberId,
    int limit = 10,
    int offset = 0,
  });

  /// Get member gift memory (preferences, history, things to avoid)
  Future<Either<Failure, MemberGiftMemory>> getMemberGiftMemory(String memberId);

  /// Get gift history for a member
  Future<Either<Failure, List<GiftHistoryItem>>> getMemberGiftHistory(String memberId);

  /// Get smart date suggestions for a member (important dates + holidays)
  Future<Either<Failure, SmartDatesResult>> getSmartDatesForMember(
    String memberId, {
    int daysAhead = 90,
  });

  /// Get intelligent budget suggestion for a member
  Future<Either<Failure, BudgetSuggestion>> getBudgetSuggestion({
    required String memberId,
    String? occasion,
  });

  Future<Either<Failure, List<Gift>>> getSavedGifts();

  Future<Either<Failure, void>> saveGift(String giftId);

  Future<Either<Failure, void>> unsaveGift(String giftId);
}
