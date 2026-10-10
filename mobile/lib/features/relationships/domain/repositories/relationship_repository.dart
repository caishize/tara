import '../entities/relationship_member.dart';

/// Repository interface for relationship management
abstract class RelationshipRepository {
  /// Get all members with health scores
  Future<RelationshipData> getAllMembersWithHealth({
    String? category,
    String sortBy = 'score',
    String sortOrder = 'desc',
  });

  /// Get single member health details
  Future<RelationshipMember> getMemberHealth(String memberId);

  /// Get members needing attention
  Future<List<RelationshipMember>> getAttentionNeeded({int limit = 10});

  /// Get relationship graph data
  Future<Map<String, dynamic>> getRelationshipGraph({String? centerMemberId});

  /// Record an interaction
  Future<bool> recordInteraction({
    required String memberId,
    required String interactionType,
    String? description,
    DateTime? interactionDate,
  });
}
