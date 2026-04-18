import mido
import os
import sys

midi_path = os.path.join("downloads", "Billie Eilish  - bad guy_basic_pitch.mid")
mid = mido.MidiFile(midi_path)
print(f"Tracks: {len(mid.tracks)}")
print(f"Ticks/beat: {mid.ticks_per_beat}")

for i, t in enumerate(mid.tracks):
    notes = sum(1 for m in t if m.type == 'note_on' and m.velocity > 0)
    print(f"Track {i}: messages={len(t)}, notes={notes}")

pitches = [m.note for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
if pitches:
    print(f"\nPitch range: {min(pitches)} - {max(pitches)}")
    print(f"Average pitch: {sum(pitches)/len(pitches):.1f}")
    print(f"Total notes: {len(pitches)}")
    
    # Count chromatic vs diatonic
    diatonic = {0, 2, 4, 5, 7, 9, 11}  # C major scale degrees
    chromatic_count = sum(1 for p in pitches if p % 12 not in diatonic)
    print(f"\nChromatic notes (sharps/flats): {chromatic_count} ({chromatic_count*100//len(pitches)}%)")
    print(f"Diatonic notes (C major): {len(pitches)-chromatic_count} ({(len(pitches)-chromatic_count)*100//len(pitches)}%)")
    
    # Count notes that have no mapping in current converter
    key_mapping = {48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83}
    mapped = 0
    unmapped = 0
    for p in pitches:
        # Apply same transposition logic
        shifted = p + int(65 - sum(pitches)/len(pitches))
        while shifted < 48: shifted += 12
        while shifted > 83: shifted -= 12
        if shifted in key_mapping:
            mapped += 1
        else:
            unmapped += 1
    print(f"\nWith current converter (after transpose):")
    print(f"  Mapped to keys: {mapped} ({mapped*100//len(pitches)}%)")
    print(f"  LOST (no mapping): {unmapped} ({unmapped*100//len(pitches)}%)")
