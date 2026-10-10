import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../bloc/trip_bloc.dart';

class TripFeedbackPage extends StatefulWidget {
  final String tripId;
  final String? tripName;

  const TripFeedbackPage({
    super.key,
    required this.tripId,
    this.tripName,
  });

  @override
  State<TripFeedbackPage> createState() => _TripFeedbackPageState();
}

class _TripFeedbackPageState extends State<TripFeedbackPage> {
  int _rating = 0;
  final _feedbackController = TextEditingController();
  final _highlightController = TextEditingController();
  bool _isSubmitting = false;
  bool _submitted = false;

  final List<String> _quickTags = [
    '行程合理',
    '景点推荐准确',
    '时间安排得当',
    '预算控制好',
    '体验超预期',
    '值得推荐',
  ];

  final Set<String> _selectedTags = {};

  @override
  void dispose() {
    _feedbackController.dispose();
    _highlightController.dispose();
    super.dispose();
  }

  void _submit() {
    if (_rating == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先为本次旅行评分')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    // Combine tags and feedback
    String feedback = '';
    if (_selectedTags.isNotEmpty) {
      feedback += '标签: ${_selectedTags.join(', ')}\n';
    }
    if (_highlightController.text.isNotEmpty) {
      feedback += '亮点: ${_highlightController.text}\n';
    }
    if (_feedbackController.text.isNotEmpty) {
      feedback += '反馈: ${_feedbackController.text}';
    }

    context.read<TripBloc>().add(
      TripFeedbackSubmitted(
        tripId: widget.tripId,
        rating: _rating,
        feedback: feedback.isEmpty ? null : feedback,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('旅行反馈'),
        centerTitle: true,
      ),
      body: BlocListener<TripBloc, TripState>(
        listener: (context, state) {
          if (state is TripOperationSuccess) {
            setState(() {
              _isSubmitting = false;
              _submitted = true;
            });
          } else if (state is TripError) {
            setState(() => _isSubmitting = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('提交失败: ${state.message}')),
            );
          }
        },
        child: _submitted ? _buildSuccessView() : _buildFeedbackForm(),
      ),
    );
  }

  Widget _buildSuccessView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: Colors.green[50],
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.check_circle,
                size: 48,
                color: Colors.green[400],
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              '感谢您的反馈！',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              '您的评价将帮助我们为您提供更好的旅行推荐',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[600],
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => context.pop(),
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
              ),
              child: const Text('返回'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeedbackForm() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Trip header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Theme.of(context).primaryColor,
                  Theme.of(context).primaryColor.withValues(alpha: 0.8),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.flight_takeoff,
                    color: Colors.white,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.tripName ?? '旅行计划',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        '旅途归来，期待您的反馈',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.white70,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Rating section
          _buildSectionTitle('整体评分', required: true),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.grey[50],
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(5, (index) {
                    return GestureDetector(
                      onTap: () => setState(() => _rating = index + 1),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        child: Icon(
                          index < _rating ? Icons.star : Icons.star_border,
                          color: Colors.amber,
                          size: 40,
                        ),
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 8),
                Text(
                  _getRatingText(),
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Quick tags
          _buildSectionTitle('快速标签'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _quickTags.map((tag) {
              final isSelected = _selectedTags.contains(tag);
              return FilterChip(
                label: Text(tag),
                selected: isSelected,
                onSelected: (selected) {
                  setState(() {
                    if (selected) {
                      _selectedTags.add(tag);
                    } else {
                      _selectedTags.remove(tag);
                    }
                  });
                },
                selectedColor: Theme.of(context).primaryColor.withValues(alpha: 0.2),
                checkmarkColor: Theme.of(context).primaryColor,
              );
            }).toList(),
          ),
          const SizedBox(height: 24),

          // Highlight
          _buildSectionTitle('旅行亮点'),
          const SizedBox(height: 12),
          TextField(
            controller: _highlightController,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: '这次旅行最让您印象深刻的是什么？',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              filled: true,
              fillColor: Colors.grey[50],
            ),
          ),
          const SizedBox(height: 24),

          // Detailed feedback
          _buildSectionTitle('详细反馈'),
          const SizedBox(height: 12),
          TextField(
            controller: _feedbackController,
            maxLines: 4,
            decoration: InputDecoration(
              hintText: '您对这次旅行有什么建议或想说的？',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              filled: true,
              fillColor: Colors.grey[50],
            ),
          ),
          const SizedBox(height: 32),

          // Submit button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _isSubmitting ? null : _submit,
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: _isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Text(
                      '提交反馈',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
            ),
          ),
          const SizedBox(height: 16),

          // Skip button
          Center(
            child: TextButton(
              onPressed: () => context.pop(),
              child: Text(
                '暂时跳过',
                style: TextStyle(color: Colors.grey[600]),
              ),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title, {bool required = false}) {
    return Row(
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        if (required)
          Text(
            ' *',
            style: TextStyle(
              fontSize: 16,
              color: Colors.red[400],
            ),
          ),
      ],
    );
  }

  String _getRatingText() {
    switch (_rating) {
      case 1:
        return '不太满意';
      case 2:
        return '一般般';
      case 3:
        return '还可以';
      case 4:
        return '很满意';
      case 5:
        return '非常完美！';
      default:
        return '点击星星评分';
    }
  }
}
