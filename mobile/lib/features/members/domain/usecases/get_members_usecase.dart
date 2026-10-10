import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/member.dart';
import '../repositories/member_repository.dart';

class GetMembersUseCase {
  final MemberRepository _repository;

  GetMembersUseCase(this._repository);

  Future<Either<Failure, List<Member>>> call() {
    return _repository.getMembers();
  }
}
