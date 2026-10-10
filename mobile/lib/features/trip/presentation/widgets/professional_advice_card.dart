import 'package:flutter/material.dart';
import '../../domain/entities/smart_itinerary.dart';

class ProfessionalAdviceCard extends StatefulWidget {
  final ProfessionalAdvice advice;
  final bool initiallyExpanded;

  const ProfessionalAdviceCard({
    super.key,
    required this.advice,
    this.initiallyExpanded = false,
  });

  @override
  State<ProfessionalAdviceCard> createState() => _ProfessionalAdviceCardState();
}

class _ProfessionalAdviceCardState extends State<ProfessionalAdviceCard> {
  late bool _isExpanded;

  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.advice.hasContent) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue[100]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Colors.blue[100],
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text('🎯', style: TextStyle(fontSize: 16)),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '旅行家建议',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: Colors.blue[800],
                      fontSize: 14,
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: Colors.blue[700],
                  ),
                ],
              ),
            ),
          ),
          if (_isExpanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (widget.advice.whyChosen.isNotEmpty)
                    _buildAdviceItem(
                      icon: '💡',
                      title: '为什么推荐',
                      content: widget.advice.whyChosen,
                    ),
                  if (widget.advice.bestExperience.isNotEmpty)
                    _buildAdviceItem(
                      icon: '⭐',
                      title: '最佳体验',
                      content: widget.advice.bestExperience,
                    ),
                  if (widget.advice.timeTips.isNotEmpty)
                    _buildAdviceItem(
                      icon: '⏰',
                      title: '时间建议',
                      content: widget.advice.timeTips,
                    ),
                  if (widget.advice.costTips.isNotEmpty)
                    _buildAdviceItem(
                      icon: '💰',
                      title: '省钱技巧',
                      content: widget.advice.costTips,
                    ),
                  if (widget.advice.warnings.isNotEmpty)
                    _buildWarnings(widget.advice.warnings),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAdviceItem({
    required String icon,
    required String title,
    required String content,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(icon, style: const TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: Colors.grey[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(left: 20),
            child: Text(
              content,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[800],
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWarnings(List<String> warnings) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.orange[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.orange[200]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('⚠️', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text(
                '避坑提示',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: Colors.orange[800],
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ...warnings.map((warning) => Padding(
                padding: const EdgeInsets.only(left: 20, bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('• ', style: TextStyle(color: Colors.orange[700])),
                    Expanded(
                      child: Text(
                        warning,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.orange[900],
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}

class AlternativesCard extends StatelessWidget {
  final List<Alternative> alternatives;

  const AlternativesCard({
    super.key,
    required this.alternatives,
  });

  @override
  Widget build(BuildContext context) {
    if (alternatives.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🔄', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text(
                '备选方案',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: Colors.grey[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...alternatives.map((alt) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        alt.name,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '- ${alt.reason}',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              )),
        ],
      ),
    );
  }
}
