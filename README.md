# 洗衣检查器 (Laundry Checker)

这是一个基于和风天气API的Home Assistant自定义组件，用于检查天气是否适合晾衣服。

> ⚠️ **重要提醒**：和风天气官方宣布 `devapi.qweather.com`、`api.qweather.com` 与 `geoapi.qweather.com` 将在 2026 年前陆续停止服务。请尽快改用你在 [和风天气控制台-设置](https://console.qweather.com/setting) 中看到的 **API Host**，本组件现已支持自定义 API Host。

## 功能特点

- 基于多个天气因素综合判断是否适合晾衣服
  - 湿度
  - 降水概率
  - 天气状况
  - 风力
  - 温度
  - 紫外线指数
  - 晾晒指数（官方指数）
  - **空气质量指数 (AQI)** - 新增
- 提供预计晾干时间
- 推荐最佳晾晒时间段
- 支持自定义参数
  - 可接受的最高湿度
  - 所需的最少适合晾晒时间
  - 可接受的最大降水概率
  - **可接受的最大空气质量指数 (AQI)** - 新增
  - 晾衣和收衣时间段
  - 更新间隔
- **新增：提供未来三天详细天气预报**
- **新增：空气质量检测，灰尘污染大时不适合晾衣**
- **新增：降雨提醒传感器（6小时内/明天/后天）**

## 安装

### HACS安装（推荐）

1. 确保已经安装了[HACS](https://hacs.xyz/)
2. 在HACS中点击"自定义存储库"
3. 添加此仓库：`https://github.com/renhai-lab/laundry_checker`
4. 在HACS的集成页面中搜索"Laundry Checker"并安装
5. 重启Home Assistant

### 手动安装

1. 前往[releases](https://github.com/renhai-lab/laundry_checker/releases)下载此仓库的最新版本
2. 将`custom_components/laundry_checker`文件夹复制到你的Home Assistant配置目录下的`custom_components`文件夹中
3. 重启Home Assistant

## 配置

### 前置要求

- 和风天气API密钥（可在[和风天气开发平台](https://dev.qweather.com/)申请）
- 和风天气账号专属 **API Host**（在[控制台-设置](https://console.qweather.com/setting)查看）

### 配置步骤

1. 在Home Assistant的集成页面中点击"添加集成"
2. 搜索"Laundry Checker"
3. 填写配置信息：
  - 和风天气API密钥
  - 和风天气 API Host（与密钥绑定的域名）
  - 位置坐标（或使用Home Assistant默认位置）
  - 其他可选参数（可使用默认值）

### 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 和风天气API密钥 | 必填，用于获取天气数据 | - |
| 和风天气 API Host | 必填，必须与账号密钥匹配。登陆和风天气控制台获取。例如 `https://api-qXXX.qweather.com` | 控制台提供 |
| 位置坐标 | 必填，格式：经度,纬度 | 120.15,30.28 |
| 最高适合晾衣湿度 | 超过此湿度认为不适合晾衣 | 85.0 |
| 最少需要的适合晾晒小时数 | 一天中需要的最少适合晾晒时间 | 6 |
| 最大可接受降水概率 | 超过此概率认为不适合晾衣 | 0 |
| 最大可接受空气质量指数 (AQI) | 超过此指数认为不适合晾衣（AQI > 100为轻度污染） | 100 |
| 开始晾衣时间 | 24小时制 | 6 |
| 最晚收衣时间 | 24小时制 | 22 |
| 建议收衣时间 | 24小时制 | 18 |

## 使用

安装并配置完成后，组件会创建以下实体：

- 二进制传感器：显示是否适合晾衣
  - 状态：开（适合）/关（不适合）
  - 属性：
    - 适合晾晒的小时数
    - 平均湿度
    - 是否有降水
    - 最大降水概率
    - 天气状况
    - 预计晾干时间
    - 最佳晾晒时间段
    - 风力情况
    - 紫外线指数
    - 空气质量指数 (AQI)
    - 空气质量等级
    - 主要污染物
    - 详细的多天预报信息
    - 未来几天的晾衣建议

- 传感器：降雨提醒
  - `sensor.laundry_checker_rain_within_6h`：6小时内是否下雨
  - `sensor.laundry_checker_rain_tomorrow`：明天是否下雨
  - `sensor.laundry_checker_rain_day_after_tomorrow`：后天是否下雨
  - 状态：`下雨` / `不下雨`（中文）或 `Rainy` / `No Rain`（英文）
  - 常用属性：
    - `rain_level`：降雨等级（无雨/小雨/中雨/大雨/暴雨）
    - `rain_hours`：窗口内预计下雨小时数
    - `total_precipitation`：窗口内累计降雨量（mm）
    - `max_hourly_precipitation`：窗口内最大单小时降雨量（mm）
    - `max_precipitation_probability`：窗口内最大降雨概率（%）

## 自动化示例

### 基本通知示例

```yaml
automation:
  - alias: "今日晾衣提醒"
    trigger:
      - platform: state
        entity_id: binary_sensor.laundry_checker_today_s_laundry_advice
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "适合晾衣提醒 - 今天"
          message: "{{ state_attr('binary_sensor.laundry_checker_today_s_laundry_advice', 'message') }}"
```

### 详细多天预报通知示例

这个自动化会在每天晚上8点发送未来三天的天气和晾衣预报。以下sensor的名称需要根据你的名称来修改。
```yaml
automation:
  - alias: "每日天气晾衣预报"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "明天我的家{{ '适合晾衣' if is_state('binary_sensor.laundry_checker_tomorrow_s_laundry_advice', 'on') else '不适合晾衣' }}
          message: "{{ state_attr('binary_sensor.laundry_checker_tomorrow_s_laundry_advice', 'detailed_message') }}"
```

### 发送到多个设备

```yaml
automation:
  - alias: "晾衣详细预报多设备通知"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_iphone
        data:
          title: "洗衣天气预报 (未来三天)"
          message: "{{ state_attr('binary_sensor.laundry_checker_tomorrow_s_laundry_advice', 'detailed_message') }}"
      - service: notify.mobile_app_ipad
        data:
          title: "洗衣天气预报 (未来三天)"
          message: "{{ state_attr('binary_sensor.laundry_checker_tomorrow_s_laundry_advice', 'detailed_message') }}"
```

### 降雨提醒

以下示例会在 **6小时内** 可能出现 **中雨及以上** 或 **持续性降雨** 时：

```yaml
automation:
  - alias: "下雨提醒罩雨布"
    description: "中雨及以上或持续降雨时提醒罩雨布"
    mode: single
    trigger:
      - platform: state
        entity_id: sensor.laundry_checker_rain_within_6h
        to: "rain"
    condition:
      - condition: template
        value_template: >
          {% set level = state_attr('sensor.laundry_checker_rain_within_6h', 'rain_level') %}
          {% set hours = state_attr('sensor.laundry_checker_rain_within_6h', 'rain_hours')|int(0) %}
          {% set total = state_attr('sensor.laundry_checker_rain_within_6h', 'total_precipitation')|float(0) %}
          {{ level in ['中雨','大雨','暴雨'] or (hours >= 2 and total >= 3) }}
    action:
      - service: notify.all_family_devices
        data:
          title: "⚠️ 可能下雨"
          message: >-
            {% set level = state_attr('sensor.laundry_checker_rain_within_6h', 'rain_level') %}
            {% set hours = state_attr('sensor.laundry_checker_rain_within_6h', 'rain_hours')|int(0) %}
            {% set total = state_attr('sensor.laundry_checker_rain_within_6h', 'total_precipitation')|float(0) %}
            6小时内预计 {{ level }}，累计 {{ total }} mm，降雨小时数 {{ hours }}。
```

> 提示：降雨等级按逐小时累计降水量分级（单位：mm）。如需更敏感/更宽松，可调整模板条件。

## 常见问题 (FAQ)

**Q: 这个集成创建了哪些传感器？它们分别代表什么？**

A: 洗衣检查器会创建以下三个传感器实体：

1.  **`binary_sensor.laundry_checker_today_s_laundry_advice` (今日洗衣建议)**
    *   **状态 (`on`/`off`)**: 反映 **今天** 是否适合晾晒。判断依据是您设置的允许时间段内（开始时间到结束时间），是否存在一个满足"最少连续晾晒小时数"且在"期望收衣时间"前结束的连续时段，同时满足湿度、降水概率等条件。
    *   **属性**: 包含今天晾晒条件的详细统计信息，如适合小时数、平均湿度、最佳晾晒时段、预计晾干时间、天气状况、风力情况、紫外线指数等。

2.  **`binary_sensor.laundry_checker_tomorrow_s_laundry_advice` (明日洗衣建议)**
    *   **状态 (`on`/`off`)**: 反映 **明天** 是否适合晾晒，判断逻辑与今天类似。
    *   **属性**: 包含明天晾晒条件的详细统计信息，以及 **未来三天的详细天气预报和晾衣建议 (`detailed_message`)**。

3.  **`sensor.laundry_checker_today_s_estimated_drying_time` (今日预计晾干时间)**
    *   **状态**: 显示 **今天** 预计晾干所需的小时数。
    *   **属性**: 包含与今天晾干时间相关的统计信息，如最佳晾晒时段、适合小时数等。

**Q: 如何获取未来几天的晾衣预报？**

A: 未来几天的详细晾衣预报存储在 **`binary_sensor.laundry_checker_tomorrow_s_laundry_advice`** 这个传感器的 `detailed_message` 属性中。您可以在自动化或卡片中引用这个属性来获取预报信息。

## 问题反馈

如果你在使用过程中遇到任何问题，请在GitHub上提交Issue。