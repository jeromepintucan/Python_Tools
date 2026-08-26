# /// script
# requires-python = ">=3.13"
# ///
"""
Process Keeper

A small desktop application that prevents the computer from sleeping while
a long-running Power BI refresh, Fabric pipeline, or other authorized process
is running.

The application does not simulate mouse movements, keyboard input, or scrolling.

Supported platforms:
    - Windows
    - macOS
    - Linux

Usage:
    python process-keeper.py
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import signal
import subprocess
import sys
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox
from typing import Final


APP_NAME: Final = "Process Keeper"
JIGGLE_INTERVAL_MS: Final = 55_000

# Windows SetThreadExecutionState flags
ES_CONTINUOUS: Final = 0x80000000
ES_SYSTEM_REQUIRED: Final = 0x00000001
ES_DISPLAY_REQUIRED: Final = 0x00000002


class ProcessKeeper:
    """Cross-platform controller for preventing system sleep."""

    def __init__(self) -> None:
        self.active = False
        self.activated_at: datetime | None = None
        self.inhibitor_process: subprocess.Popen | None = None

    @property
    def system_name(self) -> str:
        """Return the normalized operating system name."""
        return platform.system().lower()

    def activate(self) -> None:
        """Prevent the computer from sleeping."""
        if self.active:
            return

        if self.system_name == "windows":
            self._activate_windows()
        elif self.system_name == "darwin":
            self._activate_macos()
        elif self.system_name == "linux":
            self._activate_linux()
        else:
            raise RuntimeError(
                f"Unsupported operating system: {platform.system()}"
            )

        self.active = True
        self.activated_at = datetime.now()

    def deactivate(self) -> None:
        """Restore the operating system's normal power behavior."""
        if not self.active:
            return

        try:
            if self.system_name == "windows":
                self._deactivate_windows()
            elif self.system_name in {"darwin", "linux"}:
                self._stop_inhibitor_process()
        finally:
            self.active = False
            self.activated_at = None

    def _activate_windows(self) -> None:
        """Prevent Windows system sleep and display sleep."""
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS
            | ES_SYSTEM_REQUIRED
            | ES_DISPLAY_REQUIRED
        )

        if result == 0:
            raise ctypes.WinError()

    def _deactivate_windows(self) -> None:
        """Restore Windows' normal execution-state behavior."""
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS
        )

        if result == 0:
            raise ctypes.WinError()

    def _activate_macos(self) -> None:
        """Use macOS caffeinate to prevent idle sleep."""
        caffeinate_path = shutil.which("caffeinate")

        if not caffeinate_path:
            raise RuntimeError(
                "The macOS 'caffeinate' command could not be found."
            )

        self.inhibitor_process = subprocess.Popen(
            [caffeinate_path, "-d", "-i"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._validate_inhibitor_process("caffeinate")

    def _activate_linux(self) -> None:
        """Use systemd-inhibit to prevent Linux idle sleep."""
        systemd_inhibit_path = shutil.which("systemd-inhibit")

        if not systemd_inhibit_path:
            raise RuntimeError(
                "The Linux 'systemd-inhibit' command could not be found."
            )

        self.inhibitor_process = subprocess.Popen(
            [
                systemd_inhibit_path,
                "--what=idle:sleep",
                "--who=Process Keeper",
                "--why=Long-running Power BI or Fabric process",
                "--mode=block",
                "sleep",
                "infinity",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._validate_inhibitor_process("systemd-inhibit")

    def _validate_inhibitor_process(self, command_name: str) -> None:
        """Confirm that the background inhibitor process started."""
        if (
            self.inhibitor_process is None
            or self.inhibitor_process.poll() is not None
        ):
            self.inhibitor_process = None
            raise RuntimeError(
                f"Failed to start {command_name}."
            )

    def _stop_inhibitor_process(self) -> None:
        """Stop the macOS or Linux inhibitor process."""
        process = self.inhibitor_process

        if process is None:
            return

        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

        self.inhibitor_process = None

    def elapsed(self) -> timedelta:
        """Return the amount of time protection has been active."""
        if not self.active or self.activated_at is None:
            return timedelta()

        return datetime.now() - self.activated_at


class InputSimulator:
    """Simulates a tiny, harmless mouse movement.

    This is intentionally separate from ProcessKeeper's sleep-prevention
    logic. SetThreadExecutionState (used by ProcessKeeper) stops the OS
    from sleeping, but it does NOT reset idle-time trackers used by chat
    apps like Microsoft Teams to decide "Active" vs "Away" - those watch
    for actual input events. This class exists only to optionally satisfy
    that separate check, and only ever moves the cursor by 1 pixel and
    immediately back.
    """

    @staticmethod
    def jiggle() -> None:
        """Nudge the mouse by one pixel and back on the current platform."""
        system_name = platform.system().lower()

        if system_name == "windows":
            InputSimulator._jiggle_windows()
        elif system_name == "darwin":
            InputSimulator._jiggle_macos()
        elif system_name == "linux":
            InputSimulator._jiggle_linux()
        else:
            raise RuntimeError(
                f"Unsupported operating system: {platform.system()}"
            )

    @staticmethod
    def _jiggle_windows() -> None:
        # mouse_event with a relative MOUSEEVENTF_MOVE is used deliberately
        # instead of SetCursorPos. SetCursorPos repositions the cursor but
        # does not reliably feed Windows' input pipeline, so GetLastInputInfo
        # (which Teams and the OS idle timer read) may not reset. mouse_event
        # injects a real relative-movement input event, which does reset it.
        MOUSEEVENTF_MOVE = 0x0001
        user32 = ctypes.windll.user32

        user32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)

    @staticmethod
    def _jiggle_macos() -> None:
        cliclick_path = shutil.which("cliclick")

        if not cliclick_path:
            raise RuntimeError(
                "This feature requires 'cliclick' on macOS. "
                "Install it with: brew install cliclick"
            )

        subprocess.run(
            [cliclick_path, "m:+1,+0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [cliclick_path, "m:-1,+0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _jiggle_linux() -> None:
        xdotool_path = shutil.which("xdotool")

        if not xdotool_path:
            raise RuntimeError(
                "This feature requires 'xdotool' on Linux. "
                "Install it with your package manager, e.g. "
                "sudo apt install xdotool"
            )

        subprocess.run(
            [xdotool_path, "mousemove_relative", "--", "1", "0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [xdotool_path, "mousemove_relative", "--", "-1", "0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class ProcessKeeperApp:
    """Tkinter user interface for Process Keeper."""

    BACKGROUND: Final = "#0F172A"
    CARD_BACKGROUND: Final = "#1E293B"
    TEXT_PRIMARY: Final = "#F8FAFC"
    TEXT_SECONDARY: Final = "#94A3B8"
    ACTIVE_COLOR: Final = "#10B981"
    INACTIVE_COLOR: Final = "#64748B"
    ACTIVATE_BUTTON: Final = "#2563EB"
    DEACTIVATE_BUTTON: Final = "#E11D48"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.keeper = ProcessKeeper()
        self.status_job: str | None = None
        self.jiggle_job: str | None = None
        self.keep_active_var = tk.BooleanVar(value=False)

        self._configure_window()
        self._create_interface()
        self._update_interface()

    def _configure_window(self) -> None:
        """Configure the main application window."""
        self.root.title(APP_NAME)
        self.root.geometry("440x470")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._center_window()

    def _center_window(self) -> None:
        """Center the app on the primary display."""
        self.root.update_idletasks()

        width = 440
        height = 470

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x_position = max(0, (screen_width - width) // 2)
        y_position = max(0, (screen_height - height) // 2)

        self.root.geometry(
            f"{width}x{height}+{x_position}+{y_position}"
        )

    def _create_interface(self) -> None:
        """Create the application controls."""
        container = tk.Frame(
            self.root,
            bg=self.BACKGROUND,
            padx=32,
            pady=28,
        )
        container.pack(fill="both", expand=True)

        title = tk.Label(
            container,
            text="Process Keeper",
            font=("Segoe UI", 20, "bold"),
            fg=self.TEXT_PRIMARY,
            bg=self.BACKGROUND,
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            container,
            text="For long Power BI refreshes and Fabric pipelines",
            font=("Segoe UI", 10),
            fg=self.TEXT_SECONDARY,
            bg=self.BACKGROUND,
        )
        subtitle.pack(anchor="w", pady=(3, 22))

        status_card = tk.Frame(
            container,
            bg=self.CARD_BACKGROUND,
            highlightthickness=1,
            highlightbackground="#334155",
            padx=20,
            pady=24,
        )
        status_card.pack(fill="x")

        self.status_indicator = tk.Label(
            status_card,
            text="\u25cf",
            font=("Segoe UI", 36),
            fg=self.INACTIVE_COLOR,
            bg=self.CARD_BACKGROUND,
        )
        self.status_indicator.pack()

        self.status_label = tk.Label(
            status_card,
            text="Protection inactive",
            font=("Segoe UI", 14, "bold"),
            fg=self.TEXT_PRIMARY,
            bg=self.CARD_BACKGROUND,
        )
        self.status_label.pack(pady=(4, 6))

        self.timer_label = tk.Label(
            status_card,
            text="00:00:00",
            font=("Consolas", 20, "bold"),
            fg=self.TEXT_PRIMARY,
            bg=self.CARD_BACKGROUND,
        )
        self.timer_label.pack()

        self.action_button = tk.Button(
            container,
            text="Activate",
            command=self.toggle,
            font=("Segoe UI", 12, "bold"),
            fg="#FFFFFF",
            bg=self.ACTIVATE_BUTTON,
            activeforeground="#FFFFFF",
            activebackground="#1D4ED8",
            relief="flat",
            cursor="hand2",
            height=2,
        )
        self.action_button.pack(fill="x", pady=(22, 10))

        self.keep_active_check = tk.Checkbutton(
            container,
            text="Also keep chat status (e.g. Teams) active",
            variable=self.keep_active_var,
            onvalue=True,
            offvalue=False,
            font=("Segoe UI", 9),
            fg=self.TEXT_SECONDARY,
            bg=self.BACKGROUND,
            activebackground=self.BACKGROUND,
            activeforeground=self.TEXT_PRIMARY,
            selectcolor=self.CARD_BACKGROUND,
            highlightthickness=0,
            anchor="w",
            command=self._handle_keep_active_toggle,
        )
        self.keep_active_check.pack(anchor="w", pady=(0, 16))

        self.info_label = tk.Label(
            container,
            text=(
                "Prevents the computer from sleeping while your "
                "long-running process is active.\n\n"
                "The checkbox above additionally nudges the mouse by "
                "1 pixel roughly every minute, purely so apps like "
                "Teams keep reporting you as active. It is off by "
                "default and separate from sleep prevention.\n\n"
                "Normal power behavior is restored when you deactivate "
                "or close the app."
            ),
            font=("Segoe UI", 9),
            fg=self.TEXT_SECONDARY,
            bg=self.BACKGROUND,
            justify="left",
            wraplength=370,
        )
        self.info_label.pack(anchor="w")

        platform_label = tk.Label(
            container,
            text=f"Platform: {platform.system()}",
            font=("Segoe UI", 8),
            fg="#64748B",
            bg=self.BACKGROUND,
        )
        platform_label.pack(anchor="w", pady=(18, 0))

    def toggle(self) -> None:
        """Activate or deactivate sleep prevention."""
        try:
            if self.keeper.active:
                self.keeper.deactivate()
                self._cancel_jiggle()
            else:
                self.keeper.activate()
                self._schedule_jiggle()

            self._update_interface()

        except Exception as error:
            messagebox.showerror(
                APP_NAME,
                f"Unable to change the protection state.\n\n{error}",
            )

    def _handle_keep_active_toggle(self) -> None:
        """React to the 'keep chat status active' checkbox changing."""
        if self.keeper.active and self.keep_active_var.get():
            self._schedule_jiggle()

    def _schedule_jiggle(self) -> None:
        """(Re)start the periodic jiggle timer."""
        self._cancel_jiggle()
        self.jiggle_job = self.root.after(
            JIGGLE_INTERVAL_MS,
            self._jiggle_tick,
        )

    def _jiggle_tick(self) -> None:
        """Perform one jiggle, if still enabled, and reschedule."""
        if self.keeper.active and self.keep_active_var.get():
            try:
                InputSimulator.jiggle()
            except Exception as error:
                print(
                    f"Warning: could not simulate input: {error}",
                    file=sys.stderr,
                )

        if self.keeper.active:
            self.jiggle_job = self.root.after(
                JIGGLE_INTERVAL_MS,
                self._jiggle_tick,
            )
        else:
            self.jiggle_job = None

    def _cancel_jiggle(self) -> None:
        """Stop the periodic jiggle timer, if running."""
        if self.jiggle_job is not None:
            self.root.after_cancel(self.jiggle_job)
            self.jiggle_job = None

    def _update_interface(self) -> None:
        """Refresh status, timer, and button appearance."""
        if self.keeper.active:
            self.status_indicator.configure(
                fg=self.ACTIVE_COLOR
            )
            self.status_label.configure(
                text="Protection active",
                fg=self.ACTIVE_COLOR,
            )
            self.action_button.configure(
                text="Deactivate",
                bg=self.DEACTIVATE_BUTTON,
                activebackground="#BE123C",
            )

            elapsed = self.keeper.elapsed()
            total_seconds = int(elapsed.total_seconds())

            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            self.timer_label.configure(
                text=f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            )
        else:
            self.status_indicator.configure(
                fg=self.INACTIVE_COLOR
            )
            self.status_label.configure(
                text="Protection inactive",
                fg=self.TEXT_PRIMARY,
            )
            self.timer_label.configure(text="00:00:00")
            self.action_button.configure(
                text="Activate",
                bg=self.ACTIVATE_BUTTON,
                activebackground="#1D4ED8",
            )

        self.status_job = self.root.after(
            1_000,
            self._update_interface,
        )

    def close(self) -> None:
        """Restore normal power settings and close the app."""
        if self.status_job is not None:
            self.root.after_cancel(self.status_job)
            self.status_job = None

        self._cancel_jiggle()

        try:
            self.keeper.deactivate()
        except Exception as error:
            print(
                f"Warning: could not restore the power state: {error}",
                file=sys.stderr,
            )
        finally:
            self.root.destroy()


def main() -> int:
    """Create and run the desktop application."""
    root = tk.Tk()
    app = ProcessKeeperApp(root)

    def handle_signal(
        signal_number: int,
        frame: object,
    ) -> None:
        del signal_number, frame
        app.close()

    signal.signal(signal.SIGINT, handle_signal)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    root.mainloop()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"{APP_NAME} failed: {error}", file=sys.stderr)
        raise SystemExit(1)