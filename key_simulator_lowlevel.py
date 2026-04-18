"""
Low-level Key Simulator using Windows SendInput API
Works with games that block pynput (like Where Winds Meet)
"""

import time
import ctypes
from ctypes import wintypes
import threading
from typing import Callable, Optional

# Windows API constants
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# Virtual key codes for our keys
VK_CODES = {
    'Q': 0x51, 'W': 0x57, 'E': 0x45, 'R': 0x52, 'T': 0x54, 'Y': 0x59, 'U': 0x55,
    'A': 0x41, 'S': 0x53, 'D': 0x44, 'F': 0x46, 'G': 0x47, 'H': 0x48, 'J': 0x4A,
    'Z': 0x5A, 'X': 0x58, 'C': 0x43, 'V': 0x56, 'B': 0x42, 'N': 0x4E, 'M': 0x4D,
}

# Scan codes for hardware simulation
SCAN_CODES = {
    'Q': 0x10, 'W': 0x11, 'E': 0x12, 'R': 0x13, 'T': 0x14, 'Y': 0x15, 'U': 0x16,
    'A': 0x1E, 'S': 0x1F, 'D': 0x20, 'F': 0x21, 'G': 0x22, 'H': 0x23, 'J': 0x24,
    'Z': 0x2C, 'X': 0x2D, 'C': 0x2E, 'V': 0x2F, 'B': 0x30, 'N': 0x31, 'M': 0x32,
}

# Define INPUT structure with proper layout
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class _INPUTunion(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUTunion)
    ]

# Windows API constants  
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# Setup SendInput
user32 = ctypes.windll.user32
SendInput = user32.SendInput


class LowLevelKeySimulator:
    """
    Low-level key simulator using Windows SendInput API.
    Works with games that have anti-cheat protection.
    """
    
    def __init__(self):
        self._stop_flag = threading.Event()
    
    def _send_key_event(self, key: str, key_down: bool):
        """
        Send a single key event using SendInput with Hardware Scan Codes.
        NOTE: Games (DirectInput) require Scan Codes, they ignore Virtual Keys!
        """
        # DirectInput Scan Codes
        scan_code = SCAN_CODES.get(key.upper(), 0)
        
        if scan_code == 0:
            raise ValueError(f"Unknown key: {key}")
        
        # Use SCAN CODE (Hardware Input)
        # 0x0008 = KEYEVENTF_SCANCODE
        flags = 0x0008
        if not key_down:
            flags |= 0x0002  # KEYEVENTF_KEYUP
        
        x = INPUT()
        x.type = INPUT_KEYBOARD
        x.union.ki = KEYBDINPUT(
            wVk=0,  # Must be 0 for Scan Code mode
            wScan=scan_code,
            dwFlags=flags,
            time=0,
            dwExtraInfo=None
        )
        
        # Send the input
        result = SendInput(1, ctypes.byref(x), ctypes.sizeof(INPUT))
        
        # Check result
        if result != 1:
            error_code = ctypes.windll.kernel32.GetLastError()
            raise Exception(f"SendInput failed for key {key} (sent {result}/1 events, error: {error_code})")
    
    def press_key(self, key: str, duration_ms: int, on_press: Optional[Callable] = None):
        """
        Press and hold a key for specified duration.
        
        Args:
            key: Key to press
            duration_ms: Duration in milliseconds
            on_press: Optional callback
        """
        if self._stop_flag.is_set():
            raise ValueError("Simulator stopped")
        
        # Callback
        if on_press:
            on_press(key)
        
        # Press the key
        self._send_key_event(key, True)
        
        # Hold for duration
        start_time = time.perf_counter()
        duration_sec = duration_ms / 1000.0
        
        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= duration_sec:
                break
            
            # Check stop flag
            if self._stop_flag.is_set():
                self._send_key_event(key, False)
                raise ValueError("Simulator stopped")
            
            # Sleep briefly
            time.sleep(min(0.01, duration_sec - elapsed))
        
        # Release the key
        self._send_key_event(key, False)
    
    def pause(self, duration_ms: int):
        """Pause for specified duration."""
        if self._stop_flag.is_set():
            raise ValueError("Simulator stopped")
        
        start_time = time.perf_counter()
        duration_sec = duration_ms / 1000.0
        
        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed >= duration_sec:
                break
            
            if self._stop_flag.is_set():
                raise ValueError("Simulator stopped")
            
            time.sleep(min(0.01, duration_sec - elapsed))
    
    def emergency_stop(self):
        """Emergency stop - stops all operations."""
        self._stop_flag.set()
    
    def reset(self):
        """Reset the simulator."""
        self._stop_flag.clear()
    
    def is_stopped(self) -> bool:
        """Check if stopped."""
        return self._stop_flag.is_set()


# Test
if __name__ == "__main__":
    print("Low-Level Key Simulator Test (Windows SendInput)")
    print("=" * 60)
    print("This uses Windows SendInput API - works with most games!")
    print("Test will press Q, W, E keys.")
    print()
    
    input("Press Enter to start test (you have 3 seconds to switch windows)...")
    
    simulator = LowLevelKeySimulator()
    
    time.sleep(3)  # Give time to switch windows
    
    try:
        print("Pressing Q...")
        simulator.press_key('Q', 500, lambda k: print(f"  -> {k}"))
        
        print("Pausing...")
        simulator.pause(200)
        
        print("Pressing W...")
        simulator.press_key('W', 300, lambda k: print(f"  -> {k}"))
        
        print("Pausing...")
        simulator.pause(200)
        
        print("Pressing E...")
        simulator.press_key('E', 500, lambda k: print(f"  -> {k}"))
        
        print("\n✅ Test complete!")
        
    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
        simulator.emergency_stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
