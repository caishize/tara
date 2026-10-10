import 'package:flutter/material.dart';
import '../../domain/entities/smart_itinerary.dart';

class FamilyCompositionForm extends StatefulWidget {
  final Function(FamilyComposition, ItineraryPreferences) onCompositionChanged;
  final FamilyComposition? initialComposition;
  final ItineraryPreferences? initialPreferences;

  const FamilyCompositionForm({
    super.key,
    required this.onCompositionChanged,
    this.initialComposition,
    this.initialPreferences,
  });

  @override
  State<FamilyCompositionForm> createState() => _FamilyCompositionFormState();
}

class _FamilyCompositionFormState extends State<FamilyCompositionForm> {
  late List<FamilyMember> _children;
  late List<FamilyMember> _elderly;
  late bool _enableNapTime;
  late bool _weatherAware;
  late bool _includeLocalTips;

  @override
  void initState() {
    super.initState();
    _children = List.from(widget.initialComposition?.children ?? []);
    _elderly = List.from(widget.initialComposition?.elderly ?? []);
    _enableNapTime = widget.initialPreferences?.enableNapTime ?? true;
    _weatherAware = widget.initialPreferences?.weatherAware ?? true;
    _includeLocalTips = widget.initialPreferences?.includeLocalTips ?? true;
  }

  void _notifyChange() {
    widget.onCompositionChanged(
      FamilyComposition(
        children: _children,
        elderly: _elderly,
      ),
      ItineraryPreferences(
        enableNapTime: _enableNapTime,
        weatherAware: _weatherAware,
        includeLocalTips: _includeLocalTips,
      ),
    );
  }

  void _addChild() {
    setState(() {
      _children.add(const FamilyMember(age: 5));
    });
    _notifyChange();
  }

  void _removeChild(int index) {
    setState(() {
      _children.removeAt(index);
    });
    _notifyChange();
  }

  void _updateChildAge(int index, int age) {
    setState(() {
      _children[index] = FamilyMember(age: age);
    });
    _notifyChange();
  }

  void _addElderly() {
    setState(() {
      _elderly.add(const FamilyMember(age: 70));
    });
    _notifyChange();
  }

  void _removeElderly(int index) {
    setState(() {
      _elderly.removeAt(index);
    });
    _notifyChange();
  }

  void _updateElderlyAge(int index, int age) {
    setState(() {
      _elderly[index] = FamilyMember(age: age);
    });
    _notifyChange();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.family_restroom, size: 20),
              const SizedBox(width: 8),
              const Text(
                '家庭成员 & 偏好设置',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              if (_children.isNotEmpty || _elderly.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Theme.of(context).primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '已配置',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).primaryColor,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),

          // Children section
          _buildSectionHeader('儿童 (0-12岁)', Icons.child_care, _addChild),
          const SizedBox(height: 8),
          if (_children.isEmpty)
            Text('暂无儿童', style: TextStyle(color: Colors.grey[500], fontSize: 13))
          else
            ..._children.asMap().entries.map((entry) {
              return _buildAgeSelector(
                index: entry.key,
                age: entry.value.age,
                minAge: 0,
                maxAge: 12,
                onAgeChanged: (age) => _updateChildAge(entry.key, age),
                onRemove: () => _removeChild(entry.key),
              );
            }),

          const SizedBox(height: 16),

          // Elderly section
          _buildSectionHeader('老人 (65岁以上)', Icons.elderly, _addElderly),
          const SizedBox(height: 8),
          if (_elderly.isEmpty)
            Text('暂无老人', style: TextStyle(color: Colors.grey[500], fontSize: 13))
          else
            ..._elderly.asMap().entries.map((entry) {
              return _buildAgeSelector(
                index: entry.key,
                age: entry.value.age,
                minAge: 65,
                maxAge: 100,
                onAgeChanged: (age) => _updateElderlyAge(entry.key, age),
                onRemove: () => _removeElderly(entry.key),
              );
            }),

          const SizedBox(height: 16),
          const Divider(),
          const SizedBox(height: 8),

          // Preferences
          _buildSwitch(
            title: '午睡时间',
            subtitle: '14:00-16:00 安排休息',
            value: _enableNapTime,
            onChanged: (value) {
              setState(() => _enableNapTime = value);
              _notifyChange();
            },
          ),
          _buildSwitch(
            title: '天气感知',
            subtitle: '根据天气调整行程',
            value: _weatherAware,
            onChanged: (value) {
              setState(() => _weatherAware = value);
              _notifyChange();
            },
          ),
          _buildSwitch(
            title: '本地提示',
            subtitle: '包含当地人推荐',
            value: _includeLocalTips,
            onChanged: (value) {
              setState(() => _includeLocalTips = value);
              _notifyChange();
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon, VoidCallback onAdd) {
    return Row(
      children: [
        Icon(icon, size: 18, color: Colors.grey[700]),
        const SizedBox(width: 4),
        Text(
          title,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
        ),
        const Spacer(),
        TextButton.icon(
          onPressed: onAdd,
          icon: const Icon(Icons.add, size: 18),
          label: const Text('添加'),
          style: TextButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 8),
          ),
        ),
      ],
    );
  }

  Widget _buildAgeSelector({
    required int index,
    required int age,
    required int minAge,
    required int maxAge,
    required Function(int) onAgeChanged,
    required VoidCallback onRemove,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.grey[300]!),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${index + 1}号', style: const TextStyle(fontSize: 13)),
                const SizedBox(width: 8),
                DropdownButton<int>(
                  value: age,
                  isDense: true,
                  underline: const SizedBox(),
                  items: List.generate(
                    maxAge - minAge + 1,
                    (i) => DropdownMenuItem(
                      value: minAge + i,
                      child: Text('${minAge + i}岁'),
                    ),
                  ),
                  onChanged: (value) {
                    if (value != null) onAgeChanged(value);
                  },
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.remove_circle_outline, color: Colors.red),
            onPressed: onRemove,
            iconSize: 20,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
        ],
      ),
    );
  }

  Widget _buildSwitch({
    required String title,
    required String subtitle,
    required bool value,
    required Function(bool) onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 14)),
                Text(
                  subtitle,
                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}
