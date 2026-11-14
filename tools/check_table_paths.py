# -*- coding: utf-8 -*-
"""表内路径体检：扫 CSV 里的「资源路径」列，判断每一行在磁盘上是否真的存在。

为什么需要：2026-11-11 资源库两层重构把 `01_角色/…` 改成 `10_用户层/11_角色立绘/…`，
另一份母体的素材清单 199 行 591 条路径**全部静默失效，两个月没人发现**——
因为表里存的是字符串，不是超链接，Excel 不会报错。

用法：
    python tools/check_table_paths.py                      # 用配置里的 targets
    python tools/check_table_paths.py --files a.csv b.csv
    python tools/check_table_paths.py --limit 0            # 列出全部不可达
    python tools/check_table_paths.py --col 库内路径        # 指定列名（默认自动识别）

退出码：0 全可达；1 有不可达或无法解析；2 无法执行。

历史口径穿透：config/libpath.json 的 legacy_prefix 把旧前缀映射到新域，
长前缀优先。存量表全写在结构变更之前，不映射就全「无法解析」。

限制：只读 CSV，不解析 .xlsx。存量 xlsx 请先导出 CSV。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from libpath import lib_root  # noqa: E402

CONFIG = Path(__file__).resolve().parent.parent / "config" / "libpath.json"
COLPAT = re.compile(r"(库内路径|落盘相对路径|库内目录|相对路径|路径|local|path)", re.I)
RELLIKE = re.compile(r"^(00_索引|10_用户层|20_开发层)[/\\]")
LIBPREFIX = "00_资源库/"


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_legacy(cfg: dict) -> list:
    raw = cfg.get("legacy_prefix", {})
    # 长前缀优先，否则 02_剧情 会先于 02_剧情/插画 命中
    return sorted(raw.items(), key=lambda kv: -len(kv[0]))


def is_pathlike(v: str) -> bool:
    v = v.strip()
    if not v or len(v) > 400:
        return False
    return ("/" in v or "\\" in v) and bool(re.search(r"\.\w{2,5}$", v))


def resolve(v: str, root: Path, legacy: list):
    """返回 (绝对路径 | None, 是否可解析, 是否走了历史映射)。"""
    s = v.strip().strip('"').replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", s) or s.startswith("//"):
        return Path(s), True, False
    if s.startswith(LIBPREFIX):          # 带库名前缀的写法
        s = s[len(LIBPREFIX):]
    if RELLIKE.match(s):
        return root / s, True, False
    for old, new in legacy:
        o = old.replace("\\", "/").rstrip("/")
        if s == o or s.startswith(o + "/"):
            rest = s[len(o):].lstrip("/")
            return root / (new.replace("\\", "/").rstrip("/") + "/" + rest), True, True
    return None, False, False


def pick_col(header: list, forced: str) -> int:
    if forced:
        return header.index(forced) if forced in header else -1
    for i, h in enumerate(header):
        if COLPAT.search(h):
            return i
    return -1


def scan_csv(path: Path, root: Path, forced_col: str, legacy: list, limit: int):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gbk", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return dict(file=path.name, error="空文件")
    header, body = rows[0], rows[1:]
    ci = pick_col(header, forced_col)
    if ci < 0:
        return dict(file=path.name, error=f"无路径列 {header}")

    stat = dict(file=path.name, col=header[ci], ok=0, miss=0, unres=0, legacy=0, misses=[], unres_rows=[])
    for ln, row in enumerate(body, start=2):
        if ci >= len(row) or not is_pathlike(row[ci]):
            continue
        p, resolvable, via = resolve(row[ci], root, legacy)
        if not resolvable:
            stat["unres"] += 1
            if limit == 0 or len(stat["unres_rows"]) < limit:
                stat["unres_rows"].append((ln, row[ci]))
            continue
        if via:
            stat["legacy"] += 1
        if p.exists():
            stat["ok"] += 1
        else:
            stat["miss"] += 1
            if limit == 0 or len(stat["misses"]) < limit:
                stat["misses"].append((ln, row[ci]))
    return stat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", help="要扫的 CSV，默认取 config 的 targets")
    ap.add_argument("--col", default="", help="强制指定路径列名")
    ap.add_argument("--limit", type=int, default=8, help="每表列出的条目数，0=全部")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        root = lib_root()
    except SystemExit as e:
        print(e)
        return 2

    cfg = load_config()
    legacy = load_legacy(cfg)
    targets = [Path(f) for f in args.files] if args.files else [Path(t) for t in cfg.get("targets", [])]
    if not targets:
        print("没有要扫的表。用 --files 指定，或在 config/libpath.json 里写 targets。")
        return 2

    results = []
    for t in targets:
        results.append(scan_csv(t, root, args.col, legacy, args.limit) if t.exists()
                       else dict(file=str(t), error="文件不存在"))

    if args.json:
        print(json.dumps(dict(lib_root=str(root), legacy_prefix=len(legacy), results=results),
                         ensure_ascii=False, indent=2))
    else:
        print(f"资源库根 : {root}")
        print(f"历史映射 : {len(legacy)} 条" + ("（config/libpath.json 的 legacy_prefix）" if legacy else "（未配置，存量表会全「无法解析」）"))
        print("-" * 70)
        for r in results:
            if "error" in r:
                print(f"{r['file']}：{r['error']}")
                continue
            print(f"{r['file']}  [列 {r['col']}]  可达 {r['ok']} / 不可达 {r['miss']} "
                  f"/ 无法解析 {r['unres']}（其中经历史映射 {r['legacy']}）")
            for ln, v in r["misses"]:
                print(f"    L{ln}  不存在  {v}")
            for ln, v in r["unres_rows"]:
                print(f"    L{ln}  无法解析  {v}")

    bad = sum(r.get("miss", 0) + r.get("unres", 0) for r in results if "error" not in r)
    print("-" * 70)
    print(f"合计问题行 {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
