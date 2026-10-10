import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../domain/entities/trip_memory.dart';

class MemoryCard extends StatelessWidget {
  final TripMemory memory;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const MemoryCard({
    super.key,
    required this.memory,
    this.onTap,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      onLongPress: () {
        if (onDelete != null) {
          showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('删除照片'),
              content: const Text('确定要删除这张照片吗？'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('取消'),
                ),
                TextButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    onDelete!();
                  },
                  style: TextButton.styleFrom(foregroundColor: Colors.red),
                  child: const Text('删除'),
                ),
              ],
            ),
          );
        }
      },
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Stack(
            fit: StackFit.expand,
            children: [
              // Image
              if (memory.primaryUrl != null)
                CachedNetworkImage(
                  imageUrl: memory.primaryUrl!,
                  fit: BoxFit.cover,
                  placeholder: (context, url) => Container(
                    color: Colors.grey[200],
                    child: const Center(
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ),
                  errorWidget: (context, url, error) => Container(
                    color: Colors.grey[200],
                    child: const Icon(Icons.error_outline, color: Colors.grey),
                  ),
                )
              else
                Container(
                  color: Colors.grey[200],
                  child: const Icon(Icons.image, color: Colors.grey, size: 40),
                ),

              // Gradient overlay for text
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        Colors.black.withValues(alpha: 0.7),
                      ],
                    ),
                  ),
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Caption
                      if (memory.displayCaption.isNotEmpty)
                        Text(
                          memory.displayCaption,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                          ),
                        ),
                      const SizedBox(height: 4),
                      // Rating
                      if (memory.rating > 0)
                        Row(
                          children: List.generate(
                            5,
                            (index) => Icon(
                              index < memory.rating ? Icons.star : Icons.star_border,
                              color: Colors.yellow[600],
                              size: 14,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),

              // Content type indicator
              if (memory.contentType == MemoryContentType.video)
                Positioned(
                  top: 8,
                  right: 8,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Icon(
                      Icons.play_arrow,
                      color: Colors.white,
                      size: 16,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class AddMemoryButton extends StatelessWidget {
  final VoidCallback onTap;

  const AddMemoryButton({
    super.key,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: Colors.grey[300]!,
            style: BorderStyle.solid,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.add_photo_alternate_outlined,
              size: 32,
              color: Colors.grey[500],
            ),
            const SizedBox(height: 4),
            Text(
              '添加照片',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[600],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
