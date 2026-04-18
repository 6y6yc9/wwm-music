"""
Analyze optimal transposition for a MIDI file to fit into C Major (White Keys).
"""
import mido
import os
import sys

def get_best_transposition(midi_path):
    try:
        mid = mido.MidiFile(midi_path)
    except Exception as e:
        print(f"Error loading MIDI: {e}")
        return

    # Collect all notes
    notes = []
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                notes.append(msg.note)
    
    if not notes:
        print("No notes found.")
        return

    print(f"Total notes: {len(notes)}")
    
    # C Major / A Minor allowed notes (White keys)
    # 0=C, 2=D, 4=E, 5=F, 7=G, 9=A, 11=B
    white_keys = {0, 2, 4, 5, 7, 9, 11}
    
    results = []
    
    # Try all 12 semitone shifts
    for shift in range(12):
        in_key_count = 0
        for n in notes:
            transposed_note = (n + shift) % 12
            if transposed_note in white_keys:
                in_key_count += 1
        
        score = in_key_count / len(notes)
        results.append((shift, score, in_key_count))
        
    # Sort by score
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop 3 Transpositions to fit C Major (White keys):")
    for shift, score, count in results[:3]:
        print(f"Shift +{shift}: {score*100:.1f}% fit ({count}/{len(notes)} notes)")
        
    return results[0][0]

if __name__ == "__main__":
    # Test on the existing Bad Guy midi if available
    path = os.path.join("downloads", "Billie Eilish  - bad guy_basic_pitch.mid")
    if os.path.exists(path):
        print(f"Analyzing: {path}")
        best_shift = get_best_transposition(path)
        print(f"\nRecommended Transposition: +{best_shift} semitones")
    else:
        print(f"File not found: {path}")
