import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/member.dart';

/// Member repository interface
abstract class MemberRepository {
  /// Get all family members
  Future<Either<Failure, List<Member>>> getMembers();

  /// Get member by ID
  Future<Either<Failure, Member>> getMember(String id);

  /// Create new member
  Future<Either<Failure, Member>> createMember(Member member);

  /// Update member
  Future<Either<Failure, Member>> updateMember(Member member);

  /// Delete member
  Future<Either<Failure, void>> deleteMember(String id);
}
