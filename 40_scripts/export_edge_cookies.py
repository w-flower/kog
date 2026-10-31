# -*- coding: utf-8 -*-
"""export_edge_cookies.py — 从 Edge 的 cookie 库离线导出 B 站登录态

前提：Edge 已关闭，60_state/edge_ck 下有复制出来的 Cookies + Local State。
产出：cookies.txt（Netscape 格式），供 fetch_cues 的 cookies+wbi 通道使用。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BILI = Path(r"C:/Users/Lenovo/.workbuddy/skills/bilibili-video-summary/scripts")
sys.path.insert(0, str(BILI))

from import_360_cookies import _load_key, read_cookies, write_netscape  # noqa: E402
from config import DATA_DIR  # noqa: E402

STAGE = Path(r"C:/Users/Lenovo/WorkBuddy/kog/60_state/edge_ck")
OUT = Path(DATA_DIR) / "bilibili_cookies.txt"


def chrome_ts(v) -> str:
    """Chromium 时间戳（1601-01-01 起的微秒）-> 可读时间。"""
    try:
        v = int(v)
    except Exception:
        return "?"
    if v <= 0:
        return "session"
    try:
        dt = datetime(1601, 1, 1, tzinfo=timezone.utc).timestamp() + v / 1e6
        return datetime.fromtimestamp(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def main() -> int:
    ls = STAGE / "Local State"
    if not ls.exists():
        print(json.dumps({"ok": False, "error": "no_local_state"}, ensure_ascii=False))
        return 2
    try:
        key = _load_key(ls)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "key_error", "message": str(e)},
                         ensure_ascii=False, indent=2))
        return 4

    all_rows, report = [], []
    for d in sorted(STAGE.glob("ck_*")):
        db = d / "Cookies"
        if not db.exists():
            continue
        try:
            rows, verified = read_cookies(db, key)
        except Exception as e:
            report.append({"profile": d.name, "error": f"{type(e).__name__}: {e}"})
            continue
        bili = [r for r in rows if "bilibili" in r["domain"]]
        report.append({"profile": d.name, "total": len(rows),
                       "bilibili": len(bili), "verified": bool(verified)})
        all_rows.extend(bili)

    if not all_rows:
        print(json.dumps({"ok": False, "error": "no_bilibili_cookie", "report": report},
                         ensure_ascii=False, indent=2))
        return 5

    write_netscape(all_rows, OUT)

    sess = [r for r in all_rows if r["name"] == "SESSDATA"]
    # 同一 cookie 名可能多 profile 都有，取过期最晚的那条
    def exp_key(r):
        try:
            return int(r.get("expires_utc") or 0)
        except Exception:
            return 0
    sess.sort(key=exp_key, reverse=True)

    print(json.dumps({
        "ok": True,
        "out": str(OUT),
        "cookie_count": len(all_rows),
        "profiles": report,
        "sessdata_expires": chrome_ts(sess[0].get("expires_utc")) if sess else "MISSING",
        "has_sessdata": bool(sess),
        "names": sorted({r["name"] for r in all_rows})[:20],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
