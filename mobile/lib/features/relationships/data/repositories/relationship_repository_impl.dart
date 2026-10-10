import '../../domain/entities/relationship_member.dart';
import '../../domain/repositories/relationship_repository.dart';
import '../datasources/relationship_remote_datasource.dart';

/// Implementation of RelationshipRepository
class RelationshipRepositoryImpl implements RelationshipRepository {
  final RelationshipRemoteDataSource _remoteDataSource;

  RelationshipRepositoryImpl({
    required RelationshipRemoteDataSource remoteDataSource,
  }) : _remoteDataSource = remoteDataSource;

  @override
  Future<RelationshipData> getAllMembersWithHealth({
    String? category,
    String sortBy = 'score',
    String sortOrder = 'desc',
  }) async {
    return await _remoteDataSource.getAllMembersWithHealth(
      category: category,
      sortBy: sortBy,
      sortOrder: sortOrder,
    );
  }

  @override
  Future<RelationshipMember> getMemberHealth(String memberId) async {
    return await _remoteDataSource.getMemberHealth(memberId);
  }

  @override
  Future<List<RelationshipMember>> getAttentionNeeded({int limit = 10}) async {
    return await _remoteDataSource.getAttentionNeeded(limit: limit);
  }

  @override
  Future<Map<String, dynamic>> getRelationshipGraph({
    String? centerMemberId,
  }) async {
    return await _remoteDataSource.getRelationshipGraph(
      centerMemberId: centerMemberId,
    );
  }

  @override
  Future<bool> recordInteraction({
    required String memberId,
    required String interactionType,
    String? description,
    DateTime? interactionDate,
  }) async {
    final result = await _remoteDataSource.recordInteraction(
      memberId: memberId,
      interactionType: interactionType,
      description: description,
      interactionDate: interactionDate,
    );
    return result['success'] == true;
  }
}
