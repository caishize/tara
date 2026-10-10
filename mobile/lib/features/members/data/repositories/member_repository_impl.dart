import 'package:dartz/dartz.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/member.dart';
import '../../domain/repositories/member_repository.dart';
import '../datasources/member_local_datasource.dart';
import '../datasources/member_remote_datasource.dart';
import '../models/member_model.dart';

class MemberRepositoryImpl implements MemberRepository {
  final MemberRemoteDataSource remoteDataSource;
  final MemberLocalDataSource localDataSource;

  MemberRepositoryImpl({
    required this.remoteDataSource,
    required this.localDataSource,
  });

  @override
  Future<Either<Failure, List<Member>>> getMembers() async {
    try {
      final members = await remoteDataSource.getMembers();
      await localDataSource.cacheMembers(members);
      return Right(members);
    } on NetworkException catch (e) {
      // Try to get from cache when network fails
      final cached = localDataSource.getCachedMembers();
      if (cached != null) {
        return Right(cached);
      }
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('获取成员列表失败'));
    }
  }

  @override
  Future<Either<Failure, Member>> getMember(String id) async {
    try {
      final member = await remoteDataSource.getMember(id);
      return Right(member);
    } on NotFoundException {
      return const Left(NotFoundFailure('成员不存在'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('获取成员信息失败'));
    }
  }

  @override
  Future<Either<Failure, Member>> createMember(Member member) async {
    try {
      final model = MemberModel.fromEntity(member);
      final created = await remoteDataSource.createMember(model);
      return Right(created);
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('创建成员失败'));
    }
  }

  @override
  Future<Either<Failure, Member>> updateMember(Member member) async {
    try {
      final model = MemberModel.fromEntity(member);
      final updated = await remoteDataSource.updateMember(model);
      return Right(updated);
    } on NotFoundException {
      return const Left(NotFoundFailure('成员不存在'));
    } on ValidationException catch (e) {
      return Left(ValidationFailure(e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('更新成员失败'));
    }
  }

  @override
  Future<Either<Failure, void>> deleteMember(String id) async {
    try {
      await remoteDataSource.deleteMember(id);
      return const Right(null);
    } on NotFoundException {
      return const Left(NotFoundFailure('成员不存在'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('删除成员失败'));
    }
  }
}
