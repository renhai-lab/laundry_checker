"""Data update coordinator for laundry checker."""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
import requests

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    DRYING_INDEX_TYPE,
    AQI_LEVELS,
    DEFAULT_MAX_AQI,
    DEFAULT_QWEATHER_API_HOST,
    DEPRECATED_QWEATHER_DOMAINS,
    DEFAULT_RAIN_LIGHT_THRESHOLD,
    DEFAULT_RAIN_MODERATE_THRESHOLD,
    DEFAULT_RAIN_HEAVY_THRESHOLD,
    DEFAULT_RAIN_STORM_THRESHOLD,
    DEFAULT_RAIN_WORK_COMMUTE_HOURS,
)
from .helpers import normalize_api_host

_LOGGER = logging.getLogger(__name__)

# QWeather v1 error code mapping
AUTH_ERROR_CODES = {"401"}
QUOTA_ERROR_CODES = {"402"}
FORBIDDEN_ERROR_CODES = {"403"}
RATE_LIMIT_ERROR_CODES = {"429"}
SERVER_ERROR_CODES = {"500"}


class LaundryCheckerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        location: str,
        qweather_key: str,
        api_host: str = DEFAULT_QWEATHER_API_HOST,
        max_suitable_humidity: float = 85.0,
        min_suitable_hours: int = 6,
        max_pop: int = 0,
        start_hour: int = 6,
        end_hour: int = 22,
        preferred_end_hour: int = 18,
        unsuitable_weather_types: Optional[list] = None,
        max_aqi: int = DEFAULT_MAX_AQI,
        rain_light_threshold: float = DEFAULT_RAIN_LIGHT_THRESHOLD,
        rain_moderate_threshold: float = DEFAULT_RAIN_MODERATE_THRESHOLD,
        rain_heavy_threshold: float = DEFAULT_RAIN_HEAVY_THRESHOLD,
        rain_storm_threshold: float = DEFAULT_RAIN_STORM_THRESHOLD,
        rain_work_commute_hours: int = DEFAULT_RAIN_WORK_COMMUTE_HOURS,
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
        self.api_host = normalize_api_host(api_host)
        self.max_suitable_humidity = max_suitable_humidity  # Default: 85.0
        self.min_suitable_hours = min_suitable_hours  # Default: 6
        self.max_pop = max_pop  # Default: 0
        self.start_hour = start_hour  # Default: 6
        self.end_hour = end_hour  # Default: 22
        self.preferred_end_hour = preferred_end_hour  # Default: 18
        self.unsuitable_weather_types = unsuitable_weather_types or []  # Default: []
        self.max_aqi = max_aqi  # Default: DEFAULT_MAX_AQI
        self.rain_light_threshold = rain_light_threshold  # Default: 0.1
        self.rain_moderate_threshold = rain_moderate_threshold  # Default: 2.5
        self.rain_heavy_threshold = rain_heavy_threshold  # Default: 7.6
        self.rain_storm_threshold = rain_storm_threshold  # Default: 15.0
        self.rain_work_commute_hours = max(1, min(24, int(rain_work_commute_hours)))

        if any(domain in self.api_host for domain in DEPRECATED_QWEATHER_DOMAINS):
            _LOGGER.warning(
                "QWeather host %s is scheduled for retirement by 2026. "
                "Please switch to the dedicated API Host listed in your QWeather console.",
                self.api_host,
            )

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
            _LOGGER.debug("开始更新洗衣检查器数据")

            # 获取未来三天的天气数据
            weather_data = await self.hass.async_add_executor_job(self.get_weather_data)
            if not weather_data:
                raise UpdateFailed("未收到任何天气数据")

            # 获取空气质量数据
            air_quality_data = await self.hass.async_add_executor_job(
                self.get_air_quality_data
            )

            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            # 从weather_data中获取今天和明天的数据
            today_info = weather_data.get(today)
            tomorrow_info = weather_data.get(tomorrow)

            today_data = []
            today_daily_data = {}
            today_air_quality = (
                air_quality_data.get(today, {}) if air_quality_data else {}
            )

            # Helper to filter hours based on valid drying window
            def filter_hours(hours):
                return [
                    h
                    for h in hours
                    if self.start_hour
                    <= datetime.fromisoformat(h["fxTime"]).hour
                    <= self.end_hour
                ]

            today_data = []
            today_daily_data = {}
            # Initialize with empty list to prevent unbounded locals error if unused
            today_all_hours = []

            if today_info and today_info.get("hourly"):
                today_all_hours = today_info.get("hourly", [])
                today_daily_data = today_info.get("daily", {})

                # Try to filter by preferred hours
                today_data = filter_hours(today_all_hours)

                # If no hours in preferred range (e.g. late night), use all available hours
                # This ensures we always show *something* for the current day
                if not today_data and today_all_hours:
                    _LOGGER.debug("当前时间超出设定晾晒时段，使用剩余所有小时数据")
                    today_data = today_all_hours
            else:
                _LOGGER.warning("无法获取今天的小时天气数据")

            tomorrow_data = []
            tomorrow_daily_data = {}
            tomorrow_air_quality = (
                air_quality_data.get(tomorrow, {}) if air_quality_data else {}
            )
            if tomorrow_info and tomorrow_info.get("hourly"):
                tomorrow_all_hours = tomorrow_info.get("hourly", [])
                tomorrow_daily_data = tomorrow_info.get("daily", {})
                # Strictly filter tomorrow's data (plan for the future only in drying window)
                tomorrow_data = filter_hours(tomorrow_all_hours)
            else:
                # It's less critical if tomorrow's data is missing initially,
                # but we can still log a warning if needed.
                _LOGGER.warning("无法获取明天的小时天气数据")

            # 处理今天的天气适宜性
            is_suitable, message, stats = await self.hass.async_add_executor_job(
                self.check_weather_suitable,
                today_data,
                today_daily_data,
                today_air_quality,
            )

            # 处理明天的天气适宜性
            tomorrow_suitable, tomorrow_message, tomorrow_stats = (
                await self.hass.async_add_executor_job(
                    self.check_weather_suitable,
                    tomorrow_data,
                    tomorrow_daily_data,
                    tomorrow_air_quality,
                )
            )

            # 添加风力信息
            for hour in today_data:
                stats.setdefault("wind_conditions", set()).add(
                    f"{hour['windDir']}{hour['windScale']}"
                )

            for hour in tomorrow_data:
                tomorrow_stats.setdefault("wind_conditions", set()).add(
                    f"{hour['windDir']}{hour['windScale']}"
                )

            # 处理未来几天的预报
            future_days = []
            for date, data in sorted(weather_data.items()):
                if date > tomorrow:
                    hourly_all = data.get("hourly", [])
                    hourly_info = filter_hours(hourly_all)
                    daily_info = data.get("daily", {})
                    future_air_quality = (
                        air_quality_data.get(date, {}) if air_quality_data else {}
                    )
                    # Ensure both hourly and daily data are passed to check_weather_suitable
                    future_day_suitable, future_day_message, future_day_stats = (
                        await self.hass.async_add_executor_job(
                            self.check_weather_suitable,
                            hourly_info,
                            daily_info,
                            future_air_quality,
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

            # 计算降雨相关指标（6小时内 / 明天 / 后天）
            rain_metrics = self._build_rain_metrics(weather_data)

            # 构建详细的多天预报消息
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            detailed_message = f"🌈 未来三天晾衣预报 ({tomorrow_str})\n\n"

            # 明天的详细信息
            weather_emoji = (
                "🌞" if "晴" in tomorrow_stats["weather_conditions"] else "⛅"
            )
            tomorrow_detail = (
                f"明天：{weather_emoji} {'✨ 非常适合' if tomorrow_suitable else '😔 不太适合'}晾衣服\n"
                f"⏰ 时间段: {self.start_hour}:00 - {self.end_hour}:00\n"
                f"🌤️ 天气状况: {', '.join(tomorrow_stats['weather_conditions'])}\n"
                f"💧 平均湿度: {tomorrow_stats['avg_humidity']:.1f}%\n"
            )

            # 添加空气质量信息（如果有）
            if "aqi" in tomorrow_stats and tomorrow_stats["aqi"] > 0:
                aqi_emoji = (
                    "🟢"
                    if tomorrow_stats["aqi"] <= 50
                    else ("🟡" if tomorrow_stats["aqi"] <= 100 else "🔴")
                )
                tomorrow_detail += f"{aqi_emoji} 空气质量: AQI {tomorrow_stats['aqi']} ({tomorrow_stats.get('aqi_level', '')})\n"

            # 添加晾晒指数信息（如果有）
            if "drying_index_text" in tomorrow_stats:
                tomorrow_detail += (
                    f"📊 晾晒指数: {tomorrow_stats['drying_index_text']}\n"
                )

            if tomorrow_suitable:
                # 根据晾干时间给出评价
                drying_time = tomorrow_stats["estimated_drying_time"]
                if drying_time <= 2:
                    time_comment = "超快速干！"
                elif drying_time <= 3:
                    time_comment = "干得很快~"
                else:
                    time_comment = "正常晾干"

                # 根据最佳晾晒时间给出提示
                best_hour = int(tomorrow_stats["best_drying_period"].split(":")[0])
                if best_hour < 10:
                    timing_tip = "早晨阳光正好"
                elif best_hour < 14:
                    timing_tip = "正午阳光充足"
                else:
                    timing_tip = "下午温和适宜"

                tomorrow_detail += (
                    f"⏱️ 预计晾干时间: {drying_time}小时 ({time_comment})\n"
                    f"🎯 最佳晾晒时间: {tomorrow_stats['best_drying_period']} ({timing_tip})\n"
                    f"🌪️ 风力情况：{', '.join(tomorrow_stats['wind_conditions'])}\n"
                )
            else:
                reason = tomorrow_message.replace(
                    "今天不太适合晾衣服...\n原因：\n", ""
                ).split("\n")[0]
                tomorrow_detail += f"❗ {reason}\n"

            detailed_message += tomorrow_detail + "\n📅 后两天预报：\n"

            # 添加后两天的简要信息
            for future_day in future_days:
                weather_emoji = (
                    "🌞"
                    if any("晴" in w for w in future_day["stats"]["weather_conditions"])
                    else "⛅"
                )
                emoji = "✨" if future_day["is_suitable"] else "😔"
                detailed_message += f"{future_day['date']}：{weather_emoji} {emoji} "

                if future_day["is_suitable"]:
                    drying_time = future_day["stats"]["estimated_drying_time"]
                    if drying_time <= 2:
                        time_comment = "超快速干"
                    elif drying_time <= 3:
                        time_comment = "干得很快"
                    else:
                        time_comment = "正常晾干"
                    detailed_message += (
                        f"适合晾衣（{drying_time}小时 - {time_comment}）\n"
                    )
                else:
                    reason = (
                        future_day["message"]
                        .replace("今天不太适合晾衣服...\n原因：\n", "")
                        .split("\n")[0]
                    )
                    detailed_message += f"不适合（{reason}）\n"

            _LOGGER.debug(
                "数据更新完成，今天适合晾晒: %s, 明天适合晾晒: %s",
                is_suitable,
                tomorrow_suitable,
            )

            return {
                "is_suitable": is_suitable,
                "message": message,
                "stats": stats,
                "tomorrow_stats": {
                    "is_suitable": tomorrow_suitable,
                    "message": tomorrow_message,
                    "detailed_message": detailed_message,
                    **tomorrow_stats,
                },
                "last_update": datetime.now(),
                "multi_day_forecast": True,
                "detailed_message": detailed_message,
                "tomorrow_detail": tomorrow_detail,
                "future_days": future_days,
                "rain_forecast": rain_metrics,
            }

        except Exception as err:
            _LOGGER.error("更新洗衣检查器数据时出错: %s", err, exc_info=True)
            raise

    def get_weather_data(self) -> Dict:
        """Get weather data from QWeather API."""
        hourly_data_url = self._build_api_url("/v7/weather/72h")
        daily_data_url = self._build_api_url("/v7/weather/3d")
        params = {
            "location": self._location,
            "key": self.qweather_key,
        }
        daily_data = {}

        def _handle_qweather_response(
            response: requests.Response, api_name: str
        ) -> Dict:
            """Validate QWeather response and map errors."""
            # 检查HTTP状态码
            if response.status_code != 200:
                _LOGGER.error(
                    "%s HTTP错误 %s: %s",
                    api_name,
                    response.status_code,
                    response.text[:200],
                )
                if response.status_code == 401:
                    raise ConfigEntryAuthFailed(f"{api_name} 认证失败 (HTTP 401)")
                raise UpdateFailed(f"{api_name} HTTP {response.status_code} 错误")

            # 尝试解析JSON
            try:
                data = response.json()
            except ValueError as json_err:
                _LOGGER.error(
                    "%s 返回的不是有效的JSON: %s. 响应: %s",
                    api_name,
                    json_err,
                    response.text[:200],
                )
                raise UpdateFailed(f"{api_name} 返回无效的JSON响应") from json_err

            code = str(data.get("code")) if data.get("code") is not None else None
            message = data.get("message", "N/A")

            if code == "200":
                return data
            if code in AUTH_ERROR_CODES:
                raise ConfigEntryAuthFailed(f"{api_name} 认证失败 (code {code})")
            if code in RATE_LIMIT_ERROR_CODES:
                raise UpdateFailed(f"{api_name} 触发限流 (code {code})，请稍后重试")
            if code in QUOTA_ERROR_CODES:
                raise UpdateFailed(f"{api_name} 配额不足或余额不足 (code {code})")
            if code in FORBIDDEN_ERROR_CODES:
                raise UpdateFailed(
                    f"{api_name} 被拒绝访问 (code {code})，请检查主机或安全设置"
                )
            if code in SERVER_ERROR_CODES:
                raise UpdateFailed(f"{api_name} 服务端错误 (code {code})")

            raise UpdateFailed(f"{api_name} 返回异常状态码 {code}: {message}")

        try:
            # Get 72h hourly forecast
            _LOGGER.debug(
                "正在请求和风天气72小时逐小时API: %s, 参数: %s", hourly_data_url, params
            )
            response_hourly = requests.get(hourly_data_url, params=params, timeout=10)
            hourly_forecast = _handle_qweather_response(
                response_hourly, "和风天气72小时API"
            )

            for hour in hourly_forecast.get("hourly", []):
                try:
                    dt_obj = datetime.fromisoformat(hour["fxTime"])
                    date = dt_obj.date()
                    hour_time = dt_obj.hour

                    if date not in daily_data:
                        daily_data[date] = {"hourly": [], "daily": {}}

                    # Filter hours logic moved to _async_update_data
                    daily_data[date]["hourly"].append(hour)
                except (ValueError, KeyError) as e:
                    _LOGGER.warning(f"解析小时数据时出错: {hour}, 错误: {e}")

            # Get 3d daily forecast (for UV index etc.)
            _LOGGER.debug(
                "正在请求和风天气3天每日API: %s, 参数: %s", daily_data_url, params
            )
            response_daily = requests.get(daily_data_url, params=params, timeout=10)
            daily_forecast = _handle_qweather_response(
                response_daily, "和风天气3天每日API"
            )

            for day_data in daily_forecast.get("daily", []):
                try:
                    date = datetime.strptime(day_data["fxDate"], "%Y-%m-%d").date()
                    if date in daily_data:
                        # Store the entire daily data dict for the date
                        daily_data[date]["daily"] = day_data
                        _LOGGER.debug(f"为日期 {date} 添加了每日数据: {day_data}")
                    else:
                        _LOGGER.warning(
                            f"日期 {date} 的每日数据在小时数据中未找到，已跳过。"
                        )
                except (ValueError, KeyError) as e:
                    _LOGGER.warning(f"解析每日数据时出错: {day_data}, 错误: {e}")

            # Log the number of hours fetched per day
            for date, data in daily_data.items():
                _LOGGER.debug(
                    f"日期 {date} 获取到 {len(data.get('hourly',[]))} 条小时数据"
                )

            return daily_data

        except ConfigEntryAuthFailed:
            # 让认证错误继续向上抛出以触发 reauth
            raise
        except requests.exceptions.RequestException as req_err:
            raise UpdateFailed(f"请求和风天气API时网络错误: {req_err}") from req_err
        except UpdateFailed:
            raise
        except Exception as e:
            raise UpdateFailed(f"处理天气数据时发生意外错误: {e}") from e

    def get_air_quality_data(self) -> Optional[Dict]:
        """Get air quality data from QWeather API."""
        air_quality_url = self._build_api_url("/v7/air/5d")
        params = {
            "location": self._location,
            "key": self.qweather_key,
        }
        air_quality_data = {}

        try:
            _LOGGER.debug(
                "正在请求和风天气空气质量API: %s, 参数: %s", air_quality_url, params
            )
            response = requests.get(air_quality_url, params=params, timeout=10)

            # 检查HTTP状态码
            if response.status_code != 200:
                _LOGGER.error(
                    "空气质量API HTTP错误 %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            # 尝试解析JSON
            try:
                data = response.json()
            except ValueError as json_err:
                _LOGGER.error(
                    "空气质量API返回的不是有效的JSON: %s. 响应: %s",
                    json_err,
                    response.text[:200],
                )
                return None

            if data.get("code") == "200":
                for day_data in data.get("daily", []):
                    try:
                        date = datetime.strptime(day_data["fxDate"], "%Y-%m-%d").date()
                        aqi = int(day_data.get("aqi", 0))

                        # 获取空气质量等级描述
                        aqi_level = ""
                        for (low, high), level in AQI_LEVELS.items():
                            if low <= aqi <= high:
                                aqi_level = level
                                break

                        air_quality_data[date] = {
                            "aqi": aqi,
                            "aqi_level": aqi_level,
                            "primary_pollutant": day_data.get("primary", ""),
                            "pm2p5": int(day_data.get("pm2p5", 0)),
                            "pm10": int(day_data.get("pm10", 0)),
                        }
                        _LOGGER.debug(
                            f"日期 {date} 空气质量数据: AQI={aqi}, 等级={aqi_level}"
                        )
                    except (ValueError, KeyError) as e:
                        _LOGGER.warning(
                            f"解析空气质量数据时出错: {day_data}, 错误: {e}"
                        )
            else:
                _LOGGER.warning(
                    "和风天气空气质量API返回非200状态: Code %s, 消息: %s",
                    data.get("code"),
                    data.get("message", "N/A"),
                )
                return {}

            return air_quality_data

        except requests.exceptions.RequestException as req_err:
            _LOGGER.warning("请求和风天气空气质量API时网络错误: %s", req_err)
            return {}
        except Exception as e:
            _LOGGER.warning("处理空气质量数据时发生错误: %s", e)
            return {}

    def check_weather_suitable(
        self,
        hourly_data: list,
        daily_data: dict,
        air_quality_data: Optional[dict] = None,
    ) -> tuple:
        """Check if weather is suitable for laundry."""
        stats = {
            "suitable_hours": 0,
            "avg_humidity": 0,
            "has_precipitation": False,
            "max_pop": 0,
            "weather_conditions": set(),
            "wind_conditions": set(),
            "estimated_drying_time": 0,
            "best_drying_period": "",
            "uv_index": 0,
            "aqi": 0,
            "aqi_level": "",
            "primary_pollutant": "",
        }

        if not hourly_data:
            return False, "无法获取天气数据", stats

        # 添加空气质量数据到stats
        if air_quality_data:
            stats["aqi"] = air_quality_data.get("aqi", 0)
            stats["aqi_level"] = air_quality_data.get("aqi_level", "")
            stats["primary_pollutant"] = air_quality_data.get("primary_pollutant", "")

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

        # 检查空气质量
        if stats["aqi"] > self.max_aqi:
            is_suitable = False
            reasons.append(f"空气质量较差 (AQI: {stats['aqi']}，{stats['aqi_level']})")

        for weather in stats["weather_conditions"]:
            if weather in self.unsuitable_weather_types:
                is_suitable = False
                reasons.append(f"预计有{weather}")
                break

        # 生成结果消息
        if is_suitable:
            # 根据天气情况选择不同的表情和描述
            weather_emoji = "🌞" if "晴" in stats["weather_conditions"] else "⛅"
            wind_emoji = (
                "🌪️" if any("5" in w for w in stats["wind_conditions"]) else "🍃"
            )

            # 根据晾干时间给出幽默的建议
            drying_time = stats["estimated_drying_time"]
            if drying_time <= 2:
                time_comment = "速干模式已开启！"
            elif drying_time <= 3:
                time_comment = "晾晒效果杠杠的~"
            else:
                time_comment = "稍微需要点耐心哦"

            # 根据最佳晾晒时间给出贴心提示
            best_hour = int(stats["best_drying_period"].split(":")[0])
            if best_hour < 10:
                timing_tip = "早起的鸟儿晒得干！"
            elif best_hour < 14:
                timing_tip = "阳光正好，晾起来吧！"
            else:
                timing_tip = "下午也是个不错的选择~"

            message = [
                f"{weather_emoji} 今天是完美的晾衣日！",
                f"未来{self.end_hour-self.start_hour}小时中有{stats['suitable_hours']}小时都很适合晾晒",
                f"预计晾干时间：{drying_time}小时 ({time_comment})",
                f"最佳晾晒时间：{stats['best_drying_period']} ({timing_tip})",
                f"{wind_emoji} 风力情况：" + "，".join(stats["wind_conditions"]),
            ]

            # 添加空气质量信息
            if stats["aqi"] > 0:
                aqi_emoji = (
                    "🟢"
                    if stats["aqi"] <= 50
                    else ("🟡" if stats["aqi"] <= 100 else "🔴")
                )
                message.append(
                    f"{aqi_emoji} 空气质量: AQI {stats['aqi']} ({stats['aqi_level']})"
                )

            # 添加紫外线提醒
            if stats["uv_index"] > 7:
                message.append("☀️ 紫外线较强，注意防晒哦~")

            message = "\n".join(message)
        else:
            # 根据不同原因给出更友好的提示
            reason_emojis = {
                "降水": "🌧️",
                "湿度": "💧",
                "时间": "⏰",
                "概率": "📊",
                "空气质量": "😷",
            }

            formatted_reasons = []
            for reason in reasons:
                emoji = next((e for k, e in reason_emojis.items() if k in reason), "❌")
                formatted_reasons.append(f"{emoji} {reason}")

            message = "今天不太适合晾衣服...\n原因：\n" + "\n".join(formatted_reasons)

            # 添加安慰性建议
            if "降水" in "".join(reasons):
                message += "\n💡 建议使用室内晾衣架或烘干机"
            elif "湿度" in "".join(reasons):
                message += "\n💡 可以开除湿机辅助晾干哦"
            elif "空气质量" in "".join(reasons):
                message += "\n💡 空气污染较重，建议室内晾晒以避免衣物沾染灰尘"

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

    def _build_api_url(self, path: str) -> str:
        """Build an absolute QWeather API URL based on the configured host."""
        return f"{self.api_host}/{path.lstrip('/')}"

    def _build_rain_metrics(self, weather_data: Dict) -> Dict[str, Any]:
        """Build rain metrics for next 6 hours, tomorrow, and day after tomorrow."""
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        # Flatten all hourly data into a list with parsed datetime
        all_hours = []
        for date_key, data in weather_data.items():
            for hour in data.get("hourly", []):
                try:
                    fx_time = datetime.fromisoformat(hour["fxTime"])
                    if fx_time.tzinfo is not None:
                        now_ts = datetime.now(fx_time.tzinfo).timestamp()
                    else:
                        now_ts = now.timestamp()
                    all_hours.append((fx_time, hour, fx_time.timestamp(), now_ts))
                except (ValueError, KeyError):
                    continue

        all_hours.sort(key=lambda x: x[0])

        # Next 6 hours window (fixed)
        upcoming_hours = [h for h in all_hours if h[2] >= h[3]]
        next_6h_metrics = self._compute_rain_metrics([h[1] for h in upcoming_hours[:6]])

        # Work commute window (configurable)
        commute_hours = self.rain_work_commute_hours
        work_commute_metrics = self._compute_rain_metrics(
            [h[1] for h in upcoming_hours[:commute_hours]]
        )

        # Tomorrow and day after tomorrow (by date)
        tomorrow_hours = [h for h in all_hours if h[0].date() == tomorrow]
        day_after_hours = [h for h in all_hours if h[0].date() == day_after_tomorrow]

        return {
            "next_6h": next_6h_metrics,
            "work_commute": work_commute_metrics,
            "tomorrow": self._compute_rain_metrics([h[1] for h in tomorrow_hours]),
            "day_after_tomorrow": self._compute_rain_metrics(
                [h[1] for h in day_after_hours]
            ),
        }

    def _compute_rain_metrics(self, hourly_data: list) -> Dict[str, Any]:
        """Compute rain metrics from hourly data."""
        total_precip = 0.0
        max_precip = 0.0
        max_pop = 0
        rain_hours = 0

        for hour in hourly_data:
            try:
                precip = float(hour.get("precip", 0))
                pop = int(hour.get("pop", "0") or 0)
            except (ValueError, TypeError):
                precip = 0.0
                pop = 0

            total_precip += precip
            max_precip = max(max_precip, precip)
            max_pop = max(max_pop, pop)

            if precip >= self.rain_light_threshold:
                rain_hours += 1

        rain_level = self._get_rain_level(max_precip)
        will_rain = rain_hours > 0

        return {
            "will_rain": will_rain,
            "rain_level": rain_level,
            "rain_hours": rain_hours,
            "total_precipitation": round(total_precip, 2),
            "max_hourly_precipitation": round(max_precip, 2),
            "max_precipitation_probability": max_pop,
        }

    def _get_rain_level(self, max_precip: float) -> str:
        """Get rain level name based on max hourly precipitation."""
        if max_precip >= self.rain_storm_threshold:
            return "暴雨"
        if max_precip >= self.rain_heavy_threshold:
            return "大雨"
        if max_precip >= self.rain_moderate_threshold:
            return "中雨"
        if max_precip >= self.rain_light_threshold:
            return "小雨"
        return "无雨"
