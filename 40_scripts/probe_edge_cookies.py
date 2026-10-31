# -*- coding: utf-8 -*-
"""用全共享标志强行读 Edge 的 Cookies 数据库，绕过 WinError 32。"""
import ctypes
import ctypes.wintypes as wt
import shutil
import sys
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, wt.HANDLE]

GENERIC_READ = 0x80000000
SHARE_ALL = 0x1 | 0x2 | 0x4
OPEN_EXISTING = 3

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

h = k32.CreateFileW(str(src), GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING, 0x80, None)
if h == wt.HANDLE(-1).value or h is None or h == -1:
    print(f"FAIL open err={ctypes.get_last_error()}")
    sys.exit(1)

buf, total = [], 0
chunk = ctypes.create_string_buffer(1 << 20)
read = wt.DWORD(0)
while True:
    ok = k32.ReadFile(h, chunk, len(chunk), ctypes.byref(read), None)
    if not ok or read.value == 0:
        break
    buf.append(chunk.raw[: read.value])
    total += read.value
k32.CloseHandle(h)

dst.write_bytes(b"".join(buf))
print(f"OK copied {total} bytes -> {dst}")
