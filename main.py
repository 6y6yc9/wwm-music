"""
Music Auto-Player GUI
Main application for playing melodies in the game.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import logging
from pathlib import Path
from note_parser import Note, NoteParser
from playback_engine import PlaybackEngine, PlaybackState


def _setup_logging():
    """Redirect stdout/stderr to a log file so debug info is preserved."""
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wwm_music.log")
    try:
        log_file = open(log_path, "w", encoding="utf-8")
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass  # If we can't create log, just continue with console output


def _hide_console():
    """Hide the console window on Windows (only when launched via double-click/bat)."""
    try:
        import ctypes
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE = 0
    except Exception:
        pass  # Non-Windows or no console — silently ignore


class MusicPlayerGUI:
    """Main GUI application."""
    
    # Color scheme
    COLOR_BG = "#1a1a2e"
    COLOR_PANEL = "#16213e"
    COLOR_ACCENT = "#0f3460"
    COLOR_HIGHLIGHT = "#e94560"
    COLOR_TEXT = "#eaeaea"
    COLOR_MUTED = "#888888"
    
    # Key colors by octave
    COLOR_HIGH = "#ff6b9d"    # Pink
    COLOR_MID = "#4ecdc4"     # Teal
    COLOR_LOW = "#feca57"     # Yellow
    COLOR_ACTIVE = "#00ff88"  # Bright green for active note
    
    def __init__(self, root):
        self.root = root
        self.root.title("WWM Music Auto-Player")
        self.root.geometry("900x750")
        self.root.minsize(750, 650)
        self.root.configure(bg=self.COLOR_BG)
        
        # State
        self.parser = NoteParser()
        self.engine = PlaybackEngine(
            on_note_start=self._on_note_start,
            on_note_end=self._on_note_end,
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
            use_lowlevel=True  # Use low-level driver for game compatibility
        )
        
        self.melody_name = "No melody loaded"
        self.melody_notes = []
        self.key_buttons = {}
        
        # Build UI
        self._build_ui()
        
        # Start UI update loop
        self._update_ui()
    
    def _build_ui(self):
        """Build the user interface."""
        
        # Title
        title_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        title_frame.pack(pady=20)
        
        title_label = tk.Label(
            title_frame,
            text="🎵 WWM Music Auto-Player",
            font=("Segoe UI", 24, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_frame,
            text="Automatic instrument player for social experiments",
            font=("Segoe UI", 10),
            bg=self.COLOR_BG,
            fg=self.COLOR_MUTED
        )
        subtitle_label.pack()
        
        # Melody info
        info_frame = tk.Frame(self.root, bg=self.COLOR_PANEL, relief=tk.RAISED, bd=2)
        info_frame.pack(pady=10, padx=20, fill=tk.X)
        
        self.melody_label = tk.Label(
            info_frame,
            text="No melody loaded",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLOR_PANEL,
            fg=self.COLOR_HIGHLIGHT,
            anchor=tk.W
        )
        self.melody_label.pack(pady=10, padx=10, fill=tk.X)
        
        self.info_label = tk.Label(
            info_frame,
            text="",
            font=("Segoe UI", 9),
            bg=self.COLOR_PANEL,
            fg=self.COLOR_MUTED,
            anchor=tk.W
        )
        self.info_label.pack(pady=(0, 10), padx=10, fill=tk.X)
        
        # Virtual keyboard
        keyboard_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        keyboard_frame.pack(pady=20)
        
        self._build_keyboard(keyboard_frame)
        
        # Progress bar
        progress_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        progress_frame.pack(pady=10, padx=20, fill=tk.X)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack()
        
        self.progress_label = tk.Label(
            progress_frame,
            text="0 / 0",
            font=("Segoe UI", 9),
            bg=self.COLOR_BG,
            fg=self.COLOR_MUTED
        )
        self.progress_label.pack(pady=5)
        
        # Control buttons — Row 1: Import sources
        import_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        import_frame.pack(pady=(15, 5))
        
        self.load_btn = tk.Button(
            import_frame,
            text="📁 Load Melody",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._load_melody
        )
        self.load_btn.grid(row=0, column=0, padx=4)
        
        self.import_btn = tk.Button(
            import_frame,
            text="🎹 Import MIDI",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._import_midi
        )
        self.import_btn.grid(row=0, column=1, padx=4)
        
        self.yt_btn = tk.Button(
            import_frame,
            text="🔴 YouTube",
            font=("Segoe UI", 10, "bold"),
            bg="#cc0000",
            fg="#ffffff",
            activebackground="#ff3333",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._import_youtube
        )
        self.yt_btn.grid(row=0, column=2, padx=4)

        # Control buttons — Row 2: Playback controls
        control_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        control_frame.pack(pady=(5, 15))

        self.play_btn = tk.Button(
            control_frame,
            text="▶ Play",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._play,
            state=tk.DISABLED
        )
        self.play_btn.grid(row=0, column=0, padx=4)
        
        self.pause_btn = tk.Button(
            control_frame,
            text="⏸ Pause",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._pause,
            state=tk.DISABLED
        )
        self.pause_btn.grid(row=0, column=1, padx=4)
        
        self.stop_btn = tk.Button(
            control_frame,
            text="⏹ Stop",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._stop,
            state=tk.DISABLED
        )
        self.stop_btn.grid(row=0, column=2, padx=4)
        
        self.save_btn = tk.Button(
            control_frame,
            text="💾 Save",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLOR_ACCENT,
            fg=self.COLOR_TEXT,
            activebackground=self.COLOR_HIGHLIGHT,
            activeforeground=self.COLOR_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._save_melody,
            state=tk.DISABLED
        )
        self.save_btn.grid(row=0, column=3, padx=4)
        
        # Status
        status_frame = tk.Frame(self.root, bg=self.COLOR_PANEL, relief=tk.SUNKEN, bd=1)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready [Low-Level Mode for Games]",
            font=("Segoe UI", 9),
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
    
    def _build_keyboard(self, parent):
        """Build the virtual keyboard visualization."""
        
        # Labels
        tk.Label(
            parent,
            text="High Pitch",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_HIGH
        ).grid(row=0, column=0, sticky=tk.W, padx=10)
        
        tk.Label(
            parent,
            text="Medium Pitch",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_MID
        ).grid(row=1, column=0, sticky=tk.W, padx=10)
        
        tk.Label(
            parent,
            text="Low Pitch",
            font=("Segoe UI", 9, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_LOW
        ).grid(row=2, column=0, sticky=tk.W, padx=10)
        
        # Keys
        rows = [
            ('Q', 'W', 'E', 'R', 'T', 'Y', 'U', self.COLOR_HIGH),
            ('A', 'S', 'D', 'F', 'G', 'H', 'J', self.COLOR_MID),
            ('Z', 'X', 'C', 'V', 'B', 'N', 'M', self.COLOR_LOW)
        ]
        
        for row_idx, row_data in enumerate(rows):
            *keys, color = row_data
            for col_idx, key in enumerate(keys):
                btn = tk.Label(
                    parent,
                    text=f"{key}\n{col_idx + 1}",
                    font=("Segoe UI", 10, "bold"),
                    bg=color,
                    fg="#000000",
                    width=5,
                    height=2,
                    relief=tk.RAISED,
                    bd=3
                )
                btn.grid(row=row_idx, column=col_idx + 1, padx=3, pady=3)
                self.key_buttons[key] = (btn, color)
    
    def _import_midi(self):
        """Import a MIDI file and convert to melody with track selection."""
        try:
            from midi_converter import MidiConverter
        except ImportError:
            messagebox.showerror("Error", "MIDI module not installed. Run 'pip install mido'.")
            return

        filepath = filedialog.askopenfilename(
            title="Import MIDI File",
            initialdir="./",
            filetypes=[("MIDI Files", "*.mid;*.midi"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
            
        self._process_midi_file(filepath)

    def _import_youtube(self):
        """Import audio from YouTube and convert to melody."""
        # 1. Ask for URL + stem mode + preset
        url_window = tk.Toplevel(self.root)
        url_window.title("Import from YouTube")
        url_window.geometry("520x380")
        url_window.transient(self.root)
        url_window.grab_set()
        
        tk.Label(url_window, text="Enter YouTube Video URL:", font=("Segoe UI", 10)).pack(pady=10)
        
        url_entry = tk.Entry(url_window, width=50, font=("Segoe UI", 10))
        url_entry.pack(pady=5)
        url_entry.focus_set()
        
        # Add Paste Button
        def paste_from_clipboard():
            try:
                url_entry.delete(0, tk.END)
                url_entry.insert(0, self.root.clipboard_get())
            except Exception:
                pass
                
        tk.Button(url_window, text="📋 Paste", command=paste_from_clipboard,
                 font=("Segoe UI", 8)).pack(pady=2)
                 
        # Right-click context menu
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Paste", command=paste_from_clipboard)
        
        def show_menu(event):
            m.tk_popup(event.x_root, event.y_root)
            
        url_entry.bind("<Button-3>", show_menu)
        url_entry.bind("<Control-v>", lambda e: paste_from_clipboard())
        
        # --- Source Separation Mode (NEW) ---
        stem_frame = tk.Frame(url_window)
        stem_frame.pack(pady=8)
        
        tk.Label(stem_frame, text="🔀 Source Separation:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        stem_descriptions = {
            "vocals": "🎤 Vocal Only (Best for songs)",
            "melody": "🎵 Melody (Vocals+Instruments)",
            "full_no_drums": "🎼 Full (No Drums)",
            "no_separation": "⚡ Fast (No Separation — old behavior)",
        }
        
        stem_var = tk.StringVar(value="vocals")
        stem_combo = ttk.Combobox(url_window, textvariable=stem_var, state="readonly",
                                   values=list(stem_descriptions.values()),
                                   width=40, font=("Segoe UI", 9))
        stem_combo.current(0)
        stem_combo.pack(pady=2)
        
        stem_display_to_key = {v: k for k, v in stem_descriptions.items()}
        
        # --- Transcription Quality Preset ---
        preset_frame = tk.Frame(url_window)
        preset_frame.pack(pady=8)
        
        tk.Label(preset_frame, text="🎯 Transcription Quality:", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        
        preset_descriptions = {
            "balanced": "⚖️ Balanced (Recommended)",
            "clean": "🎵 Clean (Less noise, keeps bass)",
            "melody_only": "🎹 Melody Only (No bass)",
            "vocal": "🎤 Vocal Track",
            "full": "🔥 Full (All notes)",
        }
        
        preset_var = tk.StringVar(value="balanced")
        preset_combo = ttk.Combobox(url_window, textvariable=preset_var, state="readonly",
                                     values=list(preset_descriptions.values()),
                                     width=35, font=("Segoe UI", 9))
        preset_combo.current(0)
        preset_combo.pack(pady=2)
        
        # Map display name back to preset key
        display_to_key = {v: k for k, v in preset_descriptions.items()}
        
        def start_download():
            url = url_entry.get().strip()
            if not url: return
            selected_display = preset_combo.get()
            selected_preset = display_to_key.get(selected_display, "balanced")
            selected_stem_display = stem_combo.get()
            selected_stem = stem_display_to_key.get(selected_stem_display, "vocals")
            url_window.destroy()
            self._start_youtube_process(url, preset=selected_preset, stem_mode=selected_stem)
            
        tk.Button(url_window, text="Download & Convert", bg=self.COLOR_ACCENT, fg=self.COLOR_TEXT,
                 font=("Segoe UI", 10, "bold"), command=start_download).pack(pady=10)
        
        self.root.wait_window(url_window)

    def _start_youtube_process(self, url, preset="balanced", stem_mode="vocals"):
        """Run download, separation, transcription, and AUTO-OPTIMIZED conversion in background thread."""
        import threading
        
        def run_thread():
            try:
                # 1. Download
                self.root.after(0, lambda: self.status_label.config(text="Downloading audio from YouTube..."))
                
                from youtube_downloader import download_audio
                wav_path = download_audio(url, output_dir="downloads")
                
                if not wav_path:
                    raise Exception("Failed to download audio")
                
                # 2. Separate + Transcribe (new pipeline)
                if stem_mode != "no_separation":
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"🔀 Separating audio stems [{stem_mode}] (This takes time)..."))
                
                self.root.after(0, lambda: self.status_label.config(
                    text=f"AI Transcribing [{preset}] + Separation [{stem_mode}]..."))
                
                from audio_transcriber import transcribe_with_separation
                midi_path = transcribe_with_separation(
                    wav_path, preset=preset, stem_mode=stem_mode)
                
                if not midi_path:
                    raise Exception("Failed to transcribe audio")
                
                # 3. AUTO-OPTIMIZE: Convert with best settings for recognizability
                self.root.after(0, lambda: self.status_label.config(
                    text="Auto-optimizing melody for recognizability..."))
                self.root.after(0, lambda: self._auto_convert_youtube(midi_path, preset, stem_mode))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("YouTube Error", str(e)))
                self.root.after(0, lambda: self.status_label.config(text="Error processing YouTube"))
        
        threading.Thread(target=run_thread, daemon=True).start()

    def _auto_convert_youtube(self, midi_path, preset, stem_mode="no_separation"):
        """
        Auto-convert YouTube-transcribed MIDI with optimal settings for recognizability.
        Selects best tracks, detects lead, and enables smart melody extraction automatically.
        """
        try:
            from midi_converter import MidiConverter
            converter = MidiConverter()
            tracks = converter.analyze_tracks(midi_path)
            
            # Auto-select: all non-drum tracks with notes
            track_ids = [t['id'] for t in tracks if t['notes'] > 0 and not t['is_drum']]
            
            if not track_ids:
                # Fallback: all tracks with notes
                track_ids = [t['id'] for t in tracks if t['notes'] > 0]
            
            if not track_ids:
                messagebox.showerror("Error", "No notes found in transcribed audio.")
                return
            
            # Auto-detect lead track: track with most notes in vocal range (C4=60 to C6=84)
            lead_track_id = None
            if len(track_ids) > 1:
                best_vocal_count = 0
                for t in tracks:
                    if t['id'] not in track_ids:
                        continue
                    # avg_pitch in vocal range = likely melody
                    if 55 <= t['avg_pitch'] <= 84:
                        if t['notes'] > best_vocal_count:
                            best_vocal_count = t['notes']
                            lead_track_id = t['id']
            
            print(f"YouTube Auto-Optimize: tracks={track_ids}, lead={lead_track_id}, stem={stem_mode}")
            
            # Convert with best settings for recognizability
            self._convert_and_load(
                midi_path, 
                track_ids,
                quantize=True,           # Clean timing
                lead_track_id=lead_track_id,
                allow_chords=False,       # Monophonic for clarity
                filter_bass=False,        # Keep all notes, let melody extraction handle it
                simplify_chords=False,
                melody_priority=True,     # KEY: Smart melody extraction + interval snap
                octave_offset=0,
                rhythm_filter=False,      # Don't filter rhythm for YouTube
                instrument_name="default",
                smart_multitrack=False
            )
            
            sep_info = f" + {stem_mode}" if stem_mode != "no_separation" else ""
            self.status_label.config(text=f"YouTube [{preset}{sep_info}]: Auto-optimized ✓")
            
        except Exception as e:
            print(f"Auto-convert failed, falling back to manual: {e}")
            # Fallback to manual process
            self._process_midi_file(midi_path)

    def _process_midi_file(self, filepath):
        """Process a MIDI file (analyze, select track, convert)."""
        try:
            from midi_converter import MidiConverter
            
            # 1. Analyze tracks
            converter = MidiConverter()
            tracks = converter.analyze_tracks(filepath)
            
            if not tracks:
                messagebox.showerror("Error", "No tracks found in MIDI file.")
                return
                
            # 2. Show track selection dialog
            select_window = tk.Toplevel(self.root)
            select_window.title("Select Tracks to Import")
            select_window.geometry("500x650") # Increased height for all options
            select_window.transient(self.root)
            select_window.grab_set()
            
            tk.Label(select_window, text="Select track(s) containing the melody\n(Ctrl+Click to select multiple):", 
                    font=("Segoe UI", 10, "bold"), pady=10).pack()
            
            # Listbox with MULTIPLE selection
            list_frame = tk.Frame(select_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
            
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(list_frame, font=("Consolas", 10), yscrollcommand=scrollbar.set, selectmode=tk.MULTIPLE)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Populate list
            valid_indices = []
            for t in tracks:
                # Filter out empty tracks or pure control tracks
                if t['notes'] > 0:
                    drum_tag = "[DRUMS] " if t['is_drum'] else ""
                    info = f"{t['id']}: {drum_tag}{t['name']} ({t['notes']} notes)"
                    listbox.insert(tk.END, info)
                    valid_indices.append(t['id'])
                    
            if not valid_indices:
                 messagebox.showerror("Error", "No notes found in any track.")
                 select_window.destroy()
                 return
                 
            # Select first non-drum track with notes by default
            listbox.selection_set(0)
            
            # Capture results
            selected_track_ids = []
            
            def finalize():
                selections = listbox.curselection()
                if selections:
                    selected_track_ids.clear()
                    track_names = []
                    
                    for idx in selections:
                        selected_track_ids.append(valid_indices[idx])
                        track_names.append(listbox.get(idx))
                        
                    select_window.destroy()
                    
                    # If multiple tracks, ask for Lead Track
                    lead_track_id = None
                    if len(selected_track_ids) > 1:
                        lead_window = tk.Toplevel(self.root)
                        lead_window.title("Select Lead Track")
                        lead_window.geometry("400x300")
                        lead_window.transient(self.root)
                        lead_window.grab_set()
                        
                        tk.Label(lead_window, text="Which track is the MAIN Melody?\n(Notes from this track will have priority)", 
                                font=("Segoe UI", 10, "bold"), pady=10).pack()
                        
                        # Add Mix/None option
                        lead_var = tk.IntVar(value=-1)
                        
                        tk.Radiobutton(lead_window, text="Mix All Equally (Highest Note Wins)", variable=lead_var, value=-1, 
                                      font=("Segoe UI", 10)).pack(anchor=tk.W, padx=20)
                        
                        for tid, name in zip(selected_track_ids, track_names):
                            tk.Radiobutton(lead_window, text=name, variable=lead_var, value=tid, 
                                          font=("Segoe UI", 10)).pack(anchor=tk.W, padx=20)
                                          
                        def confirm_lead():
                            lead_window.destroy()
                            
                        tk.Button(lead_window, text="Continue", bg=self.COLOR_ACCENT, fg=self.COLOR_TEXT,
                                 font=("Segoe UI", 10, "bold"), command=confirm_lead).pack(pady=20)
                                 
                        self.root.wait_window(lead_window)
                        if lead_var.get() != -1:
                            lead_track_id = lead_var.get()
                            
                            
                            
                    # Convert
                    self._convert_and_load(filepath, selected_track_ids, quantize_var.get(), lead_track_id, chords_var.get(), filter_bass_var.get(), simplify_var.get(), melody_var.get(), octave_var.get(), rhythm_var.get(), smart_multitrack=multitrack_var.get())

            # Add Instrument Selection (New)
            import json
            try:
                with open("instruments.json", "r", encoding="utf-8") as f:
                    instruments = json.load(f)
            except:
                instruments = {"default": {"name": "Default"}}
            
            instrument_names = [data["name"] for key, data in instruments.items()]
            # Map name back to key
            name_to_key = {data["name"]: key for key, data in instruments.items()}
            
            tk.Label(select_window, text="Select Target Instrument:", font=("Segoe UI", 10, "bold"), pady=5).pack()
            
            instrument_var = tk.StringVar(value=instruments.get("default", {}).get("name", "Default"))
            inst_combo = ttk.Combobox(select_window, textvariable=instrument_var, values=instrument_names, state="readonly", font=("Segoe UI", 10))
            inst_combo.pack(pady=2)
            
            def on_inst_change(event):
                # Detect percussion instrument and auto-select drum tracks
                selected_name = instrument_var.get()
                inst_key = name_to_key.get(selected_name, "default")
                inst_config = instruments.get(inst_key, {})
                is_perc = inst_config.get("type") == "percussion"
                
                if is_perc:
                    # Auto-select drum tracks in the listbox
                    listbox.selection_clear(0, tk.END)
                    for list_idx, vid in enumerate(valid_indices):
                        # Find tracks marked as [DRUMS]
                        item_text = listbox.get(list_idx)
                        if "[DRUMS]" in item_text:
                            listbox.selection_set(list_idx)
                    
                    # Show hint
                    self.status_label.config(text="🥁 Percussion mode: drum tracks auto-selected")
                else:
                    self.status_label.config(text="Ready")
                    
            inst_combo.bind("<<ComboboxSelected>>", on_inst_change)

            # Add Quantize Checkbox
            quantize_var = tk.BooleanVar(value=True) # Default True
            tk.Checkbutton(select_window, text="Quantize (Align to 1/16 Grid)", variable=quantize_var,
                          font=("Segoe UI", 10)).pack(pady=5)
                          
            # Add Chords/Arpeggio Checkbox
            chords_var = tk.BooleanVar(value=False) # Default False (Monophonic)
            tk.Checkbutton(select_window, text="Play Chords (Fast Arpeggio)", variable=chords_var,
                          font=("Segoe UI", 10)).pack(pady=5)
                          
            # Add Bass Filter Checkbox (Smart Split)
            filter_bass_var = tk.BooleanVar(value=False)
            tk.Checkbutton(select_window, text="Ignore Low Bass (Fix 'Messy' Audio)", variable=filter_bass_var,
                          font=("Segoe UI", 10)).pack(pady=2)

            # Add Simplify Chords (Hollow) Checkbox
            simplify_var = tk.BooleanVar(value=False)
            tk.Checkbutton(select_window, text="Simplify Chords (Keep Melody+Bass Only)", variable=simplify_var,
                          font=("Segoe UI", 10)).pack(pady=2)

            # Add Smart Melody (Top Note Priority) Checkbox
            melody_var = tk.BooleanVar(value=False)
            tk.Checkbutton(select_window, text="🎵 Smart Melody (Recognizable Melody Extraction)", variable=melody_var,
                          font=("Segoe UI", 10, "bold"), fg=self.COLOR_ACCENT).pack(pady=2)

            # Add Rhythm Filter Checkbox (separate from Smart Melody)
            rhythm_var = tk.BooleanVar(value=False)
            tk.Checkbutton(select_window, text="🥁 Rhythm Filter (Remove noise, keep beat pattern)", variable=rhythm_var,
                          font=("Segoe UI", 10), fg="#666666").pack(pady=2)

            # Add Smart Multi-Track Checkbox
            multitrack_var = tk.BooleanVar(value=False)
            tk.Checkbutton(select_window, text="🎼 Smart Multi-Track (Per-track transposition)", variable=multitrack_var,
                          font=("Segoe UI", 10, "bold"), fg="#0f7460").pack(pady=2)

            # Add Octave Shift Spinbox
            octave_frame = tk.Frame(select_window)
            octave_frame.pack(pady=5)
            tk.Label(octave_frame, text="Manual Octave Shift:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            octave_var = tk.IntVar(value=0)
            tk.Spinbox(octave_frame, from_=-4, to=4, width=5, textvariable=octave_var, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
            
            def finalize_with_instrument():
                selections = listbox.curselection()
                if not selections: return
                
                selected_inst_key = name_to_key.get(instrument_var.get(), "default")
                
                # ... repeat finalize logic but trigger _convert_and_load with instrument
                # To avoid code duplication, we'll just leverage the existing flow but pass the instrument
                
                # Manually triggering the closure
                selected_track_ids.clear()
                for idx in selections:
                    selected_track_ids.append(valid_indices[idx])
                
                select_window.destroy()
                
                # Check Lead Track (Same logic as before)
                lead_track_id = None
                if len(selected_track_ids) > 1:
                     # (omitted for brevity, assume we want to keep it simple or copy it)
                     # For robustness, we should probably refactor finalize() to not be nested or duplicates
                     # But for now let's just use the logic in _convert_and_load
                     pass
                     
                # Since we destroyed the window, we can't accept input for lead track easily here without copy-paste
                # Let's fix this by updating `finalize` to read the combobox
                
            # Update the original finalize button to read the instrument
            def finalize():
                selections = listbox.curselection()
                if selections:
                    selected_track_ids.clear()
                    track_names = []
                    
                    for idx in selections:
                        selected_track_ids.append(valid_indices[idx])
                        track_names.append(listbox.get(idx))
                        
                    select_window.destroy()
                    
                    selected_inst_key = name_to_key.get(instrument_var.get(), "default")
                    inst_config = instruments.get(selected_inst_key, {})
                    is_perc = inst_config.get("type") == "percussion"
                    
                    # Percussion: skip lead track, melody options — go straight to convert
                    if is_perc:
                        self._convert_and_load(filepath, selected_track_ids, quantize_var.get(), None, False, False, False, False, 0, False, instrument_name=selected_inst_key, smart_multitrack=False)
                        return
                    
                    # If multiple tracks, ask for Lead Track
                    lead_track_id = None
                    if len(selected_track_ids) > 1:
                        lead_window = tk.Toplevel(self.root)
                        lead_window.title("Select Lead Track")
                        lead_window.geometry("500x400")
                        lead_window.minsize(400, 250)
                        lead_window.transient(self.root)
                        lead_window.grab_set()
                        
                        tk.Label(lead_window, text="Which track is the MAIN Melody?\n(Notes from this track will have priority)", 
                                font=("Segoe UI", 10, "bold"), pady=10).pack()
                        
                        # Scrollable frame for radio buttons
                        lead_scroll_frame = tk.Frame(lead_window)
                        lead_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10)
                        
                        lead_canvas = tk.Canvas(lead_scroll_frame, highlightthickness=0)
                        lead_scrollbar = tk.Scrollbar(lead_scroll_frame, orient=tk.VERTICAL, command=lead_canvas.yview)
                        lead_inner = tk.Frame(lead_canvas)
                        
                        lead_inner.bind("<Configure>", lambda e: lead_canvas.configure(scrollregion=lead_canvas.bbox("all")))
                        lead_canvas.create_window((0, 0), window=lead_inner, anchor=tk.NW)
                        lead_canvas.configure(yscrollcommand=lead_scrollbar.set)
                        
                        lead_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        lead_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                        
                        # Mouse wheel scrolling
                        def _on_lead_mousewheel(event):
                            lead_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        lead_canvas.bind_all("<MouseWheel>", _on_lead_mousewheel)
                        
                        # Add Mix/None option
                        lead_var = tk.IntVar(value=-1)
                        
                        tk.Radiobutton(lead_inner, text="Mix All Equally (Highest Note Wins)", variable=lead_var, value=-1, 
                                      font=("Segoe UI", 10)).pack(anchor=tk.W, padx=10, pady=2)
                        
                        for tid, name in zip(selected_track_ids, track_names):
                            tk.Radiobutton(lead_inner, text=name, variable=lead_var, value=tid, 
                                          font=("Segoe UI", 10)).pack(anchor=tk.W, padx=10, pady=2)
                                          
                        def confirm_lead():
                            lead_canvas.unbind_all("<MouseWheel>")
                            lead_window.destroy()
                            self._convert_and_load(filepath, selected_track_ids, quantize_var.get(), lead_var.get() if lead_var.get() != -1 else None, chords_var.get(), filter_bass_var.get(), simplify_var.get(), melody_var.get(), octave_var.get(), rhythm_var.get(), instrument_name=selected_inst_key, smart_multitrack=multitrack_var.get())

                        # Button pinned at bottom, always visible
                        tk.Button(lead_window, text="Continue", bg=self.COLOR_ACCENT, fg=self.COLOR_TEXT,
                                 font=("Segoe UI", 10, "bold"), command=confirm_lead, padx=30, pady=8).pack(pady=10)
                                 
                        self.root.wait_window(lead_window)
                    else:
                        # Single track
                        self._convert_and_load(filepath, selected_track_ids, quantize_var.get(), None, chords_var.get(), filter_bass_var.get(), simplify_var.get(), melody_var.get(), octave_var.get(), rhythm_var.get(), instrument_name=selected_inst_key, smart_multitrack=multitrack_var.get())

            tk.Button(select_window, text="Import Selected Track(s)", bg=self.COLOR_ACCENT, fg=self.COLOR_TEXT,
                     font=("Segoe UI", 10, "bold"), command=finalize).pack(pady=10)
            
            self.root.wait_window(select_window)
            
        except Exception as e:
            messagebox.showerror("MIDI Import Error", str(e))

    def _convert_and_load(self, filepath, track_ids, quantize, lead_track_id, allow_chords, filter_bass, simplify_chords, melody_priority=False, octave_offset=0, rhythm_filter=False, instrument_name="default", smart_multitrack=False):
        try:
            from midi_converter import MidiConverter
            # Initialize with selected instrument
            converter = MidiConverter(instrument_name=instrument_name)
            output_path = os.path.splitext(filepath)[0] + f"_{instrument_name}.txt"
            
            self.status_label.config(text=f"Converting {len(track_ids)} tracks...")
            self.root.update()
            
            # Smart Split: Filter Bass
            # Use instrument's min note if available, otherwise default
            min_pitch = converter.MIN_NOTE if filter_bass else None 
            
            text_file = converter.convert_tracks(
                filepath, 
                track_ids, 
                output_path, 
                quantize=quantize,
                lead_track_id=lead_track_id,
                allow_chords=allow_chords,
                min_pitch=min_pitch,
                max_pitch=None,
                simplify_chords=simplify_chords,
                melody_priority=melody_priority,
                octave_offset=octave_offset,
                rhythm_filter=rhythm_filter,
                smart_multitrack=smart_multitrack
            )
            
            self._load_file(text_file)
            lead_info = f"\nLead Track: {lead_track_id}" if lead_track_id is not None else "\nLead: Mix"
            chord_info = "\nMode: Arpeggio" if allow_chords else "\nMode: Single Note"
            filter_info = "\nBass Filter: ON" if filter_bass else ""
            simplify_info = "\nSimplify: ON" if simplify_chords else ""
            multitrack_info = "\nSmart Multi-Track: ON" if smart_multitrack else ""
            messagebox.showinfo("Success", f"Tracks imported!\nCount: {len(track_ids)}\nQuantize: {quantize}{lead_info}{chord_info}{filter_info}{simplify_info}{multitrack_info}\nSaved to: {os.path.basename(text_file)}")
            
        except Exception as e:
            messagebox.showerror("MIDI Import Error", str(e))
            self.status_label.config(text="Error importing MIDI")

    def _save_melody(self):
        """Save the currently loaded melody to a file."""
        if not self.melody_notes:
            messagebox.showwarning("No Melody", "No melody loaded to save.")
            return
        
        # Suggest filename based on current melody name
        default_name = self.melody_name.replace(" ", "_") + ".txt"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Melody As",
            initialdir="./melodies",
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {self.melody_name}\n")
                for note in self.melody_notes:
                    if note.pause_ms > 0:
                        f.write(f"{note.key} {note.duration_ms} {note.pause_ms}\n")
                    else:
                        f.write(f"{note.key} {note.duration_ms}\n")
            
            self.status_label.config(text=f"Saved: {os.path.basename(filepath)}")
            messagebox.showinfo("Saved", f"Melody saved to:\n{os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _load_melody(self):
        """Load a melody from file."""
        filepath = filedialog.askopenfilename(
            title="Select Melody File",
            initialdir="./melodies",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
        
        self._load_file(filepath)

    def _load_file(self, filepath):
        """Helper to load a melody file."""
        try:
            notes, name = self.parser.parse_file(filepath)
            info = self.parser.get_melody_info(notes)
            
            self.melody_notes = notes
            self.melody_name = name
            
            # Update UI
            self.melody_label.config(text=f"🎵 {name}")
            
            self.info_label.config(
                text=f"{info['total_notes']} notes  •  "
                     f"{info['unique_keys']} unique keys  •  "
                     f"{info['total_duration_sec']:.1f} seconds"
            )
            
            # Load into engine
            self.engine.load_melody(notes)
            
            # Enable play and save buttons
            self.play_btn.config(state=tk.NORMAL)
            self.save_btn.config(state=tk.NORMAL)
            self.status_label.config(text=f"Loaded: {name}")
            
        except Exception as e:
            messagebox.showerror("Error Loading Melody", str(e))
    
    def _play(self):
        """Start or resume playback."""
        try:
            # Check if resuming from pause
            if self.engine.get_state() == PlaybackState.PAUSED:
                self.engine.play()
                self.play_btn.config(state=tk.DISABLED)
                self.pause_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.NORMAL)
                self.load_btn.config(state=tk.DISABLED)
                self.status_label.config(text="Playing...")
                return
            
            # Show warning and countdown for new playback
            result = messagebox.showinfo(
                "⚠️ Switch to Game!",
                "After clicking OK, you have 3 SECONDS to switch to the game window!\n\n"
                "Instructions:\n"
                "1. Click OK\n"
                "2. Immediately switch to the game (Alt+Tab)\n"
                "3. Make sure the instrument is open\n"
                "4. Playback will start automatically in 3 seconds\n\n"
                "⚠️ The game window MUST be active to receive key presses!"
            )
            
            # Start countdown
            self._start_countdown()
            
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))
    
    def _start_countdown(self):
        """Start 3-second countdown before playback."""
        self.countdown = 3
        self.play_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self._countdown_tick()
    
    def _countdown_tick(self):
        """Countdown tick."""
        if self.countdown > 0:
            self.status_label.config(
                text=f"⏱️ Starting in {self.countdown}... (Switch to game NOW!)",
                fg=self.COLOR_HIGHLIGHT
            )
            self.countdown -= 1
            self.root.after(1000, self._countdown_tick)
        else:
            # Start playback
            self.status_label.config(text="Playing...", fg=self.COLOR_TEXT)
            self.engine.play()
            self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
    
    def _pause(self):
        """Pause playback."""
        self.engine.pause()
        self.play_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Paused")
    
    def _stop(self):
        """Stop playback."""
        self.engine.stop()
        self.play_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Stopped")
        
        # Reset progress
        self.progress_var.set(0)
        self.progress_label.config(text="0 / 0")
    
    # Callbacks from engine
    
    def _on_note_start(self, idx, note):
        """Called when note starts playing."""
        # Highlight the key
        if note.key in self.key_buttons:
            btn, _ = self.key_buttons[note.key]
            btn.config(bg=self.COLOR_ACTIVE)
    
    def _on_note_end(self, idx, note):
        """Called when note ends."""
        # Reset key color
        if note.key in self.key_buttons:
            btn, original_color = self.key_buttons[note.key]
            btn.config(bg=original_color)
    
    def _on_progress(self, current, total):
        """Called on progress update."""
        progress = (current / total * 100) if total > 0 else 0
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{current} / {total}")
    
    def _on_complete(self):
        """Called when playback completes."""
        self.status_label.config(text="Complete!")
        self.play_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.NORMAL)
    
    def _on_error(self, error):
        """Called on error."""
        messagebox.showerror("Playback Error", str(error))
        self._stop()
    
    def _update_ui(self):
        """Periodic UI update loop."""
        # Update state-dependent UI elements
        state = self.engine.get_state()
        
        # Schedule next update
        self.root.after(100, self._update_ui)


def main():
    """Main entry point."""
    _hide_console()
    _setup_logging()
    root = tk.Tk()
    app = MusicPlayerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
