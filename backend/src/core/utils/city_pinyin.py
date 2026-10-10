"""Chinese city name → Pinyin/English mapping for geocoding.

Open-Meteo (GeoNames) indexes Latin names reliably but Chinese character
search is hit-or-miss. This table covers municipalities, provincial capitals,
and common prefecture-level cities (~150 entries).

Usage:
    from core.utils.city_pinyin import CITY_PINYIN
    pinyin = CITY_PINYIN.get('揭阳')  # → 'Jieyang'
"""

from typing import Dict

CITY_PINYIN: Dict[str, str] = {
    # 4 直辖市
    '北京': 'Beijing', '上海': 'Shanghai', '天津': 'Tianjin', '重庆': 'Chongqing',
    # 省会 / 自治区首府
    '哈尔滨': 'Harbin', '长春': 'Changchun', '沈阳': 'Shenyang',
    '呼和浩特': 'Hohhot', '石家庄': 'Shijiazhuang', '太原': 'Taiyuan',
    '济南': 'Jinan', '郑州': 'Zhengzhou', '西安': 'Xian', '兰州': 'Lanzhou',
    '银川': 'Yinchuan', '西宁': 'Xining', '乌鲁木齐': 'Urumqi',
    '成都': 'Chengdu', '昆明': 'Kunming', '贵阳': 'Guiyang', '南宁': 'Nanning',
    '拉萨': 'Lhasa', '杭州': 'Hangzhou', '南昌': 'Nanchang', '合肥': 'Hefei',
    '福州': 'Fuzhou', '广州': 'Guangzhou', '海口': 'Haikou',
    '武汉': 'Wuhan', '长沙': 'Changsha', '南京': 'Nanjing', '台北': 'Taipei',
    # 副省级 / 计划单列市
    '深圳': 'Shenzhen', '大连': 'Dalian', '青岛': 'Qingdao',
    '宁波': 'Ningbo', '厦门': 'Xiamen',
    # 广东
    '佛山': 'Foshan', '东莞': 'Dongguan', '珠海': 'Zhuhai', '中山': 'Zhongshan',
    '惠州': 'Huizhou', '汕头': 'Shantou', '揭阳': 'Jieyang', '潮州': 'Chaozhou',
    '汕尾': 'Shanwei', '梅州': 'Meizhou', '湛江': 'Zhanjiang', '茂名': 'Maoming',
    '江门': 'Jiangmen', '肇庆': 'Zhaoqing', '清远': 'Qingyuan', '韶关': 'Shaoguan',
    '河源': 'Heyuan', '阳江': 'Yangjiang', '云浮': 'Yunfu',
    # 江苏
    '苏州': 'Suzhou', '无锡': 'Wuxi', '常州': 'Changzhou', '徐州': 'Xuzhou',
    '南通': 'Nantong', '扬州': 'Yangzhou', '盐城': 'Yancheng', '泰州': 'Taizhou',
    '镇江': 'Zhenjiang', '淮安': 'Huaian', '宿迁': 'Suqian', '连云港': 'Lianyungang',
    # 浙江
    '温州': 'Wenzhou', '嘉兴': 'Jiaxing', '绍兴': 'Shaoxing', '金华': 'Jinhua',
    '台州': 'Taizhou', '湖州': 'Huzhou', '衢州': 'Quzhou', '丽水': 'Lishui', '舟山': 'Zhoushan',
    # 山东
    '烟台': 'Yantai', '威海': 'Weihai', '潍坊': 'Weifang', '淄博': 'Zibo',
    '临沂': 'Linyi', '济宁': 'Jining', '泰安': 'Taian', '日照': 'Rizhao',
    '枣庄': 'Zaozhuang', '德州': 'Dezhou', '聊城': 'Liaocheng', '菏泽': 'Heze',
    '滨州': 'Binzhou', '东营': 'Dongying',
    # 福建
    '泉州': 'Quanzhou', '漳州': 'Zhangzhou', '莆田': 'Putian',
    '龙岩': 'Longyan', '三明': 'Sanming', '宁德': 'Ningde', '南平': 'Nanping',
    # 河北
    '唐山': 'Tangshan', '保定': 'Baoding', '邯郸': 'Handan', '秦皇岛': 'Qinhuangdao',
    '廊坊': 'Langfang', '沧州': 'Cangzhou', '邢台': 'Xingtai', '衡水': 'Hengshui',
    '张家口': 'Zhangjiakou', '承德': 'Chengde',
    # 河南
    '洛阳': 'Luoyang', '开封': 'Kaifeng', '南阳': 'Nanyang', '许昌': 'Xuchang',
    '新乡': 'Xinxiang', '焦作': 'Jiaozuo', '商丘': 'Shangqiu', '信阳': 'Xinyang',
    '周口': 'Zhoukou', '驻马店': 'Zhumadian', '安阳': 'Anyang', '平顶山': 'Pingdingshan',
    '濮阳': 'Puyang', '漯河': 'Luohe', '三门峡': 'Sanmenxia', '鹤壁': 'Hebi',
    # 湖北
    '宜昌': 'Yichang', '襄阳': 'Xiangyang', '荆州': 'Jingzhou', '黄冈': 'Huanggang',
    '十堰': 'Shiyan', '孝感': 'Xiaogan', '咸宁': 'Xianning', '荆门': 'Jingmen',
    # 湖南
    '株洲': 'Zhuzhou', '湘潭': 'Xiangtan', '衡阳': 'Hengyang', '岳阳': 'Yueyang',
    '常德': 'Changde', '邵阳': 'Shaoyang', '郴州': 'Chenzhou', '怀化': 'Huaihua',
    '益阳': 'Yiyang', '娄底': 'Loudi', '永州': 'Yongzhou', '张家界': 'Zhangjiajie',
    # 四川
    '绵阳': 'Mianyang', '宜宾': 'Yibin', '德阳': 'Deyang', '南充': 'Nanchong',
    '泸州': 'Luzhou', '乐山': 'Leshan', '自贡': 'Zigong', '攀枝花': 'Panzhihua',
    '内江': 'Neijiang', '遂宁': 'Suining', '广安': 'Guangan', '达州': 'Dazhou',
    # 辽宁
    '鞍山': 'Anshan', '抚顺': 'Fushun', '锦州': 'Jinzhou', '营口': 'Yingkou',
    '丹东': 'Dandong', '盘锦': 'Panjin', '葫芦岛': 'Huludao', '本溪': 'Benxi',
    '辽阳': 'Liaoyang', '铁岭': 'Tieling', '朝阳': 'Chaoyang', '阜新': 'Fuxin',
    # 其他常见
    '桂林': 'Guilin', '柳州': 'Liuzhou', '三亚': 'Sanya', '丽江': 'Lijiang',
    '大理': 'Dali', '九江': 'Jiujiang', '赣州': 'Ganzhou', '吉林': 'Jilin',
    '芜湖': 'Wuhu', '蚌埠': 'Bengbu', '马鞍山': 'Maanshan',
    '澳门': 'Macau', '香港': 'Hong Kong',
}
