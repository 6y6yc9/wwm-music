"""
Audio Transcriber Module
Transcribes audio files to MIDI using Basic Pitch with tunable parameters.

Key improvements over default Basic Pitch:
- Adjustable onset/frame thresholds for note detection quality
- Minimum note length filtering
- Minimum frequency cutoff option
- Preset modes for different audio types
"""

import os
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH


# Preset configurations for different audio types
# NOTE: For in-game instrument playback, we need ENOUGH notes to sound
# recognizable. Too few notes = sparse, unrecognizable. Too many = noise.
PRESETS = {
    "balanced": {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 30,
        "minimum_frequency": None,        # Keep bass — it's often THE melody
        "description": "Balanced (recommended) — recognizable melody"
    },
    "clean": {
        "onset_threshold": 0.55,
        "frame_threshold": 0.4,
        "minimum_note_length": 80,
        "minimum_frequency": None,
        "description": "Clean — fewer ghost notes, keeps bass"
    },
    "melody_only": {
        "onset_threshold": 0.55,
        "frame_threshold": 0.45,
        "minimum_note_length": 100,
        "minimum_frequency": 130.0,       # ~C3 — cut sub-bass
        "description": "Melody only — no bass, for piano/guitar solos"
    },
    "full": {
        "onset_threshold": 0.4,
        "frame_threshold": 0.25,
        "minimum_note_length": 20,
        "minimum_frequency": None,
        "description": "Full — maximum notes, may include noise"
    },
    "vocal": {
        "onset_threshold": 0.45,
        "frame_threshold": 0.4,
        "minimum_note_length": 100,
        "minimum_frequency": 180.0,       # ~F#3 — vocals are above bass
        "description": "Vocal — best for singing tracks"
    },
}

# Default preset for YouTube import
DEFAULT_PRESET = "balanced"


def transcribe_audio(audio_path, output_dir=None, preset="balanced",
                     onset_threshold=None, frame_threshold=None,
                     minimum_note_length=None, minimum_frequency=None):
    """
    Transcribe audio file to MIDI using Basic Pitch with tunable parameters.
    
    Args:
        audio_path: Path to WAV/MP3 file
        output_dir: Directory to save MIDI (default: same as audio)
        preset: Preset name ('balanced', 'clean', 'melody_only', 'full', 'vocal')
        onset_threshold: Override onset detection sensitivity (0.0-1.0, higher = fewer notes)
        frame_threshold: Override frame detection threshold (0.0-1.0, higher = fewer notes)
        minimum_note_length: Override minimum note duration in ms
        minimum_frequency: Override minimum frequency in Hz (filters bass)
    
    Returns:
        Path to the generated .mid file, or None on failure.
    """
    if output_dir is None:
        output_dir = os.path.dirname(audio_path)
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Load preset and apply overrides
    config = PRESETS.get(preset, PRESETS[DEFAULT_PRESET]).copy()
    if onset_threshold is not None:
        config["onset_threshold"] = onset_threshold
    if frame_threshold is not None:
        config["frame_threshold"] = frame_threshold
    if minimum_note_length is not None:
        config["minimum_note_length"] = minimum_note_length
    if minimum_frequency is not None:
        config["minimum_frequency"] = minimum_frequency
    
    print(f"Transcribing {os.path.basename(audio_path)}...")
    print(f"  Preset: {preset} - {config.get('description', '')}")
    print(f"  Onset: {config['onset_threshold']}, Frame: {config['frame_threshold']}")
    print(f"  Min note: {config['minimum_note_length']}ms", end="")
    if config['minimum_frequency']:
        print(f", Min freq: {config['minimum_frequency']}Hz")
    else:
        print(", Min freq: off")
    
    # Use predict() for full control
    model_output, midi_data, note_events = predict(
        audio_path,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=config["onset_threshold"],
        frame_threshold=config["frame_threshold"],
        minimum_note_length=config["minimum_note_length"],
        minimum_frequency=config["minimum_frequency"],
    )
    
    # Construct MIDI output path
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    midi_path = os.path.join(output_dir, f"{base_name}_basic_pitch.mid")
    
    # Save MIDI data
    midi_data.write(midi_path)
    
    # Print stats
    note_count = len(note_events)
    if note_count > 0:
        pitches = [n[2] for n in note_events]
        print(f"\n  >> {note_count} notes detected (MIDI pitch {min(pitches):.0f}-{max(pitches):.0f}, avg {sum(pitches)/len(pitches):.0f})")
    else:
        print(f"\n  >> No notes detected! Try 'full' preset.")
    
    if os.path.exists(midi_path):
        return midi_path
    else:
        return None


def transcribe_with_separation(audio_path, output_dir=None, stem_mode="vocals",
                                preset="balanced", **kwargs):
    """
    Transcribe audio with optional Demucs source separation.
    
    This is the recommended entry point for YouTube imports.
    It separates audio into stems first, then transcribes the clean stem(s).
    
    Args:
        audio_path: Path to WAV file
        output_dir: Directory for output files
        stem_mode: Source separation mode ('vocals', 'melody', 'full_no_drums', 'no_separation')
        preset: Basic Pitch preset name
        **kwargs: Additional arguments passed to transcribe_audio()
    
    Returns:
        Path to generated .mid file, or None on failure
    """
    if output_dir is None:
        output_dir = os.path.dirname(audio_path)
    
    # If no separation requested, use standard transcription
    if stem_mode == "no_separation":
        print("Stem mode: no_separation — using full mix")
        return transcribe_audio(audio_path, output_dir=output_dir, preset=preset, **kwargs)
    
    # Try to separate audio
    try:
        from audio_separator import separate_audio, merge_stem_wavs
    except ImportError:
        print("WARNING: audio_separator module not available. Using full mix.")
        return transcribe_audio(audio_path, output_dir=output_dir, preset=preset, **kwargs)
    
    stems = separate_audio(audio_path, output_dir=os.path.join(output_dir, "stems"),
                           stem_mode=stem_mode)
    
    if stems is None:
        print("Separation failed or skipped. Falling back to full mix.")
        return transcribe_audio(audio_path, output_dir=output_dir, preset=preset, **kwargs)
    
    # If single stem, transcribe directly
    if len(stems) == 1:
        stem_path = list(stems.values())[0]
        stem_name = list(stems.keys())[0]
        print(f"\nTranscribing separated {stem_name} stem...")
        return transcribe_audio(stem_path, output_dir=output_dir, preset=preset, **kwargs)
    
    # Multiple stems: merge then transcribe
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    merged_path = os.path.join(output_dir, f"{base_name}_{stem_mode}_merged.wav")
    
    merged = merge_stem_wavs(stems, merged_path)
    if merged is None:
        print("Merge failed. Falling back to first stem.")
        merged = list(stems.values())[0]
    
    print(f"\nTranscribing merged {stem_mode} audio...")
    return transcribe_audio(merged, output_dir=output_dir, preset=preset, **kwargs)


def get_preset_names():
    """Return list of available preset names with descriptions."""
    return {name: cfg["description"] for name, cfg in PRESETS.items()}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
        preset = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PRESET
        stem_mode = sys.argv[3] if len(sys.argv) > 3 else "no_separation"
        
        print(f"Available presets: {list(PRESETS.keys())}")
        print(f"Using preset: {preset}")
        print(f"Stem mode: {stem_mode}\n")
        
        midi = transcribe_with_separation(path, preset=preset, stem_mode=stem_mode)
        if midi:
            print(f"\nMIDI saved to: {midi}")
        else:
            print("\nFailed to transcribe!")
    else:
        print("Usage: python audio_transcriber.py <WAV_FILE> [preset] [stem_mode]")
        print(f"Presets: {list(PRESETS.keys())}")
        print(f"Stem modes: vocals, melody, full_no_drums, no_separation")
