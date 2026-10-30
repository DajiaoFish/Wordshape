"""主体剪影文字填充: 提取主体轮廓, 用文字填满, 默认红字透明底."""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageColor

# 复用功能一的文字渲染与轮廓填充 (同包内相对导入)
try:
    from . import textfx as tf
except ImportError:                     # 直接以脚本方式运行时的兜底
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import textfx as tf


def load_mask(image, mask_path=None, threshold=36):
    """优先 alpha / 外部蒙版; 否则按纯色背景做分割."""
    if mask_path:
        m = Image.open(mask_path)
        if m.mode == "RGBA":
            m = m.getchannel("A")
        else:
            m = m.convert("L")
        m = m.resize(image.size, Image.LANCZOS)
        return (np.asarray(m) > 127).astype(np.uint8) * 255

    if image.mode == "RGBA":
        a = np.asarray(image.getchannel("A"))
        if a.min() < 250:
            return (a > 12).astype(np.uint8) * 255

    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32)
    h, w = arr.shape[:2]
    border = np.concatenate([
        arr[:max(3, h // 40)].reshape(-1, 3),
        arr[-max(3, h // 40):].reshape(-1, 3),
        arr[:, :max(3, w // 40)].reshape(-1, 3),
        arr[:, -max(3, w // 40):].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    mask = (dist > threshold).astype(np.uint8) * 255
    m = Image.fromarray(mask, "L")
    m = m.filter(ImageFilter.MedianFilter(5))
    # 开运算去掉截图细线/毛刺, 再闭合补回主体边缘（核取小, 保住胡须/耳尖）
    m = m.filter(ImageFilter.MinFilter(3))
    m = m.filter(ImageFilter.MaxFilter(3))
    marr = np.asarray(m).copy()
    # 只清掉贴边的截图白线/噪点(固定窄带), 主体贴边时不误伤
    b = 2
    marr[:b, :] = 0
    marr[-b:, :] = 0
    marr[:, :b] = 0
    marr[:, -b:] = 0
    marr = largest_component(marr)
    cover = (marr > 0).mean()
    if cover < 0.01 or cover > 0.95:
        raise ValueError(
            "背景不是纯色或主体占比异常; 请提供已抠好的透明 PNG，或用 --mask 给蒙版")
    return marr


def largest_component(mask, min_area=24, near=20):
    """保留最大连通域, 以及贴在主域附近的小块(断开的胡须/发丝/耳尖)."""
    m = (mask > 0).astype(np.uint8)
    h, w = m.shape
    seen = np.zeros_like(m, dtype=bool)
    comps = []
    for yy in range(h):
        for xx in range(w):
            if m[yy, xx] == 0 or seen[yy, xx]:
                continue
            stack = [(yy, xx)]
            seen[yy, xx] = True
            comp = []
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            comps.append(comp)
    if not comps:
        return np.zeros_like(m, dtype=np.uint8)
    comps.sort(key=len, reverse=True)
    keep = list(comps[0])

    # 主域向外膨胀 near 像素, 落在其中的小块(细须/发丝)一并保留
    main = np.zeros_like(m, dtype=np.uint8)
    ys = np.array([p[0] for p in comps[0]])
    xs = np.array([p[1] for p in comps[0]])
    main[ys, xs] = 255
    k = max(3, near * 2 + 1)
    near_mask = np.asarray(
        Image.fromarray(main).filter(ImageFilter.MaxFilter(k))) > 0
    for comp in comps[1:]:
        if len(comp) < min_area:
            continue
        cy = np.array([p[0] for p in comp])
        cx = np.array([p[1] for p in comp])
        if near_mask[cy, cx].any():
            keep.extend(comp)

    out = np.zeros_like(m, dtype=np.uint8)
    ky = np.array([p[0] for p in keep])
    kx = np.array([p[1] for p in keep])
    out[ky, kx] = 255
    return out


def bbox(mask, pad=4):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise ValueError("主体蒙版为空")
    h, w = mask.shape
    return (max(0, xs.min() - pad), max(0, ys.min() - pad),
            min(w, xs.max() + pad + 1), min(h, ys.max() + pad + 1))


def fill_thin_details(arr, marr, fill, font_size):
    """细到写不下字的部位(胡须/发丝/尖角)直接填色补形, 只补空白处."""
    # 核取字号 1/3: 比它细的结构(胡须/发丝)开运算后消失 -> 进 thin
    k = max(9, int(font_size / 3))
    if k % 2 == 0:
        k += 1
    m = Image.fromarray((marr * 255).astype(np.uint8))
    opened = np.asarray(
        m.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))) > 0
    thin = marr & ~opened          # 比 k 还细的线状/尖状部位
    blank = arr[:, :, 3] == 0      # 不覆盖已有文字
    sel = thin & blank
    if not sel.any():
        return arr
    arr[sel, 0] = fill[0]
    arr[sel, 1] = fill[1]
    arr[sel, 2] = fill[2]
    arr[sel, 3] = 255
    return arr


def fill_inner_dark_lines(arr, image, marr, fill, font_size, thr=45):
    """主体内部的深色细线(眼镜框/瞳孔/花纹线)直接涂色勾勒, 不被文字淹没.

    原理: 大核中值滤波求局部背景亮度, 比局部背景暗 thr 以上的细结构
    (细度用开运算核 = 字号 1/3 判定)即为需要勾勒的线条.
    """
    k = max(9, int(font_size / 3))
    if k % 2 == 0:
        k += 1
    lum_img = image.convert("L")
    lum = np.asarray(lum_img, dtype=np.uint8)
    bg = np.asarray(lum_img.filter(ImageFilter.MedianFilter(41)),
                    dtype=np.float32)
    dark = (lum < bg - thr) & marr
    if not dark.any():
        return arr
    d = Image.fromarray((dark * 255).astype(np.uint8))
    opened = np.asarray(
        d.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))) > 0
    lines = dark & ~opened
    if not lines.any():
        return arr
    # 去掉孤立碎斑: 只保留成形的线条(连通域 >= min_area 像素)
    lm = (lines * 255).astype(np.uint8)
    lm = _keep_large_components(lm, min_area=max(24, font_size * 2))
    lines = lm > 0
    if not lines.any():
        return arr
    arr[lines, 0] = fill[0]
    arr[lines, 1] = fill[1]
    arr[lines, 2] = fill[2]
    arr[lines, 3] = 255
    return arr


def _keep_large_components(mask_u8, min_area=30):
    """保留面积 >= min_area 的连通域(8邻域), 其余清零."""
    m = mask_u8 > 0
    h, w = m.shape
    seen = np.zeros_like(m, dtype=bool)
    out = np.zeros_like(mask_u8)
    for yy in range(h):
        for xx in range(w):
            if not m[yy, xx] or seen[yy, xx]:
                continue
            stack = [(yy, xx)]
            seen[yy, xx] = True
            comp = []
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and m[ny, nx]
                                and not seen[ny, nx]):
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            if len(comp) >= min_area:
                cy = [p[0] for p in comp]
                cx = [p[1] for p in comp]
                out[cy, cx] = 255
    return out


def _paste_glyph(out, ch, font, gx, gy, rot, fill):
    """把单个字符旋转 rot 弧度后贴到 (gx, gy) 中心."""
    bb = font.getbbox(ch)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if w <= 0 or h <= 0:
        return
    pad = 2
    g = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(g).text((pad - bb[0], pad - bb[1]), ch, font=font, fill=fill)
    g = g.rotate(-math.degrees(rot), expand=True, resample=Image.BICUBIC)
    out.alpha_composite(g, (int(gx - g.width / 2), int(gy - g.height / 2)))


def _radial_profile(marr, cx, cy, n=720):
    """从中心按角度射线, 求到主体边界的距离, 用于把正圆环换成轮廓环."""
    H, W = marr.shape
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    rmax = int(math.hypot(max(cx, W - cx), max(cy, H - cy))) + 1
    R = np.zeros(n, dtype=np.float32)
    for i, t in enumerate(th):
        ct, st = math.cos(t), math.sin(t)
        last = 0.0
        for k in range(rmax):
            x = int(cx + ct * k)
            y = int(cy + st * k)
            if x < 0 or y < 0 or x >= W or y >= H:
                break
            if marr[y, x]:
                last = float(k)
        R[i] = last
    return th, R


def draw_tunnel_rings(out, marr, box, text, fill, font_size, font_path,
                      hole=0.12):
    """透视空间(隧道·轮廓版): 每圈都是主体轮廓的等比缩小copy,
    字号与圈距随缩小比递减, 中心留出与主体同形的空洞 → 沿轮廓的纵深;
    字符沿轮廓切线旋转, 读序绕圈连续."""
    bx0, by0, bx1, by1 = box
    cx, cy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
    th, R = _radial_profile(marr, cx, cy)
    n = len(th)
    Rmax = float(R.max())
    if Rmax <= 1:
        return 0
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("文字不能为空")
    stream = clean * 600
    idx = 0
    f_out = max(10, int(font_size * 1.05))   # 外圈字号
    meas = ImageDraw.Draw(out)
    s = 0.985          # 圈的缩放比, 1 = 贴着轮廓
    prev_r = R * s     # 上一圈各角度的半径(用于最小圈距保护)
    rings = 0
    while s > hole and idx < len(stream):
        fs = max(6, int(f_out * s))
        font = tf.pick_font(text, fs, font_path)
        r = R * s
        # 最小圈距保护: 轮廓塌缩快的方向(胡须/下巴)按等距收缩, 避免字堆叠
        r = np.maximum(r, prev_r - fs * 1.5)
        prev_r = r
        xs = cx + r * np.cos(th)
        ys = cy + r * np.sin(th)
        seg = np.hypot(np.diff(np.r_[xs, xs[0]]), np.diff(np.r_[ys, ys[0]]))
        i = 0
        while i < n and idx < len(stream):
            ch = stream[idx]
            if ch == " ":
                idx += 1
                continue
            cw = meas.textlength(ch, font=font)
            if cw <= 0:
                idx += 1
                continue
            acc = 0.0
            start = i
            while i < n and acc < cw:
                acc += float(seg[i])
                i += 1
            if i >= n:
                break
            mid = ((start + i) // 2) % n
            k0, k1 = (mid - 1) % n, (mid + 1) % n
            tang = math.atan2(float(ys[k1] - ys[k0]), float(xs[k1] - xs[k0]))
            _paste_glyph(out, ch, font, float(xs[mid]), float(ys[mid]),
                         tang + math.pi / 2, fill)
            idx += 1
        s -= (fs * 1.55) / Rmax
        rings += 1
    return rings


def draw_round_rings(out, box, text, fill, font_size, font_path, hole=0.06):
    """透视空间(圆环版): 正圆一圈圈向内写, 字号/圈距随半径递减;
    中间空洞不在这里挖, 由调用方按主体轮廓清除."""
    bx0, by0, bx1, by1 = box
    cx, cy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
    R0 = 0.5 * max(bx1 - bx0, by1 - by0) * 0.98
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("文字不能为空")
    stream = clean * 600
    idx = 0
    R = R0
    f_out = max(8, int(font_size * 0.86))
    hole_r = max(6, int(R0 * hole))
    meas = ImageDraw.Draw(out)
    rings = 0
    while R > hole_r and idx < len(stream):
        fs = max(6, int(f_out * (R / R0) ** 0.9))
        font = tf.pick_font(text, fs, font_path)
        ang = -math.pi / 2
        end = ang + 2 * math.pi
        while ang < end and idx < len(stream):
            ch = stream[idx]
            if ch == " ":
                idx += 1
                ang += (fs * 0.30) / max(R, 1.0)
                continue
            cw = meas.textlength(ch, font=font)
            if cw <= 0:
                idx += 1
                continue
            d_ang = cw / max(R, 1.0)
            mid = ang + d_ang / 2
            _paste_glyph(out, ch, font,
                         cx + R * math.cos(mid), cy + R * math.sin(mid),
                         mid + math.pi / 2, fill)
            ang += d_ang
            idx += 1
        R -= fs * 1.45
        rings += 1
    return rings


def subject_shaped_cut(marr, scale, box):
    """把主体轮廓按 scale 缩小的同形区域(用作中心空洞), 返回布尔掩膜."""
    bx0, by0, bx1, by1 = box
    W, H = marr.shape[1], marr.shape[0]
    bw, bh = bx1 - bx0, by1 - by0
    small = Image.fromarray((marr * 255).astype(np.uint8)).resize(
        (max(1, int(bw * scale)), max(1, int(bh * scale))), Image.LANCZOS)
    hole = Image.new("L", (W, H), 0)
    hole.paste(small, (int(bx0 + (bw - small.width) / 2),
                       int(by0 + (bh - small.height) / 2)))
    return np.asarray(hole) > 127


def warp_layer(img, effect):
    """对整张文字层做同尺寸原地变形(不改变画布大小, 供剪影二次裁剪).

    wave     波浪: 纵向正弦起伏 + 轻微横向错位(原 wave_v/flowline 合并)
    fisheye  鱼眼透视: 大范围中心凸起, 字被放大拉圆
    """
    W, H = img.size
    xs, ys = tf.meshgrid(W, H)
    if effect in ("wave", "wave_v", "flowline"):
        amp = H * 0.026
        sy = ys - amp * np.sin(2 * np.pi * xs / max(W - 1, 1))
        sx = xs + amp * 0.6 * np.sin(2 * np.pi * 0.9 * ys / max(H - 1, 1))
    elif effect == "swirl":
        # 环形旋转(原 ring + circular 合并): 越靠外扭转越大, 外圈字顺着圆转
        cx, cy = W * 0.5, H * 0.5
        dx = xs - cx
        dy = ys - cy
        r = np.sqrt(dx * dx + dy * dy) / (max(W, H) * 0.5)
        ang = 2.2 * np.power(np.minimum(r, 1.0), 1.15)
        scale = 1.0 - 0.14 * np.minimum(r, 1.0)
        ca, sa = np.cos(ang), np.sin(ang)
        sx = cx + (dx * ca - dy * sa) * scale
        sy = cy + (dx * sa + dy * ca) * scale
    elif effect == "fisheye":
        # 凸起范围取 0.68 半径(比原来的 0.5 大一圈), 强度 p 同步提高
        p = 1.45
        cx, cy = W * 0.5, H * 0.5
        u = (xs - cx) / (W * 0.68)
        v = (ys - cy) / (H * 0.68)
        r = np.sqrt(u * u + v * v)
        fac = np.where(r < 1.0, np.maximum(r, 1e-6) ** (p - 1.0), 1.0)
        sx = cx + u * fac * (W * 0.68)
        sy = cy + v * fac * (H * 0.68)
    else:
        return img
    return tf.remap(tf.to_arr(img), W, H, sx, sy)


def make_text_shape(image, mask, text, fg, size, rows, gap, font_path,
                    layout="h", effect=None):
    """layout=h 横排(逐行写) / v 竖排(逐列写). rows 在竖排时表示列数."""
    box = bbox(mask)
    bx0, by0, bx1, by1 = box
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
    target = max(18, int(size * 2.2))

    if layout == "v":
        bands = rows if rows else max(2, min(20, int(round(bw / target))))
        bands = max(2, int(bands))
        band = bw / bands          # 列宽 = 纵向步进(正方形字格)
    else:
        bands = rows if rows else max(12, min(26, int(round(bh / target))))
        bands = max(1, int(bands))
        band = bh / bands          # 行带高 = 横向步进

    marr = np.asarray(mask) > 0
    H, W = marr.shape
    font_size = max(7, int(band * 0.94 * max(0.65, size / 16.0) * (1 - gap)))
    font = tf.pick_font(text, font_size, font_path)
    fill = ImageColor.getrgb(fg)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)

    # 英文保留词间空格(可读), 中文不受影响; 重复段之间也以空格衔接
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("文字不能为空")
    # 中文重复段之间无缝连写(不留空格); 英文才会用空格分隔词, 避免组间空洞
    sep = " " if not tf._has_cjk(clean) else ""
    stream = (clean + sep) * 800
    idx = 0
    char_h = max(6, int(font_size * 0.95))

    def segments(prof, min_w):
        """该带所有可写的连续段(左右耳/身体两侧等分离区都要保留)."""
        segs, s = [], None
        for x, v in enumerate(prof):
            if v and s is None:
                s = x
            elif not v and s is not None:
                if x - s >= min_w:
                    segs.append((s, x))
                s = None
        if s is not None and len(prof) - s >= min_w:
            segs.append((s, len(prof)))
        return segs

    font_cache = {}

    def font_at(px):
        px = max(5, int(px))
        if px not in font_cache:
            font_cache[px] = tf.pick_font(text, px, font_path)
        return font_cache[px]

    min_seg = max(2, int(font_size * 0.35))

    if effect == "tunnel":
        # 透视空间·轮廓圈: 每圈都是主体轮廓的缩小copy, 中心自然留同形空洞
        draw_tunnel_rings(out, marr, box, text, fill, font_size, font_path)
    elif effect == "tunnel_round":
        # 透视空间·圆环版: 正圆圈排字, 中心直接扣一个主体轮廓形状的空洞
        draw_round_rings(out, box, text, fill, font_size, font_path)
        cut = subject_shaped_cut(marr, 0.24, box)
        a = np.asarray(out).copy()
        a[cut, 3] = 0
        out = Image.fromarray(a, "RGBA")
        draw = ImageDraw.Draw(out)
    elif layout == "v":
        # 竖排: 一列从上往下一路写, 写到底接着下一列, 不重新起句
        for i in range(bands):
            xc = int(bx0 + (i + 0.5) * band)
            xa = max(0, int(xc - char_h * 0.45))
            xb = min(W, int(xc + char_h * 0.45) + 1)
            prof = marr[:, xa:xb].mean(axis=1) >= 0.5
            segs = segments(prof, min_seg)
            n = 0
            for top, bottom in segs:
                seg_len = bottom - top
                # 极短段自动缩字号, 细部也塞得进字
                fs = font_size if seg_len >= font_size * 1.2 else max(5, int(seg_len * 0.9))
                f = font_at(fs)
                step = band if fs == font_size else max(fs * 1.02, 1)
                y = top - fs * 0.08
                while y < bottom and idx < len(stream):
                    ch = stream[idx]
                    if ch != " ":
                        draw.text((xc, y + fs * 0.5), ch, font=f,
                                  fill=fill, anchor="mm")
                        n += 1
                    y += step
                    idx += 1
            if os.environ.get("SFD_DEBUG"):
                print(f"col {i:02d} x={xc} segs={[(a, b) for a, b in segs]} chars={n}",
                      file=sys.stderr)
    else:
        for j in range(bands):
            y0 = int(by0 + j * band)
            yc = int(y0 + band / 2)
            # 只看字符实际占据的那条横向带, 覆盖率过半即算可写, 保留尖端起伏
            ya = max(0, yc - char_h // 2)
            yb = min(H, yc + char_h // 2 + 1)
            colprof = marr[ya:yb].mean(axis=0) >= 0.5
            segs = segments(colprof, min_seg)
            n = 0
            # 一行里的每个分离段都接着同一条文本流往下写, 不重新起句
            for left, right in segs:
                seg_w = right - left
                # 极窄段(胡须/发丝)自动缩字号, 塞得下的都写字
                fs = font_size if seg_w >= font_size * 1.2 else max(5, int(seg_w * 0.9))
                f = font_at(fs)
                x = left - fs * 0.08  # 边缘允许轻微切字, 轮廓才不被内缩
                while x < right and idx < len(stream):
                    ch = stream[idx]
                    cw = draw.textlength(ch, font=f)
                    if cw <= 0:
                        idx += 1
                        continue
                    if ch != " ":
                        draw.text((x, yc), ch, font=f, fill=fill, anchor="lm")
                        n += 1
                    x += cw
                    idx += 1
            if os.environ.get("SFD_DEBUG"):
                print(f"row {j:02d} y={yc} segs={[(a, b) for a, b in segs]} chars={n}",
                      file=sys.stderr)

    if effect and effect not in ("tunnel", "tunnel_round"):
        out = warp_layer(out, effect)

    arr = np.asarray(out).copy()
    arr[:, :, 3] = np.where(marr, arr[:, :, 3], 0)
    arr = fill_thin_details(arr, marr, fill, font_size)
    arr = fill_inner_dark_lines(arr, image, marr, fill, font_size)
    return Image.fromarray(arr, "RGBA").crop(box)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wordshape fill",
                                 description="功能二: 主体剪影文字填充")
    ap.add_argument("image")
    ap.add_argument("text")
    ap.add_argument("outdir", nargs="?", default="out", help="输出目录, 默认 ./out")
    ap.add_argument("--mask", help="外部蒙版/透明 PNG；复杂背景建议直接给抠图")
    ap.add_argument("--fg", default="#E03A2F", help="文字颜色，默认红")
    ap.add_argument("--size", type=int, default=16, help="文字字号（主体填充建议 12-20）")
    ap.add_argument("--rows", type=int, default=None, help="行数(竖排时=列数)，默认自动")
    ap.add_argument("--layout", choices=["h", "v"], default="h",
                    help="h 横排逐行写(默认) / v 竖排逐列写")
    ap.add_argument("--effect",
                    choices=["wave", "fisheye", "swirl", "tunnel",
                             "tunnel_round"],
                    default=None,
                    help="文字层的变形效果：wave 波浪 / fisheye 鱼眼 / swirl 环形旋转 / "
                         "tunnel 透视空间·轮廓圈 / tunnel_round 透视空间·圆环(中心扣主体轮廓)；"
                         "默认不变形")
    ap.add_argument("--gap", type=float, default=0.02)
    ap.add_argument("--threshold", type=int, default=36, help="纯色背景分割阈值")
    ap.add_argument("--font", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    os.makedirs(args.outdir, exist_ok=True)
    image = Image.open(args.image)
    mask = load_mask(image, args.mask, args.threshold)
    shape = make_text_shape(image, mask, args.text, args.fg, args.size,
                            args.rows, args.gap, args.font, args.layout,
                            args.effect)

    stem = os.path.splitext(os.path.basename(args.image))[0]
    out = args.out or os.path.join(args.outdir, f"{stem}_textshape.png")
    shape.save(out)
    print("TEXT ->", out)


if __name__ == "__main__":
    main()
