# -*- coding: utf-8 -*-
"""资源库定位协议 · 唯一实现。见 `02_调用/定位协议.md`。

用法：
    import sys; sys.path.insert(0, r"<本仓>/tools")
    from libpath import lib, lib_root

    p = lib("10_用户层/11_角色立绘/2B_c810_00.png")      # 拼接（不检查存在）
    p = lib("00_索引/资源总清单.md", must_exist=True)     # 检查存在

解析顺序（先命中先用）：
    1. 环境变量 NIKKE_LIB_ROOT
    2. config/libpath.json 的 lib_root
    3. 环境变量 NIKKE_ROOT  + 约定相对路径
    4. config/libpath.json 的 root + 约定相对路径
    5. 从本文件目录向上探测 00_资源库

四级全落空 → 抛 SystemExit，不猜、不回退到默认盘符。

只用标准库，Python 3.8+。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "libpath.json"

# 工作站根 → 资源库根 的约定相对路径。换库结构时改这里，不改调用方。
REL_FROM_ROOT = Path("01_母体") / "B_客户端资源" / "00_资源库"
LIB_DIRNAME = "00_资源库"


def _config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _probe(start: Path):
    """向上找 00_资源库，或找到含约定相对路径的目录。"""
    for d in [start, *start.parents]:
        if (d / LIB_DIRNAME).is_dir():
            return d / LIB_DIRNAME
        cand = d / REL_FROM_ROOT
        if cand.is_dir():
            return cand
    return None


def lib_root() -> Path:
    """返回资源库根（绝对路径）。失败即退出，不返回 None。"""
    env = os.environ.get("NIKKE_LIB_ROOT")
    if env and Path(env).is_dir():
        return Path(env).resolve()

    cfg = _config()
    if cfg.get("lib_root") and Path(cfg["lib_root"]).is_dir():
        return Path(cfg["lib_root"]).resolve()

    root = os.environ.get("NIKKE_ROOT") or cfg.get("root")
    if root and (Path(root) / REL_FROM_ROOT).is_dir():
        return (Path(root) / REL_FROM_ROOT).resolve()

    hit = _probe(HERE) or _probe(Path.cwd())
    if hit:
        return hit.resolve()

    raise SystemExit(
        "找不到资源库。按顺序试过：\n"
        "  1) 环境变量 NIKKE_LIB_ROOT\n"
        f"  2) {CONFIG} 的 lib_root\n"
        "  3) 环境变量 NIKKE_ROOT / 配置 root + 约定相对路径\n"
        f"  4) 向上探测 {LIB_DIRNAME}\n"
        "请复制 config/libpath.example.json 为 libpath.json 并填 lib_root。"
    )


def lib(rel: str, must_exist: bool = False) -> Path:
    """把库内相对路径拼成绝对路径。

    rel 一律用正斜杠，如 "10_用户层/11_角色立绘/x.png"。
    must_exist=True 时不存在即抛 FileNotFoundError —— 建议在所有「读文件」处开启。
    """
    p = lib_root() / rel.replace("\\", "/").lstrip("/")
    if must_exist and not p.exists():
        raise FileNotFoundError(f"库内路径不存在：{rel}\n资源库根：{lib_root()}")
    return p


def rel(abs_path) -> str:
    """绝对路径 → 库内相对路径（正斜杠）。写登记表时用。"""
    return Path(abs_path).resolve().relative_to(lib_root()).as_posix()


if __name__ == "__main__":
    import sys

    print(f"资源库根 : {lib_root()}")
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            p = lib(a, must_exist=True)
            print(f"  OK  {a} -> {p}")
