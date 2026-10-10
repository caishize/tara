import '../../domain/entities/vaccine.dart';

/// 疫苗记录数据模型
class VaccineRecordModel extends VaccineRecord {
  const VaccineRecordModel({
    required super.id,
    required super.childId,
    required super.vaccineName,
    required super.doseNumber,
    required super.scheduledDate,
    super.actualDate,
    required super.status,
    super.location,
    super.batchNumber,
    super.certificateUrl,
    super.notes,
    required super.createdAt,
    required super.updatedAt,
  });

  factory VaccineRecordModel.fromJson(Map<String, dynamic> json) {
    return VaccineRecordModel(
      id: json['id'] as String? ?? '',
      childId: json['child_id'] as String? ?? '',
      vaccineName: json['vaccine_name'] as String? ?? '',
      doseNumber: json['dose_number'] as int? ?? 1,
      scheduledDate: DateTime.parse(json['scheduled_date'] as String? ?? DateTime.now().toIso8601String()),
      actualDate: json['actual_date'] != null
          ? DateTime.parse(json['actual_date'] as String)
          : (json['completed_date'] != null ? DateTime.parse(json['completed_date'] as String) : null),
      status: _parseStatus(json['status'] as String? ?? 'scheduled'),
      location: json['location'] as String?,
      batchNumber: json['batch_number'] as String?,
      certificateUrl: json['certificate_url'] as String?,
      notes: json['notes'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(json['updated_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'child_id': childId,
      'vaccine_name': vaccineName,
      'dose_number': doseNumber,
      'scheduled_date': scheduledDate.toIso8601String().split('T').first,
      if (actualDate != null) 'actual_date': actualDate!.toIso8601String().split('T').first,
      'status': _statusToString(status),
      if (location != null) 'location': location,
      if (batchNumber != null) 'batch_number': batchNumber,
      if (certificateUrl != null) 'certificate_url': certificateUrl,
      if (notes != null) 'notes': notes,
    };
  }

  factory VaccineRecordModel.fromEntity(VaccineRecord entity) {
    return VaccineRecordModel(
      id: entity.id,
      childId: entity.childId,
      vaccineName: entity.vaccineName,
      doseNumber: entity.doseNumber,
      scheduledDate: entity.scheduledDate,
      actualDate: entity.actualDate,
      status: entity.status,
      location: entity.location,
      batchNumber: entity.batchNumber,
      certificateUrl: entity.certificateUrl,
      notes: entity.notes,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }

  static VaccineStatus _parseStatus(String status) {
    switch (status.toLowerCase()) {
      case 'scheduled':
        return VaccineStatus.scheduled;
      case 'completed':
        return VaccineStatus.completed;
      case 'overdue':
        return VaccineStatus.overdue;
      case 'skipped':
      case 'postponed':
        return VaccineStatus.skipped;
      default:
        return VaccineStatus.scheduled;
    }
  }

  static String _statusToString(VaccineStatus status) {
    switch (status) {
      case VaccineStatus.scheduled:
        return 'scheduled';
      case VaccineStatus.completed:
        return 'completed';
      case VaccineStatus.overdue:
        return 'overdue';
      case VaccineStatus.skipped:
        return 'skipped';
    }
  }
}
