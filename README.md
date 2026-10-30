# WordShape · 文字塑形排印

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)

**把文字变成图形，再把文字填进图形。**

纯 Python 实现的文字图形工具，两个功能、16 种效果。不调用任何 AI 生图模型 —— 全部本地计算，**无水印、不消耗生图额度、同输入必出同图**。

---

## 目录

- [功能一览](#功能一览)
- [安装](#安装)
- [快速开始](#快速开始)
- [功能一：文字复制与变形](#功能一文字复制与变形)
- [功能二：主体剪影文字填充](#功能二主体剪影文字填充)
- [字体（跨平台）](#字体跨平台)
- [接入其他软件 / Agent](#接入其他软件--agent)
- [作为 Agent Skill 使用](#作为-agent-skill-使用)
- [许可](#许可)

---

## 功能一览

| 功能                  | 输入           | 输出                         |
| ------------------- | ------------ | -------------------------- |
| **text** · 文字复制与变形  | 一段文字         | 文字复制、弯折、透视、环形排布后的图形（9 种效果） |
| **fill** · 主体剪影文字填充 | 一张主体图 + 一段文字 | 文字填满主体轮廓的透明 PNG（7 种效果）     |

输出均为 PNG，默认红字 `#E03A2F`、透明底，可直接叠加到海报 / 封面 / 视频上。

---

## 安装

```bash
git clone <your-repo-url> wordshape
cd wordshape
pip install -r requirements.txt
```

依赖只有两个：`Pillow`、`numpy`。Python 3.9+。

---

## 快速开始

```bash
# 列出全部效果
python -m wordshape list

# 功能一：文字复制与变形（默认透明底红字）
python -m wordshape text "我爱你" -o out/spiral.png --effect spiral

# 功能一：换配色（黑底红字）
python -m wordshape text "KEEP GOING" -o out/fisheye.png --effect fisheye --mode br

# 功能二：文字填进主体剪影（横排）
python -m wordshape fill cat.png "今天也要加油鸭" -o out/cat.png

# 功能二：竖排 + 波浪变形
python -m wordshape fill cat.png "今天也要加油鸭" -o out/cat_wave.png --layout v --effect wave
```

---

## 功能一：文字复制与变形

| 效果名         | 中文名    | 说明                                 |
| ----------- | ------ | ---------------------------------- |
| `spiral`    | 旋转重复   | 文字围绕中心缩放 + 旋转复制 25 份，形成涡旋，最前一层原字清晰 |
| `circular`  | 圆形文字环绕 | 文字沿圆周弯排成环，再旋转复制 8 层                |
| `tunnel`    | 透视空间   | 多行文字做成四面透视墙，向中心收缩，中间留空             |
| `wave_v`    | 垂直波浪   | 多行文字沿纵向连续起伏                        |
| `wave_h`    | 水平波浪   | 多行文字沿横向错位弯曲                        |
| `flowline`  | 流线波纹   | 多行文字沿同一条平滑曲线流动                     |
| `waveweave` | 波浪织锦   | 二十多条薄波浪带交织成纹理（可读性低，适合底纹）           |
| `fisheye`   | 鱼眼透视   | 凸透镜映射，中间放大外鼓、边缘压缩                  |
| `ring`      | 环形旋转   | 文字排成方框，嵌套旋转复制 20 层                 |

### 输出模式

| `--mode` | 背景           | 文字                  |
| -------- | ------------ | ------------------- |
| `tr`     | 透明           | 红 `#E03A2F`（**默认**） |
| `br`     | 黑 `#111111`  | 红                   |
| `bw`     | 白            | 黑                   |
| `wb`     | 黑            | 白                   |
| `white`  | 透明           | 白                   |
| `black`  | 透明           | 黑                   |
| `red`    | 红            | 白                   |
| `navy`   | 藏青 `#0A1F33` | 青 `#4FE0E6`         |

自定义：`--bg "#101010" --fg "#F0C040"`（`--mode` 会覆盖这两个参数）。

### 常用参数

| 参数           | 说明                | 默认    |
| ------------ | ----------------- | ----- |
| `--size`     | 基准字号              | 240   |
| `--rows`     | 覆盖效果行数（如透视空间每边行数） | 按效果自动 |
| `--font`     | 字体文件路径            | 自动探测  |
| `-o / --out` | 输出文件              | 必填    |

---

## 功能二：主体剪影文字填充

| 效果     | 用法                      | 说明              |
| ------ | ----------------------- | --------------- |
| 基础横写   | （不加参数）                  | 逐行写，写完一行接下一行    |
| 基础竖写   | `--layout v`            | 逐列写，写完一列接下一列    |
| 波浪     | `--effect wave`         | 字沿纵向正弦起伏        |
| 鱼眼凸起   | `--effect fisheye`      | 中间放大、四周缩小       |
| 环形旋转   | `--effect swirl`        | 越靠外扭转越大         |
| 透视·轮廓圈 | `--effect tunnel`       | 沿主体轮廓一圈圈向内写     |
| 透视·圆环  | `--effect tunnel_round` | 正圆圈排字，中心扣主体轮廓空洞 |

### 输入图要求

1. **最好：透明底 PNG** —— 直接使用 alpha 通道
2. **次选：纯色背景** —— 自动分割主体（`--threshold` 可调）
3. **复杂背景** —— 先抠图，或用 `--mask` 指定蒙版

### 常用参数

| 参数            | 说明               | 默认        |
| ------------- | ---------------- | --------- |
| `--size`      | 字号基准（控制密度）       | 16        |
| `--rows`      | 行数（竖排 = 列数），越大越密 | 自动        |
| `--gap`       | 行缝比例             | 0.02      |
| `--fg`        | 文字颜色             | `#E03A2F` |
| `--threshold` | 纯色背景分割阈值         | 36        |

---

## 字体（跨平台）

脚本会按顺序自动查找字体，无需配置：

1. 环境变量 `WORDSHAPE_FONT` 指定的字体（最优先）
2. 仓库内 `fonts/` 目录（自行放进字体文件即可随仓库分发）
3. 系统字体目录：Windows `C:/Windows/Fonts`、macOS `/System/Library/Fonts`、Linux `/usr/share/fonts` 等

内置候选包括：微软雅黑 / 黑体 / PingFang / Hiragino / 思源黑体 / Noto Sans CJK / 文泉驿 等。

找不到字体时可用 `--font` 直接指定：

```bash
python -m wordshape text "你好" -o out.png --font /path/to/NotoSansSC-Bold.otf
```

---

## 接入其他软件 / Agent

### 1. 命令行调用（n8n、脚本、CI、任何能跑 shell 的 Agent）

```bash
python -m wordshape text "<文字>" -o <输出.png> --effect <效果名>
python -m wordshape fill <图.png> "<文字>" -o <输出.png> [--layout v] [--effect wave]
```

退出码 0 表示成功，输出路径会打印到 stdout（`EFFECT -> ...` / `TEXT -> ...`）。

### 2. HTTP 服务（豆包 / 扣子 Coze / Dify / 任意低代码平台）

仓库自带零依赖服务端 `server.py`（仅用标准库，不需要 Flask）：

```bash
python server.py --port 8000
```

接口（JSON，图片用 base64 传输）：

```bash
# 功能一
curl -X POST http://127.0.0.1:8000/text \
  -H "Content-Type: application/json" \
  -d '{"text":"我爱你","effect":"spiral","mode":"tr"}'

# 功能二（image 传 base64 或 data URI）
curl -X POST http://127.0.0.1:8000/fill \
  -H "Content-Type: application/json" \
  -d '{"image":"<base64>","text":"我爱你","layout":"v","effect":"wave"}'
```

返回 `{"ok": true, "image": "<base64 PNG>"}`，直接作为图片返回给调用方。

> **关于豆包**：豆包 App 本身不能执行 Python 代码。可行路径是「扣子 Coze 工作流」——把本服务部署到一台可访问的机器（或云函数），在 Coze 里用 **HTTP 请求节点** 调 `/text` 或 `/fill`，再把返回的 base64 转成图片输出。Coze 的「代码节点」只能跑短时 Python，跑本项目的图像计算容易超时，推荐 HTTP 方式。

### 3. 作为 Agent Skill 使用（Claude Code 等支持 skills 的环境）

仓库根目录带 `SKILL.md`（Agent Skills 标准格式），把整个目录放进目标 Agent 的 skills 目录即可，Agent 会根据 description 自动选中并调用 CLI。

---

## 项目结构

```
wordshape-pack/
├── wordshape/
│   ├── textfx.py        # 功能一：9 种变形效果
│   ├── subjectfill.py   # 功能二：剪影文字填充
│   ├── cli.py           # 命令行入口
│   └── __main__.py      # python -m wordshape
├── server.py            # 零依赖 HTTP 服务（豆包/Coze/Dify 接入用）
├── SKILL.md             # Agent Skills 描述文件
├── requirements.txt
└── examples/
```

---

## 常见问题

**Q：输出是透明底，怎么看不见背景？**  
这是设计如此。输出是素材图，叠到自己的画面上用；需要底色请加 `--mode bw` 等。

**Q：为什么剪影看起来像"文字块"？**  
剪影填充的本质就是文字铺满形状，远看识形、近看全是字。主体细节越丰富（毛发、耳朵、手指），形状越容易辨认。

**Q：支持英文 / 日文 / 韩文吗？**  
支持任意语言。英文自动保留单词间距，中日韩文无缝连写。

**Q：同一个效果跑两次结果一样吗？**  
完全一样。纯确定性计算，可反复重跑调参。

**Q：会消耗 AI 生图额度吗？**  
不会。全部是本地图像处理，秒级出图。

---

## 许可

[MIT](LICENSE) © 2026 [DajiaoFish](https://github.com/DajiaoFish)

可自由使用、修改、分发与商用，保留版权声明即可。
