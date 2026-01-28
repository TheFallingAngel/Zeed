"""
闪价雷达 - 配置文件
试点区域：重庆南岸区
"""

import os
from dataclasses import dataclass
from typing import List

@dataclass
class Location:
    """位置信息"""
    name: str
    latitude: float
    longitude: float
    address: str

# ==================== 试点区域配置 ====================
# 重庆南岸区核心商圈坐标
PILOT_LOCATIONS = [
    Location(
        name="南坪步行街",
        latitude=29.5286,
        longitude=106.5694,
        address="重庆市南岸区南坪西路"
    ),
    Location(
        name="南坪万达广场",
        latitude=29.5234,
        longitude=106.5723,
        address="重庆市南岸区江南大道"
    ),
    Location(
        name="南滨路",
        latitude=29.5456,
        longitude=106.5812,
        address="重庆市南岸区南滨路"
    ),
    Location(
        name="弹子石",
        latitude=29.5589,
        longitude=106.5934,
        address="重庆市南岸区弹子石新街"
    ),
]

# 默认监控位置（南坪步行街）
DEFAULT_LOCATION = PILOT_LOCATIONS[0]

# ==================== 监控商品配置 ====================
DEFAULT_PRODUCTS = [
    "农夫山泉550ml",
    "红牛250ml",
    "元气森林白桃味",
    "可口可乐330ml",
    "东方树叶茉莉花茶",
    "百威啤酒500ml",
    "江小白100ml",
    "雪花啤酒500ml",
    "乐事薯片原味",
    "奥利奥饼干",
]

# ==================== 爬虫配置 ====================
CRAWLER_CONFIG = {
    "search_radius": 3000,
    "max_shops_per_search": 20,
    "request_delay": 2,
    "max_daily_crawls": 3,
    "timeout": 30000,
    "max_retries": 3,
}

# ==================== 平台配置 ====================
PLATFORMS = {
    "meituan": {
        "name": "美团闪购",
        "h5_url": "https://h5.waimai.meituan.com",
        "enabled": True,
    },
    "eleme": {
        "name": "饿了么",
        "h5_url": "https://h5.ele.me",
        "enabled": True,
    },
}

# ==================== AI配置 ====================
AI_CONFIG = {
    "claude_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1000,
}

# ==================== API配置 ====================
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True,
}
