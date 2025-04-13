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

1. 下载此仓库的最新版本
2. 将`custom_components/laundry_checker`文件夹复制到你的Home Assistant配置目录下的`custom_components`文件夹中
3. 重启Home Assistant

## 配置

### 前置要求

- 和风天气API密钥（可在[和风天气开发平台](https://dev.qweather.com/)申请）
- 需要配置的位置坐标（经度,纬度格式）

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
    - **晾晒指数** (官方指数，包含级别和具体建议)
    - 详细的多天预报信息
    - 未来几天的晾衣建议

## 晾晒指数说明

本集成使用和风天气API提供的官方晾晒指数（指数类型ID为13），该指数综合考虑了天气情况、湿度、风力、日照等多种因素，为用户提供专业的晾晒建议。

晾晒指数通常分为以下几个级别：
- 较适宜：天气较好，适合晾晒衣物
- 适宜：天气良好，非常适合晾晒衣物
- 不太适宜：天气条件一般，晾晒效果可能不佳
- 不宜：天气条件不好，不建议晾晒衣物

同时，晾晒指数还会提供具体的文字建议，帮助用户更好地了解晾晒情况。

## 自动化示例

### 基本通知示例

```yaml
automation:
  - alias: "晾衣提醒"
    trigger:
      - platform: state
        entity_id: binary_sensor.laundry_checker
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "适合晾衣提醒"
          message: "{{ state_attr('binary_sensor.laundry_checker', 'message') }}"
```

### 详细多天预报通知示例

```yaml
automation:
  - alias: "每日天气晾衣预报"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "洗衣天气预报"
          message: "{{ state_attr('binary_sensor.laundry_checker', 'detailed_message') }}"
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
          title: "洗衣天气预报"
          message: "{{ state_attr('binary_sensor.laundry_checker', 'detailed_message') }}"
      - service: notify.mobile_app_ipad
        data:
          title: "洗衣天气预报"
          message: "{{ state_attr('binary_sensor.laundry_checker', 'detailed_message') }}"
```

## 常见问题 (FAQ)

**Q: "洗衣建议" (binary_sensor.laundry_advice) 的状态 (`on`/`off`) 反映的是今天还是明天的情况？**

A: 该传感器的 `on`/`off` 状态 **仅反映今天** 是否适合晾晒。它会根据您设置的允许时间范围（最早开始时间到最晚结束时间），结合湿度、降水概率、天气类型等条件，判断今天是否存在一个满足您设置的"最少连续晾晒小时数"并且在"期望的最晚收衣时间"前结束的连续时间段。如果存在这样的时段，状态为 `on`，否则为 `off`。

关于明天或未来几天的晾晒建议，通常会包含在传感器的 **属性** 中，例如 `tomorrow_detail` 或 `multi_day_forecast`。

## 问题反馈

如果你在使用过程中遇到任何问题，请在GitHub上提交Issue。

## 更新日志

### v0.3.0
- 新增功能：紫外线指数支持
- 新增功能：和风天气官方晾晒指数支持
- 优化晾干时间计算，考虑紫外线因素

### v0.2.0
- 新增功能：未来三天详细天气预报
- 新增功能：风力情况显示
- 优化通知内容和格式

### v0.1.0
- 初始版本发布
- 基本功能实现
- 支持HACS安装 