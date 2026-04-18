"""
Key Simulator Module
Simulates keyboard presses for the game using pynput.
"""

import time
import threading
from typing import Callable, Optional
from pynput.keyboard import Controller, Key


class KeySimulator:
    """Simulates keyboard key presses."""
    
    def __init__(self):
        self.keyboard = Controller()
        self._stop_flag = threading.Event()
    
    def press_key(self, key: str, duration_ms: int, on_press: Optional[Callable] = None):
        """
        Press and hold a key for a specified duration.
        
        Args:
            key: The key to press (single character)
            duration_ms: How long to hold the key in milliseconds
            on_press: Optional callback when key is pressed
            
        Raises:
            ValueError: If stop flag is set (emergency stop)
        """
        if self._stop_flag.is_set():
            raise ValueError("Simulator stopped")
        
        # Call callback before pressing
        if on_press:
            on_press(key)
        
        # Press the key
        self.keyboard.press(key.lower())
        
        # Hold for duration (checking stop flag periodically)
        start_time = time.perf_counter()
        duration_sec = duration_ms / 1000.0
        
        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= duration_sec:
                break
            
            # Check stop flag every 10ms
            if self._stop_flag.is_set():
                self.keyboard.release(key.lower())
                raise ValueError("Simulator stopped")
            
            # Sleep for a short time to avoid busy waiting
            time.sleep(min(0.01, duration_sec - elapsed))
        
        # Release the key
        self.keyboard.release(key.lower())
    
    def pause(self, duration_ms: int):
        """
        Pause for a specified duration.
        
        Args:
            duration_ms: How long to pause in milliseconds
            
        Raises:
            ValueError: If stop flag is set (emergency stop)
        """
        if self._stop_flag.is_set():
            raise ValueError("Simulator stopped")
        
        start_time = time.perf_counter()
        duration_sec = duration_ms / 1000.0
        
        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= duration_sec:
                break
            
            # Check stop flag every 10ms
            if self._stop_flag.is_set():
                raise ValueError("Simulator stopped")
            
            # Sleep for a short time
            time.sleep(min(0.01, duration_sec - elapsed))
    
    def emergency_stop(self):
        """
        Emergency stop - stops all current and future key presses.
        Call reset() to resume operations.
        """
        self._stop_flag.set()
    
    def reset(self):
        """Reset the simulator after an emergency stop."""
        self._stop_flag.clear()
    
    def is_stopped(self) -> bool:
        """Check if simulator is in stopped state."""
        return self._stop_flag.is_set()


# Test function
if __name__ == "__main__":
    print("Key Simulator Test")
    print("=" * 50)
    print("This will simulate pressing Q, W, E keys.")
    print("You should see these keys being pressed in 3 seconds.")
    print("Press Ctrl+C to stop early.")
    print()
    
    input("Press Enter to start test...")
    
    simulator = KeySimulator()
    
    try:
        print("Pressing Q for 500ms...")
        simulator.press_key('Q', 500, lambda k: print(f"  -> Pressed {k}"))
        
        print("Pausing for 200ms...")
        simulator.pause(200)
        
        print("Pressing W for 300ms...")
        simulator.press_key('W', 300, lambda k: print(f"  -> Pressed {k}"))
        
        print("Pausing for 200ms...")
        simulator.pause(200)
        
        print("Pressing E for 500ms...")
        simulator.press_key('E', 500, lambda k: print(f"  -> Pressed {k}"))
        
        print("\nTest complete!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted!")
        simulator.emergency_stop()
    except Exception as e:
        print(f"\nError: {e}")
