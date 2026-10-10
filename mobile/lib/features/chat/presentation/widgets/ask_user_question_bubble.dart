import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../core/network/api_client.dart';
import '../../domain/entities/chat_message.dart';

/// Chat bubble that displays agent questions and collects user answers.
///
/// When the agent calls AskUserQuestion, the backend publishes the questions
/// via WebSocket. This widget renders them and submits the answers to
/// `POST /actions/answer-question`, which unblocks the agent hook via Redis.
class AskUserQuestionBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String answer)? onSubmitAnswer;

  const AskUserQuestionBubble({
    super.key,
    required this.message,
    this.onSubmitAnswer,
  });

  @override
  State<AskUserQuestionBubble> createState() => _AskUserQuestionBubbleState();
}

class _AskUserQuestionBubbleState extends State<AskUserQuestionBubble> {
  final List<TextEditingController> _controllers = [];
  bool _isSubmitting = false;
  bool _isSubmitted = false;

  ChatMessage get message => widget.message;

  List<Map<String, dynamic>> get _questions {
    final data = message.data ?? {};
    final raw = data['questions'];
    if (raw is List) {
      return raw.map((q) => q is Map<String, dynamic> ? q : <String, dynamic>{}).toList();
    }
    return [];
  }

  String get _questionId {
    final data = message.data ?? {};
    return (data['question_id'] ?? '') as String;
  }

  @override
  void initState() {
    super.initState();
    for (var i = 0; i < _questions.length; i++) {
      _controllers.add(TextEditingController());
    }
    // Ensure at least one controller for free-form answer
    if (_controllers.isEmpty) {
      _controllers.add(TextEditingController());
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submitAnswers() async {
    if (_isSubmitting || _isSubmitted) return;

    setState(() => _isSubmitting = true);

    try {
      final apiClient = GetIt.I<ApiClient>();
      final answers = <Map<String, String>>[];

      for (var i = 0; i < _questions.length; i++) {
        final q = _questions[i];
        final questionText = (q['question'] ?? '') as String;
        final answerText = i < _controllers.length ? _controllers[i].text.trim() : '';
        answers.add({'question': questionText, 'answer': answerText});
      }

      // If no structured questions, send the first controller's text
      if (_questions.isEmpty && _controllers.isNotEmpty) {
        answers.add({'question': '', 'answer': _controllers.first.text.trim()});
      }

      await apiClient.post('/actions/answer-question', data: {
        'question_id': _questionId,
        'answers': answers,
      });

      setState(() {
        _isSubmitted = true;
        _isSubmitting = false;
      });
    } catch (e) {
      setState(() => _isSubmitting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('提交失败: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<AppColorsExtension>();

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colors?.cardBackground ?? const Color(0xFFF5F5F5),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: const Color(0xFF1976D2).withValues(alpha: 0.3),
                  width: 1,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  const SizedBox(height: 12),
                  ..._buildQuestionFields(),
                  const SizedBox(height: 12),
                  _buildSubmitButton(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 32,
      height: 32,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF1976D2), Color(0xFF42A5F5)],
        ),
        shape: BoxShape.circle,
      ),
      child: const Icon(Icons.help_outline, color: Colors.white, size: 18),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        const Icon(Icons.question_answer, color: Color(0xFF1976D2), size: 18),
        const SizedBox(width: 6),
        Text(
          _isSubmitted ? '已回答' : '需要你的回答',
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: Color(0xFF1976D2),
          ),
        ),
      ],
    );
  }

  List<Widget> _buildQuestionFields() {
    if (_questions.isEmpty) {
      return [
        const Text('请回答以下问题:', style: TextStyle(fontSize: 14)),
        const SizedBox(height: 8),
        _buildTextField(0, '请输入你的回答...'),
      ];
    }

    final widgets = <Widget>[];
    for (var i = 0; i < _questions.length; i++) {
      final q = _questions[i];
      final questionText = (q['question'] ?? '请回答:') as String;
      final options = q['options'] as List?;

      widgets.add(Padding(
        padding: EdgeInsets.only(top: i > 0 ? 12 : 0),
        child: Text(
          questionText,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ));
      widgets.add(const SizedBox(height: 6));

      if (options != null && options.isNotEmpty) {
        widgets.add(_buildOptionsChips(i, options));
      } else {
        widgets.add(_buildTextField(i, '请输入你的回答...'));
      }
    }
    return widgets;
  }

  Widget _buildOptionsChips(int questionIndex, List options) {
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: options.map<Widget>((opt) {
        final label = opt is Map ? (opt['label'] ?? opt.toString()) : opt.toString();
        final isSelected = _controllers[questionIndex].text == label;

        return GestureDetector(
          onTap: _isSubmitted
              ? null
              : () {
                  setState(() => _controllers[questionIndex].text = label.toString());
                },
          child: Chip(
            label: Text(label.toString()),
            backgroundColor: isSelected
                ? const Color(0xFF1976D2).withValues(alpha: 0.15)
                : null,
            side: isSelected
                ? const BorderSide(color: Color(0xFF1976D2))
                : null,
          ),
        );
      }).toList(),
    );
  }

  Widget _buildTextField(int index, String hint) {
    return TextField(
      controller: _controllers[index],
      enabled: !_isSubmitted,
      maxLines: 2,
      decoration: InputDecoration(
        hintText: hint,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        isDense: true,
      ),
      style: const TextStyle(fontSize: 14),
    );
  }

  Widget _buildSubmitButton() {
    if (_isSubmitted) {
      return Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
        decoration: BoxDecoration(
          color: Colors.green.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, color: Colors.green, size: 18),
            SizedBox(width: 6),
            Text('已提交回答', style: TextStyle(color: Colors.green, fontSize: 14)),
          ],
        ),
      );
    }

    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: _isSubmitting ? null : _submitAnswers,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF1976D2),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: const EdgeInsets.symmetric(vertical: 12),
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
            : const Text('提交回答', style: TextStyle(fontSize: 14)),
      ),
    );
  }
}
