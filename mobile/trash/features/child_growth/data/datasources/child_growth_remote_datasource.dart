import '../../../../core/network/api_client.dart';
import '../models/growth_record_model.dart';
import '../models/milestone_model.dart';
import '../models/vaccine_model.dart';

/// 小孩成长远程数据源
class ChildGrowthRemoteDataSource {
  final ApiClient _apiClient;

  ChildGrowthRemoteDataSource({required ApiClient apiClient})
      : _apiClient = apiClient;

  // ==================== 成长记录 ====================

  /// 添加成长记录
  Future<Map<String, dynamic>> addGrowthRecord({
    required String childId,
    required DateTime recordDate,
    double? height,
    double? weight,
    double? headCircumference,
    String? notes,
  }) async {
    final response = await _apiClient.post('/child/growth', data: {
      'child_id': childId,
      'record_date': recordDate.toIso8601String().split('T').first,
      if (height != null) 'height': height,
      if (weight != null) 'weight': weight,
      if (headCircumference != null) 'head_circumference': headCircumference,
      if (notes != null) 'notes': notes,
    });
    return response;
  }

  /// 获取成长曲线数据
  Future<GrowthCurveDataModel> getGrowthCurveData(String childId) async {
    final response = await _apiClient.get('/child/growth/$childId');
    return GrowthCurveDataModel.fromJson(response);
  }

  // ==================== 里程碑 ====================

  /// 添加里程碑
  Future<MilestoneModel> addMilestone({
    required String childId,
    required String milestoneType,
    required String title,
    required DateTime achievedDate,
    String? description,
    String? photoUrl,
    String? videoUrl,
    String? notes,
  }) async {
    final response = await _apiClient.post('/child/milestones', data: {
      'child_id': childId,
      'milestone_type': milestoneType,
      'title': title,
      'achieved_date': achievedDate.toIso8601String().split('T').first,
      if (description != null) 'description': description,
      if (photoUrl != null) 'photo_url': photoUrl,
      if (videoUrl != null) 'video_url': videoUrl,
      if (notes != null) 'notes': notes,
    });
    return MilestoneModel.fromJson(response);
  }

  /// 获取里程碑列表
  Future<List<MilestoneModel>> getMilestones(String childId) async {
    final response = await _apiClient.get('/child/milestones/$childId');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => MilestoneModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  // ==================== 疫苗 ====================

  /// 获取疫苗记录列表
  Future<List<VaccineRecordModel>> getVaccines(String childId) async {
    final response = await _apiClient.get('/child/vaccines/$childId');
    final List<dynamic> data = response is List ? response : [];
    return data.map((e) => VaccineRecordModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// 更新疫苗状态
  Future<VaccineRecordModel> updateVaccineStatus({
    required String vaccineId,
    required String status,
    DateTime? actualDate,
    String? location,
    String? batchNumber,
    String? notes,
  }) async {
    final response = await _apiClient.put('/child/vaccines/$vaccineId', data: {
      'status': status,
      if (actualDate != null) 'actual_date': actualDate.toIso8601String().split('T').first,
      if (location != null) 'location': location,
      if (batchNumber != null) 'batch_number': batchNumber,
      if (notes != null) 'notes': notes,
    });
    return VaccineRecordModel.fromJson(response);
  }
}
