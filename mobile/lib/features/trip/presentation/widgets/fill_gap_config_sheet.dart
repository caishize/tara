import 'package:flutter/material.dart';

/// 智能补充配置弹窗
class FillGapConfigSheet extends StatefulWidget {
  final int dayNumber;
  final Function(String? startTime, String? endTime, int activityCount,
      Map<String, dynamic>? preferences) onSubmit;

  const FillGapConfigSheet({
    super.key,
    required this.dayNumber,
    required this.onSubmit,
  });

  @override
  State<FillGapConfigSheet> createState() => _FillGapConfigSheetState();
}

class _FillGapConfigSheetState extends State<FillGapConfigSheet> {
  TimeOfDay? _startTime;
  TimeOfDay? _endTime;
  int _activityCount = 2;
  final Set<String> _selectedTypes = {};
  String _style = 'relaxed';

  final List<Map<String, dynamic>> _activityTypes = [
    {'value': 'attraction', 'label': '景点', 'icon': Icons.landscape},
    {'value': 'meal', 'label': '餐饮', 'icon': Icons.restaurant},
    {'value': 'shopping', 'label': '购物', 'icon': Icons.shopping_bag},
    {'value': 'rest', 'label': '休息', 'icon': Icons.spa},
  ];

  final List<Map<String, dynamic>> _styles = [
    {'value': 'relaxed', 'label': '轻松', 'icon': Icons.spa},
    {'value': 'intensive', 'label': '紧凑', 'icon': Icons.directions_run},
    {'value': 'cultural', 'label': '文化', 'icon': Icons.museum},
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(2),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    Icons.auto_fix_high,
                    color: theme.colorScheme.primary,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '智能补充行程',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: theme.colorScheme.onSurface,
                        ),
                      ),
                      Text(
                        '第 ${widget.dayNumber} 天',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Content
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Time range
                  _buildSectionTitle('时间范围（可选）'),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: _buildTimeButton(
                          label: '开始时间',
                          time: _startTime,
                          onTap: () => _selectTime(true),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Icon(Icons.arrow_forward, color: Colors.grey[400]),
                      ),
                      Expanded(
                        child: _buildTimeButton(
                          label: '结束时间',
                          time: _endTime,
                          onTap: () => _selectTime(false),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // Activity count
                  _buildSectionTitle('补充数量'),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      for (int i = 1; i <= 4; i++)
                        Expanded(
                          child: Padding(
                            padding: EdgeInsets.only(right: i < 4 ? 8 : 0),
                            child: _buildCountChip(i),
                          ),
                        ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // Activity types
                  _buildSectionTitle('活动类型偏好'),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: _activityTypes.map((type) {
                      final isSelected =
                          _selectedTypes.contains(type['value']);
                      return FilterChip(
                        selected: isSelected,
                        label: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              type['icon'] as IconData,
                              size: 16,
                              color: isSelected
                                  ? theme.colorScheme.onPrimaryContainer
                                  : Colors.grey[600],
                            ),
                            const SizedBox(width: 6),
                            Text(type['label'] as String),
                          ],
                        ),
                        onSelected: (selected) {
                          setState(() {
                            if (selected) {
                              _selectedTypes.add(type['value'] as String);
                            } else {
                              _selectedTypes.remove(type['value']);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),

                  const SizedBox(height: 24),

                  // Style
                  _buildSectionTitle('行程风格'),
                  const SizedBox(height: 8),
                  Row(
                    children: _styles.map((style) {
                      final isSelected = _style == style['value'];
                      return Expanded(
                        child: Padding(
                          padding: EdgeInsets.only(
                            right: style != _styles.last ? 8 : 0,
                          ),
                          child: InkWell(
                            onTap: () {
                              setState(() {
                                _style = style['value'] as String;
                              });
                            },
                            borderRadius: BorderRadius.circular(12),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 12,
                              ),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? theme.colorScheme.primaryContainer
                                    : Colors.grey[100],
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: isSelected
                                      ? theme.colorScheme.primary
                                      : Colors.transparent,
                                  width: 2,
                                ),
                              ),
                              child: Column(
                                children: [
                                  Icon(
                                    style['icon'] as IconData,
                                    color: isSelected
                                        ? theme.colorScheme.primary
                                        : Colors.grey[600],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    style['label'] as String,
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: isSelected
                                          ? FontWeight.w600
                                          : FontWeight.normal,
                                      color: isSelected
                                          ? theme.colorScheme.primary
                                          : Colors.grey[700],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),

                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),

          // Submit button
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _handleSubmit,
                  style: ElevatedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.auto_fix_high, size: 20),
                      const SizedBox(width: 8),
                      Text('生成 $_activityCount 个活动'),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: Colors.grey[800],
      ),
    );
  }

  Widget _buildTimeButton({
    required String label,
    required TimeOfDay? time,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.access_time, size: 18, color: Colors.grey[600]),
            const SizedBox(width: 8),
            Text(
              time != null
                  ? '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}'
                  : label,
              style: TextStyle(
                color: time != null ? Colors.black87 : Colors.grey[500],
                fontWeight: time != null ? FontWeight.w500 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCountChip(int count) {
    final theme = Theme.of(context);
    final isSelected = _activityCount == count;

    return InkWell(
      onTap: () {
        setState(() {
          _activityCount = count;
        });
      },
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected
              ? theme.colorScheme.primaryContainer
              : Colors.grey[100],
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? theme.colorScheme.primary : Colors.transparent,
            width: 2,
          ),
        ),
        child: Center(
          child: Text(
            '$count 个',
            style: TextStyle(
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              color: isSelected ? theme.colorScheme.primary : Colors.grey[700],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _selectTime(bool isStart) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isStart
          ? (_startTime ?? const TimeOfDay(hour: 9, minute: 0))
          : (_endTime ?? const TimeOfDay(hour: 18, minute: 0)),
    );

    if (picked != null) {
      setState(() {
        if (isStart) {
          _startTime = picked;
        } else {
          _endTime = picked;
        }
      });
    }
  }

  void _handleSubmit() {
    String? startTimeStr;
    String? endTimeStr;

    if (_startTime != null) {
      startTimeStr =
          '${_startTime!.hour.toString().padLeft(2, '0')}:${_startTime!.minute.toString().padLeft(2, '0')}';
    }
    if (_endTime != null) {
      endTimeStr =
          '${_endTime!.hour.toString().padLeft(2, '0')}:${_endTime!.minute.toString().padLeft(2, '0')}';
    }

    Map<String, dynamic>? preferences;
    if (_selectedTypes.isNotEmpty || _style.isNotEmpty) {
      preferences = {
        if (_selectedTypes.isNotEmpty) 'types': _selectedTypes.toList(),
        if (_style.isNotEmpty) 'style': _style,
      };
    }

    widget.onSubmit(startTimeStr, endTimeStr, _activityCount, preferences);
    Navigator.pop(context);
  }
}
