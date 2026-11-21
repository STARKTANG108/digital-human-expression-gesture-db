# 数字人「微表情库 + 肢体动作库」双数据库（Digital Human Expression & Gesture DB）

> 面向 **InfiniteTalk / Wan2.2-Animate / DWPose** 路线的标准化数字人**面部微表情（`expression_db`）**与**肢体语言/走动动作（`gesture_db`）**双资产库。全部母带统一为 **25fps 无声 MP4 + 4 帧预览条 + 结构化 JSON 元数据**，开箱即用、跨任意人物形象复用。

![双数据库全套20条微表情与肢体动作图鉴总表](./db_catalog_preview.jpg)

## 🎬 15 合 1 完整 1080p 展示合集
- **1080p 成品展示视频（91 MB）**：已在 [GitHub Release v1.0.0](https://github.com/STARKTANG108/digital-human-expression-gesture-db/releases/tag/v1.0.0) 附带完整高清直链下载（`数字人全套微表情与肢体动作展示合集_15合1_1080p.mp4`）。

---

## 📦 仓库目录结构（20 条标准化参考母带，已全部内置）

```text
digital-human-expression-gesture-db/
├── db_catalog_preview.jpg      # 全套 20 条素材可视化图鉴总表
├── db_index.json               # 统一可检索 JSON 索引
├── db_manager.py               # 入库 / 检索 / 自动生成图鉴 CLI
├── drive_v2v_pipeline.py       # 按情绪标签直接驱动 InfiniteTalk / V2V 渲染
├── launch_g4_wan_animate.py    # Colab G4 独立 Wan2.2-Animate + DWPose 启动器
├── expression_db/              # 面部微表情库（8 条 25fps 母带 + 6 大情绪预设）
│   ├── emotion_presets.json
│   ├── clips/                  # 8 条标准化 MP4 参考视频
│   └── thumbs/                 # 对应 4 帧微表情变化预览条
└── gesture_db/                 # 肢体动作库（12 条 25fps 母带 + 9 大高频动作分类）
    ├── gesture_taxonomy.json
    ├── clips/                  # 12 条标准化 MP4 参考视频
    └── thumbs/                 # 对应 4 帧动作轨迹预览条
```

### 1. 微表情库 `expression_db`（6 大核心情绪预设）
| 预设 ID | 情绪场景 | 典型微表情特征 |
|---|---|---|
| `warm_welcome` | 亲切迎客 | 温和笑眼、自然轻点头、嘴角柔和上扬 |
| `curious_hook` | 悬念反问 | 单侧轻挑眉、略微前倾、眼神聚焦抛出问题 |
| `emphatic_explain` | 干货强调 | 眉心微聚、果断顿首、逻辑节奏感强 |
| `admiring_soft` | 欣赏陶醉 | 眼神柔光微眯、轻缓呼吸、沉浸式赞叹 |
| `surprised_contrast` | 反差惊叹 | 眼前一亮、轻微睁眼抬眉、自然惊喜反转 |
| `sincere_cta` | 真诚邀约 | 柔光直视镜头、温润微笑、亲和力收尾互动 |

### 2. 肢体动作库 `gesture_db`（9 大口播与逛店高频动作）
- **坐播类**：自然摊手讲解 (`seated_hand_open`)、竖指 1-2-3 拆解 (`seated_count_123`)、身体微前倾拉近距离 (`seated_lean_in`)、双手捧物展示 (`seated_hold_item`)、边倒茶边聊 (`seated_pour_chat`)
- **站播 / 逛店走动类**：侧身伸手展品指引 (`standing_point_side`)、展桌俯身鉴赏 (`standing_table_inspect`)、展墙慢走讲解 (`walking_shelf_guide`)、长廊回头邀约 (`walking_corridor_invite`)

---

## ⚡ 常用一键命令

### 1. 导入手机实拍或 AI 生成动作视频入库（自动统一 25fps、去噪静音并抽 4 帧预览条）
```bash
python3 db_manager.py ingest \
  --db gesture \
  --id gest_seated_hand_01 \
  --src ~/Desktop/我的摊手实拍.mp4 \
  --label "坐播·自然摊手讲解" \
  --scene seated \
  --emotion emphatic_explain \
  --gesture-type seated_hand_open \
  --source-type real_capture \
  --tags "坐播,摊手,干货"
```

### 2. 导入面部微表情参考视频入库
```bash
python3 db_manager.py ingest \
  --db expression \
  --id emo_curious_01 \
  --src ~/Desktop/挑眉反问特写.mp4 \
  --label "悬念反问·单侧微挑眉" \
  --scene closeup \
  --emotion curious_hook \
  --source-type real_capture \
  --tags "挑眉,悬念,开场"
```

### 3. 检索库内素材 & 重新生成可视化图鉴总表
```bash
python3 db_manager.py list --db all
python3 db_manager.py catalog
```

### 4. 按情绪标签直接调用 InfiniteTalk 驱动（告别面无表情）
```bash
python3 drive_v2v_pipeline.py emotion-aroll \
  --url <COMFY_TUNNEL_URL> \
  --image <人物图.png> \
  --audio <配音.wav> \
  --emotion curious_hook \
  --aspect 9:16 --steps 4 \
  --out ~/Desktop/output.mp4
```
