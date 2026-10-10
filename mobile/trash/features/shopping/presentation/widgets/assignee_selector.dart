import 'package:flutter/material.dart';

/// 家庭成员信息（简化版）
class FamilyMemberInfo {
  final String id;
  final String name;
  final String? nickname;
  final String? avatar;

  const FamilyMemberInfo({
    required this.id,
    required this.name,
    this.nickname,
    this.avatar,
  });
}

/// 购买人选择器
/// 匹配原型设计：我、老婆、儿、所有人
class AssigneeSelector extends StatelessWidget {
  final String? selectedAssigneeId;
  final ValueChanged<String?> onAssigneeChanged;
  final List<FamilyMemberInfo> familyMembers;
  final String currentUserId;

  const AssigneeSelector({
    super.key,
    this.selectedAssigneeId,
    required this.onAssigneeChanged,
    required this.familyMembers,
    required this.currentUserId,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '指定购买人',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w500,
              ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            // 我
            _buildAssigneeChip(
              context,
              id: currentUserId,
              label: '我',
              icon: '🙋',
              isMe: true,
            ),
            // 其他家庭成员
            ...familyMembers
                .where((m) => m.id != currentUserId)
                .map((member) => _buildAssigneeChip(
                      context,
                      id: member.id,
                      label: member.nickname ?? member.name,
                      icon: _getMemberIcon(member),
                    )),
            // 所有人
            _buildAssigneeChip(
              context,
              id: null,
              label: '所有人',
              icon: '👨‍👩‍👧‍👦',
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildAssigneeChip(
    BuildContext context, {
    required String? id,
    required String label,
    required String icon,
    bool isMe = false,
  }) {
    final isSelected = selectedAssigneeId == id;
    final primaryColor = Theme.of(context).primaryColor;

    return GestureDetector(
      onTap: () => onAssigneeChanged(id),
      child: Column(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isSelected ? primaryColor.withOpacity(0.1) : Colors.grey.shade100,
              border: Border.all(
                color: isSelected ? primaryColor : Colors.grey.shade300,
                width: isSelected ? 2 : 1,
              ),
            ),
            child: Center(
              child: Text(
                icon,
                style: const TextStyle(fontSize: 24),
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: isSelected ? primaryColor : Colors.black87,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }

  String _getMemberIcon(FamilyMemberInfo member) {
    // 根据成员名称推断图标
    final name = member.name.toLowerCase();
    if (name.contains('老婆') || name.contains('妻')) {
      return '👩';
    } else if (name.contains('儿') || name.contains('子')) {
      return '👦';
    } else if (name.contains('女') || name.contains('闺女')) {
      return '👧';
    } else if (name.contains('爸') || name.contains('父')) {
      return '👨';
    } else if (name.contains('妈') || name.contains('母')) {
      return '👩';
    }
    return '👤';
  }
}
