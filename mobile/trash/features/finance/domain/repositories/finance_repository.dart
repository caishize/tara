import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/transaction.dart';

abstract class FinanceRepository {
  Future<Either<Failure, List<Transaction>>> getTransactions({
    int? year,
    int? month,
    String? type,
    String? category,
    int page = 1,
    int pageSize = 50,
  });

  Future<Either<Failure, Transaction>> getTransaction(String id);

  Future<Either<Failure, Transaction>> createTransaction(Transaction transaction);

  Future<Either<Failure, Transaction>> updateTransaction(String id, Transaction transaction);

  Future<Either<Failure, void>> deleteTransaction(String id);

  Future<Either<Failure, FinanceSummary>> getSummary(int year, int month);
}
