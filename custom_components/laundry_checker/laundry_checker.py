"""Main class for Laundry Checker."""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any

import requests

from .const import (
    CONF_QWEATHER_KEY,
    DEFAULT_UNSUITABLE_WEATHER_TYPES,
    DEFAULT_QWEATHER_API_HOST,
)
from .helpers import normalize_api_host

_LOGGER = logging.getLogger(__name__)

class LaundryChecker:
    """Class to check if it's suitable for laundry based on weather forecast."""

    def __init__(
        self,
        location: Optional[str] = None,
        max_suitable_humidity: Optional[float] = None,
        min_suitable_hours: Optional[int] = None,
        max_pop: Optional[int] = None,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        preferred_end_hour: Optional[int] = None,
        unsuitable_weather_types: Optional[List[str]] = None,
        qweather_key: Optional[str] = None,
        ha_url: Optional[str] = None,
        ha_token: Optional[str] = None,
        notify_services: Optional[List[str]] = None,
        api_host: Optional[str] = None,
    ):
        """Initialize the checker."""
        # 配置参数
        self.location = location or "120.15,30.28"
        self.max_suitable_humidity = max_suitable_humidity or 85.0
        self.min_suitable_hours = min_suitable_hours or 6
        self.max_pop = 0 if max_pop is None else max_pop
        self.start_hour = start_hour or 6
        self.end_hour = end_hour or 22
        self.preferred_end_hour = preferred_end_hour or 18
        self.unsuitable_weather_types = unsuitable_weather_types or DEFAULT_UNSUITABLE_WEATHER_TYPES
        self.qweather_key = qweather_key
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.notify_services = notify_services or ["notify"]
        self.api_host = normalize_api_host(api_host or DEFAULT_QWEATHER_API_HOST)

    def get_weather_data(self, days: int = 3) -> Dict:
        """获取未来几天的天气数据

        Args:
            days: 获取未来几天的数据，默认3天

        Returns:
            Dict: 按日期分组的天气数据
        """
        try:
            # 使用和风天气的72小时预报API
            url = self._build_api_url("/v7/weather/72h")
            params = {
                "location": self.location,
                "key": self.qweather_key,
            }

            response = requests.get(url, params=params)
            data = response.json()

            if data["code"] == "200":
                # 按日期分组数据
                daily_data = {}
                for hour in data["hourly"]:
                    date = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z").date()
                    if date not in daily_data:
                        daily_data[date] = []

                    # 只保留指定时间段的数据
                    hour_time = datetime.strptime(
                        hour["fxTime"], "%Y-%m-%dT%H:%M%z"
                    ).hour
                    if self.start_hour <= hour_time <= self.end_hour:
                        daily_data[date].append(hour)

                # 只返回未来指定天数的数据
                today = datetime.now().date()
                future_dates = sorted(daily_data.keys())
                future_dates = [d for d in future_dates if d > today][:days]

                return {date: daily_data[date] for date in future_dates if date in daily_data}
            else:
                _LOGGER.error(f"获取天气数据失败: {data['code']}")
                return {}

        except Exception as e:
            _LOGGER.error(f"获取天气数据时发生错误: {str(e)}")
            return {}

    def estimate_drying_time(self, weather_data: Dict) -> float:
        """估算衣服大概需要多少小时能干

        基于以下因素：
        1. 湿度（影响权重最大）
        2. 风力等级
        3. 天气状况
        4. 温度（虽然冬天也能干，但确实会影响速度）
        """
        # 基准干燥时间（小时）
        base_time = 6.0

        # 湿度影响（40-100%）-> 0.8-1.5倍
        humidity = float(weather_data["humidity"])
        humidity_factor = 0.8 + (humidity - 40) / 100

        # 风力影响（0-12级）-> 0.7-1.2倍
        wind_scale = float(weather_data["windScale"].split("-")[0])  # 取较小值
        wind_factor = 1.2 - (wind_scale * 0.05)  # 风力越大干得越快

        # 天气状况影响
        weather_text = weather_data["text"]
        if "晴" in weather_text:
            weather_factor = 0.8  # 晴天干得快
        elif "多云" in weather_text:
            weather_factor = 1.0  # 多云正常速度
        else:
            weather_factor = 1.2  # 其他天气干得慢

        # 温度影响（0-40度）-> 0.8-1.2倍
        temp = float(weather_data["temp"])
        temp_factor = 1.2 - (temp / 100)  # 温度越高干得越快，但影响较小

        # 计算总时间
        total_time = (
            base_time * humidity_factor * wind_factor * weather_factor * temp_factor
        )
        return round(total_time, 1)

    def check_weather_suitable(self, hourly_data: List[Dict]) -> Tuple[bool, str, Dict]:
        """检查天气是否适合晾衣服"""
        if not hourly_data:
            return False, "无法获取天气数据", {}

        _LOGGER.debug(f"开始分析天气数据，收到{len(hourly_data)}小时的数据")

        # 统计数据
        stats = {
            "suitable_hours": 0,
            "avg_humidity": 0,
            "has_precipitation": False,
            "max_pop": 0,  # 最大降水概率
            "weather_conditions": set(),
            "wind_conditions": set(),
            "estimated_drying_time": 0,  # 预估晾干时间
            "should_collect_early": False,  # 是否需要提前收衣服
            "best_drying_period": "",  # 最佳晾晒时间段
        }

        total_humidity = 0
        valid_hours = 0

        # 分析天气数据
        for hour in hourly_data:
            hour_time = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z").hour
            humidity = float(hour["humidity"])
            precip = float(hour["precip"])
            pop = int(hour.get("pop", "0"))
            wind_scale = hour["windScale"]

            # 更新统计数据
            total_humidity += humidity
            valid_hours += 1
            stats["max_pop"] = max(stats["max_pop"], pop)
            stats["weather_conditions"].add(hour["text"])
            stats["wind_conditions"].add(f"{hour['windDir']}{wind_scale}")

            if precip > 0:
                stats["has_precipitation"] = True

            # 判断这个小时是否适合晾衣
            if (
                humidity <= self.max_suitable_humidity
                and precip == 0
                and hour["text"] not in self.unsuitable_weather_types
                and pop <= self.max_pop
            ):
                stats["suitable_hours"] += 1

        if valid_hours > 0:
            stats["avg_humidity"] = round(total_humidity / valid_hours, 1)

            # 预估晾干时间
            best_weather = min(hourly_data, key=lambda x: float(x["humidity"]))
            stats["estimated_drying_time"] = self.estimate_drying_time(best_weather)
            best_hour = datetime.strptime(
                best_weather["fxTime"], "%Y-%m-%dT%H:%M%z"
            ).hour
            stats["best_drying_period"] = f"{best_hour}:00"

        _LOGGER.debug(f"天气分析完成，统计结果: {stats}")

        # 判断条件和原因
        reasons = []
        is_suitable = True

        if stats["suitable_hours"] < self.min_suitable_hours:
            is_suitable = False
            reasons.append(
                f"适合晾晒的时间不足（仅{stats['suitable_hours']}小时，需要{self.min_suitable_hours}小时）"
            )

        if stats["has_precipitation"]:
            is_suitable = False
            reasons.append("预计有降水")

        if stats["avg_humidity"] > self.max_suitable_humidity:
            is_suitable = False
            reasons.append(f"平均湿度过高 ({stats['avg_humidity']}%)")

        if stats["max_pop"] > self.max_pop:
            is_suitable = False
            reasons.append(f"降水概率较高 ({stats['max_pop']}%)")

        for weather in stats["weather_conditions"]:
            if weather in self.unsuitable_weather_types:
                is_suitable = False
                reasons.append(f"预计有{weather}")
                break

        # 生成结果消息
        if is_suitable:
            message = [
                f"建议洗衣服，未来{self.end_hour-self.start_hour}小时内有{stats['suitable_hours']}小时适合晾晒"
            ]
            message.append(f"预计衣服需要{stats['estimated_drying_time']}小时晾干")
            message.append(f"最佳晾晒时间: {stats['best_drying_period']}")
        else:
            message = ["今天不建议洗衣服"]
            message.append("原因: " + "，".join(reasons))

        result_message = "；".join(message)
        _LOGGER.info(result_message)

        return is_suitable, result_message, stats

    def check_laundry_status(self, days: int = 1) -> Tuple[bool, str, Dict[str, Any]]:
        """检查未来几天的洗衣状态

        Args:
            days: 检查未来几天，默认1天

        Returns:
            Tuple: (是否适合洗衣, 消息, 统计数据)
        """
        weather_data = self.get_weather_data(days)
        if not weather_data:
            return False, "无法获取天气数据", {}

        # 对于每一天进行检查
        for date, hourly_data in weather_data.items():
            date_str = date.strftime("%Y-%m-%d")
            _LOGGER.info(f"检查 {date_str} 的天气数据")
            is_suitable, message, stats = self.check_weather_suitable(hourly_data)
            return is_suitable, message, stats

        return False, "无法获取未来天气数据", {}

    def _build_api_url(self, path: str) -> str:
        """Build an absolute QWeather API URL."""
        return f"{self.api_host}/{path.lstrip('/')}"