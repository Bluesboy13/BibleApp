"""Round 2: British accent + natural delivery + older voice. Nothing here copies a real person.

A) Voice design with accent-first descriptions (Qwen3-TTS VoiceDesign).
B) Accent transfer: make a British reading with Kokoro (a synthetic British voice), deepen it
   to sound older, then have Qwen3-TTS Base re-speak new text in that voice. Qwen adds the
   natural delivery while keeping the British accent.
Writes voice-samples/round2/*.mp3 (+ the Kokoro reference clips used, for comparison).
"""
import os
import subprocess
import urllib.request

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample
from qwen_tts import Qwen3TTSModel

OUT = "voice-samples/round2"
TEXT = (
    "The Lord is my shepherd; I shall not want. He maketh me to lie down in green pastures: "
    "he leadeth me beside the still waters. He restoreth my soul: he leadeth me in the paths "
    "of righteousness for his name's sake."
)
REF_TEXT = (
    "In the beginning God created the heaven and the earth. And the earth was without form, and void; "
    "and darkness was upon the face of the deep."
)
DESIGNS = {
    "A1_design_rp_professor": (
        "British English accent. An elderly Englishman from southern England speaking in traditional "
        "Received Pronunciation, the upper-class accent of 1950s Oxford and the BBC: non-rhotic, long 'ah' "
        "vowels, clipped consonants. Around seventy years old, deep and slightly gravelly, slow and "
        "thoughtful, reading scripture with quiet gravitas."
    ),
    "A2_design_english_vicar": (
        "Speak with a strong, posh English accent, like an old Church of England vicar in a village church "
        "in the 1950s. Elderly, warm, deep and gentle; very British pronunciation, never American. "
        "Unhurried, reverent pace."
    ),
}
KOKORO_REFS = {"B1_clone_daniel": ("bm_daniel", 0.92), "B2_clone_george": ("bm_george", 0.93),
               "B3_clone_lewis": ("bm_lewis", 0.94)}


def save_mp3(audio, sr, name):
    audio = np.asarray(audio, dtype=np.float32)
    audio = audio / max(1e-6, float(np.abs(audio).max())) * 0.9
    wav = f"{OUT}/{name}.wav"
    sf.write(wav, audio, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "96k",
                    f"{OUT}/{name}.mp3"], check=True)
    return wav


def kokoro_refs():
    from kokoro_onnx import Kokoro
    base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
    for f in ["kokoro-v1.0.onnx", "voices-v1.0.bin"]:
        if not os.path.exists(f):
            urllib.request.urlretrieve(base + f, f)
    k = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
    refs = {}
    for name, (voice, deepen) in KOKORO_REFS.items():
        a, sr = k.create(REF_TEXT, voice=voice, speed=0.92, lang="en-gb")
        a = resample(a, int(len(a) / deepen)).astype(np.float32)   # lower pitch and voice size a little
        refs[name] = (save_mp3(a, sr, f"{name}_reference"), sr)
    return refs


def main():
    os.makedirs(OUT, exist_ok=True)
    refs = kokoro_refs()

    design = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=torch.float32)
    for name, desc in DESIGNS.items():
        torch.manual_seed(11)
        wavs, sr = design.generate_voice_design(text=TEXT, language="English", instruct=desc)
        save_mp3(wavs[0], sr, name)
        print("done", name, flush=True)
    del design

    base = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cpu", dtype=torch.float32)
    for name, (ref_wav, _) in refs.items():
        torch.manual_seed(11)
        wavs, sr = base.generate_voice_clone(text=TEXT, language="English", ref_audio=ref_wav, ref_text=REF_TEXT)
        save_mp3(wavs[0], sr, name)
        print("done", name, flush=True)

    for f in os.listdir(OUT):
        if f.endswith(".wav"):
            os.remove(os.path.join(OUT, f))


if __name__ == "__main__":
    main()
