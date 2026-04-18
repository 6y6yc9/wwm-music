"""
Note Parser Module
Reads and parses melody files in the simple text format.

Format:
    KEY DURATION_MS [PAUSE_MS]
    
Example:
    Q 500        # High pitch 1, hold for 500ms
    W 300 100    # High pitch 2, hold 300ms, pause 100ms
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import os


@dataclass
class Note:
    """Represents a single note to play."""
    key: str
    duration_ms: int
    pause_ms: int = 0
    
    def __str__(self):
        if self.pause_ms > 0:
            return f"{self.key} {self.duration_ms}ms + {self.pause_ms}ms pause"
        return f"{self.key} {self.duration_ms}ms"


class NoteParser:
    """Parser for melody files."""
    
    # Valid keys based on the instrument layout (3 octaves × 7 notes = 21 keys)
    VALID_KEYS = {
        # High Pitch (row 1)
        'Q', 'W', 'E', 'R', 'T', 'Y', 'U',
        # Medium Pitch (row 2)
        'A', 'S', 'D', 'F', 'G', 'H', 'J',
        # Low Pitch (row 3)
        'Z', 'X', 'C', 'V', 'B', 'N', 'M'
    }
    
    KEY_NAMES = {
        'Q': 'High 1', 'W': 'High 2', 'E': 'High 3', 'R': 'High 4',
        'T': 'High 5', 'Y': 'High 6', 'U': 'High 7',
        'A': 'Mid 1', 'S': 'Mid 2', 'D': 'Mid 3', 'F': 'Mid 4',
        'G': 'Mid 5', 'H': 'Mid 6', 'J': 'Mid 7',
        'Z': 'Low 1', 'X': 'Low 2', 'C': 'Low 3', 'V': 'Low 4',
        'B': 'Low 5', 'N': 'Low 6', 'M': 'Low 7'
    }
    
    def parse_file(self, filepath: str) -> Tuple[List[Note], str]:
        """
        Parse a melody file.
        
        Args:
            filepath: Path to the melody file
            
        Returns:
            Tuple of (notes list, melody name)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Melody file not found: {filepath}")
        
        notes = []
        melody_name = os.path.splitext(os.path.basename(filepath))[0]
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Strip whitespace and comments
                line = line.strip()
                if '#' in line:
                    line = line.split('#')[0].strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Parse note
                try:
                    note = self._parse_line(line, line_num)
                    notes.append(note)
                except ValueError as e:
                    raise ValueError(f"Line {line_num}: {e}")
        
        if not notes:
            raise ValueError("No valid notes found in file")
        
        return notes, melody_name
    
    def _parse_line(self, line: str, line_num: int) -> Note:
        """Parse a single line into a Note object."""
        parts = line.split()
        
        if len(parts) < 2:
            raise ValueError(f"Invalid format. Expected: KEY DURATION [PAUSE]")
        
        key = parts[0].upper()
        
        # Validate key
        if key not in self.VALID_KEYS:
            raise ValueError(
                f"Invalid key '{key}'. Valid keys: {', '.join(sorted(self.VALID_KEYS))}"
            )
        
        # Parse duration
        try:
            duration_ms = int(parts[1])
            if duration_ms <= 0:
                raise ValueError("Duration must be positive")
        except ValueError:
            raise ValueError(f"Invalid duration '{parts[1]}'. Must be a positive integer")
        
        # Parse optional pause
        pause_ms = 0
        if len(parts) >= 3:
            try:
                pause_ms = int(parts[2])
                if pause_ms < 0:
                    raise ValueError("Pause must be non-negative")
            except ValueError:
                raise ValueError(f"Invalid pause '{parts[2]}'. Must be a non-negative integer")
        
        return Note(key=key, duration_ms=duration_ms, pause_ms=pause_ms)
    
    def get_melody_info(self, notes: List[Note]) -> dict:
        """Get information about a melody."""
        total_duration = sum(note.duration_ms + note.pause_ms for note in notes)
        unique_keys = len(set(note.key for note in notes))
        
        return {
            'total_notes': len(notes),
            'unique_keys': unique_keys,
            'total_duration_ms': total_duration,
            'total_duration_sec': total_duration / 1000.0
        }
    
    @classmethod
    def get_key_name(cls, key: str) -> str:
        """Get the friendly name for a key."""
        return cls.KEY_NAMES.get(key.upper(), key)


# Test function
if __name__ == "__main__":
    parser = NoteParser()
    
    # Test parsing
    test_data = """
    # Test melody
    Q 500
    W 300 100
    E 500
    """
    
    # Create a test file
    test_file = "test_melody.txt"
    with open(test_file, 'w') as f:
        f.write(test_data)
    
    try:
        notes, name = parser.parse_file(test_file)
        print(f"Melody: {name}")
        print(f"Notes: {len(notes)}")
        for i, note in enumerate(notes, 1):
            print(f"  {i}. {note}")
        
        info = parser.get_melody_info(notes)
        print(f"\nInfo: {info}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
