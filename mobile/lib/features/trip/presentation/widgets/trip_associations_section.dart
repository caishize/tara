import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/association_summary_model.dart';
import '../../data/models/related_memory_model.dart';

/// Horizontal scrolling section showing trip-associated events and memories.
/// Hidden entirely when there are no associations or memories.
class TripAssociationsSection extends StatelessWidget {
  final List<AssociationSummaryModel> associations;
  final List<RelatedMemoryModel> relatedMemories;

  const TripAssociationsSection({
    super.key,
    required this.associations,
    required this.relatedMemories,
  });

  @override
  Widget build(BuildContext context) {
    if (associations.isEmpty && relatedMemories.isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Icon(
                  Icons.link_rounded,
                  size: 18,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 6),
                const Text(
                  '关联内容',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${associations.length + relatedMemories.length}',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          // Horizontal scroll cards
          SizedBox(
            height: 110,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: associations.length + relatedMemories.length,
              itemBuilder: (context, index) {
                if (index < associations.length) {
                  return _buildAssociationCard(associations[index]);
                }
                final memoryIndex = index - associations.length;
                return _buildMemoryCard(relatedMemories[memoryIndex]);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAssociationCard(AssociationSummaryModel association) {
    final accentColor = _priorityColor(association.priority);

    return Container(
      width: 160,
      margin: const EdgeInsets.only(right: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        boxShadow: AppColors.cardShadow,
      ),
      child: Row(
        children: [
          // Priority accent bar
          Container(
            width: 3,
            decoration: BoxDecoration(
              color: accentColor,
              borderRadius: const BorderRadius.horizontal(
                left: Radius.circular(10),
              ),
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Icon
                  Text(
                    association.displayIcon,
                    style: const TextStyle(fontSize: 22),
                  ),
                  const SizedBox(height: 6),
                  // Title
                  Text(
                    association.title,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const Spacer(),
                  // Reason
                  if (association.reason != null)
                    Text(
                      association.reason!,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textTertiary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemoryCard(RelatedMemoryModel memory) {
    return Container(
      width: 160,
      margin: const EdgeInsets.only(right: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(10),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                memory.categoryIcon,
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(width: 6),
              const Text(
                '相关记忆',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: Text(
              memory.summary,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.4,
              ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Color _priorityColor(String priority) {
    switch (priority) {
      case 'high':
        return AppColors.error;
      case 'medium':
        return AppColors.accent1;
      default:
        return AppColors.accent3;
    }
  }
}
