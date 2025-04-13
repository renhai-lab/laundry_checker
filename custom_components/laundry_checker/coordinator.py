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
            _LOGGER.debug("开始更新洗衣检查器数据")
            
            # 获取未来三天的天气数据
            weather_data = await self.hass.async_add_executor_job(
                self.get_weather_data, 3
            )
            if not weather_data:
                _LOGGER.error("无法获取天气数据")
                raise ConfigEntryAuthFailed("获取天气数据失败")

            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            
            # 从weather_data中获取今天和明天的数据
            today_data = weather_data.get(today, [])
            tomorrow_data = weather_data.get(tomorrow, [])
            
            if not today_data:
                _LOGGER.warning("无法获取今天的天气数据")
                today_data = []

            if not tomorrow_data:
                _LOGGER.warning("无法获取明天的天气数据")
                tomorrow_data = []

            # 处理今天的天气适宜性
            is_suitable, message, stats = await self.hass.async_add_executor_job(
                self.check_weather_suitable, today_data
            )

            # 处理明天的天气适宜性
            tomorrow_suitable, tomorrow_message, tomorrow_stats = await self.hass.async_add_executor_job(
                self.check_weather_suitable, tomorrow_data
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

            # 构建详细的多天预报消息
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            detailed_message = f"🌈 未来三天晾衣预报 ({tomorrow_str})\n\n"

            # 明天的详细信息
            weather_emoji = "🌞" if "晴" in tomorrow_stats['weather_conditions'] else "⛅"
            tomorrow_detail = (
                f"明天：{weather_emoji} {'✨ 非常适合' if tomorrow_suitable else '😔 不太适合'}晾衣服\n"
                f"⏰ 时间段: {self.start_hour}:00 - {self.end_hour}:00\n"
                f"🌤️ 天气状况: {', '.join(tomorrow_stats['weather_conditions'])}\n"
                f"💧 平均湿度: {tomorrow_stats['avg_humidity']:.1f}%\n"
            )

            # 添加晾晒指数信息（如果有）
            if "drying_index_text" in tomorrow_stats:
                tomorrow_detail += f"📊 晾晒指数: {tomorrow_stats['drying_index_text']}\n"

            if tomorrow_suitable:
                # 根据晾干时间给出评价
                drying_time = tomorrow_stats['estimated_drying_time']
                if drying_time <= 2:
                    time_comment = "超快速干！"
                elif drying_time <= 3:
                    time_comment = "干得很快~"
                else:
                    time_comment = "正常晾干"
                
                # 根据最佳晾晒时间给出提示
                best_hour = int(tomorrow_stats['best_drying_period'].split(':')[0])
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
                reason = tomorrow_message.replace("今天不太适合晾衣服...\n原因：\n", "").split("\n")[0]
                tomorrow_detail += f"❗ {reason}\n"

            detailed_message += tomorrow_detail + "\n📅 后两天预报：\n"

            # 添加后两天的简要信息
            for future_day in future_days:
                weather_emoji = "🌞" if any("晴" in w for w in future_day['stats']['weather_conditions']) else "⛅"
                emoji = "✨" if future_day["is_suitable"] else "😔"
                detailed_message += f"{future_day['date']}：{weather_emoji} {emoji} "

                if future_day["is_suitable"]:
                    drying_time = future_day['stats']['estimated_drying_time']
                    if drying_time <= 2:
                        time_comment = "超快速干"
                    elif drying_time <= 3:
                        time_comment = "干得很快"
                    else:
                        time_comment = "正常晾干"
                    detailed_message += f"适合晾衣（{drying_time}小时 - {time_comment}）\n"
                else:
                    reason = future_day["message"].replace("今天不太适合晾衣服...\n原因：\n", "").split("\n")[0]
                    detailed_message += f"不适合（{reason}）\n"

            _LOGGER.debug("数据更新完成，今天适合晾晒: %s, 明天适合晾晒: %s", 
                         is_suitable, tomorrow_suitable)

            return {
                "is_suitable": is_suitable,
                "message": message,
                "stats": stats,
                "tomorrow_stats": {
                    "is_suitable": tomorrow_suitable,
                    "message": tomorrow_message,
                    "detailed_message": detailed_message,
                    **tomorrow_stats
                },
                "last_update": datetime.now(),
                "multi_day_forecast": True,
                "tomorrow_detail": tomorrow_detail,
                "future_days": future_days,
            }

        except Exception as err:
            _LOGGER.error("更新洗衣检查器数据时出错: %s", err, exc_info=True)
            raise

    def get_weather_data(self, days: int = 3) -> Dict:
        """Get weather data from QWeather API."""
        try:
            url = "https://devapi.qweather.com/v7/weather/24h"  # 先获取24小时数据
            params = {
                "location": self._location,
                "key": self.qweather_key,
            }

            _LOGGER.debug("正在请求和风天气24小时API: %s, 参数: %s", url, params)
            response = requests.get(url, params=params)

            if response.status_code != 200:
                _LOGGER.error(
                    "24小时API请求失败，状态码: %s, 响应内容: %s",
                    response.status_code,
                    response.text,
                )
                return None

            data = response.json()
            daily_data = {}

            if data.get("code") == "200":
                today = datetime.now().date()
                # 处理今天的24小时数据
                for hour in data.get("hourly", []):
                    date = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z").date()
                    if date not in daily_data:
                        daily_data[date] = []

                    hour_time = datetime.strptime(
                        hour["fxTime"], "%Y-%m-%dT%H:%M%z"
                    ).hour
                    if self.start_hour <= hour_time <= self.end_hour:
                        daily_data[date].append(hour)

            # 获取72小时预报数据（用于明天和后天）
            url_72h = "https://devapi.qweather.com/v7/weather/72h"
            _LOGGER.debug("正在请求和风天气72小时API: %s, 参数: %s", url_72h, params)
            response_72h = requests.get(url_72h, params=params)

            if response_72h.status_code == 200:
                data_72h = response_72h.json()
                if data_72h.get("code") == "200":
                    for hour in data_72h.get("hourly", []):
                        date = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z").date()
                        if date > today:  # 只处理未来日期的数据
                            if date not in daily_data:
                                daily_data[date] = []

                            hour_time = datetime.strptime(
                                hour["fxTime"], "%Y-%m-%dT%H:%M%z"
                            ).hour
                            if self.start_hour <= hour_time <= self.end_hour:
                                daily_data[date].append(hour)

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
                    "type": DRYING_INDEX_TYPE,
                }
                indices_response = requests.get(indices_url, params=indices_params)

                if indices_response.status_code == 200:
                    indices_data = indices_response.json()
                    if indices_data.get("code") == "200" and indices_data.get("daily"):
                        for index in indices_data.get("daily", []):
                            if index.get("type") == DRYING_INDEX_TYPE:
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
                                    for hour_data in daily_data[date]:
                                        hour_data["dryingIndex"] = drying_index
                                    _LOGGER.debug(
                                        "添加晾晒指数 %s 到日期 %s",
                                        drying_index["category"],
                                        date,
                                    )
            except Exception as indices_err:
                _LOGGER.error("获取晾晒指数时出错: %s", indices_err)

            # 检查并记录获取到的数据
            for date, data in daily_data.items():
                _LOGGER.debug("日期 %s 获取到 %d 条小时数据", date, len(data))

            return daily_data

        except Exception as err:
            _LOGGER.error("获取天气数据时出错: %s", err, exc_info=True)
            return None

    def check_weather_suitable(self, hourly_data: list) -> tuple:
        """Check if weather is suitable for laundry based on hourly data."""
        if not hourly_data:
            return False, "无法获取天气数据", {}

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
        }

        total_humidity = 0
        valid_hours = 0
        suitable_periods = []
        current_period_start = None
        current_period_length = 0

        # Sort data by time to ensure correct period calculation
        hourly_data.sort(key=lambda x: datetime.strptime(x["fxTime"], "%Y-%m-%dT%H:%M%z"))

        for i, hour in enumerate(hourly_data):
            try:
                hour_dt = datetime.strptime(hour["fxTime"], "%Y-%m-%dT%H:%M%z")
                hour_time = hour_dt.hour
                humidity = float(hour["humidity"])
                precip = float(hour["precip"])
                pop = int(hour.get("pop", "0"))
                weather_text = hour["text"]
                wind_scale = hour.get("windScale", "0")
                wind_dir = hour.get("windDir", "未知")

                stats["weather_conditions"].add(weather_text)
                stats["wind_conditions"].add(f"{wind_dir} {wind_scale}级")

                # 获取紫外线指数 (use max for the day)
                if "uvIndex" in hour:
                    uv_index_val = int(hour["uvIndex"])
                    if uv_index_val > stats["uv_index"]:
                        stats["uv_index"] = uv_index_val

                total_humidity += humidity
                valid_hours += 1
                stats["max_pop"] = max(stats["max_pop"], pop)

                if precip > 0:
                    stats["has_precipitation"] = True

                # Check suitability for this hour
                is_hour_suitable = (
                    humidity <= self.max_suitable_humidity
                    and precip == 0
                    and weather_text not in self.unsuitable_weather_types
                    and pop <= self.max_pop
                    # Ensure the hour is within the user-defined start/end times
                    and self.start_hour <= hour_time < self.end_hour
                )

                if is_hour_suitable:
                    stats["suitable_hours"] += 1
                    if current_period_start is None:
                        current_period_start = hour_dt # Store datetime object
                    current_period_length += 1
                else:
                    # End of a suitable period (or still unsuitable)
                    if current_period_start is not None:
                        # Adjust end time: period ends *before* this unsuitable hour
                        period_end_dt = current_period_start + timedelta(hours=current_period_length -1)
                        suitable_periods.append({
                            "start": current_period_start,
                            "end": period_end_dt,
                            "length": current_period_length
                        })
                        current_period_start = None
                        current_period_length = 0

            except (ValueError, KeyError) as e:
                _LOGGER.warning(f"跳过处理小时数据时出错: {hour}, 错误: {e}")
                continue # Skip this hour if data is malformed

        # Check if the last hour ended a suitable period
        if current_period_start is not None:
            period_end_dt = current_period_start + timedelta(hours=current_period_length -1)
            suitable_periods.append({
                "start": current_period_start,
                "end": period_end_dt,
                "length": current_period_length
            })

        if valid_hours > 0:
            stats["avg_humidity"] = total_humidity / valid_hours
            # Estimate drying time based on overall conditions for the day if needed
            # For now, let's use the first hour's data as a proxy if no best period found
            first_valid_hour_data = next((h for h in hourly_data if 'humidity' in h), None)
            if first_valid_hour_data:
                stats["estimated_drying_time"] = self.estimate_drying_time(first_valid_hour_data)

        # Find the longest suitable period
        if suitable_periods:
            longest_period = max(suitable_periods, key=lambda p: p["length"])
            start_hour_str = longest_period["start"].strftime("%H:00")
            # End hour should be the *start* of the hour following the period
            end_hour_dt = longest_period["end"] + timedelta(hours=1)
            end_hour_str = end_hour_dt.strftime("%H:00")

            # Ensure end hour doesn't exceed the user's end_hour setting
            if end_hour_dt.hour > self.end_hour or (end_hour_dt.hour == self.end_hour and end_hour_dt.minute > 0):
                end_hour_str = f"{self.end_hour:02d}:00"
                # Adjust start if the period was truncated? Maybe not needed if logic is correct.

            stats["best_drying_period"] = f"{start_hour_str} - {end_hour_str}"

            # Recalculate estimated drying time based on the best period's conditions
            best_period_hours = [h for h in hourly_data if longest_period["start"] <= datetime.strptime(h["fxTime"], "%Y-%m-%dT%H:%M%z") <= longest_period["end"]]
            if best_period_hours:
                # Use the average condition or the best hour within the best period?
                # Let's use the average humidity of the best period for drying time estimate
                best_period_avg_humidity = sum(float(h['humidity']) for h in best_period_hours) / len(best_period_hours)
                # Create a proxy hour dict for estimate_drying_time
                proxy_hour_for_drying = best_period_hours[0].copy() # Get structure
                proxy_hour_for_drying['humidity'] = str(best_period_avg_humidity)
                # Find max UV within the best period
                max_uv_in_best = 0
                for h in best_period_hours:
                    if 'uvIndex' in h:
                        max_uv_in_best = max(max_uv_in_best, int(h['uvIndex']))
                proxy_hour_for_drying['uvIndex'] = str(max_uv_in_best)

                stats["estimated_drying_time"] = self.estimate_drying_time(proxy_hour_for_drying)


        # Determine final suitability and message
        reasons = []
        is_suitable = False # Default to False unless a suitable period >= min_hours is found

        # Check if any suitable period meets the minimum required hours
        if any(p["length"] >= self.min_suitable_hours for p in suitable_periods):
            is_suitable = True
            # Now check other conditions that might override suitability
            if stats["has_precipitation"]:
                is_suitable = False
                reasons.append("预计有降水")
            # Add other checks if needed (e.g., overall high avg humidity despite a window?)
        else:
            if stats["suitable_hours"] < self.min_suitable_hours:
                reasons.append(
                    f"连续适合晾晒的时间不足（最长 {max(p['length'] for p in suitable_periods) if suitable_periods else 0} 小时，需要{self.min_suitable_hours}小时）"
                )
            if not suitable_periods and valid_hours > 0: # No suitable periods found at all
                if stats["avg_humidity"] > self.max_suitable_humidity:
                    reasons.append(f"平均湿度过高 ({stats['avg_humidity']:.1f}%)")
                if stats["max_pop"] > self.max_pop:
                    reasons.append(f"降水概率较高 ({stats['max_pop']}%)")
                # Check unsuitable weather types if no suitable periods found
                unsuitable_types_found = stats["weather_conditions"].intersection(self.unsuitable_weather_types)
                if unsuitable_types_found:
                    reasons.append(f"预计有{'、'.join(unsuitable_types_found)}")
            elif stats["has_precipitation"]:
                # Precipitation might occur outside the 'suitable' windows
                reasons.append("预计有降水时段")


        # Generate result message based on the *final* is_suitable status
        if is_suitable:
            weather_emoji = "🌞" if "晴" in stats["weather_conditions"] else "⛅"
            wind_emoji = "🌪️" if any(scale.isdigit() and int(scale.split('-')[0]) >= 5 for cond in stats["wind_conditions"] for scale in cond.split() if scale.endswith('级')) else "🍃"

            drying_time = stats['estimated_drying_time']
            if drying_time <= 2:
                time_comment = "速干模式已开启！"
            elif drying_time <= 3:
                time_comment = "晾晒效果杠杠的~"
            else:
                time_comment = "稍微需要点耐心哦"

            # Use the calculated best_drying_period if available
            if stats["best_drying_period"]:
                timing_tip = "抓紧这个时间段！"
                message = [
                    f"{weather_emoji} 今天适合晾衣！",
                    f"最佳晾晒时间段：{stats['best_drying_period']} ({timing_tip})",
                    f"预计晾干时间：{drying_time:.1f}小时 ({time_comment})",
                    f"{wind_emoji} 风力情况：" + "，".join(sorted(list(stats["wind_conditions"]))),
                ]
            else: # Should not happen if is_suitable is True based on new logic, but as fallback
                message = [
                    f"{weather_emoji} 今天整体天气不错，适合晾晒！",
                    f"预计晾干时间：{drying_time:.1f}小时 ({time_comment})",
                    f"{wind_emoji} 风力情况：" + "，".join(sorted(list(stats["wind_conditions"]))),
                ]

            # 添加紫外线提醒
            if stats["uv_index"] > 7:
                message.append(f"☀️ 注意：紫外线较强 ({stats['uv_index']})，深色衣物可能褪色。")

        else:
            # Not suitable
            weather_emoji = "🌧️" if stats["has_precipitation"] or any(wt in self.unsuitable_weather_types for wt in stats["weather_conditions"]) else "☁️"
            message = [f"{weather_emoji} 今天不太适合晾衣服。主要原因："] + reasons
            # Add extra info even if unsuitable
            message.append(f"(适合小时: {stats['suitable_hours']}, 平均湿度: {stats['avg_humidity']:.1f}%, 最高降水概率: {stats['max_pop']}%)")


        return is_suitable, "\n".join(message), stats

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
