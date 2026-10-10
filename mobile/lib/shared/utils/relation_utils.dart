/// Utility class for relation type handling
///
/// Provides centralized relation type labels and helpers to avoid duplication
/// across Member entity, relationship graph, member form, etc.
class RelationUtils {
  RelationUtils._();

  /// Complete mapping of relation type values to Chinese labels
  static const Map<String, String> relationLabels = {
    // 核心家庭
    'self': '本人',
    'spouse': '配偶',
    'partner': '伴侣',
    'father': '父亲',
    'mother': '母亲',
    'parent': '父母',
    'son': '儿子',
    'daughter': '女儿',
    'child': '子女',
    'brother': '兄弟',
    'sister': '姐妹',
    'sibling': '兄弟姐妹',
    // 祖辈
    'grandfather_paternal': '爷爷',
    'grandmother_paternal': '奶奶',
    'grandfather_maternal': '外公',
    'grandmother_maternal': '外婆',
    'grandparent': '祖父母',
    // 孙辈
    'grandson': '孙子',
    'granddaughter': '孙女',
    'grandchild': '孙子女',
    // 姻亲
    'father_in_law': '岳父/公公',
    'mother_in_law': '岳母/婆婆',
    'parent_in_law': '公婆/岳父母',
    'son_in_law': '女婿',
    'daughter_in_law': '儿媳',
    'child_in_law': '女婿/儿媳',
    'brother_in_law': '姐夫/妹夫',
    'sister_in_law': '嫂子/弟妹',
    'sibling_in_law': '姐夫/嫂子',
    // 亲戚
    'uncle_paternal': '叔叔/伯伯',
    'aunt_paternal': '姑姑',
    'uncle_maternal': '舅舅',
    'aunt_maternal': '姨妈',
    'uncle_aunt': '叔伯姑舅姨',
    'nephew': '侄子',
    'niece': '侄女',
    'nephew_niece': '侄子女',
    'cousin': '表亲',
    // 配偶的祖辈
    'spouse_grandfather_paternal': '配偶的爷爷',
    'spouse_grandmother_paternal': '配偶的奶奶',
    'spouse_grandfather_maternal': '配偶的外公',
    'spouse_grandmother_maternal': '配偶的外婆',
    // 配偶的亲戚
    'spouse_uncle_paternal': '配偶的叔叔/伯伯',
    'spouse_aunt_paternal': '配偶的姑姑',
    'spouse_uncle_maternal': '配偶的舅舅',
    'spouse_aunt_maternal': '配偶的姨妈',
    // 社交
    'friend': '朋友',
    'colleague': '同事',
    'classmate': '同学',
    'neighbor': '邻居',
    'caregiver': '看护人',
    'other': '其他',
  };

  /// Professional relation type labels
  static const Map<String, String> professionalRelationLabels = {
    'boss': '上级',
    'subordinate': '下属',
    'peer': '同级同事',
    'mentor': '导师',
    'mentee': '学员',
    'client': '客户',
    'vendor': '供应商',
    'partner': '合作伙伴',
    'other': '其他',
  };

  /// Get label for a relation type
  static String getRelationLabel(String relationType) {
    return relationLabels[relationType] ??
           professionalRelationLabels[relationType] ??
           (relationType.isEmpty ? '未知关系' : relationType);
  }

  /// Get label for a professional relation type
  static String getProfessionalRelationLabel(String relationType) {
    return professionalRelationLabels[relationType] ?? relationType;
  }

  /// Categorized relation options for form display
  static const List<Map<String, dynamic>> relationCategories = [
    {
      'category': '核心家庭',
      'options': [
        {'value': 'self', 'label': '自己'},
        {'value': 'spouse', 'label': '配偶'},
        {'value': 'father', 'label': '父亲'},
        {'value': 'mother', 'label': '母亲'},
        {'value': 'son', 'label': '儿子'},
        {'value': 'daughter', 'label': '女儿'},
        {'value': 'brother', 'label': '兄弟'},
        {'value': 'sister', 'label': '姐妹'},
      ],
    },
    {
      'category': '祖辈',
      'options': [
        {'value': 'grandfather_paternal', 'label': '爷爷'},
        {'value': 'grandmother_paternal', 'label': '奶奶'},
        {'value': 'grandfather_maternal', 'label': '外公'},
        {'value': 'grandmother_maternal', 'label': '外婆'},
      ],
    },
    {
      'category': '姻亲',
      'options': [
        {'value': 'father_in_law', 'label': '岳父/公公'},
        {'value': 'mother_in_law', 'label': '岳母/婆婆'},
        {'value': 'son_in_law', 'label': '女婿'},
        {'value': 'daughter_in_law', 'label': '儿媳'},
        {'value': 'brother_in_law', 'label': '姐夫/妹夫'},
        {'value': 'sister_in_law', 'label': '嫂子/弟妹'},
      ],
    },
    {
      'category': '亲戚',
      'options': [
        {'value': 'uncle_paternal', 'label': '叔叔/伯伯'},
        {'value': 'aunt_paternal', 'label': '姑姑'},
        {'value': 'uncle_maternal', 'label': '舅舅'},
        {'value': 'aunt_maternal', 'label': '姨妈'},
        {'value': 'nephew', 'label': '侄子'},
        {'value': 'niece', 'label': '侄女'},
        {'value': 'cousin', 'label': '表亲'},
        {'value': 'grandson', 'label': '孙子'},
        {'value': 'granddaughter', 'label': '孙女'},
      ],
    },
    {
      'category': '社交/商务',
      'options': [
        {'value': 'friend', 'label': '朋友'},
        {'value': 'colleague', 'label': '同事'},
        {'value': 'classmate', 'label': '同学'},
        {'value': 'neighbor', 'label': '邻居'},
        {'value': 'other', 'label': '其他'},
      ],
    },
  ];

  /// Professional relation options for multi-select
  static const List<Map<String, String>> professionalRelationOptions = [
    {'value': 'boss', 'label': '上级'},
    {'value': 'subordinate', 'label': '下属'},
    {'value': 'peer', 'label': '同级同事'},
    {'value': 'mentor', 'label': '导师'},
    {'value': 'mentee', 'label': '学员'},
    {'value': 'client', 'label': '客户'},
    {'value': 'vendor', 'label': '供应商'},
    {'value': 'partner', 'label': '合作伙伴'},
  ];

  /// Family member relation types (核心家庭 + 祖辈 + 孙辈 + 姻亲)
  static const Set<String> familyRelations = {
    // 核心家庭
    'self', 'spouse', 'partner',
    'father', 'mother', 'parent',
    'son', 'daughter', 'child',
    'brother', 'sister', 'sibling',
    // 祖辈
    'grandfather_paternal', 'grandmother_paternal',
    'grandfather_maternal', 'grandmother_maternal',
    'grandparent',
    // 孙辈
    'grandson', 'granddaughter', 'grandchild',
    // 姻亲
    'father_in_law', 'mother_in_law', 'parent_in_law',
    'son_in_law', 'daughter_in_law', 'child_in_law',
    'brother_in_law', 'sister_in_law', 'sibling_in_law',
  };

  /// Work/Business relation types
  static const Set<String> workRelations = {
    'colleague',
    'boss', 'subordinate', 'peer',
    'mentor', 'mentee',
    'client', 'vendor',
  };

  /// Friend/Social relation types (亲戚 + 社交)
  static const Set<String> friendRelations = {
    'friend', 'classmate', 'neighbor', 'caregiver',
    // 亲戚
    'uncle_paternal', 'aunt_paternal',
    'uncle_maternal', 'aunt_maternal', 'uncle_aunt',
    'nephew', 'niece', 'nephew_niece',
    'cousin',
    // 配偶的祖辈和亲戚
    'spouse_grandfather_paternal', 'spouse_grandmother_paternal',
    'spouse_grandfather_maternal', 'spouse_grandmother_maternal',
    'spouse_uncle_paternal', 'spouse_aunt_paternal',
    'spouse_uncle_maternal', 'spouse_aunt_maternal',
  };

  /// Get category for a relation type
  /// Returns: 'family', 'work', 'friend', or 'other'
  static String getRelationCategory(String relation) {
    if (familyRelations.contains(relation)) return 'family';
    if (workRelations.contains(relation)) return 'work';
    if (friendRelations.contains(relation)) return 'friend';
    return 'other';
  }

  /// Check if relation is a family member
  static bool isFamily(String relation) => familyRelations.contains(relation);

  /// Check if relation is work-related
  static bool isWork(String relation) => workRelations.contains(relation);

  /// Check if relation is friend/relative
  static bool isFriend(String relation) => friendRelations.contains(relation);
}
