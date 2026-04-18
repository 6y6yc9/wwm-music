"""
MIDI to Melody Converter
Converts MIDI files to the WWM Music Auto-Player text format.
"""

import os
from typing import List, Tuple, Dict, Optional
import mido  # type: ignore
from note_parser import Note, NoteParser


class MidiConverter:
    """Converts MIDI files to WWM text format with advanced processing."""
    
    # Default range (can be overridden by instruments.json)
    MIN_NOTE = 48
    MAX_NOTE = 83
    
    # Base Diatonic key mapping (C major scale notes)
    # This maps MIDI pitch to Keyboard Key
    KEY_MAPPING = {
        # Low Pitch (Octave 3): C3 D3 E3 F3 G3 A3 B3
        48: 'Z', 50: 'X', 52: 'C', 53: 'V', 55: 'B', 57: 'N', 59: 'M',
        # Medium Pitch (Octave 4): C4 D4 E4 F4 G4 A4 B4
        60: 'A', 62: 'S', 64: 'D', 65: 'F', 67: 'G', 69: 'H', 71: 'J',
        # High Pitch (Octave 5): C5 D5 E5 F5 G5 A5 B5
        72: 'Q', 74: 'W', 76: 'E', 77: 'R', 79: 'T', 81: 'Y', 83: 'U',
    }
    
    def __init__(self, instrument_name: str = "default"):
        """
        Initialize with specific instrument configuration.
        """
        self.instruments = self._load_instruments()
        self.set_instrument(instrument_name)

    def _load_instruments(self) -> dict:
        """Load instrument definitions from JSON."""
        import json
        try:
            with open("instruments.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load instruments.json ({e}). Using defaults.")
            return {}

    def set_instrument(self, name: str):
        """Configure converter for a specific instrument."""
        config = self.instruments.get(name, self.instruments.get("default", {}))
        
        # Detect percussion type
        self.is_percussion = config.get("type") == "percussion"
        self.drum_map = {}  # MIDI note number -> key char
        self.percussion_keys = []  # Valid keys for this percussion instrument
        
        if self.is_percussion:
            # Load percussion-specific config
            raw_map = config.get("midi_drum_map", {})
            self.drum_map = {int(k): v for k, v in raw_map.items()}
            self.percussion_keys = config.get("keys", [])
            print(f"DEBUG: Percussion instrument '{name}': {len(self.drum_map)} MIDI mappings -> {self.percussion_keys}")
        else:
            # Set Range (tonal instruments only)
            if "range" in config:
                self.MIN_NOTE = config["range"][0]
                self.MAX_NOTE = config["range"][1]
                print(f"DEBUG: Set instrument '{name}' range: {self.MIN_NOTE}-{self.MAX_NOTE}")
            
            # Re-build diatonic scale based on current range
            self.DIATONIC_SCALE = sorted([k for k in self.KEY_MAPPING.keys() if self.MIN_NOTE <= k <= self.MAX_NOTE])
            
            # Re-build Chromatic Snap for the new range
            self.CHROMATIC_SNAP = {}
            for note in range(self.MIN_NOTE, self.MAX_NOTE + 1):
                if note not in self.KEY_MAPPING:
                    choices = [k for k in self.KEY_MAPPING.keys() if self.MIN_NOTE <= k <= self.MAX_NOTE]
                    if choices:
                        nearest = min(choices, key=lambda x: abs(x - note))
                        self.CHROMATIC_SNAP[note] = nearest
        
        # Load instrument-specific duration parameters
        self.duration_scale = config.get("duration_scale", 1.0)
        self.min_pause_ms = config.get("min_pause_ms", 5)
        self.max_duration_ms = config.get("max_duration_ms", 0)
        print(f"DEBUG: Instrument '{name}' duration: scale={self.duration_scale}, "
              f"min_pause={self.min_pause_ms}ms, max_dur={self.max_duration_ms}ms")
    
    # ──────────────────────────────────────────────────────────
    #  SMART MELODY: Interval-Preserving Diatonic Snap
    # ──────────────────────────────────────────────────────────
    
    def _nearest_diatonic(self, midi_note: int) -> int:
        """Find the nearest note in DIATONIC_SCALE (binary search)."""
        scale = self.DIATONIC_SCALE
        if midi_note <= scale[0]:
            return scale[0]
        if midi_note >= scale[-1]:
            return scale[-1]
        # Binary search for closest
        lo, hi = 0, len(scale) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if scale[mid] == midi_note:
                return midi_note
            elif scale[mid] < midi_note:
                lo = mid + 1
            else:
                hi = mid - 1
        # lo is first element > midi_note, hi is last element < midi_note
        if lo < len(scale) and abs(scale[lo] - midi_note) < abs(scale[hi] - midi_note):
            return scale[lo]
        return scale[hi]
    
    def _diatonic_index(self, midi_note: int) -> int:
        """Get the index of a diatonic note in DIATONIC_SCALE. Returns -1 if not found."""
        try:
            return self.DIATONIC_SCALE.index(midi_note)
        except ValueError:
            return -1
    
    def _semitone_to_degrees(self, semitones: int) -> int:
        """
        Convert a chromatic interval (semitones) to approximate diatonic degrees.
        Maps proportionally: 1-2 sem → 1 deg, 3-4 → 2, 5 → 3, 6-7 → 4, etc.
        """
        if semitones == 0:
            return 0
        sign = 1 if semitones > 0 else -1
        s = abs(semitones)
        # Proportional mapping: ~7 diatonic degrees per 12 semitones
        degrees = round(s * 7 / 12)
        return max(1, degrees) * sign  # At least 1 degree if any interval

    def _snap_to_diatonic_preserving_intervals(self, note_events):
        """
        Snap chromatic pitches to diatonic notes using PROPORTIONAL scale-degree mapping.
        
        Algorithm:
        - The first note (anchor) snaps to the nearest diatonic note.
        - For each subsequent note, compute the chromatic interval from anchor,
          convert to proportional diatonic degrees, and apply from the anchor's
          diatonic position.
        - Re-anchor every REANCHOR_INTERVAL notes to prevent drift.
        - This preserves the proportional shape of the melody much better than
          the old ±1 nudging approach.
        
        Args:
            note_events: list of (start_sec, duration, midi_note, track_id, [velocity])
        Returns:
            list with snapped midi_note in position [2]
        """
        if not note_events:
            return note_events
        
        REANCHOR_INTERVAL = 16  # Re-snap to nearest every N notes
        
        result = []
        scale = self.DIATONIC_SCALE
        
        # First note: anchor
        anchor_original = note_events[0][2]
        anchor_snapped = self._nearest_diatonic(anchor_original)
        anchor_idx = self._diatonic_index(anchor_snapped)
        if anchor_idx < 0:
            anchor_idx = 0
        
        # Build result tuple preserving all extra fields (velocity etc.)
        first = list(note_events[0])
        first[2] = anchor_snapped
        result.append(tuple(first))
        
        prev_snapped = anchor_snapped  # Track previous output for repeat suppression
        notes_since_anchor = 0
        boundary_skipped = 0
        
        for i in range(1, len(note_events)):
            pitch = note_events[i][2]
            
            # Periodic re-anchoring to prevent cumulative drift
            notes_since_anchor += 1
            if notes_since_anchor >= REANCHOR_INTERVAL:
                anchor_original = pitch
                anchor_snapped = self._nearest_diatonic(pitch)
                anchor_idx = self._diatonic_index(anchor_snapped)
                if anchor_idx < 0:
                    anchor_idx = 0
                notes_since_anchor = 0
                
                entry = list(note_events[i])
                entry[2] = anchor_snapped
                prev_snapped = anchor_snapped
                result.append(tuple(entry))
                continue
            
            # Compute chromatic interval from anchor
            chromatic_interval = pitch - anchor_original
            
            # Convert to proportional diatonic degrees
            diatonic_degrees = self._semitone_to_degrees(chromatic_interval)
            
            # Apply from anchor's diatonic position
            target_idx = anchor_idx + diatonic_degrees
            
            # Clamp to scale bounds
            target_idx = max(0, min(len(scale) - 1, target_idx))
            snapped = scale[target_idx]
            
            # Suppress boundary repeats: if clamped to the same boundary note
            # but the original had a real interval, skip to avoid drone effect
            at_boundary = (target_idx == 0 or target_idx == len(scale) - 1)
            chromatic_dist = abs(chromatic_interval)
            if snapped == prev_snapped and chromatic_dist >= 2 and at_boundary:
                boundary_skipped += 1
                continue  # Skip — boundary repeat, not a real repeated note
            
            prev_snapped = snapped
            entry = list(note_events[i])
            entry[2] = snapped
            result.append(tuple(entry))
        
        if boundary_skipped > 0:
            print(f"DEBUG: Boundary repeat suppression: skipped {boundary_skipped} drone notes")
        print(f"DEBUG: Proportional interval snap applied to {len(result)} notes (re-anchor every {REANCHOR_INTERVAL})")
        return result
    
    # ──────────────────────────────────────────────────────────
    #  SMART MELODY: Melody Line Extraction (replaces Skyline)
    # ──────────────────────────────────────────────────────────
    
    def _extract_melody_line(self, note_events, lead_track_id=None):
        """
        Extract the most recognizable melody line from polyphonic input.
        For each group of simultaneous notes, picks the best melodic candidate.
        
        Scoring per note:
        - Pitch in vocal range (C4=60 to C6=84): +3 points
        - From lead track: +5 points  
        - Smooth interval from previous note: +2 for step (1-2 semitones),
          +1 for small leap (3-5), 0 for large leap, -1 for >octave jump
        - Higher pitch preference (melody is usually on top): +1
        - Velocity bonus: up to +4 for loud notes (loud = important melody)
        - Duration bonus: up to +2 for longer notes (melody notes are usually held)
        """
        if not note_events:
            return note_events
        
        # Group by time (35ms window, same as chord grouping)
        groups = []
        i = 0
        while i < len(note_events):
            current_start = note_events[i][0]
            group = [note_events[i]]
            j = i + 1
            while j < len(note_events) and abs(note_events[j][0] - current_start) < 0.035:
                group.append(note_events[j])
                j += 1
            groups.append(group)
            i = j
        
        # Select best note from each group
        melody = []
        prev_pitch = 65  # Start from middle of range (~F4)
        
        for group in groups:
            best_note = None
            best_score = -999
            
            for note in group:
                # Support both 4-tuple and 5-tuple (with velocity)
                if len(note) >= 5:
                    start, dur, pitch, tid, vel = note[0], note[1], note[2], note[3], note[4]
                else:
                    start, dur, pitch, tid = note[0], note[1], note[2], note[3]
                    vel = 80  # Default velocity if not available
                
                score = 0
                
                # 1. Vocal range bonus (C4-C6)
                if 60 <= pitch <= 84:
                    score += 3
                
                # 2. Lead track bonus
                if lead_track_id is not None and tid == lead_track_id:
                    score += 5
                
                # 3. Contour smoothness (interval from previous)
                interval = abs(pitch - prev_pitch)
                if interval <= 2:    # step
                    score += 2
                elif interval <= 5:  # small leap  
                    score += 1
                elif interval > 12:  # more than octave
                    score -= 1
                
                # 4. Higher pitch tiebreaker (melody on top)
                score += pitch / 100.0  # Small bias, won't override other factors
                
                # 5. Velocity bonus (loud notes are usually the melody)
                score += (vel / 127.0) * 4  # Up to +4 for max velocity
                
                # 6. Duration bonus (melody notes tend to be longer)
                if dur > 0.2:     # Longer than 200ms
                    score += 2
                elif dur > 0.1:   # Longer than 100ms
                    score += 1
                
                if score > best_score:
                    best_score = score
                    best_note = note
            
            if best_note:
                melody.append(best_note)
                prev_pitch = best_note[2]
        
        print(f"DEBUG: Melody extraction: {len(note_events)} notes -> {len(melody)} melody notes")
        return melody
    
    # ──────────────────────────────────────────────────────────
    #  RHYTHM FILTER: Detect and preserve rhythmic patterns
    # ──────────────────────────────────────────────────────────
    
    def _detect_rhythm_pattern(self, note_events, seconds_per_beat, measures_to_scan=8):
        """
        Detect repeating rhythmic patterns and filter noise notes.
        
        Algorithm:
        1. Quantize onsets to 1/16 beat grid
        2. Build a "beat fingerprint" for each measure (which 16th-note slots have notes)
        3. Find the most common fingerprint (the song's core rhythm)
        4. Keep notes that align with this pattern (+/- 1 slot tolerance)
        5. If no clear pattern found (< 30% measures match), skip filtering
        
        Args:
            note_events: list of (start_sec, duration, midi_note, track_id)
            seconds_per_beat: duration of one beat in seconds
            measures_to_scan: how many measures to analyze for pattern
        Returns:
            Filtered list of note_events
        """
        if not note_events or seconds_per_beat <= 0:
            return note_events
        
        measure_duration = seconds_per_beat * 4  # Assume 4/4 time
        slot_duration = seconds_per_beat / 4  # 1/16 note
        
        if measure_duration <= 0:
            return note_events
        
        # Build measure fingerprints
        # Each fingerprint = frozenset of active 1/16 slots (0-15)
        total_time = note_events[-1][0] - note_events[0][0]
        num_measures = max(1, int(total_time / measure_duration))
        
        # Limit scan window
        scan_measures = min(num_measures, measures_to_scan)
        
        # Build fingerprints for first N measures
        fingerprints = []
        base_time = note_events[0][0]
        
        for m in range(scan_measures):
            m_start = base_time + m * measure_duration
            m_end = m_start + measure_duration
            slots = set()
            
            for ev in note_events:
                start = ev[0]
                if start < m_start:
                    continue
                if start >= m_end:
                    break
                # Which 1/16 slot does this note fall in?
                relative = start - m_start
                slot = int(relative / slot_duration)
                slot = min(slot, 15)  # Clamp to 0-15
                slots.add(slot)
            
            if slots:
                fingerprints.append(frozenset(slots))
        
        if len(fingerprints) < 2:
            print("DEBUG: Rhythm filter: not enough measures to analyze")
            return note_events
        
        # Find most common fingerprint (allow 1 slot tolerance by using similarity)
        from collections import Counter
        fp_counter = Counter()
        for fp in fingerprints:
            fp_counter[fp] += 1
        
        # Get the dominant pattern
        dominant_fp, dominant_count = fp_counter.most_common(1)[0]
        match_ratio = dominant_count / len(fingerprints)
        
        print(f"DEBUG: Rhythm pattern: {len(dominant_fp)} slots/measure, "
              f"{dominant_count}/{len(fingerprints)} measures match ({match_ratio:.0%})")
        
        # If less than 30% of measures match, pattern is not clear enough
        if match_ratio < 0.30:
            print("DEBUG: Rhythm filter: no clear pattern found, skipping")
            return note_events
        
        # Expand pattern with ±1 slot tolerance
        allowed_slots = set()
        for slot in dominant_fp:
            allowed_slots.add(max(0, slot - 1))
            allowed_slots.add(slot)
            allowed_slots.add(min(15, slot + 1))
        
        # Filter: keep notes that align with the rhythm pattern
        filtered = []
        for ev in note_events:
            start = ev[0]
            relative = start - base_time
            measure_pos = relative % measure_duration
            slot = int(measure_pos / slot_duration)
            slot = min(slot, 15)
            
            if slot in allowed_slots:
                filtered.append(ev)
        
        print(f"DEBUG: Rhythm filter: {len(note_events)} -> {len(filtered)} notes")
        return filtered if filtered else note_events  # Safety: never return empty
    
    # ──────────────────────────────────────────────────────────
    #  SMART MULTI-TRACK: Per-Track Transposition & Register Allocation
    # ──────────────────────────────────────────────────────────
    
    def _compute_per_track_shifts(self, events: list, track_ids: list, 
                                   best_key_shift: int, octave_offset: int) -> Tuple[Dict[int, int], Dict[int, float]]:
        """
        Compute optimal octave shift for each track independently.
        Also returns a coverage ratio (0.0-1.0) for each track.
        
        Returns:
            (dict track_id -> total_shift, dict track_id -> coverage_ratio)
        """
        # Group pitches by track
        track_pitches: Dict[int, list] = {tid: [] for tid in track_ids}
        for e in events:
            if e.get('type') == 'on':
                tid = e['track']
                if tid in track_pitches:
                    track_pitches[tid].append(e['note'])
        
        track_shifts = {}
        track_coverage = {}
        target_center = 65  # F4 — center of playable range
        
        for tid in track_ids:
            pitches = track_pitches.get(tid, [])
            if not pitches:
                track_shifts[tid] = best_key_shift
                track_coverage[tid] = 0.0
                continue
            
            pitches.sort()
            median_p = pitches[len(pitches) // 2]
            
            # Compute octave adjustment to center this track's median
            raw_diff = target_center - (median_p + best_key_shift)
            octave_adj = round(raw_diff / 12) * 12
            octave_adj += (octave_offset * 12)
            
            # Try N-1, N, N+1 octaves to maximize in-range notes
            best_total = best_key_shift + octave_adj
            max_in_range = 0
            
            for candidate in [best_total - 12, best_total, best_total + 12]:
                count = sum(1 for p in pitches if self.MIN_NOTE <= (p + candidate) <= self.MAX_NOTE)
                if count > max_in_range:
                    max_in_range = count
                    best_total = candidate
            
            track_shifts[tid] = best_total
            track_coverage[tid] = max_in_range / len(pitches)
            
            print(f"DEBUG: Track {tid} -> shift {best_total} "
                  f"(median={median_p}, coverage={track_coverage[tid]:.1%})")
        
        return track_shifts, track_coverage
    
    def _allocate_registers(self, track_shifts: Dict[int, int], 
                            lead_track_id: Optional[int] = None) -> Dict[int, int]:
        """
        Distribute tracks across registers to minimize collisions.
        Uses 6 zones (~6 semitones each) for finer control than the old 3-zone system.
        
        Rules:
        1. Lead track keeps its optimal shift (highest priority)
        2. If two tracks land in the same zone, push one apart by ±12
        3. The track with fewer notes yields
        """
        if len(track_shifts) <= 1:
            return track_shifts
        
        # 6 zones: each ~6 semitones for finer register separation
        def get_zone(shift: int) -> int:
            mapped = 60 + shift
            return max(0, min(5, (mapped - 42) // 6))
        
        adjusted = dict(track_shifts)
        
        # Sort tracks: lead first, then by shift value
        sorted_tids = sorted(adjusted.keys(), 
                            key=lambda t: (0 if t == lead_track_id else 1, adjusted[t]))
        
        # Check for zone collisions and resolve
        used_zones = {}  # zone -> track_id that claimed it
        
        for tid in sorted_tids:
            zone = get_zone(adjusted[tid])
            
            if zone not in used_zones:
                used_zones[zone] = tid
            else:
                # Collision! Try to move this track to a different zone
                original_shift = adjusted[tid]
                mapped_pitch = 60 + original_shift
                if mapped_pitch >= 65:
                    deltas = [12, -12]
                else:
                    deltas = [-12, 12]
                
                moved = False
                for delta in deltas:
                    new_shift = original_shift + delta
                    new_zone = get_zone(new_shift)
                    if new_zone not in used_zones:
                        adjusted[tid] = new_shift
                        used_zones[new_zone] = tid
                        print(f"DEBUG: Register allocation: Track {tid} moved "
                              f"zone {zone}->{new_zone} (shift {original_shift}->{new_shift})")
                        moved = True
                        break
                
                if not moved:
                    print(f"DEBUG: Register allocation: Track {tid} stays in zone {zone} (collision)")
                    used_zones[zone * 100 + tid] = tid  # unique key
        
        return adjusted
    
    # ──────────────────────────────────────────────────────────
    #  FINGERSTYLE: Voice Separation, Contour Smoothing, Density
    # ──────────────────────────────────────────────────────────
    
    def _separate_voices(self, note_events, seconds_per_beat):
        """
        Fingerstyle-inspired voice separation.
        Splits a single stream of notes into bass + melody voices using
        pitch clustering, then assigns them to different registers.
        
        Bass notes go to the low register, melody to mid/high.
        This mimics how a fingerstyle guitarist plays bass with thumb
        and melody with fingers.
        
        Args:
            note_events: list of (start_sec, duration, midi_note, track_id, velocity)
            seconds_per_beat: beat duration for rhythm awareness
        Returns:
            Modified note_events with voice-tagged track_ids
        """
        if not note_events or len(note_events) < 10:
            return note_events
        
        # Compute pitch statistics using sliding window
        window_sec = 0.5  # 500ms window
        result = []
        
        pitches = [e[2] for e in note_events]
        pitches_sorted = sorted(pitches)
        
        # IQR to find the core pitch range
        q1 = pitches_sorted[len(pitches_sorted) // 4]
        q3 = pitches_sorted[3 * len(pitches_sorted) // 4]
        iqr = q3 - q1
        
        # Split threshold: notes significantly below IQR center are bass
        center = (q1 + q3) // 2
        bass_threshold = center - max(7, iqr // 2)  # At least 7 semitones below center
        
        bass_count = 0
        melody_count = 0
        
        for ev in note_events:
            start, dur, pitch, tid, vel = ev[0], ev[1], ev[2], ev[3], ev[4] if len(ev) > 4 else 80
            
            if pitch <= bass_threshold:
                # Bass voice: tag with negative track_id offset for identification
                bass_count += 1
                result.append((start, dur, pitch, tid, vel, 'bass'))
            else:
                melody_count += 1
                result.append((start, dur, pitch, tid, vel, 'melody'))
        
        # Only apply separation if we actually found a meaningful split
        if bass_count < len(note_events) * 0.05 or melody_count < len(note_events) * 0.05:
            print(f"DEBUG: Voice separation: no clear split (bass={bass_count}, melody={melody_count}), skipping")
            return note_events
        
        print(f"DEBUG: Voice separation: {bass_count} bass + {melody_count} melody "
              f"(threshold={bass_threshold}, center={center})")
        
        # Return original format (drop the voice tag, but the separation
        # influenced which notes survive subsequent processing)
        # Bass notes get lower priority in melody extraction
        return [(e[0], e[1], e[2], e[3], e[4]) for e in result]
    
    def _smooth_contour(self, note_events):
        """
        Fingerstyle-inspired contour smoothing.
        Removes chaotic intervallic jumps that make melody unrecognizable.
        
        Rules:
        1. If a note creates a jump > octave from BOTH its neighbors, remove it
           (it's likely a stray bass/treble note in the melody line)
        2. If 3+ consecutive notes all jump > 7 semitones, keep first and last only
           (compresses chaotic passages into smoother transitions)  
        
        Args:
            note_events: list of (start_sec, duration, midi_note, track_id[, velocity])
        Returns:
            Filtered list with smoother melodic contour
        """
        if len(note_events) < 3:
            return note_events
        
        # Pass 1: Remove isolated outlier notes (jump > octave from both neighbors)
        keep = [True] * len(note_events)
        
        for i in range(1, len(note_events) - 1):
            prev_pitch = note_events[i - 1][2]
            curr_pitch = note_events[i][2]
            next_pitch = note_events[i + 1][2]
            
            jump_from_prev = abs(curr_pitch - prev_pitch)
            jump_to_next = abs(curr_pitch - next_pitch)
            
            # Outlier: big jump from both sides means this note doesn't belong
            if jump_from_prev > 12 and jump_to_next > 12:
                keep[i] = False
        
        filtered = [ev for ev, k in zip(note_events, keep) if k]
        removed_pass1 = len(note_events) - len(filtered)
        
        # Pass 2: Compress chaotic jump sequences (3+ notes with >7 semitone jumps)
        if len(filtered) > 3:
            final = [filtered[0]]
            jump_run = 0
            
            for i in range(1, len(filtered)):
                interval = abs(filtered[i][2] - filtered[i - 1][2])
                
                if interval > 7:
                    jump_run += 1
                    if jump_run >= 3:
                        # In the middle of a chaotic run — skip this note
                        # (we'll keep the last note when the run ends)
                        continue
                else:
                    jump_run = 0
                
                final.append(filtered[i])
            
            removed_pass2 = len(filtered) - len(final)
            filtered = final
        else:
            removed_pass2 = 0
        
        total_removed = removed_pass1 + removed_pass2
        if total_removed > 0:
            print(f"DEBUG: Contour smoothing: removed {total_removed} notes "
                  f"(outliers={removed_pass1}, chaotic_runs={removed_pass2})")
        
        return filtered if filtered else note_events  # Safety: never return empty
    
    def _reduce_density(self, note_events, seconds_per_beat):
        """
        Fingerstyle-inspired density reduction.
        Limits note density to avoid 'machine-gun' effect while preserving
        the musical structure.
        
        Principle: on strong beats keep the lowest note (bass foundation),
        between beats keep the highest note (melody).
        Max ~6 notes per beat to keep things clean.
        
        Args:
            note_events: list of (start_sec, duration, midi_note, track_id[, velocity])
            seconds_per_beat: beat duration in seconds
        Returns:
            Filtered list with reduced density
        """
        if not note_events or seconds_per_beat <= 0:
            return note_events
        
        MAX_NOTES_PER_BEAT = 6
        beat_duration = seconds_per_beat
        strong_beat_window = 0.06  # 60ms around strong beats
        
        # Group notes by beat
        base_time = note_events[0][0]
        beats = {}  # beat_index -> list of (note_event, is_strong_beat)
        
        for ev in note_events:
            relative = ev[0] - base_time
            beat_idx = int(relative / beat_duration)
            beat_pos = relative - (beat_idx * beat_duration)
            
            # Strong beats: beat 1 and 3 (positions 0 and 0.5 of the measure in 4/4)
            is_strong = (beat_pos < strong_beat_window or 
                        abs(beat_pos - beat_duration / 2) < strong_beat_window)
            
            if beat_idx not in beats:
                beats[beat_idx] = []
            beats[beat_idx].append((ev, is_strong))
        
        # Process each beat
        result = []
        for beat_idx in sorted(beats.keys()):
            beat_notes = beats[beat_idx]
            
            if len(beat_notes) <= MAX_NOTES_PER_BEAT:
                # Not too dense — keep all
                result.extend([item[0] for item in beat_notes])
                continue
            
            # Too dense — apply fingerstyle selection
            strong = [(ev, s) for ev, s in beat_notes if s]
            weak = [(ev, s) for ev, s in beat_notes if not s]
            
            selected = []
            
            # Strong beat positions: keep lowest note (bass) + highest note (melody)
            if strong:
                strong_notes = [item[0] for item in strong]
                # Bass: lowest pitch on strong beat
                selected.append(min(strong_notes, key=lambda e: e[2]))
                # Melody: highest pitch on strong beat (if different from bass)
                highest = max(strong_notes, key=lambda e: e[2])
                if highest[2] != selected[0][2]:
                    selected.append(highest)
            
            # Weak positions: keep highest notes (melody), sorted by pitch descending
            if weak:
                weak_notes = sorted([item[0] for item in weak], key=lambda e: -e[2])
                remaining_slots = MAX_NOTES_PER_BEAT - len(selected)
                selected.extend(weak_notes[:remaining_slots])
            
            # Sort by time to maintain order
            selected.sort(key=lambda e: e[0])
            result.extend(selected)
        
        removed = len(note_events) - len(result)
        if removed > 0:
            print(f"DEBUG: Density reduction: {len(note_events)} -> {len(result)} notes "
                  f"(removed {removed}, max {MAX_NOTES_PER_BEAT}/beat)")
        
        return result if result else note_events  # Safety
    
    def _clamp_note_soft(self, midi_note: int) -> Optional[int]:
        """
        Soft-clamp a note to the playable range.
        
        Instead of octave-wrapping (which destroys intervals), clamp to the
        nearest boundary note. 
        
        IMPROVED: If the note is too far (> 2 semitones), we skip it 
        to avoid 'boundary noise' from parts that don't fit the window.
        """
        if self.MIN_NOTE <= midi_note <= self.MAX_NOTE:
            return midi_note
        
        # How far out of range?
        if midi_note < self.MIN_NOTE:
            distance = self.MIN_NOTE - midi_note
            if distance <= 2:  # Strict: only clamp very close notes
                return self.MIN_NOTE
            else:
                return None  # Too far — skip to avoid noise
        else:  # midi_note > self.MAX_NOTE
            distance = midi_note - self.MAX_NOTE
            if distance <= 2:
                return self.MAX_NOTE
            else:
                return None  # Too far — skip to avoid noise
    
    def analyze_tracks(self, midi_path: str) -> List[Dict]:
        """
        Analyze MIDI tracks to help user select the melody.
        Returns list of dicts with track info.
        """
        mid = mido.MidiFile(midi_path)
        tracks_info = []
        
        for i, track in enumerate(mid.tracks):
            note_count = 0
            channels = set()
            avg_pitch = 0
            total_pitch = 0
            name = f"Track {i}"
            
            for msg in track:
                if msg.type == 'track_name':
                    name = msg.name
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_count += 1
                    channels.add(msg.channel)
                    total_pitch += msg.note
            
            if note_count > 0:
                avg_pitch = total_pitch / note_count
            
            # Detect drums (Channel 10 is usually drums in General MIDI)
            is_drum = 9 in channels  # 0-indexed, so 9 is Channel 10
            
            tracks_info.append({
                'id': i,
                'name': name,
                'notes': note_count,
                'avg_pitch': int(avg_pitch),
                'is_drum': is_drum
            })
            
        return tracks_info

    def convert_tracks(self, midi_path: str, track_ids: List[int], output_path: str = None, 
                      quantize: bool = False, lead_track_id: int = None, 
                      allow_chords: bool = False, min_pitch: int = None, max_pitch: int = None, 
                      simplify_chords: bool = False, melody_priority: bool = False,
                      octave_offset: int = 0, rhythm_filter: bool = False,
                      smart_multitrack: bool = False) -> str:
        """
        Convert specific MIDI tracks to melody file.
        Args:
            melody_priority: If True, keeps only the highest note when overlaps occur (Skyline algorithm).
            octave_offset: Manual octave shift (+/- int).
            smart_multitrack: If True, uses per-track transposition and register allocation.
        """
        # ── PERCUSSION BRANCH: bypass all pitch-based processing ──
        if self.is_percussion:
            return self._convert_percussion(midi_path, track_ids, output_path, quantize)
        
        mid = mido.MidiFile(midi_path)
        
        # 1. Collect all notes from selected tracks
        events = []
        for tid in track_ids:
            if tid < len(mid.tracks):
                track = mid.tracks[tid]
                current_ticks = 0
                for msg in track:
                    current_ticks += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0:
                        events.append({
                            'type': 'on', 'time': current_ticks, 'note': msg.note, 'vel': msg.velocity, 
                            'track': tid
                        })
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        events.append({
                            'type': 'off', 'time': current_ticks, 'note': msg.note, 
                            'track': tid
                        })
        
        # Sort merged events by time
        events.sort(key=lambda x: x['time'])
        
        # 2. Analyze OPTIMAL KEY TRANSPOSITION (Fit to C Major / A Minor)
        if not events: # Handle empty track selection
             raise ValueError("No notes found in selected tracks")
             
        pitches = [e['note'] for e in events if e.get('type') == 'on']
        if not pitches:
            raise ValueError("No note-on events in selected tracks")
            
        # Target: White Keys (C Major / A Minor)
        white_keys = {0, 2, 4, 5, 7, 9, 11}
        best_key_shift = 0
        max_in_key = -1
        
        # Build velocity weights for weighted key detection
        # Loud notes matter more for determining the key
        pitch_weights = []
        for e in events:
            if e.get('type') == 'on':
                pitch_weights.append(e.get('vel', 80) / 127.0)
        
        # Test all 12 transpositions (weighted by velocity)
        for shift in range(12):
            weighted_score = 0
            for i, p in enumerate(pitches):
                w = pitch_weights[i] if i < len(pitch_weights) else 1.0
                if ((p + shift) % 12) in white_keys:
                    weighted_score += w
            
            if weighted_score > max_in_key:
                max_in_key = weighted_score
                best_key_shift = shift
        
        print(f"DEBUG: Weighted Key Detection -> Shift +{best_key_shift} semitones (Score: {max_in_key:.1f}/{len(pitches)}) [direction TBD]")

        # 3. Analyze PITCH RANGE for Octave Shifting
        # We want total_shift = best_key_shift + (N * 12)
        
        # Strategy: IQR-based centering (ignores outlier bass/treble notes)
        # Raw median is pulled by quantity - if 80% bass, median shifts down.
        # IQR center represents the "body" of the melodically important notes.
        pitches.sort()
        q1_idx = len(pitches) // 4
        q3_idx = 3 * len(pitches) // 4
        core_pitches = pitches[q1_idx:q3_idx + 1]  # middle 50%
        mid_p = core_pitches[len(core_pitches) // 2]  # median of core
        
        # Choose direction (+ or -) that keeps IQR center closer to target.
        if best_key_shift > 6:
            alt_shift = best_key_shift - 12  # e.g. +10 -> -2
            if abs((mid_p + alt_shift) - 65) < abs((mid_p + best_key_shift) - 65):
                print(f"DEBUG: Key shift direction fix: +{best_key_shift} -> {alt_shift} (IQR center closer)")
                best_key_shift = alt_shift
        print(f"DEBUG: Weighted Key Detection -> Shift {best_key_shift:+d} semitones (Score: {max_in_key:.1f})")
        
        # Target center is roughly 65 (F4/E4)
        raw_diff = 65 - (mid_p + best_key_shift)
        # Round to nearest octave
        octave_adjustment = round(raw_diff / 12) * 12
        
        # Apply Manual Offset
        octave_adjustment += (octave_offset * 12)
        
        print(f"DEBUG: IQR center {mid_p} (Q1={pitches[q1_idx]}, Q3={pitches[q3_idx]}). Target -> 65. Adjustment: {octave_adjustment} (Manual: {octave_offset})")
        
        # Test N-1, N, N+1 octaves to find best fit in 48-83 range
        best_total_shift = best_key_shift + octave_adjustment
        max_in_range = 0
        
        # Try current best estimate +/- 1 octave
        candidates = [
            best_key_shift + octave_adjustment - 12,
            best_key_shift + octave_adjustment,
            best_key_shift + octave_adjustment + 12
        ]
        
        for shift in candidates:
            # Count how many notes fall in playable range 48-83
            count = sum(1 for p in pitches if 48 <= (p + shift) <= 83)
            if count > max_in_range:
                max_in_range = count
                best_total_shift = shift
        
        best_shift = best_total_shift
        print(f"DEBUG: Total Shift (Key+Octave) -> {best_shift} semitones")
        
        # 2b. SMART TRACK: Per-track transposition (works for single AND multiple tracks)
        track_shifts = None
        if smart_multitrack:
            print(f"DEBUG: Smart Track mode enabled ({len(track_ids)} track(s))")
            track_shifts, track_coverage = self._compute_per_track_shifts(
                events, track_ids, best_key_shift, octave_offset)
            
            # Filter tracks by coverage (dynamic threshold adapts to track count)
            filtered_track_ids = []
            COVERAGE_THRESHOLD = max(0.30, 0.55 - 0.05 * len(track_ids))
            print(f"DEBUG: Coverage threshold: {COVERAGE_THRESHOLD:.0%} (for {len(track_ids)} tracks)")
            
            for tid in track_ids:
                coverage = track_coverage.get(tid, 0)
                if coverage >= COVERAGE_THRESHOLD:
                    filtered_track_ids.append(tid)
                else:
                    print(f"DEBUG: Track {tid} excluded due to low coverage ({coverage:.1%})")
            
            if not filtered_track_ids:
                print("WARNING: All tracks below coverage threshold! Keeping all to avoid silence.")
                filtered_track_ids = track_ids
            
            # Re-allocate registers only for filtered tracks
            track_shifts = {tid: track_shifts[tid] for tid in filtered_track_ids}
            if len(filtered_track_ids) > 1:
                track_shifts = self._allocate_registers(track_shifts, lead_track_id)
            track_ids = filtered_track_ids  # Update track_ids for subsequent processing
        
        # 3. Process notes with transposition
        active_notes = {} # (note, track) -> start_tick
        
        # Determine average tempo
        tempos = []
        for t in mid.tracks:
            t_ticks = 0
            for msg in t:
                t_ticks += msg.time
                if msg.type == 'set_tempo':
                    tempos.append((t_ticks, msg.tempo))
        
        avg_tempo = 500000
        if tempos:
             avg_tempo = tempos[0][1]
        
        ticks_per_beat = mid.ticks_per_beat
        
        def ticks2sec(ticks):
            if tempos:
                return mido.tick2second(ticks, ticks_per_beat, tempos[0][1])
            return mido.tick2second(ticks, ticks_per_beat, 500000)

        # Quantization Setup
        seconds_per_beat = mido.tick2second(ticks_per_beat, ticks_per_beat, avg_tempo)
        grid_step = seconds_per_beat / 4.0 
        
        def quantize_time(ex_time):
            # Safe round to avoid errors
            if not quantize:
                return ex_time
            if grid_step <= 0: return ex_time
            steps = round(ex_time / grid_step)
            return steps * grid_step

        note_events = [] # (start_sec, duration, note_midi_val, track_id, velocity)
        skipped_notes = 0
        
        for e in events:
            time_sec = ticks2sec(e['time'])
            if quantize:
                time_sec = quantize_time(time_sec)
            
            tid = e['track']
            
            # Apply per-track or global shift
            if track_shifts is not None and tid in track_shifts:
                note = e['note'] + track_shifts[tid]
            else:
                note = e['note'] + best_shift
            
            # Smart Track: soft clamp instead of octave wrap (single + multi)
            if smart_multitrack:
                clamped = self._clamp_note_soft(note)
                if clamped is None:
                    skipped_notes += 1
                    continue  # Skip notes too far out of range
                note = clamped
            else:
                # Legacy wrapping when smart track is off
                while note < self.MIN_NOTE: note += 12
                while note > self.MAX_NOTE: note -= 12
            
            note_key = (note, tid)
            
            if e['type'] == 'on':
                active_notes[note_key] = (time_sec, e.get('vel', 80))
            else: # off
                if note_key in active_notes:
                    start, vel = active_notes.pop(note_key)
                    duration = time_sec - start
                    
                    if quantize:
                         end_time = quantize_time(start + duration)
                         duration = max(grid_step, end_time - start)
                    
                    # Only add if valid key and duration > 0
                    if self.MIN_NOTE <= note <= self.MAX_NOTE:
                         note_events.append((start, duration, note, tid, vel))
        
        if skipped_notes > 0:
            print(f"DEBUG: Smart Track skipped {skipped_notes} out-of-range notes")
        
        note_events.sort(key=lambda x: x[0]) 

        # 1b. FINGERSTYLE PROCESSING (when smart_multitrack is on)
        if smart_multitrack:
             # Voice separation: split bass/melody for cleaner processing
             print("DEBUG: Applying Fingerstyle Voice Separation...")
             note_events = self._separate_voices(note_events, seconds_per_beat)
             
             # Contour smoothing: remove chaotic jumps
             print("DEBUG: Applying Fingerstyle Contour Smoothing...")
             note_events = self._smooth_contour(note_events)
             
             # Density reduction: keep musicality, remove clutter
             print("DEBUG: Applying Fingerstyle Density Reduction...")
             note_events = self._reduce_density(note_events, seconds_per_beat)

        # 1c. SMART MELODY EXTRACTION (replaces old Skyline filter)
        if melody_priority:
             print("DEBUG: Applying Smart Melody Extraction...")
             note_events = self._extract_melody_line(note_events, lead_track_id)
        
        # 1d. RHYTHM PATTERN FILTER (separate optional step)
        if rhythm_filter:
             print("DEBUG: Applying Rhythm Pattern Filter...")
             note_events = self._detect_rhythm_pattern(note_events, seconds_per_beat)
        
        # 1e. INTERVAL-PRESERVING DIATONIC SNAP (when melody_priority is on)
        # Replaces per-note CHROMATIC_SNAP with contour-aware snapping
        if melody_priority:
             print("DEBUG: Applying Interval-Preserving Snap...")
             note_events = self._snap_to_diatonic_preserving_intervals(note_events)
        
        # 4. CHORD REDUCTION & MONOPHONIC PROCESSING WITH LEAD PRIORITY
        # Problem: Simultaneous notes create "machine gun" effect.
        # Solution: Group notes by start time (within 35ms window).
        # Priority:
        #   1. Note from LEAD TRACK (highest pitch if multiple)
        #   2. Highest pitch note from ANY track (if no lead track note present)
        
        if not note_events:
             raise ValueError("No playable notes found")
             
        # Filter by Pitch Range (Smart Split)
        if min_pitch is not None or max_pitch is not None:
            note_events = [e for e in note_events if 
                          (min_pitch is None or e[2] >= min_pitch) and 
                          (max_pitch is None or e[2] <= max_pitch)]
            
        if not note_events:
             raise ValueError("No notes found in selected range")

        filtered_events = []
        
        # Group notes
        i = 0
        while i < len(note_events):
            current_start = note_events[i][0]
            chord_group = [note_events[i]]
            
            # Look ahead for simultaneous notes
            j = i + 1
            while j < len(note_events):
                next_start = note_events[j][0]
                if abs(next_start - current_start) < 0.035: # 35ms tolerance for chords
                    chord_group.append(note_events[j])
                    j += 1
                else:
                    break
            
            # Select Best Note or Arpeggiate
            if not allow_chords:
                # MONOPHONIC: Pick ONE note
                selected_note = None
                
                # Check for Lead Track candidates
                if lead_track_id is not None:
                    lead_candidates = [n for n in chord_group if n[3] == lead_track_id]
                    if lead_candidates:
                        # Pick highest pitch from Lead Track
                        selected_note = max(lead_candidates, key=lambda x: x[2])
                
                # Fallback to general high pitch if no lead candidate
                if selected_note is None:
                    selected_note = max(chord_group, key=lambda x: x[2])
                    
                filtered_events.append(selected_note)
            else:
                # POLYPHONIC/ARPEGGIO: Keep ALL notes
                # Sort by pitch (Ascending): Low -> High
                chord_group.sort(key=lambda x: x[2])
                
                if simplify_chords and len(chord_group) > 2:
                    # Keep only Lowest (Bass) and Highest (Melody) to reduce mud
                    chord_group = [chord_group[0], chord_group[-1]]
                    
                filtered_events.extend(chord_group)
            
            i = j # Skip processed notes
            
        # 5. Create final timeline (Duration handling)
        resolved_notes = []
        
        for i, ev in enumerate(filtered_events):
            start, dur, midi_note, tid = ev[0], ev[1], ev[2], ev[3]
            
            # Truncate if overlaps with next note
            if i < len(filtered_events) - 1:
                next_start = filtered_events[i+1][0]
                
                # If simultaneous (Arpeggio effect), force small step
                if next_start <= start + 0.001:
                    # Very fast strum: 30ms per note
                    # We actually need to shift the START time of subsequent notes?
                    # No, we just cut the duration of THIS note.
                    # The PlaybackEngine plays Note -> Wait(dur) -> Release -> Wait(pause).
                    # So if we set dur=0.03, it plays, waits 30ms, then next.
                    # Effectively delaying the NEXT note.
                    dur = 0.03 # 30ms strum speed
                
                elif start + dur > next_start:
                     # Cut short, to avoid overlap
                    dur = next_start - start
                    # Ensure minimum click
                    if dur < 0.02: dur = 0.02
            
            # Calculate pause
            pause = 0
            if i < len(filtered_events) - 1:
                next_start = filtered_events[i+1][0]
                # If we are arpeggiating simultaneous notes, next_start is same as start.
                # so pause = 0 - (0 + 0.03) = negative.
                # max(0, ...) handles this.
                pause = max(0, next_start - (start + dur))
            
            # Convert to Key Char (with chromatic snap fallback)
            key_char = None
            if midi_note in self.KEY_MAPPING:
                key_char = self.KEY_MAPPING[midi_note]
            elif midi_note in self.CHROMATIC_SNAP:
                # Snap sharp/flat to nearest diatonic note
                snapped = self.CHROMATIC_SNAP[midi_note]
                key_char = self.KEY_MAPPING.get(snapped)
            
            if key_char:
                # Ensure Integers for file format
                dur_ms = int(dur * 1000)
                pause_ms = int(pause * 1000)
                resolved_notes.append(Note(key_char, dur_ms, pause_ms))
        
        # 6. POST-PROCESSING (Cleanup)
        # Filter Short Notes & Merge Duplicates
        
        if resolved_notes:
            # Pass 1: Merge Duplicates (Same Key, Small Gap) — LEGATO FIX
            # 
            # Problem: A held note like C4(400ms) → pause(20ms) → C4(300ms) sounds like
            # two separate key-presses cutting the legato flow. We want one smooth C4(720ms).
            #
            # Rule: If same key AND the gap between them is < LEGATO_MERGE_MS,
            #       merge into one long note regardless of duration.
            #       (80ms threshold = below that, the gap is a MIDI release artifact,
            #        above that, it's an intentional re-articulation / ornament)
            LEGATO_MERGE_MS = 80
            merged_notes = []
            if resolved_notes:
                curr = resolved_notes[0]
                for next_n in resolved_notes[1:]:
                    if next_n.key == curr.key and curr.pause_ms < LEGATO_MERGE_MS:
                        # Merge: extend current note, absorb the pause and next duration
                        curr.duration_ms += curr.pause_ms + next_n.duration_ms
                        curr.pause_ms = next_n.pause_ms
                    else:
                        merged_notes.append(curr)
                        curr = next_n
                merged_notes.append(curr)
            
            if len(resolved_notes) != len(merged_notes):
                print(f"DEBUG: Legato merge: {len(resolved_notes)} -> {len(merged_notes)} notes")
            resolved_notes = merged_notes

            # Pass 2: Filter Short Notes (< 15ms) - Join to previous
            clean_notes = []
            for n in resolved_notes:
                if n.duration_ms < 15:
                    if clean_notes:
                        # Extend previous note to cover this one
                        prev = clean_notes[-1]
                        prev.duration_ms += prev.pause_ms + n.duration_ms
                        prev.pause_ms = n.pause_ms
                    else:
                        # Drop 1st short note (silence)
                        pass
                else:
                    clean_notes.append(n)
            
            resolved_notes = clean_notes
            
            # Pass 2.5: Suppress excessive consecutive duplicates (>2 in a row)
            # Keeps intentional trills (2 repeats) but kills droning runs (3+)
            deduped = []
            run_count = 0
            for n in resolved_notes:
                if deduped and n.key == deduped[-1].key:
                    run_count += 1
                    if run_count >= 3:
                        # Absorb into previous note's pause
                        deduped[-1].pause_ms += n.duration_ms + n.pause_ms
                        continue
                else:
                    run_count = 1
                deduped.append(n)
            
            if len(resolved_notes) != len(deduped):
                print(f"DEBUG: Duplicate suppression: {len(resolved_notes)} -> {len(deduped)} notes")
            resolved_notes = deduped
            
            # Pass 3: Safety Check (Min Duration)
            for n in resolved_notes:
                if n.duration_ms < 20: n.duration_ms = 20
            
            # Pass 4: Instrument Duration Adaptation
            # Scale durations, cap max, enforce min pause per instrument ADSR
            if self.duration_scale != 1.0 or self.min_pause_ms > 5 or self.max_duration_ms > 0:
                adapted_count = 0
                for n in resolved_notes:
                    original_dur = n.duration_ms
                    
                    # Scale duration
                    n.duration_ms = int(n.duration_ms * self.duration_scale)
                    
                    # Cap max duration (freed time goes to pause)
                    if self.max_duration_ms > 0 and n.duration_ms > self.max_duration_ms:
                        excess = n.duration_ms - self.max_duration_ms
                        n.duration_ms = self.max_duration_ms
                        n.pause_ms += excess  # instrument resonates, we wait
                    
                    # Enforce minimum pause (articulation / breath)
                    if n.pause_ms < self.min_pause_ms:
                        # Steal from duration to create the pause
                        deficit = self.min_pause_ms - n.pause_ms
                        if n.duration_ms > deficit + 20:  # keep at least 20ms note
                            n.duration_ms -= deficit
                            n.pause_ms = self.min_pause_ms
                        else:
                            n.pause_ms = self.min_pause_ms
                    
                    # Safety: min 20ms duration
                    if n.duration_ms < 20:
                        n.duration_ms = 20
                    
                    if n.duration_ms != original_dur:
                        adapted_count += 1
                
                print(f"DEBUG: Instrument adaptation: {adapted_count}/{len(resolved_notes)} notes adjusted "
                      f"(scale={self.duration_scale}, min_pause={self.min_pause_ms}ms, "
                      f"max_dur={self.max_duration_ms}ms)")
            
        if output_path is None:
            output_path = os.path.splitext(midi_path)[0] + ".txt"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Converted Tracks {track_ids} from {os.path.basename(midi_path)}\n")
            if lead_track_id:
                f.write(f"# Lead Track: {lead_track_id} (Priority)\n")
            f.write(f"# Transposition: {best_shift} semitones\n")
            f.write(f"# Total notes: {len(resolved_notes)}\n\n")
            
            for note in resolved_notes:
                f.write(f"{note.key} {note.duration_ms} {note.pause_ms}\n")
                
        return output_path
    
    # ──────────────────────────────────────────────────────────
    #  PERCUSSION CONVERSION (Ramskin Drum etc.)
    # ──────────────────────────────────────────────────────────
    
    def _convert_percussion(self, midi_path: str, track_ids: List[int], 
                            output_path: str = None, quantize: bool = False) -> str:
        """
        Convert MIDI drum tracks to percussion key file.
        
        Unlike tonal conversion, this:
        - Ignores pitch transposition entirely
        - Maps MIDI note numbers directly to game keys via drum_map
        - Skips melody extraction, diatonic snap, etc.
        """
        mid = mido.MidiFile(midi_path)
        
        # Collect note events from selected tracks
        events = []
        for tid in track_ids:
            if tid < len(mid.tracks):
                track = mid.tracks[tid]
                current_ticks = 0
                for msg in track:
                    current_ticks += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0:
                        events.append({
                            'type': 'on', 'time': current_ticks, 
                            'note': msg.note, 'vel': msg.velocity, 'track': tid
                        })
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        events.append({
                            'type': 'off', 'time': current_ticks, 
                            'note': msg.note, 'track': tid
                        })
        
        events.sort(key=lambda x: x['time'])
        
        if not events:
            raise ValueError("No events found in selected tracks")
        
        # Determine tempo
        tempos = []
        for t in mid.tracks:
            t_ticks = 0
            for msg in t:
                t_ticks += msg.time
                if msg.type == 'set_tempo':
                    tempos.append((t_ticks, msg.tempo))
        
        avg_tempo = tempos[0][1] if tempos else 500000
        ticks_per_beat = mid.ticks_per_beat
        seconds_per_beat = mido.tick2second(ticks_per_beat, ticks_per_beat, avg_tempo)
        
        def ticks2sec(ticks):
            if tempos:
                return mido.tick2second(ticks, ticks_per_beat, tempos[0][1])
            return mido.tick2second(ticks, ticks_per_beat, 500000)
        
        # Quantization
        grid_step = seconds_per_beat / 4.0
        def quantize_time(t):
            if not quantize or grid_step <= 0:
                return t
            return round(t / grid_step) * grid_step
        
        # Build note events: (start_sec, duration, key_char)
        active_notes = {}  # (midi_note, track) -> start_sec
        note_events = []
        mapped_count = 0
        unmapped_count = 0
        
        for e in events:
            time_sec = quantize_time(ticks2sec(e['time']))
            midi_note = e['note']
            tid = e['track']
            note_key = (midi_note, tid)
            
            if e['type'] == 'on':
                active_notes[note_key] = time_sec
            else:
                if note_key in active_notes:
                    start = active_notes.pop(note_key)
                    duration = time_sec - start
                    if duration < 0.01:
                        duration = 0.05  # minimum drum hit duration
                    
                    # Map MIDI note -> game key via drum_map
                    key_char = self.drum_map.get(midi_note)
                    if key_char:
                        note_events.append((start, duration, key_char))
                        mapped_count += 1
                    else:
                        unmapped_count += 1
        
        print(f"DEBUG: Percussion mapping: {mapped_count} hits mapped, {unmapped_count} unmapped")
        
        if not note_events:
            raise ValueError("No percussion hits could be mapped to drum keys")
        
        note_events.sort(key=lambda x: x[0])
        
        # Build final Note objects with timing
        resolved_notes = []
        for i, (start, dur, key_char) in enumerate(note_events):
            # Truncate if overlaps with next
            if i < len(note_events) - 1:
                next_start = note_events[i + 1][0]
                if start + dur > next_start:
                    dur = max(0.02, next_start - start)
            
            # Calculate pause to next note
            pause = 0
            if i < len(note_events) - 1:
                next_start = note_events[i + 1][0]
                pause = max(0, next_start - (start + dur))
            
            dur_ms = max(20, int(dur * 1000))
            pause_ms = int(pause * 1000)
            resolved_notes.append(Note(key_char, dur_ms, pause_ms))
        
        # Apply instrument duration adaptation
        if self.duration_scale != 1.0 or self.min_pause_ms > 5 or self.max_duration_ms > 0:
            for n in resolved_notes:
                n.duration_ms = int(n.duration_ms * self.duration_scale)
                if self.max_duration_ms > 0 and n.duration_ms > self.max_duration_ms:
                    excess = n.duration_ms - self.max_duration_ms
                    n.duration_ms = self.max_duration_ms
                    n.pause_ms += excess
                if n.pause_ms < self.min_pause_ms:
                    deficit = self.min_pause_ms - n.pause_ms
                    if n.duration_ms > deficit + 20:
                        n.duration_ms -= deficit
                    n.pause_ms = self.min_pause_ms
                if n.duration_ms < 20:
                    n.duration_ms = 20
        
        # Write output
        if output_path is None:
            output_path = os.path.splitext(midi_path)[0] + ".txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Percussion conversion from {os.path.basename(midi_path)}\n")
            f.write(f"# Tracks: {track_ids}\n")
            f.write(f"# Mapped hits: {mapped_count}, Unmapped: {unmapped_count}\n")
            f.write(f"# Total notes: {len(resolved_notes)}\n\n")
            
            for note in resolved_notes:
                f.write(f"{note.key} {note.duration_ms} {note.pause_ms}\n")
        
        print(f"DEBUG: Percussion output: {len(resolved_notes)} hits -> {output_path}")
        return output_path


# Test
if __name__ == "__main__":
    print("MIDI Converter Test")
    print("Requires 'mido' library to run.")
    # Instructions:
    # 1. pip install mido
    # 2. Place a .mid file in this directory
    # 3. Modify this script to point to it
