#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""重定基：把项目内硬编码的旧根路径换成新根路径。见 `02_调用/映射与重定基.md`。

用法（默认只预览，不落盘）：
    python tools/rebase_paths.py --old "F:\Codex\Nikke" --new "D:\Work\Nikke"
    python tools/rebase_paths.py --old "F:\Codex\Nikke" --new "D:\Work\Nikke" --apply

改什么：
    文档（*.md）、脚本（*.py *.bat *.cmd *.ps1）、配置（*.json *.yaml *.toml *.ini）

不改什么（默认跳过，可用 --skip 增补）：
    迭代记录\   —— 历史证据，路径是当时的事实快照，改了等于伪造记录
    回收站\ 临时车间\ 临时\ node_modules\ .git\ __pycache__\ 归档\ 母体\
    二进制文件（前 4 KB 含 NUL）

为什么分四种写法：同一根路径在 Windows 上有四种存储形态，
    F:\Codex\Nikke     普通字符串
    F:/Codex/Nikke     正斜杠
    F:\\Codex\\Nikke   JSON 转义
    F://Codex//Nikke   少数字段
四种都要换，否则会出现「改了一半」的假成功。
"""
from __future__ import annotations

import argparse
import os
import sys

TEXT_EXT = {".md", ".py", ".pyi", ".bat", ".cmd", ".ps1", ".psm1", ".sh",
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".txt",
            ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".vue",
            ".html", ".htm", ".css", ".scss", ".xml",
            ".cs", ".csproj", ".sln", ".sql", ".reg"}

SKIP_DIRS = {"迭代记录", "回收站", "临时车间", "临时文件", "临时",
             "node_modules", ".git", "__pycache__", ".venv", "venv",
             "dist", "build", "release", "03_归档", "01_母体"}


def variants(root: str) -> list[bytes]:
    r"""展开成 4 种写法，长串在前，避免单斜杠先命中把双斜杠拆坏。

    Git Bash / MSYS 会把命令行里的 F:\Codex\Nikke 自动转成 F:/Codex/Nikke，
    所以不能信入参的分隔符形态，一律先归一成反斜杠再派生。
    """
    r = root.replace("/", "\\").rstrip("\\")
    return [
        r.replace("\\", "\\\\").encode(),   # F:\\Codex\\Nikke
        r.replace("\\", "//").encode(),     # F://Codex//Nikke
        r.replace("\\", "/").encode(),      # F:/Codex/Nikke
        r.encode(),                         # F:\Codex\Nikke
    ]


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help=r"旧根路径，如 F:\Codex\Nikke")
    ap.add_argument("--new", required=True, help=r"新根路径，如 D:\Work\Nikke")
    ap.add_argument("--root", default=".", help="要处理的目录，默认当前目录")
    ap.add_argument("--skip", nargs="*", default=[], help="额外跳过的目录名")
    ap.add_argument("--apply", action="store_true", help="真正写入（默认只预览）")
    args = ap.parse_args()

    olds, news = variants(args.old), variants(args.new)
    skip = SKIP_DIRS | set(args.skip)
    root = os.path.abspath(args.root)

    print(f"根目录 : {root}")
    print(f"旧路径 : {args.old}")
    print(f"新路径 : {args.new}")
    print(f"模式   : {'写入' if args.apply else '预览（加 --apply 才落盘）'}")
    print("-" * 66)

    files = affected = hits = 0
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in names:
            if os.path.splitext(name)[1].lower() not in TEXT_EXT:
                continue
            path = os.path.join(base, name)
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                continue
            if is_binary(data):
                continue
            files += 1
            n, out = 0, data
            for o, nw in zip(olds, news):
                c = out.count(o)
                if c:
                    n += c
                    out = out.replace(o, nw)
            if not n:
                continue
            hits += n
            affected += 1
            print(f"{n:>6}  {os.path.relpath(path, root)}")
            if args.apply:
                with open(path, "wb") as f:
                    f.write(out)

    print("-" * 66)
    print(f"扫描 {files} 个文本文件，命中 {affected} 个文件 / {hits} 处")
    print("已替换" if args.apply else "预览完毕，确认后加 --apply 落盘")
    return 0


if __name__ == "__main__":
    sys.exit(main())
