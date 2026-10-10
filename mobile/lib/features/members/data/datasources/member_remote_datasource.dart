import '../../../../core/network/api_client.dart';
import '../models/member_model.dart';
import '../models/member_insight_model.dart';
import '../models/work_history_model.dart';
import '../models/professional_relation_model.dart';

class MemberRemoteDataSource {
  final ApiClient _client;

  MemberRemoteDataSource(this._client);

  // ==========================================================================
  // Member CRUD
  // ==========================================================================

  Future<List<MemberModel>> getMembers() async {
    final response = await _client.get<List<dynamic>>('/members/');
    return response.map((json) => MemberModel.fromJson(json)).toList();
  }

  Future<MemberModel> getMember(String id) async {
    final response = await _client.get<Map<String, dynamic>>('/members/$id');
    return MemberModel.fromJson(response);
  }

  Future<MemberModel> createMember(MemberModel member) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/members/',
      data: member.toCreateRequest(),
    );
    return MemberModel.fromJson(response);
  }

  Future<MemberModel> updateMember(MemberModel member) async {
    final response = await _client.put<Map<String, dynamic>>(
      '/members/${member.id}',
      data: member.toCreateRequest(),
    );
    return MemberModel.fromJson(response);
  }

  Future<void> deleteMember(String id) async {
    await _client.delete('/members/$id');
  }

  // ==========================================================================
  // Member Insights
  // ==========================================================================

  Future<List<MemberInsightModel>> getMemberInsights(
    String memberId, {
    int limit = 20,
  }) async {
    final response = await _client.get<List<dynamic>>(
      '/members/$memberId/insights',
      queryParameters: {'limit': limit},
    );
    return response
        .map((json) => MemberInsightModel.fromJson(json))
        .toList();
  }

  // ==========================================================================
  // Work History CRUD
  // ==========================================================================

  Future<List<WorkHistoryModel>> getWorkHistory(
    String memberId, {
    bool includePast = true,
  }) async {
    final response = await _client.get<List<dynamic>>(
      '/members/$memberId/work-history',
      queryParameters: {'include_past': includePast},
    );
    return response.map((json) => WorkHistoryModel.fromJson(json)).toList();
  }

  Future<WorkHistoryModel> createWorkHistory(
    String memberId,
    WorkHistoryModel workHistory,
  ) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/members/$memberId/work-history',
      data: workHistory.toCreateRequest(),
    );
    return WorkHistoryModel.fromJson(response);
  }

  Future<WorkHistoryModel> updateWorkHistory(
    String memberId,
    WorkHistoryModel workHistory,
  ) async {
    final response = await _client.put<Map<String, dynamic>>(
      '/members/$memberId/work-history/${workHistory.id}',
      data: workHistory.toCreateRequest(),
    );
    return WorkHistoryModel.fromJson(response);
  }

  Future<void> deleteWorkHistory(String memberId, String workHistoryId) async {
    await _client.delete('/members/$memberId/work-history/$workHistoryId');
  }

  // ==========================================================================
  // Professional Relations CRUD
  // ==========================================================================

  Future<List<ProfessionalRelationType>> getProfessionalRelationTypes() async {
    final response = await _client.get<List<dynamic>>(
      '/members/professional-relation-types',
    );
    return response.map((json) {
      final value = json['value'] as String;
      return ProfessionalRelationType.fromValue(value);
    }).toList();
  }

  Future<List<ProfessionalRelationModel>> getProfessionalRelations(
    String memberId, {
    bool includePast = true,
  }) async {
    final response = await _client.get<List<dynamic>>(
      '/members/$memberId/professional-relations',
      queryParameters: {'include_past': includePast},
    );
    return response
        .map((json) => ProfessionalRelationModel.fromJson(json))
        .toList();
  }

  Future<ProfessionalRelationModel> createProfessionalRelation(
    ProfessionalRelationModel relation,
  ) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/members/professional-relations',
      data: relation.toCreateRequest(),
    );
    return ProfessionalRelationModel.fromJson(response);
  }

  Future<ProfessionalRelationModel> updateProfessionalRelation(
    ProfessionalRelationModel relation,
  ) async {
    final response = await _client.put<Map<String, dynamic>>(
      '/members/professional-relations/${relation.id}',
      data: relation.toCreateRequest(),
    );
    return ProfessionalRelationModel.fromJson(response);
  }

  Future<void> deleteProfessionalRelation(String relationId) async {
    await _client.delete('/members/professional-relations/$relationId');
  }
}
