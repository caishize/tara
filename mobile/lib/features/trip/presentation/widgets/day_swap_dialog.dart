import 'package:flutter/material.dart';
import '../../domain/entities/itinerary.dart';

class DaySwapDialog extends StatefulWidget {
  final List<DayItinerary> days;
  final int currentDayNumber;
  final Function(int sourceDay, int targetDay) onSwap;

  const DaySwapDialog({
    super.key,
    required this.days,
    required this.currentDayNumber,
    required this.onSwap,
  });

  @override
  State<DaySwapDialog> createState() => _DaySwapDialogState();
}

class _DaySwapDialogState extends State<DaySwapDialog> {
  late int _selectedTargetDay;

  @override
  void initState() {
    super.initState();
    // Default to next day or previous day
    _selectedTargetDay = widget.currentDayNumber < widget.days.length
        ? widget.currentDayNumber + 1
        : widget.currentDayNumber - 1;
  }

  @override
  Widget build(BuildContext context) {
    final availableDays = widget.days
        .where((d) => d.dayNumber != widget.currentDayNumber)
        .toList();

    return AlertDialog(
      title: Row(
        children: [
          Icon(Icons.swap_horiz, color: Theme.of(context).primaryColor),
          const SizedBox(width: 8),
          const Text('交换日程'),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '将第 ${widget.currentDayNumber} 天的行程与以下日期交换：',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[700],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.grey[300]!),
              borderRadius: BorderRadius.circular(8),
            ),
            child: DropdownButton<int>(
              value: _selectedTargetDay,
              isExpanded: true,
              underline: const SizedBox(),
              items: availableDays.map((day) {
                final activityCount = day.activities.length;
                return DropdownMenuItem<int>(
                  value: day.dayNumber,
                  child: Row(
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          color: Theme.of(context).primaryColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Center(
                          child: Text(
                            '${day.dayNumber}',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context).primaryColor,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '第 ${day.dayNumber} 天',
                              style: const TextStyle(fontWeight: FontWeight.w500),
                            ),
                            Text(
                              '$activityCount 个活动',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[600],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null) {
                  setState(() => _selectedTargetDay = value);
                }
              },
            ),
          ),
          const SizedBox(height: 16),

          // Preview
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue[50],
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                _buildDayPreview(widget.currentDayNumber, '原位置'),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12),
                  child: Icon(Icons.swap_horiz, color: Colors.blue),
                ),
                _buildDayPreview(_selectedTargetDay, '目标位置'),
              ],
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        ElevatedButton(
          onPressed: () {
            widget.onSwap(widget.currentDayNumber, _selectedTargetDay);
            Navigator.pop(context);
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: Theme.of(context).primaryColor,
            foregroundColor: Colors.white,
          ),
          child: const Text('确认交换'),
        ),
      ],
    );
  }

  Widget _buildDayPreview(int dayNumber, String label) {
    final day = widget.days.firstWhere((d) => d.dayNumber == dayNumber);
    return Expanded(
      child: Column(
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              children: [
                Text(
                  '第$dayNumber天',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
                Text(
                  '${day.activities.length}个活动',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class QuickDaySwapButton extends StatelessWidget {
  final int dayNumber;
  final VoidCallback onTap;

  const QuickDaySwapButton({
    super.key,
    required this.dayNumber,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.swap_horiz, size: 20),
      onPressed: onTap,
      tooltip: '交换日程',
      style: IconButton.styleFrom(
        backgroundColor: Colors.grey[100],
        padding: const EdgeInsets.all(8),
      ),
    );
  }
}
