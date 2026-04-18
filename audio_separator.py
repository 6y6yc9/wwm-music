"""
Audio Source Separator Module
Separates audio into stems (vocals, drums, bass, other) using Demucs
for cleaner transcription.

Dependencies: pip install demucs
"""

import os
import subprocess
import sys
from typing import Dict, Optional


# Available separation modes
STEM_MODES = {
    "vocals": {
        "stems": ["vocals"],
        "description": "🎤 Vocal Only — best for songs with clear melody/singing",
    },
    "melody": {
        "stems": ["vocals", "other"],
        "description": "🎵 Melody (Vocals+Instruments) — vocals + synths/guitar/keys",
    },
    "full_no_drums": {
        "stems": ["vocals", "bass", "other"],
        "description": "🎼 Full (No Drums) — everything except percussion",
    },
    "no_separation": {
        "stems": [],
        "description": "⚡ Fast (No Separation) — original behavior, full mix",
    },
}


def is_demucs_available() -> bool:
    """Check if demucs is installed."""
    try:
        import demucs  # noqa: F401
        return True
    except ImportError:
        return False


def separate_audio(
    wav_path: str,
    output_dir: str = None,
    model: str = "htdemucs",
    stem_mode: str = "vocals",
) -> Optional[Dict[str, str]]:
    """
    Separate audio into stems using Demucs.

    Args:
        wav_path: Path to input WAV file
        output_dir: Directory to save stems (default: alongside input file)
        model: Demucs model to use (htdemucs = best quality 4-stem)
        stem_mode: Which stems to keep ('vocals', 'melody', 'full_no_drums')

    Returns:
        Dict of stem name -> file path, or None on failure.
        Example: {"vocals": "/path/to/vocals.wav", "other": "/path/to/other.wav"}
    """
    if stem_mode == "no_separation":
        return None  # Caller should fall back to original behavior

    if not is_demucs_available():
        print("WARNING: demucs not installed. Run 'pip install demucs'.")
        print("Falling back to full-mix transcription.")
        return None

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(wav_path), "stems")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(wav_path))[0]

    # Check if stems already exist (avoid re-processing)
    stem_dir = os.path.join(output_dir, model, base_name)
    mode_config = STEM_MODES.get(stem_mode, STEM_MODES["vocals"])
    requested_stems = mode_config["stems"]

    if os.path.exists(stem_dir):
        existing = {}
        all_exist = True
        for stem_name in requested_stems:
            stem_path = os.path.join(stem_dir, f"{stem_name}.wav")
            if os.path.exists(stem_path):
                existing[stem_name] = stem_path
            else:
                all_exist = False
                break

        if all_exist and existing:
            print(f"Using cached stems from: {stem_dir}")
            return existing

    # Run Demucs separation
    print(f"Separating audio with Demucs ({model})...")
    print(f"  Input: {os.path.basename(wav_path)}")
    print(f"  Mode: {stem_mode} -> stems: {requested_stems}")

    try:
        # Use subprocess to run demucs CLI (most reliable method)
        cmd = [
            sys.executable, "-m", "demucs",
            "--out", output_dir,
            "-n", model,
            "--mp3",  # Disable (we want WAV output by default)
            wav_path
        ]

        # Remove --mp3 flag — we want WAV
        cmd = [
            sys.executable, "-m", "demucs",
            "--out", output_dir,
            "-n", model,
            wav_path
        ]

        print(f"  Running: {' '.join(cmd[:5])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for long tracks
        )

        if result.returncode != 0:
            print(f"Demucs error: {result.stderr[:500]}")
            return None

        # Collect stem paths
        stems = {}
        for stem_name in requested_stems:
            stem_path = os.path.join(stem_dir, f"{stem_name}.wav")
            if os.path.exists(stem_path):
                stems[stem_name] = stem_path
                size_mb = os.path.getsize(stem_path) / (1024 * 1024)
                print(f"  ✓ {stem_name}: {size_mb:.1f} MB")
            else:
                print(f"  ✗ {stem_name}: not found at {stem_path}")

        if not stems:
            print("WARNING: No stems produced by Demucs!")
            return None

        print(f"Separation complete: {len(stems)} stems ready")
        return stems

    except subprocess.TimeoutExpired:
        print("ERROR: Demucs timed out (>10 minutes). Try a shorter audio file.")
        return None
    except Exception as e:
        print(f"ERROR: Demucs separation failed: {e}")
        return None


def merge_stem_wavs(stem_paths: Dict[str, str], output_path: str) -> Optional[str]:
    """
    Merge multiple stem WAV files into a single WAV file.
    Uses simple mixing (addition + normalization).

    Args:
        stem_paths: Dict of stem name -> WAV file path
        output_path: Where to save the merged WAV

    Returns:
        Path to merged WAV, or None on failure
    """
    try:
        import numpy as np
        import wave

        if len(stem_paths) == 1:
            # Only one stem — just return it directly
            return list(stem_paths.values())[0]

        # Read all stems
        arrays = []
        params = None

        for name, path in stem_paths.items():
            with wave.open(path, 'rb') as wf:
                if params is None:
                    params = wf.getparams()
                frames = wf.readframes(wf.getnframes())
                dtype = np.int16 if wf.getsampwidth() == 2 else np.int32
                arr = np.frombuffer(frames, dtype=dtype).astype(np.float64)
                arrays.append(arr)

        if not arrays or params is None:
            return None

        # Mix: pad shorter arrays to max length
        max_len = max(len(a) for a in arrays)
        mixed = np.zeros(max_len, dtype=np.float64)
        for arr in arrays:
            mixed[:len(arr)] += arr

        # Normalize to prevent clipping
        peak = np.max(np.abs(mixed))
        if peak > 0:
            target_peak = 32767 if params.sampwidth == 2 else 2147483647
            mixed = mixed * (target_peak * 0.95 / peak)

        dtype_out = np.int16 if params.sampwidth == 2 else np.int32
        mixed = mixed.astype(dtype_out)

        # Write merged WAV
        with wave.open(output_path, 'wb') as wf:
            wf.setparams(params)
            wf.writeframes(mixed.tobytes())

        print(f"Merged {len(stem_paths)} stems -> {os.path.basename(output_path)}")
        return output_path

    except Exception as e:
        print(f"ERROR: Merge failed: {e}")
        # Fallback: return first stem
        return list(stem_paths.values())[0]


def get_stem_mode_descriptions() -> Dict[str, str]:
    """Return stem mode names with descriptions for UI."""
    return {key: cfg["description"] for key, cfg in STEM_MODES.items()}


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1:
        path = _sys.argv[1]
        mode = _sys.argv[2] if len(_sys.argv) > 2 else "vocals"

        print(f"Available modes: {list(STEM_MODES.keys())}")
        print(f"Using mode: {mode}\n")

        result = separate_audio(path, stem_mode=mode)
        if result:
            print(f"\nStems ready: {result}")
        else:
            print("\nSeparation failed or skipped.")
    else:
        print("Usage: python audio_separator.py <WAV_FILE> [stem_mode]")
        print(f"Modes: {list(STEM_MODES.keys())}")
