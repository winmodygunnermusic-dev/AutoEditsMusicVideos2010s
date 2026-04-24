import json
import os
import random
import shlex
import subprocess
import tempfile
import threading
from dataclasses import dataclass, asdict
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
    transition_sec: float = 0.3
    dance_energy: int = 50
    beat_preset: str = "Auto"
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
        self.log_var = tk.StringVar(value="Ready")
        self.vars: Dict[str, tk.Variable] = {}

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)

        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Button(top, text="Save preset JSON", command=self.save_preset).pack(side="left", padx=3)
        ttk.Button(top, text="Load preset JSON", command=self.load_preset).pack(side="left", padx=3)
        ttk.Button(top, text="Run Auto-Edit", command=self.run_async).pack(side="right", padx=3)

        paths = ttk.LabelFrame(frame, text="Tools + Output")
        paths.pack(fill="x", pady=6)
        self._entry_row(paths, "FFmpeg", "ffmpeg_path", browse_exec=True)
        self._entry_row(paths, "FFprobe", "ffprobe_path", browse_exec=True)
        self._entry_row(paths, "Output video", "output_file", browse_save=True)

        media = ttk.LabelFrame(frame, text="Media Pools")
        media.pack(fill="both", expand=True, pady=6)

        self._multi_pool(media, "Video files", self.video_files, 0, 0, kinds=[("Video", VIDEO_EXTS)])
        self._multi_pool(media, "Video folders", self.video_folders, 0, 1, folder=True)
        self._multi_pool(media, "Audio sources", self.audio_files, 1, 0, kinds=[("Audio", AUDIO_EXTS)])
        self._multi_pool(media, "Music sources", self.music_files, 1, 1, kinds=[("Audio", AUDIO_EXTS)])

        if self.mode != "small":
            self._multi_pool(media, "SFX sources", self.sfx_files, 2, 0, kinds=[("Audio", AUDIO_EXTS)])
            self._multi_pool(media, "Intro assets", self.intro_files, 2, 1, kinds=[("Video", VIDEO_EXTS)])
            self._multi_pool(media, "Outro assets", self.outro_files, 3, 0, kinds=[("Video", VIDEO_EXTS)])

        for c in range(2):
            media.columnconfigure(c, weight=1)

        settings = ttk.LabelFrame(frame, text="Generation Controls")
        settings.pack(fill="x", pady=6)

        self._control_grid(settings)

        ttk.Label(frame, textvariable=self.log_var, foreground="navy").pack(anchor="w", pady=4)

    def _entry_row(self, parent, label, key, browse_exec=False, browse_save=False):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        v = tk.StringVar(value=getattr(self.config, key))
        self.vars[key] = v
        ttk.Entry(row, textvariable=v).pack(side="left", fill="x", expand=True)
        if browse_exec:
            ttk.Button(row, text="Browse", command=lambda: self._browse_exe(v)).pack(side="left", padx=4)
        if browse_save:
            ttk.Button(row, text="Browse", command=lambda: self._browse_output(v)).pack(side="left", padx=4)

    def _control_grid(self, parent):
        rows = ttk.Frame(parent)
        rows.pack(fill="x", pady=4)

        def add_field(r, c, text, key, default, width=10, widget="entry", values=None):
            ttk.Label(rows, text=text).grid(row=r, column=c * 2, sticky="w", padx=3, pady=2)
            if widget == "combo":
                v = tk.StringVar(value=str(default))
                cb = ttk.Combobox(rows, textvariable=v, values=values or [], width=width, state="readonly")
                cb.grid(row=r, column=c * 2 + 1, sticky="we", padx=3, pady=2)
            elif widget == "check":
                v = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(rows, variable=v).grid(row=r, column=c * 2 + 1, sticky="w", padx=3, pady=2)
            else:
                v = tk.StringVar(value=str(default))
                ttk.Entry(rows, textvariable=v, width=width).grid(row=r, column=c * 2 + 1, sticky="we", padx=3, pady=2)
            self.vars[key] = v

        add_field(0, 0, "Min clip sec", "min_clip_sec", self.config.min_clip_sec)
        add_field(0, 1, "Max clip sec", "max_clip_sec", self.config.max_clip_sec)
        add_field(0, 2, "Total clips", "total_clips", self.config.total_clips)
        add_field(1, 0, "Resolution", "resolution", self.config.resolution)
        add_field(1, 1, "FPS", "fps", self.config.fps)
        add_field(1, 2, "CRF", "crf", self.config.crf)
        add_field(2, 0, "Random seed", "random_seed", self.config.random_seed)
        add_field(2, 1, "Transition", "transition_mode", self.config.transition_mode, widget="combo", values=["Cut", "Fade"])
        add_field(2, 2, "Transition sec", "transition_sec", self.config.transition_sec)
        if self.mode != "small":
            add_field(3, 0, "Dance energy 0-100", "dance_energy", self.config.dance_energy)
            add_field(3, 1, "Beat preset", "beat_preset", self.config.beat_preset, widget="combo", values=["Auto", "Soft", "Hard", "Off"])
            add_field(3, 2, "Remix mode", "remix_mode", self.config.remix_mode, widget="combo", values=["Original", "Nightcore", "Slow Jam", "Hyper Dance"])
            add_field(4, 0, "Audio mode", "audio_mode", self.config.audio_mode, widget="combo", values=["Random one song", "Combine all shuffled"])
            add_field(4, 1, "BPM fallback", "bpm_fallback", self.config.bpm_fallback)
            add_field(4, 2, "Instant VFX", "instant_vfx", self.config.instant_vfx, widget="check")
            add_field(5, 0, "10x draft mode", "draft_mode", self.config.draft_mode, widget="check")
            add_field(5, 1, "Intro clips", "intro_count", self.config.intro_count)
            add_field(5, 2, "Outro clips", "outro_count", self.config.outro_count)
            add_field(6, 0, "Speed ramp", "speed_ramp", self.config.speed_ramp, widget="check")
            add_field(6, 1, "Loop %", "loop_chance", self.config.loop_chance)
            add_field(6, 2, "Reverse %", "reverse_chance", self.config.reverse_chance)
            add_field(7, 0, "Stutter %", "stutter_chance", self.config.stutter_chance)
            add_field(7, 1, "Trailer mode", "trailer_mode", self.config.trailer_mode, widget="combo", values=["Off", "Trailer", "Teaser"])
            add_field(7, 2, "Remix style", "remix_style", self.config.remix_style, widget="combo", values=["Chaos remix", "Beat remix", "Meme remix", "YouTube Poop", "TikTok", "AMV"])
            add_field(8, 0, "Branding logo", "branding_logo", self.config.branding_logo)
            add_field(8, 1, "Logo opacity", "branding_opacity", self.config.branding_opacity)

        rows.columnconfigure(1, weight=1)
        rows.columnconfigure(3, weight=1)
        rows.columnconfigure(5, weight=1)

        rv = tk.BooleanVar(value=self.config.recursive_scan)
        self.vars["recursive_scan"] = rv
        ttk.Checkbutton(parent, text="Recursive folder scan", variable=rv).pack(anchor="w", padx=4, pady=2)

    def _multi_pool(self, parent, title, store, row, col, kinds=None, folder=False):
        box = ttk.LabelFrame(parent, text=title)
        box.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        lb = tk.Listbox(box, height=4)
        lb.pack(fill="both", expand=True, padx=3, pady=3)

        btns = ttk.Frame(box)
        btns.pack(fill="x", padx=3, pady=2)

        def add_items():
            if folder:
                p = filedialog.askdirectory()
                if p:
                    store.append(p)
                    lb.insert("end", p)
                return
            patterns = [(k, " ".join([f"*{e}" for e in exts])) for k, exts in (kinds or [])]
            files = filedialog.askopenfilenames(filetypes=patterns or [("All", "*.*")])
            for f in files:
                if f not in store:
                    store.append(f)
                    lb.insert("end", f)

        def remove_selected():
            for idx in reversed(lb.curselection()):
                store.pop(idx)
                lb.delete(idx)

        ttk.Button(btns, text="Add", command=add_items).pack(side="left", padx=2)
        ttk.Button(btns, text="Remove", command=remove_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear", command=lambda: (store.clear(), lb.delete(0, "end"))).pack(side="left", padx=2)

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

        def to_bool(k):
            v = self.vars[k]
            return bool(v.get()) if isinstance(v, tk.BooleanVar) else str(v.get()).strip().lower() in {"1", "true", "yes", "on"}

        c.ffmpeg_path = self.vars["ffmpeg_path"].get().strip() or "ffmpeg"
        c.ffprobe_path = self.vars["ffprobe_path"].get().strip() or "ffprobe"
        c.output_file = self.vars["output_file"].get().strip() or "output_autoedit.mp4"
        c.recursive_scan = to_bool("recursive_scan")
        c.min_clip_sec = float(self.vars["min_clip_sec"].get())
        c.max_clip_sec = float(self.vars["max_clip_sec"].get())
        c.total_clips = int(self.vars["total_clips"].get())
        c.resolution = self.vars["resolution"].get().strip()
        c.fps = int(self.vars["fps"].get())
        c.crf = int(self.vars["crf"].get())
        c.random_seed = self.vars["random_seed"].get().strip()
        c.transition_mode = self.vars["transition_mode"].get().strip()
        c.transition_sec = float(self.vars["transition_sec"].get())

        for k in [
            "dance_energy", "beat_preset", "audio_mode", "remix_mode", "bpm_fallback", "instant_vfx", "draft_mode",
            "intro_count", "outro_count", "speed_ramp", "loop_chance", "reverse_chance", "stutter_chance",
            "trailer_mode", "branding_logo", "branding_opacity", "remix_style",
        ]:
            if k in self.vars:
                val = self.vars[k].get()
                cur = getattr(c, k)
                if isinstance(cur, bool):
                    setattr(c, k, bool(val))
                elif isinstance(cur, int):
                    setattr(c, k, int(val))
                else:
                    setattr(c, k, val)

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
            data = json.load(f)
        cfg = data.get("config", {})
        for k, v in cfg.items():
            if k in self.vars:
                self.vars[k].set(v)
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        for key in ["video_files", "video_folders", "audio_files", "music_files", "sfx_files", "intro_files", "outro_files"]:
            setattr(self, key, data.get(key, []))
        self.log_var.set(f"Preset loaded: {p}")

    def run_async(self):
        try:
            self._sync_config()
        except Exception as exc:
            messagebox.showerror("Invalid values", f"Please fix settings: {exc}")
            return
        t = threading.Thread(target=self._run_edit, daemon=True)
        t.start()

    def _collect_videos(self) -> List[str]:
        vids = list(self.video_files)
        for folder in self.video_folders:
            p = Path(folder)
            if not p.exists():
                continue
            iterator = p.rglob("*") if self.config.recursive_scan else p.glob("*")
            for f in iterator:
                if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                    vids.append(str(f))
        return sorted(set(vids))

    def _probe_duration(self, file_path: str) -> float:
        cmd = [self.config.ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out)

    def _probe_tbpm(self, file_path: str) -> Optional[float]:
        cmd = [self.config.ffprobe_path, "-v", "error", "-show_entries", "format_tags=TBPM", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        try:
            out = subprocess.check_output(cmd, text=True).strip()
            return float(out) if out else None
        except Exception:
            return None

    def _run(self, cmd: List[str]):
        self.log_var.set("Running: " + " ".join(shlex.quote(x) for x in cmd[:8]) + (" ..." if len(cmd) > 8 else ""))
        subprocess.check_call(cmd)

    def _run_edit(self):
        try:
            vids = self._collect_videos()
            if not vids:
                raise RuntimeError("No video files found.")
            songs = self.music_files or self.audio_files
            if not songs:
                raise RuntimeError("No music/audio sources provided.")

            rng = random.Random()
            if self.config.random_seed:
                rng.seed(self.config.random_seed)

            with tempfile.TemporaryDirectory(prefix="autoedit_") as td:
                temp = Path(td)

                selected = []
                intro = [f for f in self.intro_files if Path(f).exists()]
                outro = [f for f in self.outro_files if Path(f).exists()]
                body_count = max(1, self.config.total_clips - len(intro) - len(outro))
                if self.config.trailer_mode == "Trailer":
                    body_count = min(body_count, 40)
                elif self.config.trailer_mode == "Teaser":
                    body_count = min(body_count, 20)

                selected.extend(rng.sample(intro, k=min(self.config.intro_count, len(intro))))
                for _ in range(body_count):
                    selected.append(rng.choice(vids))
                selected.extend(rng.sample(outro, k=min(self.config.outro_count, len(outro))))

                clip_files = []
                for i, src in enumerate(selected):
                    dur = self._probe_duration(src)
                    clip_len = rng.uniform(self.config.min_clip_sec, self.config.max_clip_sec)
                    clip_len = min(clip_len, max(0.3, dur))
                    start = 0.0 if dur <= clip_len else rng.uniform(0, max(0.0, dur - clip_len))
                    out_clip = temp / f"clip_{i:04d}.mp4"

                    vf = [f"scale={self.config.resolution}", f"fps={self.config.fps}"]
                    energy = self.config.dance_energy / 100.0
                    if self.config.speed_ramp and rng.random() < 0.45:
                        speed = rng.choice([0.75, 0.85, 1.15, 1.3])
                        vf.append(f"setpts={1/speed:.4f}*PTS")
                    if rng.randint(1, 100) <= self.config.reverse_chance:
                        vf.append("reverse")
                    if rng.randint(1, 100) <= self.config.loop_chance:
                        vf.append("loop=2:1:0")
                    if rng.randint(1, 100) <= self.config.stutter_chance:
                        vf.append("tblend=all_mode=difference")
                    if self.config.instant_vfx or self.config.remix_style in {"Chaos remix", "YouTube Poop", "TikTok"}:
                        vf.append("noise=alls=12:allf=t")
                        vf.append("unsharp=5:5:1.2:3:3:0.2")
                    if self.config.transition_mode == "Fade":
                        t = min(self.config.transition_sec, clip_len / 3)
                        vf.append(f"fade=t=in:st=0:d={t}")
                        vf.append(f"fade=t=out:st={max(0, clip_len - t):.3f}:d={t}")
                    if energy > 0:
                        sat = 1 + 0.8 * energy
                        con = 1 + 0.25 * energy
                        vf.append(f"eq=saturation={sat:.2f}:contrast={con:.2f}")
                    vf_str = ",".join(vf)

                    preset = "ultrafast" if self.config.draft_mode else "medium"
                    cmd = [
                        self.config.ffmpeg_path, "-y", "-ss", f"{start:.3f}", "-t", f"{clip_len:.3f}", "-i", src,
                        "-vf", vf_str, "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(self.config.crf), str(out_clip)
                    ]
                    self._run(cmd)
                    clip_files.append(out_clip)

                list_txt = temp / "clips.txt"
                with open(list_txt, "w", encoding="utf-8") as f:
                    for c in clip_files:
                        f.write(f"file '{c.as_posix()}'\n")

                video_noaudio = temp / "video_noaudio.mp4"
                self._run([
                    self.config.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt),
                    "-c:v", "libx264", "-preset", "ultrafast" if self.config.draft_mode else "medium",
                    "-crf", str(self.config.crf), "-pix_fmt", "yuv420p", str(video_noaudio)
                ])

                song_list = list(songs)
                rng.shuffle(song_list)
                if self.config.audio_mode == "Random one song":
                    song_list = [rng.choice(song_list)]

                mix_file = temp / "music_mix.wav"
                if len(song_list) == 1:
                    bpm = self._probe_tbpm(song_list[0]) or float(self.config.bpm_fallback)
                    atempo = 1.0
                    if self.config.remix_mode == "Nightcore":
                        atempo = 1.25
                    elif self.config.remix_mode == "Slow Jam":
                        atempo = 0.8
                    elif self.config.remix_mode == "Hyper Dance":
                        atempo = 1.35
                    if self.config.beat_preset == "Soft":
                        atempo *= 1.02
                    elif self.config.beat_preset == "Hard":
                        atempo *= 1.07
                    elif self.config.beat_preset == "Auto":
                        atempo *= 1.04 if bpm < 120 else 0.97
                    self._run([self.config.ffmpeg_path, "-y", "-i", song_list[0], "-filter:a", f"atempo={atempo:.3f}", str(mix_file)])
                else:
                    music_txt = temp / "music.txt"
                    with open(music_txt, "w", encoding="utf-8") as f:
                        for s in song_list:
                            f.write(f"file '{Path(s).as_posix()}'\n")
                    self._run([self.config.ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", str(music_txt), "-c", "copy", str(mix_file)])

                final_audio = mix_file
                if self.sfx_files:
                    sfx_choice = rng.choice(self.sfx_files)
                    sfx_mix = temp / "sfx_mix.wav"
                    self._run([
                        self.config.ffmpeg_path, "-y", "-i", str(mix_file), "-i", sfx_choice,
                        "-filter_complex", "[1:a]volume=0.25[s];[0:a][s]amix=inputs=2:duration=first:dropout_transition=2",
                        str(sfx_mix)
                    ])
                    final_audio = sfx_mix

                overlay_args = []
                logo = self.config.branding_logo.strip()
                if logo and Path(logo).exists():
                    alpha = max(0.0, min(1.0, self.config.branding_opacity / 100.0))
                    overlay_args = ["-i", logo, "-filter_complex", f"[1:v]format=rgba,colorchannelmixer=aa={alpha:.2f}[wm];[0:v][wm]overlay=W-w-20:H-h-20"]

                out = self.config.output_file
                cmd = [self.config.ffmpeg_path, "-y", "-i", str(video_noaudio), "-i", str(final_audio)]
                cmd += overlay_args
                cmd += ["-shortest", "-c:v", "libx264", "-preset", "ultrafast" if self.config.draft_mode else "medium", "-crf", str(self.config.crf), "-c:a", "aac", out]
                self._run(cmd)

            self.log_var.set(f"Done! Output: {self.config.output_file}")
            messagebox.showinfo("Auto-Edit Complete", f"Finished!\n{self.config.output_file}")
        except Exception as exc:
            self.log_var.set(f"Error: {exc}")
            messagebox.showerror("Auto-Edit Failed", str(exc))


def run_app(mode: str = "deluxe"):
    root = tk.Tk()
    if mode == "small":
        root.geometry("1080x720")
    else:
        root.geometry("1280x900")
    AutoEditGUI(root, mode=mode)
    root.mainloop()


if __name__ == "__main__":
    run_app("deluxe")
