import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:image_picker/image_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../domain/entities/trip_memory.dart';
import '../bloc/trip_bloc.dart';
import '../widgets/memory_card.dart';

class MemoryGalleryPage extends StatefulWidget {
  final String tripId;
  final String? tripName;

  const MemoryGalleryPage({
    super.key,
    required this.tripId,
    this.tripName,
  });

  @override
  State<MemoryGalleryPage> createState() => _MemoryGalleryPageState();
}

class _MemoryGalleryPageState extends State<MemoryGalleryPage> {
  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    _loadMemories();
  }

  void _loadMemories() {
    context.read<TripBloc>().add(
      MemoriesLoadRequested(widget.tripId),
    );
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );

      if (pickedFile != null) {
        _showUploadDialog(File(pickedFile.path));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('选择图片失败: $e')),
      );
    }
  }

  void _showImageSourceDialog() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                margin: const EdgeInsets.only(bottom: 20),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const Text(
                '添加旅行回忆',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _buildSourceOption(
                    icon: Icons.photo_library,
                    label: '相册',
                    color: Colors.purple,
                    onTap: () {
                      Navigator.pop(ctx);
                      _pickImage(ImageSource.gallery);
                    },
                  ),
                  _buildSourceOption(
                    icon: Icons.camera_alt,
                    label: '拍照',
                    color: Colors.blue,
                    onTap: () {
                      Navigator.pop(ctx);
                      _pickImage(ImageSource.camera);
                    },
                  ),
                ],
              ),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSourceOption({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 32),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[700],
            ),
          ),
        ],
      ),
    );
  }

  void _showUploadDialog(File imageFile) {
    final captionController = TextEditingController();
    int selectedRating = 0;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('添加照片'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Image preview
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.file(
                    imageFile,
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover,
                  ),
                ),
                const SizedBox(height: 16),

                // Caption input
                TextField(
                  controller: captionController,
                  maxLines: 2,
                  decoration: InputDecoration(
                    labelText: '说明 (可选)',
                    hintText: '记录这一刻...',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Rating
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '评分 (可选)',
                    style: TextStyle(fontSize: 14),
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(5, (index) {
                    return GestureDetector(
                      onTap: () {
                        setDialogState(() {
                          selectedRating = index + 1;
                        });
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: Icon(
                          index < selectedRating
                              ? Icons.star
                              : Icons.star_border,
                          color: Colors.amber,
                          size: 32,
                        ),
                      ),
                    );
                  }),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(ctx);
                _uploadMemory(
                  imageFile,
                  captionController.text.isEmpty ? null : captionController.text,
                  selectedRating == 0 ? null : selectedRating,
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).primaryColor,
                foregroundColor: Colors.white,
              ),
              child: const Text('上传'),
            ),
          ],
        ),
      ),
    );
  }

  void _uploadMemory(File file, String? caption, int? rating) {
    context.read<TripBloc>().add(
      MemoryUploadRequested(
        tripId: widget.tripId,
        file: file,
        caption: caption,
        rating: rating,
      ),
    );
  }

  void _deleteMemory(String memoryId) {
    context.read<TripBloc>().add(
      MemoryDeleteRequested(
        tripId: widget.tripId,
        memoryId: memoryId,
      ),
    );
  }

  void _showMemoryDetail(TripMemory memory) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        insetPadding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Full image
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              child: CachedNetworkImage(
                imageUrl: memory.primaryUrl ?? '',
                width: double.infinity,
                fit: BoxFit.contain,
                placeholder: (context, url) => const SizedBox(
                  height: 200,
                  child: Center(child: CircularProgressIndicator()),
                ),
                errorWidget: (context, url, error) => const SizedBox(
                  height: 200,
                  child: Center(child: Icon(Icons.error)),
                ),
              ),
            ),

            // Details
            if (memory.displayCaption.isNotEmpty || memory.rating > 0)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (memory.displayCaption.isNotEmpty)
                      Text(
                        memory.displayCaption,
                        style: const TextStyle(fontSize: 14),
                      ),
                    if (memory.rating > 0) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: List.generate(5, (index) {
                          return Icon(
                            index < memory.rating
                                ? Icons.star
                                : Icons.star_border,
                            color: Colors.amber,
                            size: 20,
                          );
                        }),
                      ),
                    ],
                  ],
                ),
              ),

            // Actions
            Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('关闭'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.tripName ?? '旅行回忆'),
        centerTitle: true,
        actions: [
          BlocBuilder<TripBloc, TripState>(
            builder: (context, state) {
              if (state is TripDetailLoaded && state.memories.isNotEmpty) {
                return IconButton(
                  icon: const Icon(Icons.picture_as_pdf),
                  onPressed: () {
                    context.read<TripBloc>().add(
                      PdfExportRequested(widget.tripId),
                    );
                  },
                  tooltip: '导出PDF',
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ],
      ),
      body: BlocConsumer<TripBloc, TripState>(
        listener: (context, state) {
          if (state is PdfExportComplete) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: const Text('PDF导出成功'),
                action: SnackBarAction(
                  label: '查看',
                  onPressed: () {
                    // Open PDF
                  },
                ),
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is TripLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is TripError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline, size: 48, color: Colors.red[300]),
                  const SizedBox(height: 16),
                  Text(state.message),
                  const SizedBox(height: 16),
                  OutlinedButton(
                    onPressed: _loadMemories,
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          List<TripMemory> memories = [];
          if (state is TripDetailLoaded) {
            memories = state.memories;
          }

          if (memories.isEmpty) {
            return _buildEmptyState();
          }

          return _buildMemoryGrid(memories);
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showImageSourceDialog,
        icon: const Icon(Icons.add_a_photo),
        label: const Text('添加照片'),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.photo_library_outlined, size: 80, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            '还没有旅行回忆',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w500,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '添加照片记录美好瞬间',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _showImageSourceDialog,
            icon: const Icon(Icons.add_a_photo),
            label: const Text('添加第一张照片'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Theme.of(context).primaryColor,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemoryGrid(List<TripMemory> memories) {
    return Stack(
      children: [
        GridView.builder(
          padding: const EdgeInsets.all(12),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
          ),
          itemCount: memories.length + 1, // +1 for add button
          itemBuilder: (context, index) {
            if (index == memories.length) {
              return AddMemoryButton(onTap: _showImageSourceDialog);
            }

            final memory = memories[index];
            return MemoryCard(
              memory: memory,
              onTap: () => _showMemoryDetail(memory),
              onDelete: () => _deleteMemory(memory.id),
            );
          },
        ),

        // Upload progress indicator
        BlocBuilder<TripBloc, TripState>(
          builder: (context, state) {
            if (state is MemoryUploadInProgress) {
              return Container(
                color: Colors.black26,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 16),
                        Text(
                          '上传中... ${(state.progress * 100).toInt()}%',
                          style: const TextStyle(fontSize: 14),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ],
    );
  }
}
