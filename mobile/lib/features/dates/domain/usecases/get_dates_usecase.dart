import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/important_date.dart';
import '../repositories/date_repository.dart';

class GetDatesUseCase {
  final DateRepository _repository;

  GetDatesUseCase(this._repository);

  Future<Either<Failure, List<ImportantDate>>> call({
    String? memberId,
    DateType? dateType,
  }) {
    return _repository.getDates(memberId: memberId, dateType: dateType);
  }
}

class GetUpcomingDatesUseCase {
  final DateRepository _repository;

  GetUpcomingDatesUseCase(this._repository);

  Future<Either<Failure, List<ImportantDate>>> call({int daysAhead = 30}) {
    return _repository.getUpcomingDates(daysAhead: daysAhead);
  }
}

class CreateDateUseCase {
  final DateRepository _repository;

  CreateDateUseCase(this._repository);

  Future<Either<Failure, ImportantDate>> call(ImportantDate date) {
    return _repository.createDate(date);
  }
}

class UpdateDateUseCase {
  final DateRepository _repository;

  UpdateDateUseCase(this._repository);

  Future<Either<Failure, ImportantDate>> call(ImportantDate date) {
    return _repository.updateDate(date);
  }
}

class DeleteDateUseCase {
  final DateRepository _repository;

  DeleteDateUseCase(this._repository);

  Future<Either<Failure, void>> call(String id) {
    return _repository.deleteDate(id);
  }
}
