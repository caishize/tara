import '../../../../core/storage/local_storage.dart';
import '../models/member_model.dart';

class MemberLocalDataSource {
  final LocalStorage _storage;
  static const _key = 'cached_members';

  MemberLocalDataSource(this._storage);

  Future<void> cacheMembers(List<MemberModel> members) async {
    await _storage.saveJsonList(
      _key,
      members.map((m) => m.toJson()).toList(),
    );
  }

  List<MemberModel>? getCachedMembers() {
    final cached = _storage.getJsonList(_key);
    if (cached == null) return null;
    return cached.map((json) => MemberModel.fromJson(json)).toList();
  }

  Future<void> clearCache() async {
    await _storage.remove(_key);
  }
}
