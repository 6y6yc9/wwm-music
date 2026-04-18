"""
Playback Engine Module
Orchestrates melody playback with timing and callbacks.
"""

import threading
import time
from typing import List, Callable, Optional
from enum import Enum
from note_parser import Note
from key_simulator import KeySimulator
from key_simulator_lowlevel import LowLevelKeySimulator


class PlaybackState(Enum):
    """Playback state enumeration."""
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class PlaybackEngine:
    """
    Engine for playing back melodies.
    
    Callbacks:
        on_note_start(note_index, note): Called when a note starts playing
        on_note_end(note_index, note): Called when a note finishes
        on_progress(current_index, total_notes): Called periodically for progress
        on_complete(): Called when melody finishes
        on_error(error): Called if an error occurs
    """
    
    def __init__(
        self,
        on_note_start: Optional[Callable] = None,
        on_note_end: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        use_lowlevel: bool = True  # Use low-level by default for game compatibility
    ):
        # Choose simulator based on mode
        if use_lowlevel:
            self.simulator = LowLevelKeySimulator()
        else:
            self.simulator = KeySimulator()
        
        # Callbacks
        self.on_note_start = on_note_start
        self.on_note_end = on_note_end
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        
        # State
        self._melody: List[Note] = []
        self._state = PlaybackState.IDLE
        self._current_index = 0
        self._playback_thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
    
    def load_melody(self, notes: List[Note]):
        """Load a melody for playback."""
        with self._lock:
            if self._state == PlaybackState.PLAYING:
                raise ValueError("Cannot load melody while playing")
            
            self._melody = notes.copy()
            self._current_index = 0
            self._state = PlaybackState.IDLE
    
    def play(self):
        """Start or resume playback."""
        with self._lock:
            if not self._melody:
                raise ValueError("No melody loaded")
            
            if self._state == PlaybackState.PLAYING:
                return  # Already playing
            
            if self._state == PlaybackState.PAUSED:
                # Resume from pause
                self._pause_event.set()
                self._state = PlaybackState.PLAYING
                return
            
            # Start new playback
            self._state = PlaybackState.PLAYING
            self._current_index = 0
            self._stop_event.clear()
            self._pause_event.set()
            self.simulator.reset()
            
            self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._playback_thread.start()
    
    def pause(self):
        """Pause playback."""
        with self._lock:
            if self._state == PlaybackState.PLAYING:
                self._state = PlaybackState.PAUSED
                self._pause_event.clear()
    
    def stop(self):
        """Stop playback."""
        with self._lock:
            if self._state in (PlaybackState.PLAYING, PlaybackState.PAUSED):
                self._state = PlaybackState.STOPPED
                self._stop_event.set()
                self._pause_event.set()  # Unblock if paused
                self.simulator.emergency_stop()
        
        # Wait for thread to finish
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2.0)
        
        with self._lock:
            self._current_index = 0
            self._state = PlaybackState.IDLE
            self.simulator.reset()
    
    def get_state(self) -> PlaybackState:
        """Get current playback state."""
        with self._lock:
            return self._state
    
    def get_progress(self) -> tuple:
        """Get current progress (current_index, total_notes)."""
        with self._lock:
            return (self._current_index, len(self._melody))
    
    def _playback_loop(self):
        """Main playback loop (runs in separate thread)."""
        try:
            # ─────────────────────────────────────────────────────────────
            # CLOSED-LOOP TIMING SYSTEM (Drift Compensation)
            # 
            # Problem: Sequential sleep() calls accumulate error (overhead).
            # Solution: Track absolute start time and target timestamps.
            # ─────────────────────────────────────────────────────────────
            
            start_time = time.perf_counter()
            cumulative_target = 0.0  # Seconds from start to note end
            prev_key = None  # Track previous key for re-press detection
            
            # Minimum gap (seconds) between two presses of the SAME key.
            # Gives the game engine time to register key-up before next key-down.
            # 20ms is imperceptible musically but enough for one DirectInput frame.
            REPRESS_GAP_SEC = 0.020
            
            while self._current_index < len(self._melody):
                # Check if stopped
                if self._stop_event.is_set():
                    break
                
                # Check pause state
                if self._pause_event.is_set() is False:
                    # User paused. We must pause the clock too.
                    pause_start = time.perf_counter()
                    self._pause_event.wait()
                    # Add paused duration to start_time so targets shift forward
                    pause_duration = time.perf_counter() - pause_start
                    start_time += pause_duration
                
                # Check again after unpausing
                if self._stop_event.is_set():
                    break
                
                # Get current note
                note = self._melody[self._current_index]
                
                # Callback: note start
                if self.on_note_start:
                    self.on_note_start(self._current_index, note)
                
                try:
                    # Re-press guard: if same key as previous note, ensure
                    # the game engine has time to register the key release
                    # before the next key-down arrives.
                    if note.key == prev_key:
                        time.sleep(REPRESS_GAP_SEC)
                        cumulative_target += REPRESS_GAP_SEC  # Keep clock in sync
                    
                    # Play the note
                    # simulator.press_key blocks for duration_ms
                    self.simulator.press_key(note.key, note.duration_ms)
                    prev_key = note.key
                    
                    # Update target time for NEXT event (end of this note + pause gap)
                    # Note: We track when the *next* note should theoretically start
                    note_total_duration = (note.duration_ms + note.pause_ms) / 1000.0
                    cumulative_target += note_total_duration
                    
                    # Calculate drift
                    target_timestamp = start_time + cumulative_target
                    now = time.perf_counter()
                    remaining = target_timestamp - now
                    
                    # Sleep only if we are ahead (or on time)
                    # If remaining < 0, we are behind -> skip sleep to catch up
                    if remaining > 0:
                        time.sleep(remaining)
                    
                except ValueError as e:
                    # Simulator was stopped
                    if "stopped" in str(e).lower():
                        break
                    raise
                
                # Callback: note end
                if self.on_note_end:
                    self.on_note_end(self._current_index, note)
                
                # Update progress
                with self._lock:
                    self._current_index += 1
                
                # Callback: progress
                if self.on_progress:
                    self.on_progress(self._current_index, len(self._melody))
            
            # Playback complete
            if not self._stop_event.is_set():
                if self.on_complete:
                    self.on_complete()
            
            # Reset state
            with self._lock:
                self._state = PlaybackState.IDLE
                self._current_index = 0
        
        except Exception as e:
            # Error occurred
            if self.on_error:
                self.on_error(e)
            
            with self._lock:
                self._state = PlaybackState.IDLE
                self._current_index = 0


# Test function
if __name__ == "__main__":
    from note_parser import Note
    
    print("Playback Engine Test")
    print("=" * 50)
    
    # Create test melody
    test_notes = [
        Note('Q', 500, 100),
        Note('W', 500, 100),
        Note('E', 500, 100),
        Note('R', 1000, 0),
    ]
    
    # Callbacks
    def on_note_start(idx, note):
        print(f"Playing note {idx + 1}: {note}")
    
    def on_note_end(idx, note):
        print(f"  -> Finished note {idx + 1}")
    
    def on_progress(current, total):
        print(f"Progress: {current}/{total}")
    
    def on_complete():
        print("\n=== Melody complete! ===\n")
    
    def on_error(error):
        print(f"\nERROR: {error}\n")
    
    # Create engine
    engine = PlaybackEngine(
        on_note_start=on_note_start,
        on_note_end=on_note_end,
        on_progress=on_progress,
        on_complete=on_complete,
        on_error=on_error
    )
    
    # Load and play
    engine.load_melody(test_notes)
    
    print("Starting playback in 2 seconds...")
    time.sleep(2)
    
    engine.play()
    
    # Wait for completion
    time.sleep(5)
    
    print("Test complete!")
