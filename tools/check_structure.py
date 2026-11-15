# -*- coding: utf-8 -*-
"""结构体检：层/域/深度/散落文件/空目录。见 `01_标准/`。

用法：
    python tools/check_structure.py
    python tools/check_structure.py --root "D:/lib"      # 临时指定
    python tools/check_structure.py --max-depth 3

退出码：0 全部合规；1 有 FAIL；2 资源库定位失败。

只检查「结构」，不检查内容。素材对不对不归本脚本管。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from libpath import lib_root  # noqa: E402

INDEX = "00_索引"

# 账本层（00_索引）本身放文件是设计意图：取件表、入库登记、清单都在其下。
# 素材层（10/20）根上不许有文件 —— 红线 4。
LAYER_SPEC = {
    INDEX: dict(rng=None, allow_files=True, note="账本层"),
    "10_用户层": dict(rng=(11, 19), allow_files=False),
    "20_开发层": dict(rng=(21, 29), allow_files=False),
}


class Report:
    def __init__(self):
        self.fail = []
        self.warn = []
        self.info = []

    def add(self, level, msg):
        getattr(self, level).append(msg)

    def dump(self):
        for tag, items in (("FAIL", self.fail), ("WARN", self.warn), ("INFO", self.info)):
            for m in items:
                print(f"[{tag}] {m}")


def check_layers(root: Path, r: Report):
    for p in sorted(root.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            r.add("fail", f"库根有散落文件（红线 4）：{p.name}")
    for name in LAYER_SPEC:
        if not (root / name).is_dir():
            r.add("fail", f"缺层目录：{name}")


def check_domains(root: Path, r: Report):
    for layer, spec in LAYER_SPEC.items():
        d = root / layer
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file():
                if p.name.startswith("."):
                    continue
                if spec["allow_files"]:
                    continue
                r.add("fail", f"{layer} 根上有散落文件（红线 4）：{p.name}")
                continue
            if spec["rng"] is None:
                # 账本层的子目录不编号，属正常（_基线 / 头像框 / 音频 / 采集模板）
                r.add("info", f"{layer}\\{p.name}（账本子目录）")
                continue
            head = p.name.split("_", 1)[0]
            if not (len(head) == 2 and head.isdigit()):
                r.add("fail", f"{layer}\\{p.name} 缺两位编号前缀")
                continue
            n = int(head)
            lo, hi = spec["rng"]
            if not (lo <= n <= hi):
                r.add("fail", f"{layer}\\{p.name} 编号 {n} 不在区间 {lo}–{hi}")
            if "_" not in p.name:
                r.add("warn", f"{p.name} 编号后无中文名")


def depth_dist(root: Path, r: Report, max_depth, from_root=False):
    """统计目录深度分布。两种口径：

    默认「相对域」—— 域目录本身算 0，`域/类别/子类/组` = 3 层。
        判据挂在结构语义上，加一次层不会让全库自动超标。
    --from-root —— 相对库根，含 `层/域` 两级骨架，比相对域恒多 2。

    max_depth 为 None 时只报告，不判 FAIL。目标值由使用方显式给出。
    """
    dist = {}
    over = []
    for base, dirs, names in os.walk(root):
        rel = Path(base).relative_to(root)
        parts = rel.parts
        if from_root:
            d = len(parts)
        elif len(parts) >= 2 and parts[0] in ("10_用户层", "20_开发层"):
            d = len(parts) - 2                    # 域本身 = 0
        else:
            continue                              # 库根与 00_索引 不计入
        dist[d] = dist.get(d, 0) + 1
        if max_depth is not None and d > max_depth:
            over.append((d, rel.as_posix(), len(names)))
            # 不在这里 dirs[:] = []：停了下钻就数不全超标数。
            # 只截断打印（见下方 [:20]），计数始终是全量。

    tag = "相对库根" if from_root else "相对域"
    parts_s = " / ".join(f"{d}层={dist[d]}" for d in sorted(dist))
    r.add("info", f"深度分布（{tag}）：{parts_s}")
    r.add("info", f"最深 {max(dist) if dist else 0} 层（{tag}），共 {sum(dist.values())} 个目录")

    for d, p, n in sorted(over, reverse=True)[:20]:
        r.add("fail", f"超深 {d}>{max_depth}（{tag}）：{p}（{n} 文件）")
    if len(over) > 20:
        r.add("fail", f"…另有 {len(over) - 20} 个超深目录未列出")


def check_empty(root: Path, r: Report):
    for base, dirs, names in os.walk(root):
        if not dirs and not names:
            r.add("warn", f"空目录：{Path(base).relative_to(root).as_posix()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="资源库根，默认走定位协议")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="显式设上限才判 FAIL；默认口径为「相对域」")
    ap.add_argument("--from-root", action="store_true",
                    help="深度改按「相对库根」计（比相对域恒多 2 层）")
    ap.add_argument("--no-empty", action="store_true", help="跳过空目录检查（大库会慢）")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else lib_root()
    if not root.is_dir():
        print(f"资源库不存在：{root}")
        return 2

    print(f"资源库根 : {root}")
    print(f"深度口径 : {'相对库根' if args.from_root else '相对域'}"
          f" ｜ 上限 {args.max_depth if args.max_depth else '不设（只报告）'}")
    print("-" * 60)

    r = Report()
    check_layers(root, r)
    check_domains(root, r)
    depth_dist(root, r, args.max_depth, args.from_root)
    if not args.no_empty:
        check_empty(root, r)
    r.dump()

    print("-" * 60)
    print(f"FAIL {len(r.fail)} ｜ WARN {len(r.warn)} ｜ INFO {len(r.info)}")
    return 0 if not r.fail else 1


if __name__ == "__main__":
    sys.exit(main())
