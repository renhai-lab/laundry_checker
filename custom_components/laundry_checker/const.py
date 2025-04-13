"""Constants for Laundry Checker integration."""

DOMAIN = "laundry_checker"
PLATFORMS = ["sensor", "binary_sensor"]

# 配置选项
CONF_LOCATION = "location"
CONF_MAX_SUITABLE_HUMIDITY = "max_suitable_humidity"
CONF_MIN_SUITABLE_HOURS = "min_suitable_hours"
CONF_MAX_POP = "max_pop"
CONF_START_HOUR = "start_hour"
CONF_END_HOUR = "end_hour"
CONF_PREFERRED_END_HOUR = "preferred_end_hour"
CONF_QWEATHER_KEY = "qweather_key"
CONF_UNSUITABLE_WEATHER_TYPES = "unsuitable_weather_types"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_USE_HA_LOCATION = "use_ha_location"

# 默认值
DEFAULT_LOCATION = "120.15,30.28"  # 默认经纬度坐标
DEFAULT_MAX_SUITABLE_HUMIDITY = 85.0
DEFAULT_MIN_SUITABLE_HOURS = 6
DEFAULT_MAX_POP = 0
DEFAULT_START_HOUR = 6
DEFAULT_END_HOUR = 22
DEFAULT_PREFERRED_END_HOUR = 18
DEFAULT_SCAN_INTERVAL = 6  # 小时
DEFAULT_UNSUITABLE_WEATHER_TYPES = [
    "雨",
    "阵雨",
    "小雨",
    "中雨",
    "大雨",
    "暴雨",
    "雪",
    "阵雪",
    "小雪",
    "中雪",
    "大雪",
    "暴雪",
    "雾",
    "浓雾",
    "强浓雾",
    "轻雾",
    "大雾",
    "霾",
    "中度霾",
    "重度霾",
    "严重霾",
]

# 传感器
ATTR_SUITABLE_HOURS = "suitable_hours"
ATTR_AVERAGE_HUMIDITY = "average_humidity"
ATTR_HAS_PRECIPITATION = "has_precipitation"
ATTR_MAX_POP = "max_precipitation_probability"
ATTR_WEATHER_CONDITIONS = "weather_conditions"
ATTR_ESTIMATED_DRYING_TIME = "estimated_drying_time"
ATTR_BEST_DRYING_PERIOD = "best_drying_period"
ATTR_WIND_CONDITIONS = "wind_conditions"
ATTR_DETAILED_MESSAGE = "detailed_message"
ATTR_MULTI_DAY_FORECAST = "multi_day_forecast"
ATTR_TOMORROW_DETAIL = "tomorrow_detail"
ATTR_FUTURE_DAYS = "future_days"
ATTR_UV_INDEX = "uv_index"
ATTR_DRYING_INDEX = "drying_index"
ATTR_DRYING_INDEX_LEVEL = "drying_index_level"
ATTR_DRYING_INDEX_CATEGORY = "drying_index_category"
ATTR_DRYING_INDEX_TEXT = "drying_index_text"

# 晾晒指数类型ID
DRYING_INDEX_TYPE = "13"

# 传感器名称
BINARY_SENSOR_NAME = "洗衣建议"
DRYING_TIME_SENSOR_NAME = "预计晾干时间"
