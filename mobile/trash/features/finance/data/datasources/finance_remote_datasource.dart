import 'package:dio/dio.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/error/exceptions.dart';
import '../models/transaction_model.dart';

abstract class FinanceRemoteDataSource {
  Future<List<TransactionModel>> getTransactions({
    int? year,
    int? month,
    String? type,
    String? category,
    int page = 1,
    int pageSize = 50,
  });

  Future<TransactionModel> getTransaction(String id);

  Future<TransactionModel> createTransaction(TransactionModel transaction);

  Future<TransactionModel> updateTransaction(String id, TransactionModel transaction);

  Future<void> deleteTransaction(String id);

  Future<FinanceSummaryModel> getSummary(int year, int month);
}

class FinanceRemoteDataSourceImpl implements FinanceRemoteDataSource {
  final ApiClient apiClient;

  FinanceRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<List<TransactionModel>> getTransactions({
    int? year,
    int? month,
    String? type,
    String? category,
    int page = 1,
    int pageSize = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'page_size': pageSize,
      };
      if (year != null) queryParams['year'] = year;
      if (month != null) queryParams['month'] = month;
      if (type != null) queryParams['type'] = type;
      if (category != null) queryParams['category'] = category;

      final response = await apiClient.get(
        '/finance/transactions',
        queryParameters: queryParams,
      );

      if (response is List) {
        return response.map((json) => TransactionModel.fromJson(json)).toList();
      }

      // Handle paginated response
      final data = response['items'] ?? response['data'] ?? response;
      if (data is List) {
        return data.map((json) => TransactionModel.fromJson(json)).toList();
      }

      return [];
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to load transactions');
    }
  }

  @override
  Future<TransactionModel> getTransaction(String id) async {
    try {
      final response = await apiClient.get('/finance/transactions/$id');
      return TransactionModel.fromJson(response);
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to load transaction');
    }
  }

  @override
  Future<TransactionModel> createTransaction(TransactionModel transaction) async {
    try {
      final response = await apiClient.post(
        '/finance/transactions',
        data: transaction.toCreateJson(),
      );
      return TransactionModel.fromJson(response);
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to create transaction');
    }
  }

  @override
  Future<TransactionModel> updateTransaction(String id, TransactionModel transaction) async {
    try {
      final response = await apiClient.put(
        '/finance/transactions/$id',
        data: transaction.toCreateJson(),
      );
      return TransactionModel.fromJson(response);
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to update transaction');
    }
  }

  @override
  Future<void> deleteTransaction(String id) async {
    try {
      await apiClient.delete('/finance/transactions/$id');
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to delete transaction');
    }
  }

  @override
  Future<FinanceSummaryModel> getSummary(int year, int month) async {
    try {
      final response = await apiClient.get('/finance/summary/$year/$month');
      return FinanceSummaryModel.fromJson(response);
    } on DioException catch (e) {
      throw ServerException(message: e.message ?? 'Failed to load summary');
    }
  }
}
