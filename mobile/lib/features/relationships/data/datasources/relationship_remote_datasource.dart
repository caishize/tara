import '../../../../core/network/api_client.dart';
import '../models/relationship_member_model.dart';

/// Remote data source for relationship health data
class RelationshipRemoteDataSource {
  final ApiClient _apiClient;

  RelationshipRemoteDataSource(this._apiClient);

  /// Get all members with health scores
  Future<RelationshipDataModel> getAllMembersWithHealth({
    String? category,
    String sortBy = 'score',
    String sortOrder = 'desc',
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/health/members',
      queryParameters: {
        if (category != null) 'category': category,
        'sort_by': sortBy,
        'sort_order': sortOrder,
      },
    );
    return RelationshipDataModel.fromJson(response);
  }

  /// Get single member health details
  Future<RelationshipMemberModel> getMemberHealth(String memberId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/health/members/$memberId',
    );
    return RelationshipMemberModel.fromJson(response);
  }

  /// Get members needing attention
  Future<List<RelationshipMemberModel>> getAttentionNeeded({int limit = 10}) async {
    final response = await _apiClient.get<List<dynamic>>(
      '/relationships/health/attention',
      queryParameters: {'limit': limit},
    );
    return response
        .map((item) =>
            RelationshipMemberModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// Get relationship graph data
  Future<Map<String, dynamic>> getRelationshipGraph({String? centerMemberId}) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/health/graph',
      queryParameters: {
        if (centerMemberId != null) 'center_member_id': centerMemberId,
      },
    );
    return response;
  }

  /// Record an interaction
  Future<Map<String, dynamic>> recordInteraction({
    required String memberId,
    required String interactionType,
    String? description,
    DateTime? interactionDate,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/relationships/health/interactions',
      data: {
        'member_id': memberId,
        'interaction_type': interactionType,
        if (description != null) 'description': description,
        if (interactionDate != null)
          'interaction_date': interactionDate.toIso8601String().split('T')[0],
      },
    );
    return response;
  }

  // ============ Favor Ledger APIs ============

  /// Get favor statistics
  Future<Map<String, dynamic>> getFavorStatistics(String familyId) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/favors/statistics',
      queryParameters: {'family_id': familyId},
    );
    return response;
  }

  /// Get all favor records
  Future<Map<String, dynamic>> getFavorRecords({
    required String familyId,
    String? direction,
    String? status,
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/favors',
      queryParameters: {
        'family_id': familyId,
        if (direction != null) 'direction': direction,
        if (status != null) 'status': status,
        'page': page,
        'page_size': pageSize,
      },
    );
    return response;
  }

  /// Get pending favor returns
  Future<List<dynamic>> getPendingFavors(String familyId) async {
    final response = await _apiClient.get<List<dynamic>>(
      '/relationships/favors/pending',
      queryParameters: {'family_id': familyId},
    );
    return response;
  }

  /// Quick create a favor record
  Future<Map<String, dynamic>> createQuickFavor({
    required String familyId,
    required String contactName,
    String? contactId,
    required double amount,
    required String direction,
    required String eventType,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/relationships/favors/quick',
      data: {
        'family_id': familyId,
        'contact_name': contactName,
        if (contactId != null) 'contact_id': contactId,
        'amount': amount,
        'direction': direction,
        'event_type': eventType,
      },
    );
    return response;
  }

  // ============ Smart Groups APIs ============

  /// Get all smart groups
  Future<List<dynamic>> getSmartGroups({bool includeEmpty = false}) async {
    final response = await _apiClient.get<List<dynamic>>(
      '/relationships/groups',
      queryParameters: {'include_empty': includeEmpty},
    );
    return response;
  }

  /// Get smart group detail
  Future<Map<String, dynamic>> getSmartGroupDetail(String groupKey) async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/groups/$groupKey',
    );
    return response;
  }

  /// Get daily reminders
  Future<Map<String, dynamic>> getDailyReminders() async {
    final response = await _apiClient.get<Map<String, dynamic>>(
      '/relationships/groups/reminders/daily',
    );
    return response;
  }
}
