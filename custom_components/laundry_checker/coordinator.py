"""Data update coordinator for laundry checker."""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryAuthFailed
import requests

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    DRYING_INDEX_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class LaundryCheckerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        location: str,
        qweather_key: str,
        max_suitable_humidity: float = 85.0,
        min_suitable_hours: int = 6,
        max_pop: int = 0,
        start_hour: int = 6,
        end_hour: int = 22,
        preferred_end_hour: int = 18,
        unsuitable_weather_types: Optional[list] = None,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL),
        )
        self._location = location
        self.qweather_key = qweather_key
        self.max_suitable_humidity = max_suitable_humidity
        self.min_suitable_hours = min_suitable_hours
        self.max_pop = max_pop
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.preferred_end_hour = preferred_end_hour
        self.unsuitable_weather_types = unsuitable_weather_types or []

    @property
    def location(self) -> str:
        """Get the location."""
        return self._location

    @location.setter
    def location(self, value: str) -> None:
        """Set the location."""
        self._location = value

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library."""
        try:
            # 获取未来三天的天气数据
            weather_data = await self.hass.async_add_executor_job(
                self.get_weather_data, 3
            )
            if not weather_data:
                raise ConfigEntryAuthFailed("Failed to get weather data")

            tomorrow = datetime.now().date() + timedelta(days=1)
            tomorrow_data = weather_data.get(tomorrow, [])

            # 先处理明天的天气适宜性
            is_suitable, message, stats = await self.hass.async_add_executor_job(
                self.check_weather_suitable, tomorrow_data
            )

            # 处理未来几天的预报
            future_days = []
            for date, daily_data in sorted(weather_data.items()):
                if date > tomorrow:
                    future_day_suitable, future_day_message, future_day_stats = (
                        await self.hass.async_add_executor_job(
                            self.check_weather_suitable, daily_data
                        )
                    )
                    future_days.append(
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "is_suitable": future_day_suitable,
                            "message": future_day_message,
                            "stats": future_day_stats,
                        }
                    )

            # 添加风力信息
            wind_conditions = set()
            for hour in tomorrow_data:
                wind_conditions.add(f"{hour['windDir']}{hour['windScale']}")
            stats["wind_conditions"] = wind_conditions

            # 构建详细的多天预报消息
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            detailed_message = f"未来三天晾衣建议 ({tomorrow_str})\n\n"

            # 明天的详细信息
            tomorrow_detail = (
                f"明天：{'✅ 适合' if is_suitable else '❌ 不适合'}晾衣服\n"
                f"时间段: {self.start_hour}:00 - {self.end_hour}:00\n"
                f"天气状况: {', '.join(stats['weather_conditions'])}\n"
                f"平均湿度: {stats['avg_humidity']:.1f}%\n"
            )

            # 添加晾晒指数信息（如果有）
            if "drying_index_text" in stats:
                tomorrow_detail += f"晾晒指数: {stats['drying_index_text']}\n"

            if is_suitable:
                tomorrow_detail += (
                    f"预计晾干时间: {stats['estimated_drying_time']}小时\n"
                    f"最佳晾晒时间: {stats['best_drying_period']}\n"
                    f"风力情况：{', '.join(stats['wind_conditions'])}\n"
                )
            else:
                reason = message.replace("不建议洗衣服，原因：", "")
                tomorrow_detail += f"原因: {reason}\n"

            detailed_message += tomorrow_detail + "\n后两天预报：\n"

            # 添加后两天的简要信息
            for future_day in future_days:
                emoji = "✅" if future_day["is_suitable"] else "❌"
                detailed_message += f"{future_day['date']}：{emoji} "

                if future_day["is_suitable"]:
                    detailed_message += f"适合晾衣（{future_day['stats']['estimated_drying_time']}小时）\n"
                else:
                    reason = future_day["message"].replace("不建议洗衣服，原因：", "")
                    detailed_message += f"不适合（{reason}）\n"

            return {
                "is_suitable": is_suitable,
                "message": message,
                "stats": stats,
                "last_update": datetime.now(),
                "detailed_message": detailed_message,
                "multi_day_forecast": True,
                "tomorrow_detail": tomorrow_detail,
                "future_days": future_days,
            }

        except Exception as err:
            _LOGGER.error("Error updating laundry checker data: %s", err)
            raise

    def get_weather_data(self, days: int = 3) -> Dict:
        """Get weather data from QWeather API."""
        try:
            url = "https://devapi.qweather.com/v7/weather/72h"
            params = {
                "location": self._location,
                "key": self.qweather_key,
            }

            _LOGGER.debug("正在请求和风天气API: %s, 参数: %s", url, params)

            response = requests.get(url, params=params)

            # 记录详细的响应信息，帮助排查问题
            _LOGGER.debug("API响应状态码: %s", response.status_code)

            if response.status_code != 200:
                _LOGGER.error(
                    "API请求失败，状态码: %s, 响应内容: %s",
                    response.status_code,
                    response.text,
                )
                return None

            data = response.json()

            if data.get("code") == "200":
                daily_data = {}
                for hour in data.get("hourly", []):
                    date = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z").date()
                    if date not in daily_data:
                        daily_data[date] = []

                    hour_time = datetime.strptime(
                        hour["fxTime"], "%Y-%m-%dT%H:%M%z"
                    ).hour
                    if self.start_hour <= hour_time <= self.end_hour:
                        daily_data[date].append(hour)

                today = datetime.now().date()
                future_dates = sorted(daily_data.keys())
                future_dates = [d for d in future_dates if d > today][:days]

                # 获取每日紫外线指数
                try:
                    uv_url = "https://devapi.qweather.com/v7/weather/3d"
                    uv_response = requests.get(uv_url, params=params)
                    if uv_response.status_code == 200:
                        uv_data = uv_response.json()
                        if uv_data.get("code") == "200":
                            for daily in uv_data.get("daily", []):
                                date = datetime.strptime(
                                    daily["fxDate"], "%Y-%m-%d"
                                ).date()
                                if date in daily_data:
                                    uv_index = daily.get("uvIndex", "0")
                                    for hour_data in daily_data[date]:
                                        hour_data["uvIndex"] = uv_index
                                    _LOGGER.debug(
                                        "添加紫外线指数 %s 到日期 %s", uv_index, date
                                    )
                except Exception as uv_err:
                    _LOGGER.error("获取UV指数时出错: %s", uv_err)

                # 获取晾晒指数
                try:
                    indices_url = "https://devapi.qweather.com/v7/indices/1d"
                    indices_params = {
                        "location": self._location,
                        "key": self.qweather_key,
                        "type": DRYING_INDEX_TYPE,  # 晾晒指数类型ID
                    }
                    indices_response = requests.get(indices_url, params=indices_params)

                    if indices_response.status_code == 200:
                        indices_data = indices_response.json()
                        if indices_data.get("code") == "200" and indices_data.get(
                            "daily"
                        ):
                            for index in indices_data.get("daily", []):
                                if index.get("type") == DRYING_INDEX_TYPE:
                                    # 获取晾晒指数
                                    date = datetime.strptime(
                                        index["date"], "%Y-%m-%d"
                                    ).date()
                                    if date in daily_data:
                                        drying_index = {
                                            "name": index.get("name", "晾晒指数"),
                                            "category": index.get("category", ""),
                                            "level": index.get("level", ""),
                                            "text": index.get("text", ""),
                                        }
                                        # 为当天每个小时数据添加晾晒指数
                                        for hour_data in daily_data[date]:
                                            hour_data["dryingIndex"] = drying_index
                                        _LOGGER.debug(
                                            "添加晾晒指数 %s 到日期 %s",
                                            drying_index["category"],
                                            date,
                                        )
                except Exception as indices_err:
                    _LOGGER.error("获取晾晒指数时出错: %s", indices_err)

                return {date: daily_data[date] for date in future_dates}
            else:
                error_msg = f"API返回错误码: {data.get('code')}, 错误信息: {data.get('message', '未知错误')}"
                _LOGGER.error("Failed to get weather data: %s", error_msg)
                return None

        except Exception as err:
            _LOGGER.error("Error getting weather data: %s", err)
            return None

    def check_weather_suitable(self, hourly_data: list) -> tuple:
        """Check if weather is suitable for laundry."""
        if not hourly_data:
            return False, "无法获取天气数据", {}

        stats = {
            "suitable_hours": 0,
            "avg_humidity": 0,
            "has_precipitation": False,
            "max_pop": 0,
            "weather_conditions": set(),
            "estimated_drying_time": 0,
            "best_drying_period": "",
            "uv_index": 0,
        }

        total_humidity = 0
        valid_hours = 0

        for hour in hourly_data:
            humidity = float(hour["humidity"])
            precip = float(hour["precip"])
            pop = int(hour.get("pop", "0"))

            # 获取紫外线指数
            if "uvIndex" in hour:
                uv_index = int(hour["uvIndex"])
                stats["uv_index"] = max(stats["uv_index"], uv_index)

            # 获取晾晒指数
            if "dryingIndex" in hour:
                drying_index = hour["dryingIndex"]
                stats["drying_index"] = drying_index["name"]
                stats["drying_index_level"] = drying_index["level"]
                stats["drying_index_category"] = drying_index["category"]
                stats["drying_index_text"] = drying_index["text"]

            total_humidity += humidity
            valid_hours += 1
            stats["max_pop"] = max(stats["max_pop"], pop)
            stats["weather_conditions"].add(hour["text"])

            if precip > 0:
                stats["has_precipitation"] = True

            if (
                humidity <= self.max_suitable_humidity
                and precip == 0
                and hour["text"] not in self.unsuitable_weather_types
                and pop <= self.max_pop
            ):
                stats["suitable_hours"] += 1

        if valid_hours > 0:
            stats["avg_humidity"] = total_humidity / valid_hours
            best_weather = min(hourly_data, key=lambda x: float(x["humidity"]))
            stats["estimated_drying_time"] = self.estimate_drying_time(best_weather)
            best_hour = datetime.strptime(
                best_weather["fxTime"], "%Y-%m-%dT%H:%M%z"
            ).hour
            stats["best_drying_period"] = f"{best_hour}:00"

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
            reasons.append(f"平均湿度过高 ({stats['avg_humidity']:.1f}%)")

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
                f"建议洗衣服，未来{self.end_hour-self.start_hour}小时内有{stats['suitable_hours']}小时适合晾晒",
                f"预计衣服需要{stats['estimated_drying_time']}小时晾干",
                f"最佳晾晒时间: {stats['best_drying_period']}",
            ]

            # 添加晾晒指数信息
            if "drying_index_text" in stats:
                message.append(f"晾晒指数: {stats['drying_index_text']}")

            message = "\n".join(message)
        else:
            message = f"不建议洗衣服，原因：{', '.join(reasons)}"

        return is_suitable, message, stats

    def estimate_drying_time(self, weather_data: Dict) -> float:
        """Estimate drying time based on weather conditions."""
        base_time = 6.0

        humidity = float(weather_data["humidity"])
        humidity_factor = 0.8 + (humidity - 40) / 100

        wind_scale = float(weather_data["windScale"].split("-")[0])
        wind_factor = 1.2 - (wind_scale * 0.05)

        weather_text = weather_data["text"]
        if "晴" in weather_text:
            weather_factor = 0.8
        elif "多云" in weather_text:
            weather_factor = 1.0
        else:
            weather_factor = 1.2

        temp = float(weather_data["temp"])
        temp_factor = 1.2 - (temp / 100)

        # 添加紫外线因素
        uv_index = int(weather_data.get("uvIndex", 0))
        # 紫外线强度越高，干燥速度越快
        uv_factor = 1.0
        if uv_index > 0:
            uv_factor = 1.2 - (min(uv_index, 10) * 0.04)  # UV指数最高10，最低因子为0.8

        # 添加紫外线因子到计算公式
        total_time = (
            base_time
            * humidity_factor
            * wind_factor
            * weather_factor
            * temp_factor
            * uv_factor
        )
        return round(total_time, 1)
