import 'package:dartz/dartz.dart';
import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/gift.dart';
import '../../domain/repositories/gift_repository.dart';
import '../datasources/gift_remote_datasource.dart';

class GiftRepositoryImpl implements GiftRepository {
  final GiftRemoteDataSource remoteDataSource;

  GiftRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, List<Gift>>> getPopularGifts({
    GiftCategory? category,
    int? limit,
  }) async {
    try {
      final gifts = await remoteDataSource.getPopularGifts(
        category: category,
        limit: limit,
      );
      return Right(gifts);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Gift>>> searchGifts({
    required String query,
    GiftCategory? category,
    double? minPrice,
    double? maxPrice,
  }) async {
    try {
      final gifts = await remoteDataSource.searchGifts(
        query: query,
        category: category,
        minPrice: minPrice,
        maxPrice: maxPrice,
      );
      return Right(gifts);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, GiftRecommendation>> generateRecommendation({
    required String memberId,
    required GiftOccasion occasion,
    int? budgetMin,
    int? budgetMax,
    String? urgency,
  }) async {
    try {
      final recommendation = await remoteDataSource.generateRecommendation(
        memberId: memberId,
        occasion: occasion,
        budgetMin: budgetMin,
        budgetMax: budgetMax,
        urgency: urgency,
      );
      return Right(recommendation);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<GiftRecommendation>>> getRecommendationHistory({
    String? memberId,
    int limit = 10,
    int offset = 0,
  }) async {
    try {
      final history = await remoteDataSource.getRecommendationHistory(
        memberId: memberId,
        limit: limit,
        offset: offset,
      );
      return Right(history);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, MemberGiftMemory>> getMemberGiftMemory(String memberId) async {
    try {
      final memory = await remoteDataSource.getMemberGiftMemory(memberId);
      return Right(memory);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<GiftHistoryItem>>> getMemberGiftHistory(String memberId) async {
    try {
      final history = await remoteDataSource.getMemberGiftHistory(memberId);
      return Right(history);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, SmartDatesResult>> getSmartDatesForMember(
    String memberId, {
    int daysAhead = 90,
  }) async {
    try {
      final result = await remoteDataSource.getSmartDatesForMember(
        memberId,
        daysAhead: daysAhead,
      );
      return Right(result);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, BudgetSuggestion>> getBudgetSuggestion({
    required String memberId,
    String? occasion,
  }) async {
    try {
      final suggestion = await remoteDataSource.getBudgetSuggestion(
        memberId: memberId,
        occasion: occasion,
      );
      return Right(suggestion);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, List<Gift>>> getSavedGifts() async {
    try {
      final gifts = await remoteDataSource.getSavedGifts();
      return Right(gifts);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> saveGift(String giftId) async {
    try {
      await remoteDataSource.saveGift(giftId);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }

  @override
  Future<Either<Failure, void>> unsaveGift(String giftId) async {
    try {
      await remoteDataSource.unsaveGift(giftId);
      return const Right(null);
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(UnknownFailure(e.toString()));
    }
  }
}
