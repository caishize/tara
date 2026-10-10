import 'package:flutter/foundation.dart' show debugPrint;
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';

import 'location_data.dart';

/// Provides device location with graceful degradation.
///
/// Returns `null` when permission is denied or an error occurs,
/// so callers can fall back to backend-resolved defaults.
class LocationService {
  LocationData? _cached;
  DateTime? _cachedAt;

  /// Cache TTL — avoid hitting GPS on every chat message.
  static const _cacheDuration = Duration(minutes: 5);

  /// Get current location. Returns null on any failure (graceful degradation).
  Future<LocationData?> getCurrentLocation() async {
    // Return cached value if still fresh
    if (_cached != null &&
        _cachedAt != null &&
        DateTime.now().difference(_cachedAt!) < _cacheDuration) {
      return _cached;
    }

    try {
      // Check if location services are enabled
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        debugPrint('LocationService: location services disabled');
        return null;
      }

      // Check / request permission
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          debugPrint('LocationService: permission denied');
          return null;
        }
      }
      if (permission == LocationPermission.deniedForever) {
        debugPrint('LocationService: permission denied forever');
        return null;
      }

      // Get position
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low,
          timeLimit: Duration(seconds: 5),
        ),
      );

      // Reverse geocode to get city name
      String? cityName;
      try {
        final placemarks = await placemarkFromCoordinates(
          position.latitude,
          position.longitude,
        );
        if (placemarks.isNotEmpty) {
          final place = placemarks.first;
          // Prefer locality (city), fallback to subAdministrativeArea
          cityName = place.locality?.isNotEmpty == true
              ? place.locality
              : place.subAdministrativeArea;
        }
      } catch (e) {
        debugPrint('LocationService: reverse geocode failed: $e');
        // Position is still usable without city name
      }

      _cached = LocationData(
        latitude: position.latitude,
        longitude: position.longitude,
        cityName: cityName,
      );
      _cachedAt = DateTime.now();

      return _cached;
    } catch (e) {
      debugPrint('LocationService: failed to get location: $e');
      return null;
    }
  }
}
