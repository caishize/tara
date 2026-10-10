import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/member.dart';
import '../repositories/member_repository.dart';

class CreateMemberUseCase {
  final MemberRepository _repository;

  CreateMemberUseCase(this._repository);

  Future<Either<Failure, Member>> call(Member member) {
    return _repository.createMember(member);
  }
}
