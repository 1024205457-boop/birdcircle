# BirdCircle — 鸟有圈

> 基于 AI 识鸟与地图鸟讯的观鸟社交产品

## 产品痛点

- **找不到鸟**：观鸟新人不知道附近哪里能看什么鸟，依赖口口相传
- **不会认鸟**：遇到不认识的鸟种，缺乏便捷的识别工具
- **照片散乱**：拍了大量鸟类照片，散落在手机相册里，无法按鸟种归档
- **社区缺失**：国内缺少针对观鸟爱好者的垂直社交与信息共享平台

## 核心链路

发现附近鸟点 → 上传照片和位置 → AI 初步识鸟 → 生成鸟讯 → 同步到相册 → 获得积分

1. **地图发现**：打开地图，查看附近鸟点的鸟种记录、时效和活跃度
2. **上传识别**：拍摄或导入鸟类照片，AI 自动识别鸟种并归档
3. **鸟讯生成**：上传的照片自动关联地点，生成可分享的鸟讯记录
4. **相册管理**：按鸟种自动分类，支持三层卡片滑动浏览，可 ZIP 导出
5. **积分激励**：每次上传、打卡、归档均获得积分，提升用户参与感

## 技术实现

| 模块 | 技术方案 |
|------|---------|
| 地图底图 | Leaflet + 高德地图瓦片 |
| 鸟点数据 | 基于 eBird 热点数据整理的 Demo 数据 + 公开资料补充 |
| AI 识鸟 | 百度 AI 图像识别（通过本地代理 `/api/baidu`） |
| 相册滑动 | Pointer Events 状态机 + `setPointerCapture` |
| 相册导出 | JSZip 打包，img+canvas 读取本地照片（兼容 `file://`） |
| 前端框架 | 纯原生 HTML/CSS/JS，零依赖框架 |

## API 环境变量

AI 识鸟功能通过 `proxy.py` 本地代理调用百度 API，**密钥不在前端暴露**。

```bash
export BAIDU_CLIENT_ID="你的百度 API Key"
export BAIDU_CLIENT_SECRET="你的百度 Secret Key"
python3 proxy.py
```

前端通过以下接口访问：
- `POST /api/baidu/token` — 获取 access_token
- `POST /api/baidu/animal` — 图像识别

## 如何运行

### 方式一：直接打开（纯前端，无 AI 识鸟）
```bash
open birdcircle.html
```
AI 识鸟会进入演示模式（文件名关键词匹配 + 确定性算法），其他功能正常。

### 方式二：完整功能（需配置 API）
```bash
# 1. 配置环境变量
export BAIDU_CLIENT_ID="xxx"
export BAIDU_CLIENT_SECRET="xxx"

# 2. 启动代理服务器
python3 proxy.py

# 3. 浏览器访问
open http://localhost:8080/birdcircle.html
```

## 鸟类保护机制

| 场景 | 处理方式 | 提示 |
|------|---------|------|
| 敏感物种 | 坐标模糊偏移 | 导航禁用 |
| 夜行鸟类（如鸮类） | 坐标模糊 + 靠近劝阻 | 夜间请勿靠近 |
| 繁殖/育雏地 | 坐标大幅模糊 | 巢区禁用导航 |

地图页面顶部固定显示保护规则提示条，鸟点 tooltip 和详情页均带保护标签。

## 文件结构

```
birdcircle.html     # 主应用（首页、地图、上传、相册、积分）
proxy.py            # 百度 AI 代理（保护 API Key）
README.md           # 本文件
docs/
  architecture.md   # 技术架构说明
deferred/
  old-index.html    # 旧版页面（保留参考）
birds/              # 鸟种示例图片
photos/             # 场景/产品图片
libs/               # JSZip、Leaflet
```

## 演示数据说明

- 地图鸟点数据基于 eBird 公开热点信息整理，非实时 API 调用
- AI 识鸟在无网络或 API 未配置时进入演示模式，基于文件名关键词匹配
- 所有鸟讯统计数字使用确定性算法生成，同一鸟点每次打开数据一致
