/// Immutable location data from device GPS + reverse geocoding.
class LocationData {
  final double latitude;
  final double longitude;
  final String? cityName;

  const LocationData({
    required this.latitude,
    required this.longitude,
    this.cityName,
  });

  @override
  String toString() =>
      'LocationData(lat=$latitude, lng=$longitude, city=$cityName)';
}
