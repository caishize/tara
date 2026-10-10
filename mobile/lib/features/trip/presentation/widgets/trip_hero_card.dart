import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/trip.dart';

/// Green gradient hero card for Trip Detail V2.
/// Rounded bottom corners, contains title, subtitle, dates, status, progress bar.
class TripHeroCard extends StatelessWidget {
  final Trip trip;

  const TripHeroCard({super.key, required this.trip});

  static final _uuidRegex = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment(-0.5, -0.5),
          end: Alignment(0.5, 0.5),
          colors: [
            Color(0xFF2D7A46),
            Color(0xFF3D8A5A),
            Color(0xFF4A9E6A),
          ],
        ),
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(20),
          bottomRight: Radius.circular(20),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            _displayTitle,
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              letterSpacing: -0.5,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 16),
          // Sub row: calendar icon + "N天行程 · destination"
          Row(
            children: [
              const Icon(
                Icons.calendar_today_outlined,
                size: 14,
                color: Color(0xAAFFFFFF),
              ),
              const SizedBox(width: 6),
              Text(
                '${trip.durationDays}天行程 \u00B7 ${trip.destination}',
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xAAFFFFFF),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Meta row: dates + status badge
          Row(
            children: [
              Text(
                _dateRange,
                style: const TextStyle(
                  fontSize: 13,
                  color: Color(0xAAFFFFFF),
                ),
              ),
              const SizedBox(width: 10),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 3,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  trip.statusName,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Progress bar
          _buildProgressBar(),
        ],
      ),
    );
  }

  String get _displayTitle {
    final name = trip.tripName;
    if (name != null && name.isNotEmpty && !_uuidRegex.hasMatch(name)) {
      return name;
    }
    return trip.destination;
  }

  String get _dateRange {
    final df = DateFormat('M月d日');
    final start = df.format(trip.startDate.toLocal());
    final end = df.format(trip.endDate.toLocal());
    return '$start - $end';
  }

  Widget _buildProgressBar() {
    final progress = _progressPercent;

    return Row(
      children: [
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 4,
              backgroundColor: Colors.white.withValues(alpha: 0.2),
              valueColor: const AlwaysStoppedAnimation<Color>(
                Colors.white,
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          '${(progress * 100).round()}%',
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  double get _progressPercent {
    final now = DateTime.now();
    if (now.isBefore(trip.startDate)) return 0.0;
    if (now.isAfter(trip.endDate)) return 1.0;
    final total = trip.endDate.difference(trip.startDate).inHours;
    if (total <= 0) return 0.0;
    final elapsed = now.difference(trip.startDate).inHours;
    return (elapsed / total).clamp(0.0, 1.0);
  }
}
