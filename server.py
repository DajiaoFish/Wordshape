#!/usr/bin/env python3
"""WordShape HTTP 服务 (零依赖, 仅标准库).

给豆包 / 扣子 Coze / Dify / 任意低代码平台调用:
    python server.py --port 8000

接口 (JSON, 图片用 base64):
    POST /text  {"text":"我爱你","effect":"spiral","mode":"tr"}
    POST /fill  {"image":"<base64 或 data URI>","text":"我爱你","layout":"v"}
响应:
    {"ok": true, "image": "<base64 PNG>"}  或  {"ok": false, "error": "..."}
"""
import argparse
import base64
import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

from wordshape import textfx, subjectfill

MODE_MAP = {
    "tr": ("transparent", "#E03A2F"),
    "br": ("#111111", "#E03A2F"),
    "bw": ("#FFFFFF", "#111111"),
    "wb": ("#111111", "#FFFFFF"),
    "white": ("transparent", "#FFFFFF"),
    "black": ("transparent", "#000000"),
    "red": ("#E03A2F", "#FFFFFF"),
    "navy": ("#0A1F33", "#4FE0E6"),
}


def _decode_image(data):
    """支持纯 base64 与 data URI 两种写法"""
    if "," in data and data.strip().lower().startswith("data:"):
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    return Image.open(io.BytesIO(raw))


def _encode_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def do_text(payload):
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("缺少 text")
    effect = payload.get("effect")
    if not effect or effect not in textfx.FX_FUNCS:
        raise ValueError(f"未知效果: {effect!r}, 可选: {list(textfx.FX_FUNCS)}")

    mode = payload.get("mode") or "tr"
    if mode == "custom":
        bg = payload.get("bg")
        fg = payload.get("fg")
        if not bg or not fg:
            raise ValueError("mode=custom 需要同时提供 bg 与 fg")
    else:
        if mode not in MODE_MAP:
            raise ValueError(f"未知模式: {mode!r}, 可选: {list(MODE_MAP)}")
        bg, fg = MODE_MAP[mode]

    size = int(payload.get("size") or 240)
    textfx.set_style(bg, fg)
    textfx._CUR_TEXT = text
    base = textfx.render_text(text, payload.get("font"), size, fg)
    base.info["bg"] = bg
    rows = payload.get("rows")
    rows = int(rows) if rows else textfx._default_rows(effect, text)
    img = textfx.crop_alpha(textfx.FX_FUNCS[effect](base, rows=rows))
    return img


def do_fill(payload):
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("缺少 text")
    if not payload.get("image"):
        raise ValueError("缺少 image (base64 或 data URI)")
    image = _decode_image(payload["image"])
    if payload.get("mode") == "RGBA":
        image = image.convert("RGBA")

    mask = subjectfill.load_mask(
        image, payload.get("mask"),
        int(payload.get("threshold") or 36))
    shape = subjectfill.make_text_shape(
        image, mask, text,
        payload.get("fg") or "#E03A2F",
        int(payload.get("size") or 16),
        int(payload["rows"]) if payload.get("rows") else None,
        float(payload.get("gap") if payload.get("gap") is not None else 0.02),
        payload.get("font"),
        payload.get("layout") or "h",
        payload.get("effect"),
    )
    return shape


class Handler(BaseHTTPRequestHandler):
    server_version = "WordShape/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/health"):
            self._send(200, {
                "ok": True, "service": "wordshape",
                "endpoints": ["/text", "/fill"],
                "text_effects": [k for k, _ in textfx.EFFECTS],
                "modes": list(MODE_MAP),
            })
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8") or "{}")
            if path == "/text":
                img = do_text(payload)
            elif path == "/fill":
                img = do_fill(payload)
            else:
                self._send(404, {"ok": False, "error": "not found"})
                return
            self._send(200, {"ok": True, "image": _encode_png(img)})
        except Exception as exc:                       # 统一转为 JSON 错误
            self._send(400, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def main():
    ap = argparse.ArgumentParser(description="WordShape HTTP 服务")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址, 默认仅本机")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"WordShape server -> http://{args.host}:{args.port}")
    print("  GET  /         查看能力")
    print("  POST /text     {\"text\",\"effect\",\"mode\"}")
    print("  POST /fill     {\"image\",\"text\",\"layout\",\"effect\"}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
