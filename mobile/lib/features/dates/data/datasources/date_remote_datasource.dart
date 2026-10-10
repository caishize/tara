import '../../../../core/network/api_client.dart';
import '../../domain/entities/important_date.dart';
import '../models/important_date_model.dart';

class DateRemoteDataSource {
  final ApiClient _client;

  DateRemoteDataSource(this._client);

  Future<List<ImportantDateModel>> getDates({
    String? memberId,
    DateType? dateType,
  }) async {
    final queryParams = <String, dynamic>{};
    if (memberId != null) queryParams['member_id'] = memberId;
    if (dateType != null) queryParams['date_type'] = dateType.name;

    final response = await _client.get<List<dynamic>>(
      '/dates/',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );

    return response
        .map((json) => ImportantDateModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<List<ImportantDateModel>> getUpcomingDates({int daysAhead = 30}) async {
    final response = await _client.get<List<dynamic>>(
      '/dates/upcoming',
      queryParameters: {'days_ahead': daysAhead},
    );

    return response
        .map((json) => ImportantDateModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<ImportantDateModel> getDateById(String id) async {
    final response = await _client.get<Map<String, dynamic>>('/dates/$id');
    return ImportantDateModel.fromJson(response);
  }

  Future<ImportantDateModel> createDate(ImportantDateModel date) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/dates/',
      data: date.toJson(),
    );
    return ImportantDateModel.fromJson(response);
  }

  Future<ImportantDateModel> updateDate(ImportantDateModel date) async {
    final response = await _client.put<Map<String, dynamic>>(
      '/dates/${date.id}',
      data: date.toJson(),
    );
    return ImportantDateModel.fromJson(response);
  }

  Future<void> deleteDate(String id) async {
    await _client.delete('/dates/$id');
  }
}
