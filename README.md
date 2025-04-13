# 洗衣检查器 (Laundry Checker)

这是一个基于和风天气API的Home Assistant自定义组件，用于检查天气是否适合晾衣服。

## 功能特点

- 基于多个天气因素综合判断是否适合晾衣服
  - 湿度
  - 降水概率
  - 天气状况
  - 风力
  - 温度
  - 紫外线指数
  - 晾晒指数（官方指数）
- 提供预计晾干时间
- 推荐最佳晾晒时间段
- 支持自定义参数
  - 可接受的最高湿度
  - 所需的最少适合晾晒时间
  - 可接受的最大降水概率
  - 晾衣和收衣时间段
  - 更新间隔
- **新增：提供未来三天详细天气预报**

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

### 配置步骤

1. 在Home Assistant的集成页面中点击"添加集成"
2. 搜索"Laundry Checker"
3. 填写配置信息：
   - 和风天气API密钥
   - 位置坐标
   - 其他可选参数（可使用默认值）

### 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 和风天气API密钥 | 必填，用于获取天气数据 | - |
| 位置坐标 | 必填，格式：经度,纬度 | 120.15,30.28 |
| 最高适合晾衣湿度 | 超过此湿度认为不适合晾衣 | 85.0 |
| 最少需要的适合晾晒小时数 | 一天中需要的最少适合晾晒时间 | 6 |
| 最大可接受降水概率 | 超过此概率认为不适合晾衣 | 0 |
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
    - 详细的多天预报信息
    - 未来几天的晾衣建议

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

这个自动化会在每天晚上8点发送未来三天的天气和晾衣预报。

```yaml
automation:
  - alias: "每日天气晾衣预报"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "洗衣天气预报 (未来三天)"
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

## 更新日志

### v0.3.0
- 新增功能：紫外线指数支持
- 优化晾干时间计算，考虑紫外线因素

### v0.2.0
- 新增功能：未来三天详细天气预报
- 新增功能：风力情况显示
- 优化通知内容和格式

### v0.1.0
- 初始版本发布
- 基本功能实现
- 支持HACS安装 