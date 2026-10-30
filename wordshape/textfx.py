# -*- coding: utf-8 -*-
"""
text_fx.py - 12 种 Illustrator 风格文字复制与变形效果（纯 Pillow+numpy 实现）

用法:
  12 格合集:
    python text_fx.py "CREATE" <outdir> --grid <outdir>/grid.png
  单个效果:
    python text_fx.py "CREATE" <outdir> --effect spiral --out <outdir>/spiral.png
  查看效果列表:
    python text_fx.py --list

公共参数:
  --bg    背景色 (默认 "transparent", 支持 hex 色值)
  --fg    文字色 (默认 #E03A2F)
  --mode  输出模式 (默认 tr=透明底红字)
  --font  字体文件路径 (默认自动: 含 CJK 用 msyhbd.ttc, 否则 arialbd.ttf)
  --size  基准字号 (默认 240)
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

Image.MAX_IMAGE_PIXELS = None  # 输入为脚本自产图像, 关闭炸弹保护

# ---------------------------------------------------------------- 效果注册表
EFFECTS = [
    ("spiral",    "01 旋转重复 Spiral Repeat"),
    ("circular",  "02 圆形文字环绕 Circular Text"),
    ("tunnel",    "03 透视空间 Perspective Tunnel"),
    ("wave_v",    "04 垂直波浪 Vertical Wave"),
    ("wave_h",    "05 水平波浪 Horizontal Wave"),
    ("flowline",  "06 流线波纹 Flowline Wave"),
    ("waveweave", "07 波浪织锦 Wave Weave"),
    ("fisheye",   "08 鱼眼透视 Fisheye"),
    ("ring",      "09 环形旋转 Ring Rotation"),
]
EFFECT_KEYS = [k for k, _ in EFFECTS]

# 全局输出风格: 红底演示 / 纯白透明 / 纯黑透明 / 白底黑字 / 黑底白字
STYLE = {
    "bg": (224, 58, 47),
    "fg": (255, 255, 255),
    "transparent": False,
    "shadow": (85, 18, 14),
    "shadow_alpha": 0.55,
}


def _hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


_CUR_TEXT = ""   # 当前输入文字, 供效果内部做 CJK 密度自适应


def set_style(bg_hex, fg_hex):
    """设置当前输出风格; transparent 背景时关闭投影和底色装饰."""
    global STYLE
    transparent = bg_hex.lower() == "transparent"
    bg = (0, 0, 0) if transparent else _hex_rgb(bg_hex)
    fg = _hex_rgb(fg_hex)
    if transparent:
        shadow = (0, 0, 0)
        alpha = 0.0
    elif bg == (255, 255, 255):
        shadow = (0, 0, 0)
        alpha = 0.10
    else:
        shadow = tuple(int(c * 0.35) for c in bg)
        alpha = 0.55
    STYLE = {
        "bg": bg,
        "fg": fg,
        "transparent": transparent,
        "shadow": shadow,
        "shadow_alpha": alpha,
    }

# ---------------------------------------------------------------- 字体 (跨平台自动探测)
# 优先顺序: 环境变量 WORDSHAPE_FONT > 包内 fonts/ 目录 > 系统字体目录
_FONT_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "fonts"),
    "C:/Windows/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "/usr/share/fonts/truetype",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]

FONT_CJK_CANDIDATES = [
    "msyhbd.ttc", "msyh.ttc", "simhei.ttf",            # Windows 微软雅黑/黑体
    "PingFang.ttc", "Hiragino Sans GB.ttc",            # macOS
    "STHeiti Medium.ttc", "Songti.ttc",
    "NotoSansCJK-Bold.ttc", "NotoSansCJKsc-Bold.otf",  # Linux / Noto
    "NotoSansSC-Bold.otf", "SourceHanSansCN-Bold.otf",
    "wqy-zenhei.ttc", "DroidSansFallbackFull.ttf",
]
FONT_LATIN_CANDIDATES = [
    "arialbd.ttf", "Arial Bold.ttf", "calibrib.ttf", "impact.ttf",
    "HelveticaNeue-Bold.ttf", "Helvetica.ttc",
    "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf",
]


def _iter_font_files():
    """遍历候选目录下的字体文件 (含一层子目录)"""
    for d in _FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            depth = root[len(d):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            for fn in files:
                if fn.lower().endswith((".ttf", ".ttc", ".otf")):
                    yield fn.lower(), os.path.join(root, fn)


def _find_font_file(name):
    target = name.lower()
    for fn, path in _iter_font_files():
        if fn == target:
            return path
    return None


def _has_cjk(s):
    return any('\u4e00' <= ch <= '\u9fff'
               or '\u3040' <= ch <= '\u30ff'
               or '\uac00' <= ch <= '\ud7af' for ch in s)


def pick_font(text, size, font_path=None):
    env_font = os.environ.get("WORDSHAPE_FONT")
    if not font_path and env_font and os.path.exists(env_font):
        font_path = env_font
    if font_path:
        return ImageFont.truetype(font_path, size)
    cjk = _has_cjk(text)
    cands = FONT_CJK_CANDIDATES if cjk else FONT_LATIN_CANDIDATES
    others = FONT_LATIN_CANDIDATES if cjk else FONT_CJK_CANDIDATES
    for name in cands + others:
        p = _find_font_file(name)
        if not p:
            continue
        try:
            f = ImageFont.truetype(p, size)
            if f.getmask(text or "A").getbbox() is not None:
                return f
        except OSError:
            continue
    raise RuntimeError(
        "找不到可用字体。请安装中文字体, 或用 --font 指定字体文件, "
        "或设置环境变量 WORDSHAPE_FONT 指向字体路径。")


# ---------------------------------------------------------------- 文字渲染
def render_text(text, font_path=None, size=240, fg="#FFFFFF"):
    """渲染文字为 RGBA 紧凑图 (多行支持 \\n)"""
    lines = text.split("\n")
    font = pick_font(text, size, font_path)
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    widths, heights = [], []
    for ln in lines:
        bbox = d.textbbox((0, 0), ln, font=font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    gap = int(size * 0.18)
    W = max(widths) + size
    H = int(sum(heights) + gap * (len(lines) - 1) + size)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = size // 2
    for ln, h in zip(lines, heights):
        bbox = d.textbbox((0, 0), ln, font=font)
        d.text(((W - (bbox[2] - bbox[0])) / 2 - bbox[0], y - bbox[1]), ln,
               font=font, fill=fg)
        y += h + gap
    return crop_alpha(img)


def crop_alpha(img, pad=8):
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return img
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, img.width)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, img.height)
    return img.crop((x0, y0, x1, y1))


def _key_out_bg(img):
    """黑填充遮挡版 -> 透明底: 黑色(含字身内部与层间遮挡区)转 alpha=0,
    红色描边保留; 亮度即覆盖率, 边缘自然抗锯齿"""
    a = np.asarray(img).astype(np.int32)
    mx = a[:, :, :3].max(axis=2)            # 黑=0, 红≈224
    fg = STYLE["fg"]
    top = max(int(max(fg)), 1)
    alpha = np.clip(mx * 255 // top, 0, 255).astype(np.uint8)
    out = np.zeros((a.shape[0], a.shape[1], 4), dtype=np.uint8)
    out[:, :, 0], out[:, :, 1], out[:, :, 2] = fg
    out[:, :, 3] = alpha
    return Image.fromarray(out, "RGBA")


def _bg_rgb(img):
    # 透明模式下, 字身/底色装饰使用前景色, 避免残留红块
    return STYLE["fg"] if STYLE["transparent"] else STYLE["bg"]


def _fg_rgb(img):
    return STYLE["fg"]


def _solid_stroke_text(img, outline=5, grow=0):
    """白色实心文字 + 背景色细描边; grow 用于加粗白色字身."""
    arr = np.asarray(img).copy()
    outline = max(3, int(outline) | 1)
    if grow:
        grow = max(3, int(grow) | 1)
    alpha = Image.fromarray(arr[:, :, 3], "L")
    core = alpha.filter(ImageFilter.MaxFilter(grow)) if grow else alpha
    body_mask = np.asarray(core, dtype=np.int16) > 12
    outer = np.asarray(core.filter(ImageFilter.MaxFilter(outline)),
                       dtype=np.int16)
    rim = (outer > 12) & (~body_mask)
    fg = _fg_rgb(img)
    bg = _bg_rgb(img)
    body = body_mask
    arr[:, :, 0][body] = fg[0]
    arr[:, :, 1][body] = fg[1]
    arr[:, :, 2][body] = fg[2]
    arr[:, :, 3][body] = 255
    if STYLE["transparent"]:
        arr[:, :, 3][rim] = 0
    else:
        arr[:, :, 0][rim] = bg[0]
        arr[:, :, 1][rim] = bg[1]
        arr[:, :, 2][rim] = bg[2]
        arr[:, :, 3][rim] = 255
    return Image.fromarray(arr, "RGBA")


def _add_shadow(img, dx=10, dy=12, alpha=None, color=None):
    """给文字图加一层偏移投影; 透明模式下不投影."""
    if STYLE["transparent"] or STYLE["shadow_alpha"] <= 0:
        return img
    alpha = STYLE["shadow_alpha"] if alpha is None else alpha
    color = STYLE["shadow"] if color is None else color
    a = np.asarray(img).copy()
    sh = a.copy()
    sh[:, :, 0], sh[:, :, 1], sh[:, :, 2] = color
    sh[:, :, 3] = (sh[:, :, 3] * alpha).astype(np.uint8)
    shadow = Image.fromarray(sh, "RGBA")
    pad = max(6, abs(dx) + 4, abs(dy) + 4)
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2),
                       (0, 0, 0, 0))
    canvas.alpha_composite(shadow, (pad + dx, pad + dy))
    canvas.alpha_composite(img, (pad, pad))
    return canvas


def _outline_text(img, stroke=5, fill=None):
    """白描边文字; fill 指定时不透明填充, 使复制层互相遮挡."""
    arr = np.asarray(img).copy()
    stroke = max(3, int(stroke) | 1)
    alpha = Image.fromarray(arr[:, :, 3], "L")
    outer = np.asarray(alpha.filter(ImageFilter.MaxFilter(stroke)), dtype=np.int16)
    inner = np.asarray(alpha.filter(ImageFilter.MinFilter(stroke)), dtype=np.int16)
    edge = np.clip(outer - inner, 0, 255).astype(np.uint8)
    mask = edge > 12
    opaque = arr[:, :, 3] > 128
    fg = np.array([255, 255, 255], dtype=np.uint8)
    if opaque.any():
        fg = np.median(arr[:, :, :3][opaque], axis=0).astype(np.uint8)
    if fill is not None:
        body = outer > 12
        arr[:, :, 0][body] = fill[0]
        arr[:, :, 1][body] = fill[1]
        arr[:, :, 2][body] = fill[2]
        arr[:, :, 3][body] = 255
    arr[:, :, 0][mask] = fg[0]
    arr[:, :, 1][mask] = fg[1]
    arr[:, :, 2][mask] = fg[2]
    arr[:, :, 3][mask] = 255
    if fill is None:
        arr[:, :, 3] = np.where(mask, 255, 0)
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------- 重映射核心
def remap(src, out_w, out_h, sx, sy, wrap_x=False):
    """逆向映射 + 双线性采样. src: np float32 HxWx4; sx/sy: out 形状坐标图"""
    H, W = src.shape[:2]
    if wrap_x:
        sx = np.mod(sx, W)
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    fx = (sx - x0)[..., None]
    fy = (sy - y0)[..., None]
    x0c, x1c = np.clip(x0, 0, W - 1), np.clip(x0 + 1, 0, W - 1)
    y0c, y1c = np.clip(y0, 0, H - 1), np.clip(y0 + 1, 0, H - 1)
    tl = src[y0c, x0c]
    tr = src[y0c, x1c]
    bl = src[y1c, x0c]
    br = src[y1c, x1c]
    out = (tl * (1 - fx) * (1 - fy) + tr * fx * (1 - fy)
           + bl * (1 - fx) * fy + br * fx * fy)
    valid = ((sx >= 0) & (sx <= W - 1) & (sy >= 0) & (sy <= H - 1))[..., None]
    out = np.where(valid, out, 0.0)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def meshgrid(out_w, out_h):
    xs, ys = np.meshgrid(np.arange(out_w, dtype=np.float32),
                         np.arange(out_h, dtype=np.float32))
    return xs, ys


def to_arr(img):
    return np.asarray(img, dtype=np.float32)


# ---------------------------------------------------------------- 变形核心(纯warp)
def _warp_twist(img, k=1.1):
    """径向涡旋扭转"""
    W, H = img.size
    S = int(max(W, H) * 1.45)
    src = to_arr(img)
    cx, cy = W / 2, H / 2
    xs, ys = meshgrid(S, S)
    dx, dy = xs - S / 2, ys - S / 2
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx)
    R = max(W, H) * 0.62
    theta = theta + k * (r / R) ** 2
    sx = cx + r * np.cos(theta)
    sy = cy + r * np.sin(theta)
    return remap(src, S, S, sx, sy)


def _warp_banana(img, span=math.pi * 0.62):
    """文字沿圆弧弯排, 字母随弧旋转"""
    W, H = img.size
    ow, oh = int(W * 1.45), int(H * 2.1)
    src = to_arr(img)
    Rc = W / span                       # 弧长 ≈ 文字宽度
    ccx, ccy = ow / 2, oh * 0.28 + Rc   # 圆心在弧顶下方 (可超出画布)
    xs, ys = meshgrid(ow, oh)
    dx, dy = xs - ccx, ys - ccy
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dx, ccy - ys)    # 弧顶为 0
    sx = (theta / span + 0.5) * W
    sy = H / 2 - (r - Rc)   # 弧线外侧对应文字顶部, 保持正向
    return remap(src, ow, oh, sx, sy)


def _warp_wavesh(img, amp=0.38, cycles=1.0):
    """基线沿横向正弦起伏 (S 形波浪)"""
    W, H = img.size
    ow, oh = int(W * 1.2), int(H * 2.1)
    src = to_arr(img)
    xs, ys = meshgrid(ow, oh)
    sy = ys - amp * H * np.sin(2 * np.pi * cycles * xs / ow)
    sx = xs - W * 0.1
    return remap(src, ow, oh, sx, sy)


def _warp_fisheye(img, p=1.75):
    """中心放大外缘压缩"""
    W, H = img.size
    S = int(max(W, H) * 1.4)
    src = to_arr(img)
    xs, ys = meshgrid(S, S)
    dx, dy = xs - S / 2, ys - S / 2
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx)
    R = max(W, H) * 0.55
    scale = np.where(r < R, (r / R) ** p * R, r)
    sx = W / 2 + scale * np.cos(theta)
    sy = H / 2 + scale * np.sin(theta)
    return remap(src, S, S, sx, sy)


def _stack_copies(img, n, rot_deg, scale, canvas_mult=2.4,
                  x_squeeze=1.0, drift=(0.0, 0.0)):
    """Transform 效果: n 份复制, 第 i 份 = 原图缩放 scale^i + 旋转 rot_deg*i,
    围绕中心独立叠加 (不累积变换); drift 为每份漂移量 (占文字尺寸比例)"""
    base = img
    bw, bh = base.size
    S = int(max(img.size) * canvas_mult)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for i in range(n):
        s = scale ** i
        cur = base.resize((max(int(bw * s), 1), max(int(bh * s), 1)),
                          Image.LANCZOS)
        if x_squeeze != 1.0:
            cur = cur.resize((max(int(cur.width * x_squeeze), 1),
                              cur.height), Image.LANCZOS)
        if i > 0:
            cur = cur.rotate(rot_deg * i, expand=True, resample=Image.BICUBIC)
        # 旋转 expand 后可能超出画布, 等比缩回
        m = max(cur.width, cur.height)
        if m > S * 0.92:
            r = S * 0.92 / m
            cur = cur.resize((max(int(cur.width * r), 1),
                              max(int(cur.height * r), 1)), Image.LANCZOS)
        px = int(S / 2 - cur.width / 2 + i * drift[0] * bw)
        py = int(S / 2 - cur.height / 2 + i * drift[1] * bh)
        canvas.alpha_composite(cur, (px, py))
    return crop_alpha(canvas)


def _blend_cascade(img, steps, warp_fn, gap=0.35):
    """混合工具>指定步数: 从原状到变形插值出 steps 个中间态, 纵向排开"""
    n = steps + 2                      # 含首尾两个原始对象
    frames = [warp_fn(img, i / (n - 1)) for i in range(n)]
    w = max(f.width for f in frames)
    h = sum(int(f.height * (1 + gap)) for f in frames)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for f in frames:
        out.alpha_composite(f, (int((w - f.width) / 2), y))
        y += int(f.height * (1 + gap))
    return crop_alpha(out)


def _warp_wave_vert(img, amp_frac=0.8, row_h=None):
    """Warp>Wave 垂直方向: 基线沿横向正弦起伏, amp_frac 为弯曲度(相对行高)"""
    W, H = img.size
    rh = row_h or H
    src = to_arr(img)
    ow, oh = int(W * 1.2), int(H * 2.0)
    xs, ys = meshgrid(ow, oh)
    amp = amp_frac * rh
    sy = ys - (oh - H) / 2 - amp * np.sin(2 * np.pi * xs / ow)
    sx = xs - (ow - W) / 2
    return remap(src, ow, oh, sx, sy)


def _square_frame(img, per_edge=1, Lf=1.05, fill=None):
    """文字沿正方形四边排布成方框; 参考图每边仅一个完整词.
    fill: 填色(遮挡用); None=用底色. 透明底传黑色, 之后抠黑成透明"""
    sq = _outline_text(_fit_aspect(img, 3.2), stroke=3,
                       fill=_bg_rgb(img) if fill is None else fill)
    W, H = sq.size
    L = int(W * Lf)
    slot = L / per_edge
    s = slot * 0.92 / W
    tile = sq.resize((max(int(W * s), 1), max(int(H * s), 1)), Image.LANCZOS)
    tw, th = tile.size
    t90 = tile.rotate(90, expand=True, resample=Image.BICUBIC)
    t180 = tile.rotate(180, expand=True, resample=Image.BICUBIC)
    t270 = tile.rotate(-90, expand=True, resample=Image.BICUBIC)
    frame = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    for k in range(per_edge):
        pos = int(k * slot + (slot - tw) / 2)
        frame.alpha_composite(tile, (pos, 0))
        frame.alpha_composite(t180, (pos, L - th))
        frame.alpha_composite(t270, (L - th, pos))
        frame.alpha_composite(t90, (0, pos))
    return frame


def fx_ring(img, rows=4, copies=None, scale=None, ang=3.0):
    """05 环形旋转: 文字方框做嵌套, 每份缩放95%+旋转3° (Transform).
    透明底 = 同一管线(黑填充互遮挡)渲染后抠黑成透明"""
    copies = 20 if copies is None else copies
    scale = 0.95 if scale is None else scale
    frame = _square_frame(img, fill=(0, 0, 0) if STYLE["transparent"] else None)
    L = frame.width
    D = int(L * 1.3)
    canvas = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    for i in reversed(range(copies)):
        s = scale ** i
        f = frame.resize((max(int(L * s), 1), max(int(L * s), 1)),
                         Image.LANCZOS)
        f = f.rotate(ang * i, expand=True, resample=Image.BICUBIC)
        canvas.alpha_composite(f, ((D - f.width) // 2, (D - f.height) // 2))
    if STYLE["transparent"]:
        return crop_alpha(_key_out_bg(canvas))
    return crop_alpha(canvas)


def fx_spiral(img, rows=4, copies=None, scale=None, ang=None):
    """06 旋转重复: Effect>Transform, 围绕文字中心缩放97%+旋转10°, 复制25份.
    透明底 = 同一条管线(黑填充互遮挡)渲染后把黑底抠成透明, 结构与黑底版完全一致"""
    copies = 25 if copies is None else copies
    scale = 0.97 if scale is None else scale
    ang = 10.0 if ang is None else ang
    # 透明底用纯黑填充做遮挡, 最后抠黑成透明; 实体底用底色填充融入背景
    fill = (0, 0, 0) if STYLE["transparent"] else _bg_rgb(img)
    sq = _outline_text(_fit_aspect(img, 4.4), stroke=3, fill=fill)
    W, H = sq.size
    S = int(max(W, H) * 1.9)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 逆序绘制, 最外层原字最后压上, 与参考图一致
    for i in reversed(range(copies)):
        s = scale ** i
        cur = sq.resize((max(int(W * s), 1), max(int(H * s), 1)),
                        Image.LANCZOS)
        cur = cur.rotate(-35.0 + ang * i, expand=True, resample=Image.BICUBIC)
        canvas.alpha_composite(cur, ((S - cur.width) // 2,
                                     (S - cur.height) // 2))
    if STYLE["transparent"]:
        return crop_alpha(_key_out_bg(canvas))
    return crop_alpha(canvas)


def fx_circular(img, copies=8, squeeze=0.75, ang=24.0, repeats=4, rows=None):
    """07 圆形文字环绕: 文字沿圆周连续弯曲, 再横向75%+旋转24°复制8份.
    透明底 = 按黑底管线(黑环带+黑描边)渲染后抠黑成透明"""
    key_out = STYLE["transparent"]
    saved = dict(STYLE)
    if key_out:                     # 临时切到黑底管线渲染, 结束再抠黑
        STYLE["transparent"] = False
        STYLE["bg"] = (0, 0, 0)
    try:
        D = 1600
        W, H = img.size
        src = to_arr(img)
        xs, ys = meshgrid(D, D)
        dx, dy = xs - D / 2, ys - D / 2
        theta = (np.arctan2(dx, -dy) + 2 * math.pi) % (2 * math.pi)
        r = np.sqrt(dx * dx + dy * dy)
        R, band = D * 0.42, D * 0.12
        u = ((theta / (2 * math.pi) * repeats) % 1.0) * 0.96
        v = ((R + band / 2) - r) / band   # 源图顶部朝外, 字头沿圆周向外, 避免镜像
        ring = remap(src, D, D, u * (W - 1), v * (H - 1))
        arr = np.asarray(ring).copy()
        arr[:, :, 3] = np.where((r >= R - band / 2) & (r <= R + band / 2),
                                arr[:, :, 3], 0)
        ring = _solid_stroke_text(Image.fromarray(arr, "RGBA"), outline=5, grow=5)
        band_mask = Image.new("L", (D, D), 0)
        bd = ImageDraw.Draw(band_mask)
        bd.ellipse([D / 2 - R - band / 2, D / 2 - R - band / 2,
                    D / 2 + R + band / 2, D / 2 + R + band / 2], fill=255)
        bd.ellipse([D / 2 - R + band / 2, D / 2 - R + band / 2,
                    D / 2 + R - band / 2, D / 2 + R - band / 2], fill=0)
        backing = Image.new("RGBA", (D, D), _bg_rgb(img) + (255,))
        backing.putalpha(band_mask)
        ring = Image.alpha_composite(backing, ring)
        canvas = Image.new("RGBA", (D, D), (0, 0, 0, 0))
        for i in reversed(range(copies)):
            s = squeeze ** i
            cur = ring.resize((max(2, int(D * s)), D), Image.LANCZOS)
            cur = cur.rotate(ang * i, expand=True, resample=Image.BICUBIC)
            canvas.alpha_composite(cur, ((D - cur.width) // 2,
                                         (D - cur.height) // 2))
    finally:
        STYLE.clear()
        STYLE.update(saved)
    if key_out:
        return crop_alpha(_key_out_bg(canvas))
    return crop_alpha(canvas)


def _phase_wave(img, phase, amp=0.22):
    W, H = img.size
    out = Image.new("RGBA", (int(W * 1.25), int(H * 1.7)), (0, 0, 0, 0))
    src = to_arr(img)
    xs, ys = meshgrid(out.width, out.height)
    sy = ys - amp * H * np.sin(2 * np.pi * (xs / out.width) + phase)
    sx = xs - W * 0.12
    return remap(src, out.width, out.height, sx, sy)


def fx_waveblend(img, rows=24, steps=3, bend=0.80):
    """08 波浪混合: 顶行原字, 下方23条薄波浪带横向错位交织."""
    W, H = img.size
    base = img.info.get("bg", "#E03A2F")
    top_src = img.resize((W, int(H * 0.55)), Image.LANCZOS)
    top_src.info["bg"] = base
    top = _solid_stroke_text(top_src, 3)
    amp = H * 0.14
    oh = int(H + 2 * amp + 6)
    src = to_arr(img)
    frames = [top]
    for k in range(1, 24):
        xs, ys = meshgrid(W, oh)
        wave = np.sin(2 * math.pi * 2.2 * xs / max(W - 1, 1) + k * 0.8)
        sy = ys - (oh - H) / 2 - amp * wave
        frame = crop_alpha(remap(src, W, oh, xs, sy), pad=2)
        frame = frame.resize((W, int(H * 0.18)), Image.LANCZOS)
        frame.info["bg"] = base
        frames.append(_solid_stroke_text(frame, 3))
    pos = [0]
    y = int(H * 0.55)
    for _ in range(1, 24):
        pos.append(y)
        y += int(H * 0.15)
    total = pos[-1] + frames[-1].height
    out = Image.new("RGBA", (W, total), (0, 0, 0, 0))
    out.alpha_composite(frames[0], (0, 0))
    for k in range(1, 24):
        dx = int(W * 0.22 * math.sin(k * 0.9))
        for sx in (dx - W, dx, dx + W):
            out.alpha_composite(frames[k], (sx, pos[k]))
    return crop_alpha(out)


def _shear(img, k):
    W, H = img.size
    src = to_arr(img)
    ow, oh = int(W + abs(k) * H) + 4, H
    xs, ys = meshgrid(ow, oh)
    sx = (xs - (ow - W) / 2) - k * (ys - H / 2)
    return remap(src, ow, oh, sx, ys)


def fx_freeblend(img, rows=5, steps=3, k=0.95):
    """09 自由变形混合: 5行逐步增加斜切并压缩高度, 对应指定步数3."""
    def distort(im, t):
        frame = _shear(im, k * t)
        nh = max(2, int(im.height * (1.0 - 0.62 * t)))
        nw = max(2, int(frame.width * (1.0 - 0.18 * t)))
        return frame.resize((nw, nh), Image.LANCZOS)
    return _blend_cascade(img, steps, distort, gap=0.02)


def _wall_trap(img, inner, persp=0.38):
    """透视墙: inner 指定的边向内收窄"""
    W, H = img.size
    src = to_arr(img)
    xs, ys = meshgrid(W, H)
    if inner == 'bottom':
        s = 1 - (1 - persp) * (ys / H)
    elif inner == 'top':
        s = persp + (1 - persp) * (ys / H)
    elif inner == 'right':
        s = 1 - (1 - persp) * (xs / W)
    else:
        s = persp + (1 - persp) * (xs / W)
    x_src = W / 2 + (xs - W / 2) / s
    y_src = H / 2 + (ys - H / 2) / s
    return remap(src, W, H, x_src, y_src)


def _perspective_wall(img, width, height, inner=0.20, power=1.8):
    """多行文字映射成外宽内窄的透视墙; 行距向消失点指数压缩."""
    W, H = img.size
    src = to_arr(img)
    xs, ys = meshgrid(width, height)
    t = ys / max(height - 1, 1)
    half = width * 0.5 * (1.0 - (1.0 - inner) * t)
    sx = W / 2 + (xs - width / 2) * W / (2 * half)
    v = 1.0 - (1.0 - t) ** (1.0 / power)
    sy = v * (H - 1)
    return remap(src, width, height, sx, sy)


def fx_tunnel(img, persp=0.20, rows=8, power=1.8):
    """03 透视空间: 多行文字透视墙复制3次, 围成方形走廊与中心方孔."""
    rows = max(1, int(rows))
    block = _block(img, rows, gap=0.03)
    D = int(block.width * 1.18)
    wall_h = int(D * 0.40)
    top = _perspective_wall(block, D, wall_h, inner=persp, power=power)
    canvas = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    canvas.alpha_composite(top, (0, 0))
    bottom = top.rotate(180, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(bottom, (0, D - wall_h))
    left = top.rotate(90, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(left, (0, 0))
    right = top.rotate(-90, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(right, (D - wall_h, 0))
    return crop_alpha(canvas)


def fx_sphereline(img, rows=6, steps=4):
    """11 球体文字: 镜像双词压成透镜条, 6行渐薄后上下镜像 (Blend Steps 4)."""
    W, H = img.size
    bw = int(W * 1.75)
    band = Image.new("RGBA", (bw, H), (0, 0, 0, 0))
    band.alpha_composite(img, (0, 0))
    band.alpha_composite(img.transpose(Image.FLIP_LEFT_RIGHT),
                         (int(W * 0.75), 0))
    band.info["bg"] = img.info.get("bg", "#E03A2F")
    band = _solid_stroke_text(band, outline=4)
    src = to_arr(band)
    xs, ys = meshgrid(bw, H)
    q = np.clip(np.sin(math.pi * xs / max(bw - 1, 1)), 0, 1) ** 0.7
    scale = 0.08 + 0.92 * q
    sy = H / 2 + (ys - H / 2) / scale
    row_img = remap(src, bw, H, xs, sy)

    rows = 6 if rows <= 4 else rows
    frames = []
    for i in range(rows):
        nh = max(8, int(H * (1.0 - 0.68 * i / (rows - 1))))
        frames.append(row_img.resize((bw, nh), Image.LANCZOS))
    step = [max(4, int(f.height * 1.22)) for f in frames]
    top_h = sum(step[:-1]) + frames[-1].height + 8
    top = Image.new("RGBA", (bw, top_h), (0, 0, 0, 0))
    y = 0
    for f, dy in zip(frames, step):
        sh = np.asarray(f).copy()
        sh[:, :, 0], sh[:, :, 1], sh[:, :, 2] = 105, 24, 20
        sh[:, :, 3] = (sh[:, :, 3] * 0.55).astype(np.uint8)
        shadow = Image.fromarray(sh, "RGBA")
        top.alpha_composite(shadow, (5, y + 7))
        top.alpha_composite(f, (0, y))
        y += dy
    bottom = top.transpose(Image.FLIP_TOP_BOTTOM)
    seam = int(top_h * 0.99)
    out = Image.new("RGBA", (bw, seam + bottom.height), (0, 0, 0, 0))
    out.alpha_composite(top, (0, 0))
    out.alpha_composite(bottom, (0, seam))
    out = crop_alpha(out)
    # 超椭圆球面: 上下行向中心弯, 四角收圆
    W2, H2 = out.size
    src2 = to_arr(out)
    xs2, ys2 = meshgrid(W2, H2)
    u = (xs2 - W2 / 2) / (W2 / 2)
    v = (ys2 - H2 / 2) / (H2 / 2)
    p = 4.0
    chord = np.maximum(1 - np.abs(v) ** p, 1e-4) ** (1 / p)
    sx2 = (u / chord * 0.5 + 0.5) * (W2 - 1)
    sy2 = (v * 0.5 + 0.5) * (H2 - 1)
    ball = remap(src2, W2, H2, sx2, sy2)
    arr = np.asarray(ball).copy()
    inside = (np.abs(u) ** p + np.abs(v) ** p) <= 1.0
    arr[:, :, 3] = np.where(inside, arr[:, :, 3], 0)
    shade = 0.80 + 0.20 * np.abs(v)[..., None]
    arr[:, :, :3] = np.clip(arr[:, :, :3] * shade, 0, 255)
    return Image.fromarray(arr, "RGBA")


def fx_envelope(img, repeat=1, rows=12):
    """12 封套半球: 多行文字作为纬线, 按圆形截弦宽度映射成球体."""
    block = fx_sphereline(img, rows=16, steps=4, cols=8)
    W, H = block.size
    R = max(W, H) * 0.56
    D = int(R * 2.12)
    src = to_arr(block)
    xs, ys = meshgrid(D, D)
    dx = (xs - D / 2) / R
    dy = (ys - D / 2) / R
    rr = dx * dx + dy * dy
    inside = rr <= 1.0
    lat = np.clip(dy, -0.995, 0.995)
    chord = np.sqrt(np.clip(1 - lat * lat, 1e-4, 1.0))
    u = np.clip(0.5 + dx / (2 * chord), 0.0, 1.0)
    # 靠近两极时压缩行距, 形成封套球面的纵向曲率
    v = 0.5 + 0.5 * np.sign(lat) * np.abs(lat) ** 0.88
    sx = u * (W - 1)
    sy = v * (H - 1)
    out = remap(src, D, D, sx, sy)
    arr = np.asarray(out).copy()
    arr[~inside] = 0
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------- 轮廓填充
import random


def make_mask(shape, size=1200):
    """生成或加载轮廓掩膜, 返回 L 模式图 (255=形状内部)"""
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    if shape == "square":
        pad = int(size * 0.08)
        d.rectangle([pad, pad, size - pad, size - pad], fill=255)
    elif shape == "circle":
        pad = int(size * 0.06)
        d.ellipse([pad, pad, size - pad, size - pad], fill=255)
    elif shape == "triangle":
        pad = int(size * 0.08)
        d.polygon([(size / 2, pad), (size - pad, size - pad),
                   (pad, size - pad)], fill=255)
    elif shape == "star":
        cx = cy = size / 2
        R, r = size * 0.46, size * 0.20
        pts = []
        for i in range(10):
            rad = R if i % 2 == 0 else r
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        d.polygon(pts, fill=255)
    elif shape == "heart":
        pts = []
        cx, cy = size / 2, size * 0.44
        s = size * 0.027
        for i in range(200):
            t = i / 199 * 2 * math.pi
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) \
                - math.cos(4 * t)
            pts.append((cx + x * s, cy - y * s))
        d.polygon(pts, fill=255)
    elif os.path.exists(shape):
        src = Image.open(shape).convert("RGBA")
        src.thumbnail((size, size))
        arr = np.asarray(src)
        alpha = arr[:, :, 3]
        # 灰度/白底轮廓图: alpha 全 255 时改用亮度当掩膜
        if alpha.max() - alpha.min() < 10:
            alpha = arr[:, :, :3].mean(axis=2)
        # 白底深色图自动反相, 保证形状为高亮区域
        if alpha.mean() > 127:
            alpha = 255 - alpha
        m = Image.fromarray(np.where(alpha > 100, 255, 0).astype(np.uint8), "L")
    else:
        raise ValueError(f"未知轮廓: {shape} (支持 square/circle/triangle/star/heart 或轮廓图路径)")
    return m


def fx_fill(img, mask, rows=None, gap=0.10):
    """把文字逐行缩放平铺, 填充进任意轮廓掩膜"""
    W, H = img.size
    mw, mh = mask.size
    marr = np.asarray(mask) > 0
    if rows is None:
        rows = int(np.clip(mh / (H * 0.85), 3, 14))
    band = mh / rows
    out = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
    for j in range(rows):
        y0, y1 = int(j * band), int((j + 1) * band)
        if y1 <= y0 or y0 >= mh:
            continue
        band_mask = marr[y0:min(y1, mh)]
        xs = np.where(band_mask.any(axis=0))[0]
        if len(xs) == 0:
            continue
        x_left, x_right = xs.min(), xs.max()
        row_w = x_right - x_left + 1
        rh = max(int(band * (1 - gap)), 2)
        tile = img.resize((max(int(W * rh / H), 1), rh), Image.LANCZOS)
        # 从轮廓中心向两侧平铺, 保证水平居中
        cx = (x_left + x_right) / 2
        n_total = int(np.ceil(row_w / (tile.width * 0.99))) + 1
        start = cx - n_total * tile.width / 2
        for k in range(n_total):
            px = int(start + k * tile.width * 0.99)
            if px + tile.width < 0 or px > mw:
                continue
            out.alpha_composite(tile, (px, y0 + int((band - rh) / 2)))
    # 用轮廓裁剪
    out_arr = np.asarray(out).copy()
    out_arr[:, :, 3] = np.where(marr, out_arr[:, :, 3], 0)
    return Image.fromarray(out_arr, "RGBA")


def fill_text(text, shape="circle", rows=None, font_path=None, size=240,
              fg="#FFFFFF", mask_path=None):
    """轮廓填充总入口: 渲染文字 -> 生成/加载掩膜 -> 填充"""
    base = render_text(text, font_path, size, fg)
    mask = make_mask(mask_path or shape)
    return fx_fill(base, mask, rows)


# ---------------------------------------------------------------- 合成辅助
def _fill_block(img, shape="square", rows=6):
    """把文字填进指定轮廓, 生成大块填充素材 (供变形效果合成用)"""
    size = int(max(img.size) * 3.2)
    mask = make_mask(shape, size)
    return fx_fill(img, mask, rows)


def _clip_shape(img, shape):
    """按轮廓裁剪 (掩膜外透明)"""
    m = make_mask(shape, max(img.size)).resize(img.size)
    marr = np.asarray(m) > 0
    arr = np.asarray(img).copy()
    arr[:, :, 3] = np.where(marr, arr[:, :, 3], 0)
    return Image.fromarray(arr, "RGBA")


def _squash(img, max_aspect=2.6):
    """过宽的文字水平压缩到指定长宽比 (参考图 7 的'水平缩放'手法)"""
    W, H = img.size
    if W / H <= max_aspect:
        return img
    return img.resize((max(int(H * max_aspect), 1), H), Image.LANCZOS)


def _fit_aspect(img, target):
    """文字条长宽比强制适配到 target: 过宽压缩, 过窄拉伸.
    保证任意语言/任意长度的文字进效果前规格一致 (字距/长宽自动调节)"""
    W, H = img.size
    a = W / H
    if abs(a - target) < 0.05:
        return img
    return img.resize((max(int(H * target), 1), H), Image.LANCZOS)


def _block(img, rows=4, gap=0.10):
    """文字原尺寸纵向堆叠 rows 行, 形成方块基底 (参考图 1-4/8-10 的基底)"""
    W, H = img.size
    step = int(H * (1 + gap))
    out = Image.new("RGBA", (W, step * rows), (0, 0, 0, 0))
    for i in range(rows):
        out.alpha_composite(img, (0, i * step))
    return out


# ---------------------------------------------------------------- 12 种效果(对齐参考图)
def fx_twist(img, rows=5, amp=32.0):
    """01 扭曲旋转: Warp>Twist 垂直 Bend100. 左端0度到右端最大角的连续扭转场."""
    rows = 5 if rows <= 4 else rows
    W, H = img.size
    gap = int(H * 0.04)
    block = Image.new("RGBA", (W, H * rows + gap * (rows - 1)), (0, 0, 0, 0))
    for i in range(rows):
        block.alpha_composite(img, (0, i * (H + gap)))
    bw, bh = block.size
    ow, oh = int(W * 1.18), int(bh * 1.20)
    off_x, off_y = (ow - bw) / 2, (oh - bh) / 2
    xs, ys = meshgrid(ow, oh)
    cx, cy = off_x + bw / 2, off_y + bh / 2
    dx, dy = xs - cx, ys - cy
    u = np.clip((xs - off_x) / max(bw - 1, 1), 0.0, 1.0)
    a = np.radians(amp) * u
    ct, st = np.cos(a), np.sin(a)
    sx = cx + dx * ct + dy * st
    sy = cy - dx * st + dy * ct
    return remap(to_arr(block), ow, oh, sx, sy)


def fx_banana(img, rows=4, amp=0.45):
    """02 香蕉波浪: 方块整体同相 S 形波浪 (Warp>Wave 弯曲方向: 垂直)"""
    block = _block(img, rows)
    W, H = block.size
    row_h = H / max(rows, 1)
    src = to_arr(block)
    ow, oh = int(W * 1.15), int(H * 1.6)
    xs, ys = meshgrid(ow, oh)
    sy = ys - (oh - H) / 2 - amp * row_h * np.sin(2 * np.pi * xs / ow)
    sx = xs - (ow - W) / 2
    return remap(src, ow, oh, sx, sy)


def fx_wavesh(img, rows=4, amp=0.32):
    """03 水平凹变: 方块整块中段下凹 (Warp>Wave 弯曲方向: 水平)"""
    block = _block(img, rows)
    W, H = block.size
    src = to_arr(block)
    ow, oh = int(W * 1.1), int(H * 1.55)
    xs, ys = meshgrid(ow, oh)
    u = xs / ow
    sy = ys - (oh - H) / 2 - amp * H * np.sin(math.pi * u)
    sx = xs - (ow - W) / 2
    return remap(src, ow, oh, sx, sy)


def fx_fisheye(img, rows=5, p=1.65):
    """08 鱼眼透视: 5行凸透镜 + 6°上斜 + 投影厚度."""
    rows = 5 if rows <= 4 else rows
    W, H = img.size
    gap = int(H * 0.10)
    block = Image.new("RGBA", (W, H * rows + gap * (rows - 1)), (0, 0, 0, 0))
    for i in range(rows):
        block.alpha_composite(img, (0, i * (H + gap)))
    bw, bh = block.size
    src = to_arr(block)
    xs, ys = meshgrid(bw, bh)
    cx, cy = bw * 0.45, bh * 0.50
    u = (xs - cx) / (bw * 0.5)
    v = (ys - cy) / (bh * 0.5)
    r = np.sqrt(u * u + v * v)
    fac = np.where(r < 1.0, np.maximum(r, 1e-6) ** (p - 1.0), 1.0)
    sx = cx + u * fac * (bw * 0.5)
    sy = cy + v * fac * (bh * 0.5)
    out = remap(src, bw, bh, sx, sy)
    out = out.rotate(6.0, expand=True, resample=Image.BICUBIC)
    out = _add_shadow(out, dx=10, dy=12)
    return crop_alpha(out)


def fx_wave_v(img, rows=5, amp=0.05, cycles=0.9):
    """04 垂直波浪: 5行原地纵向正弦弯曲 + 投影."""
    block = _block(img, 5, gap=0.05)
    W, H = block.size
    a = H * amp
    oh = int(H + 2 * a + 10)
    xs, ys = meshgrid(W, oh)
    sy = ys - (oh - H) / 2 - a * np.sin(2 * math.pi * cycles * xs / max(W - 1, 1))
    out = remap(to_arr(block), W, oh, xs, sy)
    return crop_alpha(_add_shadow(out))


def fx_wave_h(img, rows=5, amp=0.035, cycles=1.5):
    """05 水平波浪: 5行原地横向正弦错位 + 投影."""
    block = _block(img, 5, gap=0.05)
    W, H = block.size
    a = W * amp
    ow = int(W + 2 * a + 10)
    xs, ys = meshgrid(ow, H)
    sx = xs - (ow - W) / 2 - a * np.sin(2 * math.pi * cycles * ys / max(H - 1, 1))
    out = remap(to_arr(block), ow, H, sx, ys)
    return crop_alpha(_add_shadow(out))


def fx_flowline(img, rows=5, amp=0.38, step_ratio=1.18):
    """06 流线波纹: 5行完整文字沿同一条平滑正弦曲线流动."""
    W, H = img.size
    a = H * amp
    oh = int(H + 2 * a + 16)
    xs, ys = meshgrid(W, oh)
    sy = ys - (oh - H) / 2 - a * np.sin(2 * math.pi * 1.25 * xs / max(W - 1, 1))
    row = remap(to_arr(img), W, oh, xs, sy)
    row = _add_shadow(row, dx=8, dy=10)
    step = int(H * step_ratio)
    out = Image.new("RGBA", (row.width, step * 4 + row.height), (0, 0, 0, 0))
    for k in range(5):
        out.alpha_composite(row, (0, k * step))
    return crop_alpha(out)

FX_FUNCS = {
    "spiral": fx_spiral, "circular": fx_circular, "tunnel": fx_tunnel,
    "wave_v": fx_wave_v, "wave_h": fx_wave_h, "flowline": fx_flowline,
    "waveweave": fx_waveblend, "fisheye": fx_fisheye, "ring": fx_ring,
}

# ---------------------------------------------------------------- 输出
def parse_color(s):
    if s.lower() == "transparent":
        return (0, 0, 0, 0)
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def fit_into(img, box_w, box_h):
    s = min(box_w / img.width, box_h / img.height)
    return img.resize((max(int(img.width * s), 1), max(int(img.height * s), 1)),
                      Image.LANCZOS)


def make_cell(effect_rgba, caption, bg, fg, cell=920, content_h=700,
              caption_font=None):
    cellimg = Image.new("RGBA", (cell, cell), bg)
    eff = fit_into(effect_rgba, int(cell * 0.86), content_h)
    cellimg.alpha_composite(eff, (int((cell - eff.width) / 2),
                                  int((content_h - eff.height) / 2) + 20))
    d = ImageDraw.Draw(cellimg)
    if caption_font is None:
        caption_font = pick_font(caption, 46)
    bbox = d.textbbox((0, 0), caption, font=caption_font)
    tw = bbox[2] - bbox[0]
    ty = content_h + (cell - content_h) // 2 - (bbox[3] - bbox[1]) // 2
    d.text(((cell - tw) / 2, ty), caption, font=caption_font, fill=fg)
    return cellimg


def _default_rows(key, text):
    if key == "tunnel":
        return 8
    return 1 if "\n" in text else 4


def make_grid(text, out_path, bg_hex="#E03A2F", fg_hex="#FFFFFF",
              font_path=None, size=240, cell=920):
    bg, fg = parse_color(bg_hex), parse_color(fg_hex)
    set_style(bg_hex, fg_hex)
    base = render_text(text, font_path, size, fg_hex)
    base.info["bg"] = bg_hex
    caption_font = pick_font("01 旋转重复", 46)
    n_rows = 1 if "\n" in text else 4     # 多行文本(如诗句)直接作基底
    cols, rows = 3, 3
    grid = Image.new("RGBA", (cell * cols, cell * rows), bg)
    for idx, (key, caption) in enumerate(EFFECTS):
        eff = FX_FUNCS[key](base, rows=_default_rows(key, text))
        c = make_cell(eff, caption, bg, fg, cell, int(cell * 0.76), caption_font)
        grid.alpha_composite(c, ((idx % cols) * cell, (idx // cols) * cell))
        print(f"  [{idx+1}/9] {key} done")
    grid.convert("RGB").save(out_path, quality=92)
    return out_path


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="wordshape text",
                                 description="功能一: 文字复制与变形")
    ap.add_argument("text", nargs="?", help="要变形的文字 (支持 \\n 多行)")
    ap.add_argument("outdir", nargs="?", help="输出目录")
    ap.add_argument("--effect", help="单个效果名, 见 --list")
    ap.add_argument("--fill", help="轮廓填充: square/circle/triangle/star/heart 或轮廓图 PNG 路径")
    ap.add_argument("--rows", type=int, default=None,
                    help="覆盖效果行数（如透视空间 6 行）/ 填充行数")
    ap.add_argument("--out", help="单效果输出文件路径")
    ap.add_argument("--grid", help="9 格合集输出路径")
    ap.add_argument("--mode",
                    choices=["tr", "red", "white", "black", "bw", "wb",
                             "br", "navy", "custom"],
                    default=None,
                    help="tr=透明底红字(默认); red=红底白字; white=透明白字; black=透明黑字; bw=白底黑字; wb=黑底白字; br=黑底红字; navy=藏青底青字; custom=用--bg/--fg自定义")
    ap.add_argument("--bg", default=None)
    ap.add_argument("--fg", default=None)
    ap.add_argument("--font", default=None)
    ap.add_argument("--size", type=int, default=240)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for k, c in EFFECTS:
            print(f"{k:12s} {c}")
        return
    if not args.text or not args.outdir:
        ap.error("需要 text 与 outdir (或使用 --list)")
    global _CUR_TEXT
    _CUR_TEXT = args.text

    mode_map = {
        "tr": ("transparent", "#E03A2F"),
        "red": ("#E03A2F", "#FFFFFF"),
        "white": ("transparent", "#FFFFFF"),
        "black": ("transparent", "#000000"),
        "bw": ("#FFFFFF", "#111111"),
        "wb": ("#111111", "#FFFFFF"),
        "br": ("#111111", "#E03A2F"),
        "navy": ("#0A1F33", "#4FE0E6"),
    }
    if args.mode == "custom":
        if not args.bg or not args.fg:
            ap.error("--mode custom 需要同时提供 --bg 和 --fg，例如：--bg \"#0A1F33\" --fg \"#4FE0E6\"")
        bg_hex, fg_hex = args.bg, args.fg
    elif args.mode:
        bg_hex, fg_hex = mode_map[args.mode]
    else:
        # 本 Skill 默认：透明底红字
        bg_hex = args.bg or "transparent"
        fg_hex = args.fg or "#E03A2F"
    set_style(bg_hex, fg_hex)

    os.makedirs(args.outdir, exist_ok=True)
    if args.grid:
        grid_bg = "#E03A2F" if bg_hex.lower() == "transparent" else bg_hex
        grid_fg = "#FFFFFF" if bg_hex.lower() == "transparent" else fg_hex
        p = make_grid(args.text, args.grid, grid_bg, grid_fg,
                      args.font, args.size)
        print("GRID ->", p)
    if args.fill:
        eff = fill_text(args.text, shape="circle", rows=args.rows,
                        font_path=args.font, size=args.size, fg=fg_hex,
                        mask_path=args.fill)
        out = args.out or os.path.join(args.outdir, f"fill_{os.path.basename(args.fill)}.png")
        if bg_hex.lower() == "transparent":
            eff.save(out)
        else:
            cell = Image.new("RGBA", eff.size, parse_color(bg_hex))
            cell.alpha_composite(eff)
            cell.convert("RGB").save(out, quality=92)
        print("FILL ->", out)
    if args.effect:
        if args.effect not in FX_FUNCS:
            sys.exit(f"未知效果: {args.effect}; 用 --list 查看")
        base = render_text(args.text, args.font, args.size, fg_hex)
        base.info["bg"] = bg_hex
        row_override = (args.rows if args.rows is not None
                        else _default_rows(args.effect, args.text))
        eff = crop_alpha(FX_FUNCS[args.effect](base, rows=row_override))
        out = args.out or os.path.join(args.outdir, f"{args.effect}.png")
        if bg_hex.lower() == "transparent":
            eff.save(out)
        else:
            cell = Image.new("RGBA", eff.size, parse_color(bg_hex))
            cell.alpha_composite(eff)
            cell.convert("RGB").save(out, quality=92)
        print("EFFECT ->", out)


if __name__ == "__main__":
    main()
