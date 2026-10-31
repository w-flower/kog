#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy.py — 一键：重建索引 → 重建站点 → 提交 → 推送 → Pages 自动部署

用法：
  python deploy.py                     # 默认提交信息带时间
  python deploy.py -m "补 D 类开局两条"
  python deploy.py --no-push           # 只本地提交
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", default="")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    # 1. 构建
    if not args.skip_build:
        for s in ("s5_index.py", "build_site.py"):
            code, out = run([PY, str(ROOT / "40_scripts" / s)])
            print(f"[{s}]\n{out}\n")
            if code != 0:
                print(f"✗ {s} 失败，中止")
                return code

    # 2. 有没有东西要提交
    code, out = run(["git", "status", "--porcelain"])
    if not out:
        print("✓ 没有改动，无需提交")
        return 0

    # 3. 提交
    msg = args.message or f"update {dt.datetime.now():%Y-%m-%d %H:%M}"
    run(["git", "add", "-A"])
    code, out = run(["git", "commit", "-m", msg])
    print(out)
    if code != 0:
        print("✗ 提交失败")
        return code

    # 4. 推送
    if args.no_push:
        print("（--no-push，已停在本地）")
        return 0
    code, out = run(["git", "push", "origin", "HEAD"])
    print(out)
    if code != 0:
        print("✗ 推送失败（检查 SSH：ssh -T git@github.com）")
        return code
    print("✓ 已推送，Actions 会在 1–2 分钟内重新部署")
    return 0


if __name__ == "__main__":
    sys.exit(main())
