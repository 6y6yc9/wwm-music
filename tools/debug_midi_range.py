import mido
import sys
import os

if len(sys.argv) > 1:
    filepath = sys.argv[1]
else:
    filepath = os.path.join(os.path.dirname(__file__), "..", "melodies", "Pirates of the Caribbean - He's a Pirate (1).mid")

mid = mido.MidiFile(filepath)

def analyze_track(track):
    pitches = []
    for msg in track:
        if msg.type == 'note_on' and msg.velocity > 0:
            pitches.append(msg.note)
    return pitches

all_pitches = []
print(f"File: {filepath}")

for i, track in enumerate(mid.tracks):
    pitches = analyze_track(track)
    if not pitches: continue
    
    min_p = min(pitches)
    max_p = max(pitches)
    range_st = max_p - min_p
    avg_p = sum(pitches) / len(pitches)
    
    all_pitches.extend(pitches)
    
    print(f"Track {i} ({track.name}): {len(pitches)} notes")
    print(f"  Range: {min_p}-{max_p} ({range_st} semitones)")
    print(f"  Avg Pitch: {avg_p:.1f}")

# Combined
if all_pitches:
    min_all = min(all_pitches)
    max_all = max(all_pitches)
    range_all = max_all - min_all
    
    print("\nCOMBINED:")
    print(f"  Total Range: {min_all}-{max_all} ({range_all} semitones)")
    print(f"  Limit: 36 semitones (3 octaves)")
    
    excess = range_all - 36
    if excess > 0:
        print(f"  ⚠️ EXCEEDS LIMIT by {excess} semitones!")
        print("  Result: Bass notes will be wrapped up and clash with melody.")
