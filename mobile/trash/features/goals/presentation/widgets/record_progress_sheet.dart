import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/goal.dart';
import '../bloc/goals_bloc.dart';

class RecordProgressSheet extends StatefulWidget {
  final Goal goal;
  final String memberId;

  const RecordProgressSheet({
    super.key,
    required this.goal,
    required this.memberId,
  });

  @override
  State<RecordProgressSheet> createState() => _RecordProgressSheetState();
}

class _RecordProgressSheetState extends State<RecordProgressSheet> {
  final _progressController = TextEditingController();
  final _notesController = TextEditingController();

  @override
  void dispose() {
    _progressController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.textSecondary.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Title
              Text('记录进度', style: AppTextStyles.headline6),
              const SizedBox(height: 8),
              Text(
                widget.goal.description,
                style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 20),

              // Current progress
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('当前进度', style: AppTextStyles.caption),
                        Text(
                          widget.goal.progressDisplay,
                          style: AppTextStyles.subtitle1.copyWith(color: AppColors.primary),
                        ),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('完成率', style: AppTextStyles.caption),
                        Text(
                          widget.goal.completionDisplay,
                          style: AppTextStyles.subtitle1.copyWith(color: AppColors.primary),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // Quick increment buttons
              Text('快速增加', style: AppTextStyles.subtitle2),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [1, 5, 10, 0.5].map((increment) {
                  return ActionChip(
                    label: Text('+${increment is int ? increment : increment.toString()} ${widget.goal.unit}'),
                    onPressed: () {
                      _progressController.text = increment.toString();
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),

              // Progress input
              TextFormField(
                controller: _progressController,
                decoration: InputDecoration(
                  labelText: '增加量',
                  hintText: '输入增加的数量',
                  prefixIcon: const Icon(Icons.add_circle_outline),
                  suffixText: widget.goal.unit,
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
              ),
              const SizedBox(height: 16),

              // Notes input
              TextFormField(
                controller: _notesController,
                decoration: const InputDecoration(
                  labelText: '备注 (可选)',
                  hintText: '添加任何备注...',
                  prefixIcon: Icon(Icons.note),
                ),
                maxLines: 2,
              ),
              const SizedBox(height: 24),

              // Submit button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text('记录进度'),
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _submit() {
    final progressIncrement = double.tryParse(_progressController.text.trim());
    if (progressIncrement == null || progressIncrement <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入有效的进度值')),
      );
      return;
    }

    context.read<GoalsBloc>().add(GoalProgressRecorded(
      goalId: widget.goal.id,
      memberId: widget.memberId,
      progressIncrement: progressIncrement,
      notes: _notesController.text.trim().isNotEmpty ? _notesController.text.trim() : null,
    ));

    Navigator.of(context).pop();
  }
}
