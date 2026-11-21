# -*- coding: utf-8 -*-
"""s52_transcribe.py — 本地 ASR 转写（B 站无字幕视频兜底）。

用法:
    python 40_scripts/s52_transcribe.py <音频路径> <输出txt> [模型] [语言]

例:
    python 40_scripts/s52_transcribe.py a.wav out.txt medium zh

说明:
- 用 faster-whisper（CPU int8），模型从 hf-mirror.com 拉，国内可达。
- 首次运行会下模型：tiny 75MB / small 480MB / medium 1.5GB / large-v3 3GB。
- initial_prompt 里塞领域词，能明显提升「辅助/兵线/转线/闪现/大招」这类词的准确率。
"""
import os
import shutil
import subprocess
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# 新版 huggingface_hub 默认走 Xet 存储（cas-server.xethub.hf.co），国内不通，必须关掉回落 HTTP
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

SR = 16000


def load_audio(path):
    """用 ffmpeg 解码成 16k 单声道 float32，绕开 PyAV 版本兼容问题。"""
    exe = shutil.which("ffmpeg") or r"D:/app/tools/ffmpeg/ffmpeg.exe"
    cmd = [exe, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

DEFAULT_PROMPT = (
    "以下是王者荣耀游戏教学视频的普通话讲解。常见词：辅助、射手、打野、中单、对抗路、"
    "兵线、推进、转线、开团、拉扯、闪现、大招、召唤师技能、经济、发育、视野、龙坑、"
    "蓝领、红领、节奏、对线、蹲草、站桩、poke、poke消耗。"
)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    audio, out = sys.argv[1], sys.argv[2]
    size = sys.argv[3] if len(sys.argv) > 3 else "small"
    lang = sys.argv[4] if len(sys.argv) > 4 else "zh"
    prompt = sys.argv[5] if len(sys.argv) > 5 else DEFAULT_PROMPT
    # 第五个参数可以是文件：.txt 直接读，.py 取其中 PROMPT 变量
    if prompt and os.path.isfile(prompt):
        if prompt.endswith(".py"):
            ns = {}
            exec(open(prompt, encoding="utf-8").read(), ns)
            prompt = ns.get("PROMPT", DEFAULT_PROMPT)
        else:
            prompt = open(prompt, encoding="utf-8").read().strip()

    # 允许直接传本地模型目录（国内从 hf-mirror 用 curl 下好更快）
    if os.path.isdir(size):
        size = os.path.abspath(size)

    print(f"[load] model={size} device=cpu int8", flush=True)
    model = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=10)

    print(f"[run] {audio}", flush=True)
    data = load_audio(audio)
    print(f"[audio] {len(data)/SR:.1f}s @ {SR}Hz", flush=True)
    segments, info = model.transcribe(
        data,
        language=lang,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=5,
        initial_prompt=prompt,
        condition_on_previous_text=False,
    )
    print(f"[info] duration={info.duration:.1f}s lang={info.language} p={info.language_probability:.2f}", flush=True)

    lines = []
    for seg in segments:
        m, s = int(seg.start // 60), int(seg.start % 60)
        text = seg.text.strip()
        if text:
            lines.append(f"[{m:02d}:{s:02d}] {text}")
            if len(lines) % 20 == 0:
                print(f"  ... {len(lines)} segs", flush=True)

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    total = sum(len(x) for x in lines)
    print(f"[done] {len(lines)} segs, {total} chars -> {out}")


if __name__ == "__main__":
    main()
