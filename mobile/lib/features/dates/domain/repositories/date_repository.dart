import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/important_date.dart';

abstract class DateRepository {
  Future<Either<Failure, List<ImportantDate>>> getDates({
    String? memberId,
    DateType? dateType,
  });

  Future<Either<Failure, List<ImportantDate>>> getUpcomingDates({
    int daysAhead = 30,
  });

  Future<Either<Failure, ImportantDate>> getDateById(String id);

  Future<Either<Failure, ImportantDate>> createDate(ImportantDate date);

  Future<Either<Failure, ImportantDate>> updateDate(ImportantDate date);

  Future<Either<Failure, void>> deleteDate(String id);
}
