"""Generate sample readings with designed (not cloned) voices using Qwen3-TTS VoiceDesign.

Each voice is described in words; the model invents a matching voice, so no real person's
voice is copied. Writes a clean and a "vintage 1950s radio" MP3 of each voice to voice-samples/.
"""
import os
import subprocess

import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, sosfilt
from qwen_tts import Qwen3TTSModel

TEXT = (
    "The Lord is my shepherd; I shall not want. He maketh me to lie down in green pastures: "
    "he leadeth me beside the still waters. He restoreth my soul: he leadeth me in the paths "
    "of righteousness for his name's sake."
)

VOICES = {
    "1_oxford_professor": (
        "An elderly English gentleman in his late sixties, an Oxford professor of the 1950s. "
        "Deep, warm, slightly gravelly baritone with crisp, old-fashioned BBC Received Pronunciation. "
        "Speaks slowly and thoughtfully with gentle gravitas, as if reading scripture aloud in a college chapel."
    ),
    "2_cambridge_don": (
        "A kindly retired Cambridge don of about seventy. Soft-spoken and mellow, with a refined, "
        "cultured 1950s English accent. Unhurried and reverent, with a slightly aged, breathy texture to the voice."
    ),
    "3_bbc_broadcaster": (
        "A distinguished older British broadcaster from 1950s BBC radio. Rich, resonant bass voice, "
        "precise old-fashioned diction, measured pace, solemn and dignified."
    ),
    "4_clergyman_scholar": (
        "An elderly Anglican clergyman and scholar in his seventies. Gentle, wise and fatherly, "
        "with a cultured English accent from the 1950s. Slow, deliberate, warm reading of the King James Bible."
    ),
}

OUT = "voice-samples"


def vintage(audio, sr, seed=0):
    """Subtle 1950s radio character: narrower band, gentle saturation, faint hiss and crackle."""
    rng = np.random.default_rng(seed)
    sos = butter(4, [120, 5500], btype="bandpass", fs=sr, output="sos")
    a = sosfilt(sos, audio)
    a = np.tanh(a * 1.6) / np.tanh(1.6)
    hiss = sosfilt(butter(2, [1500, 7000], btype="bandpass", fs=sr, output="sos"), rng.normal(0, 1, len(a)))
    a = a + hiss / np.abs(hiss).max() * 0.006
    crackle = np.zeros(len(a))
    idx = rng.integers(0, len(a), size=int(len(a) / sr * 6))
    crackle[idx] = rng.uniform(-0.05, 0.05, len(idx))
    a = a + sosfilt(butter(2, 3000, btype="highpass", fs=sr, output="sos"), crackle)
    return a


def save_mp3(audio, sr, name):
    audio = np.asarray(audio, dtype=np.float32)
    audio = audio / max(1e-6, float(np.abs(audio).max())) * 0.9
    wav = f"{OUT}/{name}.wav"
    sf.write(wav, audio, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "96k", f"{OUT}/{name}.mp3"], check=True)
    os.remove(wav)


def main():
    os.makedirs(OUT, exist_ok=True)
    torch.manual_seed(7)
    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=torch.float32
    )
    for name, desc in VOICES.items():
        torch.manual_seed(7)
        wavs, sr = model.generate_voice_design(text=TEXT, language="English", instruct=desc)
        audio = np.asarray(wavs[0], dtype=np.float32)
        save_mp3(audio, sr, f"{name}_clean")
        save_mp3(vintage(audio, sr), sr, f"{name}_vintage")
        print("done", name, round(len(audio) / sr, 1), "s", flush=True)
    with open(f"{OUT}/DESCRIPTIONS.md", "w") as f:
        f.write("# Voice sample descriptions\n\nModel: Qwen3-TTS-12Hz-1.7B-VoiceDesign (Apache-2.0). "
                "Text: Psalm 23:1-3 (KJV).\n\n")
        for name, desc in VOICES.items():
            f.write(f"- **{name}**: {desc}\n")


if __name__ == "__main__":
    main()
