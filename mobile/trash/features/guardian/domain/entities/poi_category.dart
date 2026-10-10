/// POI (Point of Interest) category
enum POICategory {
  food,       // 美食
  attraction, // 景点
  hotel,      // 酒店
  activity,   // 活动
}

extension POICategoryExtension on POICategory {
  String get displayName {
    switch (this) {
      case POICategory.food:
        return '美食';
      case POICategory.attraction:
        return '景点';
      case POICategory.hotel:
        return '酒店';
      case POICategory.activity:
        return '活动';
    }
  }

  String get icon {
    switch (this) {
      case POICategory.food:
        return '🍜';
      case POICategory.attraction:
        return '🏛️';
      case POICategory.hotel:
        return '🏨';
      case POICategory.activity:
        return '🎭';
    }
  }
}
