"""WordShape · 文字塑形排印

两个功能:
  textfx      功能一: 文字复制与变形 (9 种效果)
  subjectfill 功能二: 主体剪影文字填充 (7 种效果)

命令行入口:
  python -m wordshape text "我爱你" -o out.png --effect spiral
  python -m wordshape fill cat.png "我爱你" -o out.png --layout v
"""

__version__ = "1.0.0"
__all__ = ["textfx", "subjectfill"]
