import json
import random
import shlex
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}


@dataclass
class EditConfig:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    output_file: str = "output_autoedit.mp4"
    recursive_scan: bool = True

    min_clip_sec: float = 1.5
    max_clip_sec: float = 4.5
    total_clips: int = 120
    resolution: str = "1920x1080"
    fps: int = 30
    crf: int = 20
    random_seed: str = ""

    transition_mode: str = "Cut"
    transition_sec: float = 0.30
    transition_fx: str = "Fade"

    dance_energy: int = 50
    beat_preset: str = "Auto"
    beat_sync: bool = True
    beat_strength: int = 60

    audio_mode: str = "Random one song"
    remix_mode: str = "Original"
    bpm_fallback: int = 128
    instant_vfx: bool = False
    draft_mode: bool = False

    intro_count: int = 1
    outro_count: int = 1

    speed_ramp: bool = True
    loop_chance: int = 15
    reverse_chance: int = 10
    stutter_chance: int = 8

    trailer_mode: str = "Off"
    branding_logo: str = ""
    branding_opacity: int = 70

    remix_style: str = "Beat remix"
    sfx_mode: str = "Random one"
    sfx_concat_count: int = 6


class AutoEditGUI:
    def __init__(self, root: tk.Tk, mode: str = "deluxe"):
        self.root = root
        self.mode = mode
        self.root.title("AutoEdits Music Videos 2010s - Super Deluxe GUI")
        self.config = EditConfig()

        self.video_files: List[str] = []
        self.video_folders: List[str] = []
        self.audio_files: List[str] = []
        self.music_files: List[str] = []
        self.sfx_files: List[str] = []
        self.intro_files: List[str] = []
        self.outro_files: List[str] = []

        self.vars: Dict[str, tk.Variable] = {}
        self.pool_listboxes: Dict[str, tk.Listbox] = {}
        self.log_var = tk.StringVar(value="Ready")

        self._build_ui()

    def _build_ui(self):
        root_frame = ttk.Frame(self.root, padding=10)
        root_frame.pack(fill="both", expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill="x")
        ttk.Button(header, text="Save preset JSON", command=self.save_preset).pack(side="left", padx=3)
        ttk.Button(header, text="Load preset JSON", command=self.load_preset).pack(side="left", padx=3)
        ttk.Button(header, text="Run Auto-Edit", command=self.run_async).pack(side="right", padx=3)

        paths = ttk.LabelFrame(root_frame, text="Tools + Output")
        paths.pack(fill="x", pady=6)
        self._entry_row(paths, "FFmpeg", "ffmpeg_path", browse_exec=True)
        self._entry_row(paths, "FFprobe", "ffprobe_path", browse_exec=True)
        self._entry_row(paths, "Output video", "output_file", browse_save=True)

        media = ttk.LabelFrame(root_frame, text="Media Pools")
        media.pack(fill="both", expand=True, pady=6)
        self._multi_pool(media, "video_files", "Video files", self.video_files, 0, 0, kinds=[("Video", VIDEO_EXTS)])
        self._multi_pool(media, "video_folders", "Video folders", self.video_folders, 0, 1, folder=True)
        self._multi_pool(media, "audio_files", "Audio sources", self.audio_files, 1, 0, kinds=[("Audio", AUDIO_EXTS)])
        self._multi_pool(media, "music_files", "Music sources", self.music_files, 1, 1, kinds=[("Audio", AUDIO_EXTS)])
        if self.mode != "small":
            self._multi_pool(media, "sfx_files", "SFX sources", self.sfx_files, 2, 0, kinds=[("Audio", AUDIO_EXTS)])
            self._multi_pool(media, "intro_files", "Intro assets", self.intro_files, 2, 1, kinds=[("Video", VIDEO_EXTS)])
            self._multi_pool(media, "outro_files", "Outro assets", self.outro_files, 3, 0, kinds=[("Video", VIDEO_EXTS)])
        media.columnconfigure(0, weight=1)
        media.columnconfigure(1, weight=1)

        settings = ttk.LabelFrame(root_frame, text="Generation Controls")
        settings.pack(fill="x", pady=6)
        self._controls(settings)

        ttk.Label(root_frame, textvariable=self.log_var, foreground="navy").pack(anchor="w", pady=4)

    def _controls(self, parent):
        panel = ttk.Frame(parent)
        panel.pack(fill="x", pady=4)

        def add(r, c, label, key, default, widget="entry", values=None):
            ttk.Label(panel, text=label).grid(row=r, column=c * 2, sticky="w", padx=3, pady=2)
            if widget == "combo":
                var = tk.StringVar(value=str(default))
                ctl = ttk.Combobox(panel, textvariable=var, values=values or [], state="readonly", width=16)
                ctl.grid(row=r, column=c * 2 + 1, sticky="we", padx=3, pady=2)
            elif widget == "check":
                var = tk.BooleanVar(value=bool(default))
                ctl = ttk.Checkbutton(panel, variable=var)
                ctl.grid(row=r, column=c * 2 + 1, sticky="w", padx=3, pady=2)
            else:
                var = tk.StringVar(value=str(default))
                ctl = ttk.Entry(panel, textvariable=var, width=16)
                ctl.grid(row=r, column=c * 2 + 1, sticky="we", padx=3, pady=2)
            self.vars[key] = var

        add(0, 0, "Min clip sec", "min_clip_sec", self.config.min_clip_sec)
        add(0, 1, "Max clip sec", "max_clip_sec", self.config.max_clip_sec)
        add(0, 2, "Total clips", "total_clips", self.config.total_clips)

        add(1, 0, "Resolution", "resolution", self.config.resolution)
        add(1, 1, "FPS", "fps", self.config.fps)
        add(1, 2, "CRF", "crf", self.config.crf)

        add(2, 0, "Random seed", "random_seed", self.config.random_seed)
        add(2, 1, "Transition", "transition_mode", self.config.transition_mode, widget="combo", values=["Cut", "Fade"])
        add(2, 2, "Transition sec", "transition_sec", self.config.transition_sec)

        if self.mode != "small":
            add(3, 0, "Transition FX", "transition_fx", self.config.transition_fx, widget="combo", values=["Fade", "Glitch", "Warp", "RGB Split"])
            add(3, 1, "Dance energy", "dance_energy", self.config.dance_energy)
            add(3, 2, "Beat preset", "beat_preset", self.config.beat_preset, widget="combo", values=["Auto", "Soft", "Hard", "Off"])

            add(4, 0, "Beat sync", "beat_sync", self.config.beat_sync, widget="check")
            add(4, 1, "Beat strength", "beat_strength", self.config.beat_strength)
            add(4, 2, "BPM fallback", "bpm_fallback", self.config.bpm_fallback)

            add(5, 0, "Audio mode", "audio_mode", self.config.audio_mode, widget="combo", values=["Random one song", "Combine all shuffled"])
            add(5, 1, "Remix mode", "remix_mode", self.config.remix_mode, widget="combo", values=["Original", "Nightcore", "Slow Jam", "Hyper Dance"])
            add(5, 2, "Instant VFX", "instant_vfx", self.config.instant_vfx, widget="check")

            add(6, 0, "10x draft mode", "draft_mode", self.config.draft_mode, widget="check")
            add(6, 1, "Intro clips", "intro_count", self.config.intro_count)
            add(6, 2, "Outro clips", "outro_count", self.config.outro_count)

            add(7, 0, "Speed ramp", "speed_ramp", self.config.speed_ramp, widget="check")
            add(7, 1, "Loop %", "loop_chance", self.config.loop_chance)
            add(7, 2, "Reverse %", "reverse_chance", self.config.reverse_chance)

            add(8, 0, "Stutter %", "stutter_chance", self.config.stutter_chance)
            add(8, 1, "Trailer mode", "trailer_mode", self.config.trailer_mode, widget="combo", values=["Off", "Trailer", "Teaser"])
            add(8, 2, "Remix style", "remix_style", self.config.remix_style, widget="combo", values=["Chaos remix", "Beat remix", "Meme remix", "YouTube Poop", "TikTok", "AMV"])

            add(9, 0, "Branding logo", "branding_logo", self.config.branding_logo)
            add(9, 1, "Logo opacity", "branding_opacity", self.config.branding_opacity)
            add(9, 2, "SFX mode", "sfx_mode", self.config.sfx_mode, widget="combo", values=["Off", "Random one", "Random concat bed"])
            add(10, 0, "SFX concat clips", "sfx_concat_count", self.config.sfx_concat_count)

        for col in [1, 3, 5]:
            panel.columnconfigure(col, weight=1)

        var = tk.BooleanVar(value=self.config.recursive_scan)
        self.vars["recursive_scan"] = var
        ttk.Checkbutton(parent, text="Recursive folder scan", variable=var).pack(anchor="w", padx=4, pady=2)

    def _entry_row(self, parent, label, key, browse_exec=False, browse_save=False):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        var = tk.StringVar(value=getattr(self.config, key))
        self.vars[key] = var
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        if browse_exec:
            ttk.Button(row, text="Browse", command=lambda: self._browse_exe(var)).pack(side="left", padx=4)
        if browse_save:
            ttk.Button(row, text="Browse", command=lambda: self._browse_output(var)).pack(side="left", padx=4)

    def _multi_pool(self, parent, pool_name, title, store, row, col, kinds=None, folder=False):
        frame = ttk.LabelFrame(parent, text=title)
        frame.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        lb = tk.Listbox(frame, height=4)
        lb.pack(fill="both", expand=True, padx=3, pady=3)
        self.pool_listboxes[pool_name] = lb

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", padx=3, pady=2)

        def add_items():
            if folder:
                p = filedialog.askdirectory()
                if p and p not in store:
                    store.append(p)
                    lb.insert("end", p)
                return
            patterns = [(k, " ".join([f"*{x}" for x in exts])) for k, exts in (kinds or [])]
            files = filedialog.askopenfilenames(filetypes=patterns or [("All", "*.*")])
            for p in files:
                if p not in store:
                    store.append(p)
                    lb.insert("end", p)

        def remove_sel():
            for idx in reversed(lb.curselection()):
                store.pop(idx)
                lb.delete(idx)

        ttk.Button(buttons, text="Add", command=add_items).pack(side="left", padx=2)
        ttk.Button(buttons, text="Remove", command=remove_sel).pack(side="left", padx=2)
        ttk.Button(buttons, text="Clear", command=lambda: self._clear_pool(lb, store)).pack(side="left", padx=2)

    @staticmethod
    def _clear_pool(lb: tk.Listbox, store: List[str]):
        store.clear()
        lb.delete(0, "end")

    def _browse_exe(self, var):
        p = filedialog.askopenfilename()
        if p:
            var.set(p)

    def _browse_output(self, var):
        p = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv")])
        if p:
            var.set(p)

    def _sync_config(self):
        c = self.config

        def as_bool(key):
            var = self.vars[key]
            if isinstance(var, tk.BooleanVar):
                return bool(var.get())
            return str(var.get()).strip().lower() in {"1", "true", "yes", "on"}

        def parse_value(cur, key):
            if key not in self.vars:
                return cur
            raw = self.vars[key].get()
            if isinstance(cur, bool):
                return as_bool(key)
            if isinstance(cur, int):
                return int(raw)
            if isinstance(cur, float):
                return float(raw)
            return raw

        for key in asdict(c).keys():
            setattr(c, key, parse_value(getattr(c, key), key))

        if c.min_clip_sec <= 0 or c.max_clip_sec <= 0:
            raise ValueError("Clip durations must be positive.")
        if c.max_clip_sec < c.min_clip_sec:
            raise ValueError("Max clip sec must be >= min clip sec.")
        if c.total_clips <= 0:
            raise ValueError("Total clips must be > 0.")
        if c.fps <= 0 or c.crf < 0:
            raise ValueError("FPS must be >0 and CRF must be >=0.")

    def _refresh_all_listboxes(self):
        mapping = {
            "video_files": self.video_files,
            "video_folders": self.video_folders,
            "audio_files": self.audio_files,
            "music_files": self.music_files,
            "sfx_files": self.sfx_files,
            "intro_files": self.intro_files,
            "outro_files": self.outro_files,
        }
        for name, items in mapping.items():
            lb = self.pool_listboxes.get(name)
            if not lb:
                continue
            lb.delete(0, "end")
            for item in items:
                lb.insert("end", item)

    def save_preset(self):
        self._sync_config()
        preset = {
            "config": asdict(self.config),
            "video_files": self.video_files,
            "video_folders": self.video_folders,
            "audio_files": self.audio_files,
            "music_files": self.music_files,
            "sfx_files": self.sfx_files,
            "intro_files": self.intro_files,
            "outro_files": self.outro_files,
        }
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2)
        self.log_var.set(f"Preset saved: {p}")

    def load_preset(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        with open(p, "r", encoding="utf-8") as f:
            payload = json.load(f)

        for key, value in payload.get("config", {}).items():
            if key in self.vars:
                self.vars[key].set(value)
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        for name in ["video_files", "video_folders", "audio_files", "music_files", "sfx_files", "intro_files", "outro_files"]:
            setattr(self, name, list(payload.get(name, [])))

        self._refresh_all_listboxes()
        self.log_var.set(f"Preset loaded: {p}")

    def run_async(self):
        try:
            self._sync_config()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        threading.Thread(target=self._run_edit, daemon=True).start()

    def _collect_videos(self) -> List[str]:
        videos = list(self.video_files)
        for folder in self.video_folders:
            p = Path(folder)
            if not p.exists():
                continue
            globber = p.rglob("*") if self.config.recursive_scan else p.glob("*")
            for file_path in globber:
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTS:
                    videos.append(str(file_path))
        return sorted(set(videos))

    def _probe_duration(self, media_path: str) -> float:
        cmd = [
            self.config.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        return float(subprocess.check_output(cmd, text=True).strip())

    def _probe_tbpm(self, media_path: str) -> Optional[float]:
        cmd = [
            self.config.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format_tags=TBPM",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        try:
            raw = subprocess.check_output(cmd, text=True).strip()
            return float(raw) if raw else None
        except Exception:
            return None

    def _run(self, cmd: List[str]):
        shown = " ".join(shlex.quote(x) for x in cmd[:8])
        self.log_var.set(f"Running: {shown}{' ...' if len(cmd) > 8 else ''}")
        subprocess.check_call(cmd)

    def _validate_tools(self):
        self._run([self.config.ffmpeg_path, "-version"])
        self._run([self.config.ffprobe_path, "-version"])

    @staticmethod
    def _write_concat_list(path: Path, files: List[Path]):
        with open(path, "w", encoding="utf-8") as f:
            for fp in files:
                clean = str(fp).replace("'", "'\\''")
                f.write(f"file '{clean}'\n")

    def _style_adjustments(self):
        style = self.config.remix_style
        loop = self.config.loop_chance
        rev = self.config.reverse_chance
        stutter = self.config.stutter_chance
        if style == "Chaos remix":
            loop, rev, stutter = max(loop, 30), max(rev, 20), max(stutter, 22)
        elif style == "Meme remix":
            loop, rev, stutter = max(loop, 25), max(rev, 14), max(stutter, 30)
        elif style == "YouTube Poop":
            loop, rev, stutter = max(loop, 35), max(rev, 25), max(stutter, 35)
        elif style == "TikTok":
            loop, rev, stutter = max(loop, 16), max(rev, 9), max(stutter, 18)
        elif style == "AMV":
            loop, rev, stutter = max(loop, 10), max(rev, 6), max(stutter, 6)
        return loop, rev, stutter

    def _transition_fx_filters(self):
        if self.config.transition_fx == "Glitch":
            return ["noise=alls=16:allf=t", "hue=h=2*t"]
        if self.config.transition_fx == "Warp":
            return ["rotate=0.02*sin(2*PI*t)", "vignette"]
        if self.config.transition_fx == "RGB Split":
            return ["eq=saturation=1.45:contrast=1.08", "gblur=sigma=0.8"]
        return []

    def _build_audio_bed(self, temp: Path, songs: List[str], rng: random.Random) -> Path:
        songs = list(songs)
        rng.shuffle(songs)
        if self.config.audio_mode == "Random one song":
            songs = [rng.choice(songs)]

        mix_file = temp / "music_mix.wav"

        if len(songs) == 1:
            song = songs[0]
            bpm = self._probe_tbpm(song) or float(self.config.bpm_fallback)
            atempo = 1.0
            if self.config.remix_mode == "Nightcore":
                atempo = 1.25
            elif self.config.remix_mode == "Slow Jam":
                atempo = 0.80
            elif self.config.remix_mode == "Hyper Dance":
                atempo = 1.35

            if self.config.beat_preset == "Soft":
                atempo *= 1.02
            elif self.config.beat_preset == "Hard":
                atempo *= 1.07
            elif self.config.beat_preset == "Auto":
                atempo *= 1.04 if bpm < 120 else 0.97

            self._run([self.config.ffmpeg_path, "-y", "-i", song, "-filter:a", f"atempo={atempo:.3f}", str(mix_file)])
            return mix_file

        concat_file = temp / "music_concat.txt"
        self._write_concat_list(concat_file, [Path(p) for p in songs])
        self._run([
            self.config.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            str(mix_file),
        ])
        return mix_file

    def _apply_sfx(self, temp: Path, base_audio: Path, rng: random.Random) -> Path:
        if not self.sfx_files or self.config.sfx_mode == "Off":
            return base_audio

        if self.config.sfx_mode == "Random one":
            sfx = rng.choice(self.sfx_files)
            out = temp / "audio_sfx.wav"
            self._run([
                self.config.ffmpeg_path,
                "-y",
                "-i",
                str(base_audio),
                "-i",
                sfx,
                "-filter_complex",
                "[1:a]volume=0.25[s];[0:a][s]amix=inputs=2:duration=first:dropout_transition=2",
                str(out),
            ])
            return out

        # Random concat bed
        picks = [Path(rng.choice(self.sfx_files)) for _ in range(max(1, self.config.sfx_concat_count))]
        sfx_concat = temp / "sfx_concat.txt"
        self._write_concat_list(sfx_concat, picks)
        sfx_bed = temp / "sfx_bed.wav"
        self._run([
            self.config.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(sfx_concat),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            str(sfx_bed),
        ])
        out = temp / "audio_sfx_bed.wav"
        self._run([
            self.config.ffmpeg_path,
            "-y",
            "-i",
            str(base_audio),
            "-i",
            str(sfx_bed),
            "-filter_complex",
            "[1:a]volume=0.20[s];[0:a][s]amix=inputs=2:duration=first:dropout_transition=2",
            str(out),
        ])
        return out

    def _run_edit(self):
        try:
            self._validate_tools()

            videos = self._collect_videos()
            if not videos:
                raise RuntimeError("No video files found.")
            songs = self.music_files or self.audio_files
            if not songs:
                raise RuntimeError("No music/audio sources provided.")

            rng = random.Random(self.config.random_seed or None)

            with tempfile.TemporaryDirectory(prefix="autoedit_") as tmp:
                temp = Path(tmp)

                selected: List[str] = []
                intros = [f for f in self.intro_files if Path(f).exists()]
                outros = [f for f in self.outro_files if Path(f).exists()]
                body = max(1, self.config.total_clips - min(self.config.intro_count, len(intros)) - min(self.config.outro_count, len(outros)))
                if self.config.trailer_mode == "Trailer":
                    body = min(body, 40)
                elif self.config.trailer_mode == "Teaser":
                    body = min(body, 20)

                selected.extend(rng.sample(intros, k=min(self.config.intro_count, len(intros))))
                selected.extend(rng.choice(videos) for _ in range(body))
                selected.extend(rng.sample(outros, k=min(self.config.outro_count, len(outros))))

                song_for_beat = rng.choice(songs)
                song_bpm = self._probe_tbpm(song_for_beat) or float(self.config.bpm_fallback)
                beat_len = 60.0 / max(1.0, song_bpm)

                loop_chance, rev_chance, stutter_chance = self._style_adjustments()
                extra_fx = self._transition_fx_filters()
                clip_paths: List[Path] = []

                for idx, src in enumerate(selected):
                    src_duration = self._probe_duration(src)
                    clip_len = rng.uniform(self.config.min_clip_sec, self.config.max_clip_sec)
                    if self.config.beat_sync and self.config.beat_preset != "Off":
                        strength = max(0, min(100, self.config.beat_strength)) / 100.0
                        base_beats = max(1, int(round((clip_len / beat_len) * max(0.3, strength))))
                        clip_len = max(self.config.min_clip_sec, min(self.config.max_clip_sec, base_beats * beat_len))
                    clip_len = min(clip_len, max(0.3, src_duration))

                    start = 0.0 if src_duration <= clip_len else rng.uniform(0, src_duration - clip_len)
                    out_clip = temp / f"clip_{idx:05d}.mp4"

                    filters = [f"scale={self.config.resolution}", f"fps={self.config.fps}"]
                    energy = max(0, min(100, self.config.dance_energy)) / 100.0
                    if self.config.speed_ramp and rng.random() < 0.45:
                        speed = rng.choice([0.75, 0.85, 1.15, 1.30])
                        filters.append(f"setpts={1/speed:.4f}*PTS")
                    if rng.randint(1, 100) <= rev_chance:
                        filters.append("reverse")
                    if rng.randint(1, 100) <= loop_chance:
                        filters.append("loop=loop=2:size=15:start=0")
                    if rng.randint(1, 100) <= stutter_chance:
                        filters.append("tblend=all_mode=difference")
                    if self.config.instant_vfx or self.config.remix_style in {"Chaos remix", "YouTube Poop", "TikTok"}:
                        filters += ["noise=alls=10:allf=t", "unsharp=5:5:1.2:3:3:0.2"]
                    filters += extra_fx
                    if self.config.transition_mode == "Fade":
                        t = min(self.config.transition_sec, clip_len / 3.0)
                        filters.append(f"fade=t=in:st=0:d={t}")
                        filters.append(f"fade=t=out:st={max(0.0, clip_len - t):.3f}:d={t}")
                    if energy > 0:
                        filters.append(f"eq=saturation={1 + 0.8 * energy:.2f}:contrast={1 + 0.25 * energy:.2f}")

                    self._run([
                        self.config.ffmpeg_path,
                        "-y",
                        "-ss",
                        f"{start:.3f}",
                        "-t",
                        f"{clip_len:.3f}",
                        "-i",
                        src,
                        "-vf",
                        ",".join(filters),
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast" if self.config.draft_mode else "medium",
                        "-crf",
                        str(self.config.crf),
                        str(out_clip),
                    ])
                    clip_paths.append(out_clip)

                clip_concat = temp / "clips_concat.txt"
                self._write_concat_list(clip_concat, clip_paths)
                cut_video = temp / "video_noaudio.mp4"
                self._run([
                    self.config.ffmpeg_path,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(clip_concat),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast" if self.config.draft_mode else "medium",
                    "-crf",
                    str(self.config.crf),
                    "-pix_fmt",
                    "yuv420p",
                    str(cut_video),
                ])

                audio = self._build_audio_bed(temp, songs, rng)
                audio = self._apply_sfx(temp, audio, rng)

                output_cmd = [self.config.ffmpeg_path, "-y", "-i", str(cut_video), "-i", str(audio)]
                logo = self.config.branding_logo.strip()
                if logo and Path(logo).exists():
                    alpha = max(0.0, min(1.0, self.config.branding_opacity / 100.0))
                    output_cmd += [
                        "-i",
                        logo,
                        "-filter_complex",
                        f"[2:v]format=rgba,colorchannelmixer=aa={alpha:.2f}[wm];[0:v][wm]overlay=W-w-20:H-h-20",
                    ]
                output_cmd += [
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast" if self.config.draft_mode else "medium",
                    "-crf",
                    str(self.config.crf),
                    "-c:a",
                    "aac",
                    self.config.output_file,
                ]
                self._run(output_cmd)

            self.log_var.set(f"Done! Output: {self.config.output_file}")
            messagebox.showinfo("Auto-Edit Complete", f"Finished!\n{self.config.output_file}")
        except Exception as exc:
            self.log_var.set(f"Error: {exc}")
            messagebox.showerror("Auto-Edit Failed", str(exc))


def run_app(mode: str = "deluxe"):
    root = tk.Tk()
    root.geometry("1080x720" if mode == "small" else "1280x900")
    AutoEditGUI(root, mode=mode)
    root.mainloop()


if __name__ == "__main__":
    run_app("deluxe")
