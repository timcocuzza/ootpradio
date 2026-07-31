"""Native Tk desktop interface for configuring and controlling OOTP Radio."""

from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ootp_radio.app_settings import (
    AppSettings,
    SettingsError,
    default_settings_path,
    load_settings,
    move_segment,
    save_settings,
    set_segment_enabled,
)
from ootp_radio.listening_session import (
    ListeningSession,
    SessionStatus,
)
from ootp_radio.models import BroadcastSegment
from ootp_radio.paths import SaveDirectoryError, require_valid_save_dir
from ootp_radio.team_discovery import TeamDiscoveryError, discover_mlb_teams

SYSTEM_DEFAULT_VOICE = "macOS System Default"
SEGMENT_LABELS = {
    BroadcastSegment.HIGHLIGHTS: "Highlights Play-by-Play",
    BroadcastSegment.TEAM_RECAP: "Team Radio — WBAL",
    BroadcastSegment.SCORES: "Scores Around the League",
    BroadcastSegment.NEWS: "League News",
}


def discover_macos_voices() -> tuple[str, ...]:
    """Return installed voice names while keeping system default first."""
    try:
        completed = subprocess.run(
            ["say", "-v", "?"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return (SYSTEM_DEFAULT_VOICE,)

    voices = tuple(
        voice_name
        for line in completed.stdout.splitlines()
        if (voice_name := line[:20].strip())
    )
    return (SYSTEM_DEFAULT_VOICE, *dict.fromkeys(voices))


class OOTPRadioWindow:
    """One-window desktop controller with no direct access to OOTP writes."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        settings_path: Path | str | None = None,
        session: ListeningSession | None = None,
    ) -> None:
        self.root = root
        self.settings_path = (
            Path(settings_path)
            if settings_path is not None
            else default_settings_path()
        )
        self._drag_index: int | None = None
        self._closing = False
        self._teams_save_dir: Path | None = None
        self._team_ids_by_name: dict[str, int] = {}
        self._settings_warning: str | None = None
        try:
            settings = load_settings(self.settings_path)
        except SettingsError as error:
            settings = AppSettings()
            self._settings_warning = str(error)

        self._segment_order = settings.segments
        self.save_dir_var = tk.StringVar(
            value=str(settings.save_dir) if settings.save_dir else ""
        )
        self.team_var = tk.StringVar(value=settings.team_name)
        self._selected_team_id = settings.team_id
        self.voice_var = tk.StringVar(
            value=settings.voice or SYSTEM_DEFAULT_VOICE
        )
        self.rate_var = tk.StringVar(
            value=str(settings.rate) if settings.rate is not None else ""
        )
        self.poll_interval_var = tk.StringVar(
            value=f"{settings.poll_interval_seconds:g}"
        )
        self.off_day_var = tk.BooleanVar(value=settings.off_day_broadcasts)
        self.play_current_var = tk.BooleanVar(value=settings.play_current)
        self.segment_vars = {
            segment: tk.BooleanVar(value=segment in self._segment_order)
            for segment in BroadcastSegment
        }
        self.status_var = tk.StringVar(value="Stopped")
        self.status_detail_var = tk.StringVar(
            value="Choose your options, then start listening."
        )

        self.session = session or ListeningSession(
            status_callback=self._session_status_changed
        )
        if session is not None:
            session.status_callback = self._session_status_changed

        self._editable_widgets: list[tk.Widget] = []
        self._build_window()
        self._render_segment_order()
        self._apply_session_status(SessionStatus.STOPPED, None)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        if settings.save_dir is not None:
            self.root.after(
                50,
                self._refresh_teams,
                settings.save_dir,
                False,
            )
        if self._settings_warning:
            self.root.after(100, self._show_settings_warning)

    def _build_window(self) -> None:
        self.root.title("OOTP Radio")
        self.root.geometry("780x720")
        self.root.minsize(700, 650)

        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Helvetica Neue", 26, "bold"))
        style.configure("Subtitle.TLabel", foreground="#59636e")
        style.configure("Status.TLabel", font=("Helvetica Neue", 14, "bold"))
        style.configure("Hint.TLabel", foreground="#66717c")
        style.configure("Start.TButton", font=("Helvetica Neue", 13, "bold"))

        outer = ttk.Frame(self.root, padding=(24, 20, 24, 20))
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="OOTP Radio", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Your configurable, spoiler-aware baseball broadcast",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.status_label = ttk.Label(
            header,
            textvariable=self.status_var,
            style="Status.TLabel",
        )
        self.status_label.grid(row=0, column=1, rowspan=2, sticky="e")

        source = ttk.LabelFrame(outer, text="Save & voice", padding=14)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        source.columnconfigure(1, weight=1)

        ttk.Label(source, text="OOTP save").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=4
        )
        save_entry = ttk.Entry(source, textvariable=self.save_dir_var)
        save_entry.grid(row=0, column=1, sticky="ew", pady=4)
        browse_button = ttk.Button(source, text="Browse…", command=self._browse_save)
        browse_button.grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(source, text="Team").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=4
        )
        self.team_combo = ttk.Combobox(
            source,
            textvariable=self.team_var,
            values=(self.team_var.get(),),
            state="readonly",
        )
        self.team_combo.grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=4,
        )
        self.team_combo.bind("<<ComboboxSelected>>", self._team_selected)
        ttk.Label(
            source,
            text="Teams are discovered read-only from recent MLB box scores.",
            style="Hint.TLabel",
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 3))

        ttk.Label(source, text="Voice").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=4
        )
        voices = list(discover_macos_voices())
        if self.voice_var.get() not in voices:
            voices.append(self.voice_var.get())
        voice_combo = ttk.Combobox(
            source,
            textvariable=self.voice_var,
            values=voices,
            state="readonly",
        )
        voice_combo.grid(row=3, column=1, sticky="ew", pady=4)
        rate_frame = ttk.Frame(source)
        rate_frame.grid(row=3, column=2, sticky="e", padx=(8, 0), pady=4)
        ttk.Label(rate_frame, text="Rate").grid(row=0, column=0, padx=(0, 5))
        rate_entry = ttk.Entry(rate_frame, width=7, textvariable=self.rate_var)
        rate_entry.grid(row=0, column=1)
        ttk.Label(rate_frame, text="wpm").grid(row=0, column=2, padx=(5, 0))
        ttk.Label(
            source,
            text="System Default uses the voice currently configured in macOS. "
            "Leave rate blank for its normal speed.",
            style="Hint.TLabel",
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 3))

        self._editable_widgets.extend(
            [save_entry, browse_button, self.team_combo, voice_combo, rate_entry]
        )

        broadcast = ttk.LabelFrame(
            outer,
            text="Broadcast options & playback order",
            padding=14,
        )
        broadcast.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        broadcast.columnconfigure(1, weight=1)
        outer.rowconfigure(2, weight=1)

        choices = ttk.Frame(broadcast)
        choices.grid(row=0, column=0, sticky="nw", padx=(0, 24))
        for row, segment in enumerate(BroadcastSegment):
            check = ttk.Checkbutton(
                choices,
                text=SEGMENT_LABELS[segment],
                variable=self.segment_vars[segment],
                command=lambda selected=segment: self._toggle_segment(selected),
            )
            check.grid(row=row, column=0, sticky="w", pady=5)
            self._editable_widgets.append(check)

        order_frame = ttk.Frame(broadcast)
        order_frame.grid(row=0, column=1, sticky="nsew")
        order_frame.columnconfigure(0, weight=1)
        ttk.Label(
            order_frame,
            text="Drag enabled options into your preferred order",
            style="Hint.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.order_list = tk.Listbox(
            order_frame,
            height=5,
            activestyle="none",
            selectmode=tk.SINGLE,
            font=("Helvetica Neue", 13),
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=0,
            exportselection=False,
        )
        self.order_list.grid(row=1, column=0, sticky="nsew")
        self.order_list.bind("<ButtonPress-1>", self._drag_start)
        self.order_list.bind("<B1-Motion>", self._drag_motion)
        self.order_list.bind("<ButtonRelease-1>", self._drag_end)
        ttk.Label(
            order_frame,
            text="League News stays last so late message files cannot delay audio.",
            style="Hint.TLabel",
            wraplength=380,
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._editable_widgets.append(self.order_list)

        behavior = ttk.LabelFrame(outer, text="Listening behavior", padding=14)
        behavior.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        behavior.columnconfigure(2, weight=1)
        off_day_check = ttk.Checkbutton(
            behavior,
            text="Broadcast on Orioles off days",
            variable=self.off_day_var,
        )
        off_day_check.grid(row=0, column=0, sticky="w", padx=(0, 24))
        current_check = ttk.Checkbutton(
            behavior,
            text="Play current day when starting",
            variable=self.play_current_var,
        )
        current_check.grid(row=0, column=1, sticky="w", padx=(0, 24))
        poll_frame = ttk.Frame(behavior)
        poll_frame.grid(row=0, column=2, sticky="e")
        ttk.Label(poll_frame, text="Check every").grid(row=0, column=0)
        poll_entry = ttk.Entry(
            poll_frame,
            width=5,
            textvariable=self.poll_interval_var,
        )
        poll_entry.grid(row=0, column=1, padx=5)
        ttk.Label(poll_frame, text="sec").grid(row=0, column=2)
        self._editable_widgets.extend(
            [off_day_check, current_check, poll_entry]
        )

        controls = ttk.Frame(outer)
        controls.grid(row=4, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        ttk.Label(
            controls,
            textvariable=self.status_detail_var,
            style="Hint.TLabel",
            wraplength=390,
        ).grid(row=0, column=0, sticky="w", padx=(0, 20))
        self.stop_playback_button = ttk.Button(
            controls,
            text="Stop Playback",
            command=self._stop_playback,
        )
        self.stop_playback_button.grid(row=0, column=1, padx=(0, 8))
        self.stop_listening_button = ttk.Button(
            controls,
            text="Stop Listening",
            command=self._stop_listening,
        )
        self.stop_listening_button.grid(row=0, column=2, padx=(0, 8))
        self.start_button = ttk.Button(
            controls,
            text="Start Listening",
            style="Start.TButton",
            command=self._start_listening,
        )
        self.start_button.grid(row=0, column=3)

    def _show_settings_warning(self) -> None:
        messagebox.showwarning(
            "Settings could not be loaded",
            f"{self._settings_warning}\n\nDefaults are shown. The existing file "
            "will not be replaced until you press Start Listening.",
            parent=self.root,
        )

    def _browse_save(self) -> None:
        initial = self.save_dir_var.get().strip()
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Choose an OOTP saved game (.lg)",
            initialdir=initial if Path(initial).is_dir() else None,
            mustexist=True,
        )
        if selected:
            self.save_dir_var.set(selected)
            self._refresh_teams(Path(selected), True)

    def _team_selected(self, _event: tk.Event | None = None) -> None:
        self._selected_team_id = self._team_ids_by_name.get(self.team_var.get())

    def _refresh_teams(
        self,
        save_dir: Path | str,
        show_errors: bool = True,
    ) -> None:
        save_path = Path(save_dir).expanduser()
        if self._teams_save_dir is not None and self._teams_save_dir != save_path:
            self._selected_team_id = None
        try:
            teams = discover_mlb_teams(save_path)
        except TeamDiscoveryError as error:
            self._teams_save_dir = None
            if show_errors:
                messagebox.showerror(
                    "Could not discover MLB teams",
                    str(error),
                    parent=self.root,
                )
            return

        self._teams_save_dir = save_path
        self._team_ids_by_name = {team.name: team.team_id for team in teams}
        names = tuple(team.name for team in teams)
        self.team_combo.configure(values=names)

        selected_name = None
        if self._selected_team_id is not None:
            selected_name = next(
                (
                    team.name
                    for team in teams
                    if team.team_id == self._selected_team_id
                ),
                None,
            )
        if selected_name is None and self.team_var.get() in self._team_ids_by_name:
            selected_name = self.team_var.get()
        if selected_name is None:
            self.team_var.set("")
            self._selected_team_id = None
            self.status_detail_var.set(
                "Choose the controlled MLB team for this save."
            )
            return
        self.team_var.set(selected_name)
        self._selected_team_id = self._team_ids_by_name[selected_name]

    def _toggle_segment(self, segment: BroadcastSegment) -> None:
        try:
            self._segment_order = set_segment_enabled(
                self._segment_order,
                segment,
                enabled=self.segment_vars[segment].get(),
            )
        except SettingsError as error:
            self.segment_vars[segment].set(True)
            messagebox.showerror("Broadcast options", str(error), parent=self.root)
        self._render_segment_order()

    def _render_segment_order(self, selected: BroadcastSegment | None = None) -> None:
        self.order_list.delete(0, tk.END)
        for segment in self._segment_order:
            suffix = "  · always last" if segment is BroadcastSegment.NEWS else ""
            self.order_list.insert(
                tk.END,
                f"  ≡  {SEGMENT_LABELS[segment]}{suffix}",
            )
        if selected is not None and selected in self._segment_order:
            index = self._segment_order.index(selected)
            self.order_list.selection_set(index)
            self.order_list.activate(index)

    def _drag_start(self, event: tk.Event) -> None:
        if self.session.status is not SessionStatus.STOPPED:
            self._drag_index = None
            return
        index = self.order_list.nearest(event.y)
        self._drag_index = index if 0 <= index < len(self._segment_order) else None

    def _drag_motion(self, event: tk.Event) -> None:
        if self._drag_index is None or not self._segment_order:
            return
        target_index = self.order_list.nearest(event.y)
        target_index = max(0, min(target_index, len(self._segment_order) - 1))
        if target_index == self._drag_index:
            return
        moved_segment = self._segment_order[self._drag_index]
        try:
            updated = move_segment(
                self._segment_order,
                source_index=self._drag_index,
                target_index=target_index,
            )
        except SettingsError:
            return
        self._segment_order = updated
        self._drag_index = self._segment_order.index(moved_segment)
        self._render_segment_order(moved_segment)

    def _drag_end(self, _event: tk.Event) -> None:
        self._drag_index = None

    def _settings_from_form(self) -> AppSettings:
        save_text = self.save_dir_var.get().strip()
        voice_text = self.voice_var.get().strip()
        rate_text = self.rate_var.get().strip()
        poll_text = self.poll_interval_var.get().strip()
        try:
            rate = int(rate_text) if rate_text else None
        except ValueError as error:
            raise SettingsError("Speech rate must be a positive whole number.") from error
        try:
            poll_interval = float(poll_text)
        except ValueError as error:
            raise SettingsError("Check interval must be a positive number.") from error
        return AppSettings(
            save_dir=Path(save_text).expanduser() if save_text else None,
            team_name=self.team_var.get(),
            team_id=self._selected_team_id,
            voice=(
                None
                if voice_text in {"", SYSTEM_DEFAULT_VOICE}
                else voice_text
            ),
            rate=rate,
            segments=self._segment_order,
            off_day_broadcasts=self.off_day_var.get(),
            play_current=self.play_current_var.get(),
            poll_interval_seconds=poll_interval,
        )

    def _start_listening(self) -> None:
        try:
            settings = self._settings_from_form()
            if settings.save_dir is None:
                raise SettingsError("Choose an OOTP saved-game folder first.")
            require_valid_save_dir(settings.save_dir)
            if self._teams_save_dir != settings.save_dir:
                self._refresh_teams(settings.save_dir, True)
                settings = self._settings_from_form()
            save_settings(settings, self.settings_path)
            self.session.start(settings)
        except (SettingsError, SaveDirectoryError, OSError, RuntimeError) as error:
            self.status_detail_var.set(str(error))
            messagebox.showerror("Could not start listening", str(error), parent=self.root)

    def _stop_playback(self) -> None:
        if self.session.stop_playback():
            self.status_detail_var.set(
                "Playback stopped. OOTP Radio is still listening for the next day."
            )
        else:
            self.status_detail_var.set(
                "No audio is playing right now. OOTP Radio is still listening."
            )

    def _stop_listening(self) -> None:
        self.session.stop_listening()

    def _session_status_changed(
        self,
        status: SessionStatus,
        error: Exception | None,
    ) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, self._apply_session_status, status, error)
        except tk.TclError:
            pass

    def _apply_session_status(
        self,
        status: SessionStatus,
        error: Exception | None,
    ) -> None:
        labels = {
            SessionStatus.STOPPED: "● Stopped",
            SessionStatus.STARTING: "● Starting…",
            SessionStatus.LISTENING: "● Listening",
            SessionStatus.STOPPING: "● Stopping…",
        }
        self.status_var.set(labels[status])
        editable = status is SessionStatus.STOPPED
        for widget in self._editable_widgets:
            try:
                if isinstance(widget, tk.Listbox):
                    widget.configure(state=tk.NORMAL if editable else tk.DISABLED)
                elif isinstance(widget, ttk.Combobox):
                    widget.configure(state="readonly" if editable else "disabled")
                else:
                    widget.configure(state="normal" if editable else "disabled")
            except tk.TclError:
                pass
        self.start_button.configure(state="normal" if editable else "disabled")
        active = status is SessionStatus.LISTENING
        stopping_allowed = status in {
            SessionStatus.STARTING,
            SessionStatus.LISTENING,
        }
        self.stop_playback_button.configure(
            state="normal" if active else "disabled"
        )
        self.stop_listening_button.configure(
            state="normal" if stopping_allowed else "disabled"
        )

        if error is not None:
            self.status_detail_var.set(str(error))
        elif status is SessionStatus.STOPPED:
            self.status_detail_var.set(
                "Choose your options, then start listening."
            )
        elif status is SessionStatus.STARTING:
            self.status_detail_var.set("Validating the save and starting the monitor…")
        elif status is SessionStatus.LISTENING:
            self.status_detail_var.set(
                "Watching for stable new OOTP files. Settings are locked while active."
            )
        else:
            self.status_detail_var.set("Stopping playback and file monitoring…")

    def _close(self) -> None:
        self._closing = True
        self.session.stop_listening()
        self.session.wait(timeout=1.0)
        self.root.destroy()


def main() -> int:
    """Launch the desktop application."""
    root = tk.Tk()
    OOTPRadioWindow(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
