#!/usr/bin/env python3
"""
XTTS v2 TTS generation for MCH voice reports.
Usage: python3 xtts_generate.py "<text>" "<speaker_wav>" "<output_mp3>"
Fallback: gTTS if XTTS fails.
"""
import sys, time, os

def xtts_generate(text, speaker_wav, out_path):
    from TTS.api import TTS
    print(f"Loading XTTS v2...", flush=True)
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False, gpu=False)
    print(f"Generating {len(text)} chars...", flush=True)
    start = time.time()
    tts.tts_to_file(
        text=text,
        speaker_wav=speaker_wav,
        file_path=out_path,
        language="it",
    )
    elapsed = time.time() - start
    print(f"XTTS done in {elapsed:.0f}s → {out_path}", flush=True)
    return True

def gtts_fallback(text, out_path):
    from gtts import gTTS
    print(f"Fallback: gTTS {len(text)} chars...", flush=True)
    tts = gTTS(text, lang='it')
    tts.save(out_path)
    print(f"gTTS done → {out_path}", flush=True)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    text, speaker, out = sys.argv[1], sys.argv[2], sys.argv[3]
    # Also support reading text from file
    if text.endswith(".txt"):
        text = open(text).read().strip()

    # Default: gTTS (fast, ~20s). Use XTTS only if --xtts flag or TTS_FORCE=1
    use_xtts = os.environ.get("TTS_FORCE", "0") == "1" or len(sys.argv) > 4 and sys.argv[4] == "--xtts"
    if use_xtts:
        try:
            xtts_generate(text, speaker, out)
            sys.exit(0)
        except Exception as e:
            print(f"XTTS failed: {e}. Falling back to gTTS.", flush=True)
    gtts_fallback(text, out)
