"""WordShape 命令行入口: python -m wordshape <text|fill|list>"""

import argparse
import os
import sys

from . import textfx, subjectfill

TEXT_EFFECTS = textfx.EFFECTS
FILL_EFFECTS = ["wave", "fisheye", "swirl", "tunnel", "tunnel_round"]


def _outdir_of(out):
    return os.path.dirname(os.path.abspath(out)) or "."


def cmd_list(_args):
    print("功能一 text (文字复制与变形):")
    for key, desc in TEXT_EFFECTS:
        print(f"  {key:12s} {desc}")
    print("\n功能二 fill (主体剪影文字填充):")
    print("  基础横写      (默认, 不加 --effect)")
    print("  基础竖写      --layout v")
    for k in FILL_EFFECTS:
        print(f"  {k:12s} --effect {k}")


def cmd_text(args):
    out = args.out
    argv = [args.text, _outdir_of(out), "--out", out]
    if args.effect:
        argv += ["--effect", args.effect]
    if args.mode:
        argv += ["--mode", args.mode]
    if args.bg:
        argv += ["--bg", args.bg]
    if args.fg:
        argv += ["--fg", args.fg]
    if args.size:
        argv += ["--size", str(args.size)]
    if args.rows:
        argv += ["--rows", str(args.rows)]
    if args.font:
        argv += ["--font", args.font]
    textfx.main(argv)


def cmd_fill(args):
    out = args.out
    argv = [args.image, args.text, _outdir_of(out), "--out", out]
    if args.layout:
        argv += ["--layout", args.layout]
    if args.effect:
        argv += ["--effect", args.effect]
    if args.size:
        argv += ["--size", str(args.size)]
    if args.rows:
        argv += ["--rows", str(args.rows)]
    if args.fg:
        argv += ["--fg", args.fg]
    if args.gap is not None:
        argv += ["--gap", str(args.gap)]
    if args.mask:
        argv += ["--mask", args.mask]
    if args.threshold:
        argv += ["--threshold", str(args.threshold)]
    if args.font:
        argv += ["--font", args.font]
    subjectfill.main(argv)


def build_parser():
    ap = argparse.ArgumentParser(
        prog="wordshape",
        description="WordShape 文字塑形排印 — 文字变形 / 文字填充剪影")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出全部效果")
    p_list.set_defaults(func=cmd_list)

    p_text = sub.add_parser("text", help="功能一: 文字复制与变形")
    p_text.add_argument("text", help="要变形的文字")
    p_text.add_argument("-o", "--out", required=True, help="输出 PNG 路径")
    p_text.add_argument("--effect", help="效果名, 见 wordshape list")
    p_text.add_argument("--mode", default=None,
                        help="tr 透明底红字(默认) / br 黑底红字 / bw 白底黑字 / "
                             "wb 黑底白字 / white 透明白字 / black 透明黑字 / "
                             "red 红底白字 / navy 藏青底青字")
    p_text.add_argument("--bg", help="自定义底色 (配 --mode custom 或单独使用)")
    p_text.add_argument("--fg", help="自定义字色")
    p_text.add_argument("--size", type=int, help="基准字号, 默认 240")
    p_text.add_argument("--rows", type=int, help="覆盖效果行数")
    p_text.add_argument("--font", help="字体文件路径")
    p_text.set_defaults(func=cmd_text)

    p_fill = sub.add_parser("fill", help="功能二: 主体剪影文字填充")
    p_fill.add_argument("image", help="主体图 (透明 PNG 最佳)")
    p_fill.add_argument("text", help="要填充的文字")
    p_fill.add_argument("-o", "--out", required=True, help="输出 PNG 路径")
    p_fill.add_argument("--layout", choices=["h", "v"], help="h 横排(默认) / v 竖排")
    p_fill.add_argument("--effect", choices=FILL_EFFECTS,
                        help="wave 波浪 / fisheye 鱼眼 / swirl 环形旋转 / "
                             "tunnel 透视·轮廓圈 / tunnel_round 透视·圆环")
    p_fill.add_argument("--size", type=int, help="字号基准, 默认 16")
    p_fill.add_argument("--rows", type=int, help="行数(竖排=列数), 默认自动")
    p_fill.add_argument("--fg", help="文字颜色, 默认 #E03A2F")
    p_fill.add_argument("--gap", type=float, help="行缝比例, 默认 0.02")
    p_fill.add_argument("--mask", help="外部蒙版 / 透明剪影")
    p_fill.add_argument("--threshold", type=int, help="纯色背景分割阈值, 默认 36")
    p_fill.add_argument("--font", help="字体文件路径")
    p_fill.set_defaults(func=cmd_fill)

    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
