"""Helper utilities for the Laundry Checker integration."""

from __future__ import annotations

from homeassistant.util import slugify

try:
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover - optional dependency
    lazy_pinyin = None


def normalize_api_host(api_host: str) -> str:
    """Return a normalized QWeather API host with scheme and without trailing slash."""
    host = (api_host or "").strip()
    if not host:
        raise ValueError("QWeather API host cannot be empty")

    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"

    return host.rstrip("/")


def validate_coordinates(longitude: float, latitude: float) -> None:
    """验证经纬度坐标是否在有效范围内。

    Args:
        longitude: 经度值
        latitude: 纬度值

    Raises:
        ValueError: 如果坐标超出有效范围
    """
    if not -180 <= longitude <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    if not -90 <= latitude <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")


def format_location(longitude: float, latitude: float) -> str:
    """格式化经纬度为QWeather API所需的字符串格式。

    Args:
        longitude: 经度值
        latitude: 纬度值

    Returns:
        格式化的位置字符串: "longitude,latitude"
    """
    # 保留最多6位小数（GPS标准精度约0.1米）
    return f"{longitude:.6f},{latitude:.6f}".rstrip("0").rstrip(".")


def build_location_suffix(text: str) -> str:
    """基于文本构建适合entity_id的后缀。"""
    if not text:
        return "location"

    if lazy_pinyin is not None:
        text = "".join(lazy_pinyin(text))

    return slugify(text) or "location"
