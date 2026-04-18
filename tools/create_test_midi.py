import mido
from mido import Message, MidiFile, MidiTrack

mid = MidiFile()
track = MidiTrack()
mid.tracks.append(track)

# C Major Scale (3 Octaves)
# Octave 3 (Low)
notes_low = [48, 50, 52, 53, 55, 57, 59] # C3-B3
# Octave 4 (Mid)
notes_mid = [60, 62, 64, 65, 67, 69, 71] # C4-B4
# Octave 5 (High)
notes_high = [72, 74, 76, 77, 79, 81, 83] # C5-B5

all_notes = notes_low + notes_mid + notes_high

track.append(Message('program_change', program=0, time=0))

for note in all_notes:
    track.append(Message('note_on', note=note, velocity=64, time=0))
    track.append(Message('note_off', note=note, velocity=64, time=240)) # 240 ticks = 0.25s at 120BPM (approx)

mid.save('test_scale.mid')
print("Created test_scale.mid")
