import '../../domain/entities/shopping_list.dart';

class ShoppingListModel extends ShoppingList {
  const ShoppingListModel({
    required super.id,
    required super.familyId,
    required super.createdBy,
    required super.listName,
    required super.listType,
    required super.status,
    super.dueDate,
    super.totalItems,
    super.purchasedItems,
    super.completionPercentage,
    required super.createdAt,
    required super.updatedAt,
    super.completedAt,
  });

  factory ShoppingListModel.fromJson(Map<String, dynamic> json) {
    return ShoppingListModel(
      id: json['id']?.toString() ?? '',
      familyId: json['family_id']?.toString() ?? '',
      createdBy: json['created_by']?.toString() ?? '',
      listName: json['list_name'] ?? '',
      listType: _parseListType(json['list_type']),
      status: _parseListStatus(json['status']),
      dueDate: json['due_date'] != null ? DateTime.tryParse(json['due_date']) : null,
      totalItems: json['total_items'] ?? 0,
      purchasedItems: json['purchased_items'] ?? 0,
      completionPercentage: (json['completion_percentage'] ?? 0).toDouble(),
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] ?? '') ?? DateTime.now(),
      completedAt: json['completed_at'] != null ? DateTime.tryParse(json['completed_at']) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'family_id': familyId,
      'created_by': createdBy,
      'list_name': listName,
      'list_type': _listTypeToString(listType),
      'status': _listStatusToString(status),
      'due_date': dueDate?.toIso8601String(),
      'total_items': totalItems,
      'purchased_items': purchasedItems,
      'completion_percentage': completionPercentage,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'completed_at': completedAt?.toIso8601String(),
    };
  }

  static ListType _parseListType(String? type) {
    switch (type?.toLowerCase()) {
      case 'regular':
        return ListType.regular;
      case 'replenishment':
        return ListType.replenishment;
      case 'seasonal':
        return ListType.seasonal;
      case 'bulk':
        return ListType.bulk;
      case 'urgent':
        return ListType.urgent;
      default:
        return ListType.regular;
    }
  }

  static ListStatus _parseListStatus(String? status) {
    switch (status?.toLowerCase()) {
      case 'active':
        return ListStatus.active;
      case 'in_progress':
        return ListStatus.inProgress;
      case 'completed':
        return ListStatus.completed;
      case 'archived':
        return ListStatus.archived;
      default:
        return ListStatus.active;
    }
  }

  static String _listTypeToString(ListType type) {
    switch (type) {
      case ListType.regular:
        return 'regular';
      case ListType.replenishment:
        return 'replenishment';
      case ListType.seasonal:
        return 'seasonal';
      case ListType.bulk:
        return 'bulk';
      case ListType.urgent:
        return 'urgent';
    }
  }

  static String _listStatusToString(ListStatus status) {
    switch (status) {
      case ListStatus.active:
        return 'active';
      case ListStatus.inProgress:
        return 'in_progress';
      case ListStatus.completed:
        return 'completed';
      case ListStatus.archived:
        return 'archived';
    }
  }
}
