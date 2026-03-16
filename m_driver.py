"""
Mouse Mover with Sleep Inhibitor (Windows/macOS/Linux)

- Press "Activate" to move the cursor in a circle and keep the system/display awake.
- If you manually move the mouse > sensitivity pixels from the last commanded point,
  it stops and auto-resumes after 5 seconds (unless you pressed Stop).
- UI updates are marshaled to the Tk main thread for stability.
"""

import sys
import time
import math
import threading
import subprocess
import atexit

import tkinter as tk

import pyautogui

# Optional: ctypes is only needed on Windows
try:
    import ctypes
except Exception:
    ctypes = None


class SleepInhibitor:
    """
    Cross-platform sleep/display inhibitor.
      - Windows: SetThreadExecutionState (prevents system + display sleep)
      - macOS:   'caffeinate -dimsu' helper process
      - Linux:   'systemd-inhibit --what=idle:sleep' helper (if available)
    """

    def __init__(self):
        self.proc = None

    def prevent(self):
        if sys.platform.startswith('win') and ctypes is not None:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            # Keep system and display on while running
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        elif sys.platform == 'darwin':
            # Launch caffeinate if not already running
            if self.proc is None or self.proc.poll() is not None:
                try:
                    self.proc = subprocess.Popen(["caffeinate", "-dimsu"])
                except Exception as e:
                    print(f"[SleepInhibitor] Failed to start caffeinate: {e}")
        else:
            # Linux (systemd). If command not found, we silently skip.
            if self.proc is None or self.proc.poll() is not None:
                try:
                    self.proc = subprocess.Popen([
                        "systemd-inhibit",
                        "--what=idle:sleep",
                        "--mode=block",
                        "--why=MouseMover",
                        "bash", "-c", "sleep infinity"
                    ])
                except FileNotFoundError:
                    # systemd-inhibit not available; continue without inhibition
                    print("[SleepInhibitor] systemd-inhibit not found; skipping inhibition.")
                except Exception as e:
                    print(f"[SleepInhibitor] Failed to start systemd-inhibit: {e}")

    def allow(self):
        if sys.platform.startswith('win') and ctypes is not None:
            # Clear the execution state flags so normal sleep resumes
            ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        else:
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=2)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
            self.proc = None


# Global inhibitor and cleanup registration
inhibitor = SleepInhibitor()
atexit.register(inhibitor.allow)


class MouseMoverApp:
    def __init__(self, master):
        self.master = master
        master.title("Mouse Mover")
        master.geometry("260x160")
        master.resizable(False, False)

        # State
        self.is_moving = False
        self.was_interrupted = False
        self.user_stopped_flag = False
        self.thread = None

        # UI
        self.activate_button = tk.Button(master, text="Activate", command=self.start_movement, width=25)
        self.activate_button.pack(pady=10)

        self.stop_button = tk.Button(master, text="Stop", command=self.user_stopped, width=25)
        self.stop_button.pack(pady=5)

        self.status_label = tk.Label(master, text="Status: Stopped", fg="red")
        self.status_label.pack(pady=5)

        # Safe Tk shutdown
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # PyAutoGUI: keep failsafe ON so dragging to top-left aborts if needed
        pyautogui.FAILSAFE = True

    # -------------------- UI helpers (main-thread only) --------------------

    def _set_status(self, text, color):
        # Route UI update to main thread
        self.master.after(0, lambda: self.status_label.config(text=text, fg=color))

    # -------------------- Core logic --------------------

    def move_mouse_in_circle(self, radius=100, interval=0.02, sensitivity=50):
        """
        Worker thread: moves the mouse in a circle around the current position.
        Stops if user moves mouse far from last commanded point.
        """
        try:
            # Screen bounds and starting center
            screen_w, screen_h = pyautogui.size()
            cx, cy = pyautogui.position()

            # Keep the circle within screen bounds
            safe_margin = 5
            max_r = min(cx, screen_w - cx, cy, screen_h - cy) - safe_margin
            if max_r < 10:
                max_r = 10
            radius = int(min(radius, max_r))

            angle = 0.0

            # Issue an initial move so we have a last commanded point
            last_cmd_x = cx + int(radius * math.cos(angle))
            last_cmd_y = cy + int(radius * math.sin(angle))
            pyautogui.moveTo(last_cmd_x, last_cmd_y)
            angle += 0.1

            while self.is_moving:
                # Detect manual movement relative to the last commanded position
                cur_x, cur_y = pyautogui.position()
                if math.hypot(cur_x - last_cmd_x, cur_y - last_cmd_y) > sensitivity:
                    print("[MouseMover] Manual movement detected. Pausing...")
                    self.was_interrupted = True
                    # Stop safely via main thread
                    self.master.after(0, self.stop_movement)
                    return

                # Compute and move to next point on the circle
                x = cx + int(radius * math.cos(angle))
                y = cy + int(radius * math.sin(angle))
                pyautogui.moveTo(x, y)

                last_cmd_x, last_cmd_y = x, y
                angle += 0.1
                if angle >= math.tau:
                    angle -= math.tau

                time.sleep(interval)

        except pyautogui.FailSafeException:
            # User yanked to (0,0); stop without scheduling auto-resume
            print("[MouseMover] Fail-safe triggered. Stopping.")
            self.was_interrupted = False
            self.master.after(0, self.stop_movement)
        except Exception as e:
            print(f"[MouseMover] Worker error: {e}")
            self.was_interrupted = False
            self.master.after(0, self.stop_movement)

    def start_movement(self):
        if not self.is_moving:
            self.user_stopped_flag = False
            self.was_interrupted = False
            self.is_moving = True

            # Keep system/display awake while running
            inhibitor.prevent()

            self._set_status("Status: Running", "green")
            self.thread = threading.Thread(target=self.move_mouse_in_circle, daemon=True)
            self.thread.start()

    def stop_movement(self):
        if self.is_moving:
            self.is_moving = False

            # Allow normal sleep again
            inhibitor.allow()

            self._set_status("Status: Stopped", "red")

            # If this stop was due to manual movement, schedule auto-resume
            if self.was_interrupted:
                print("[MouseMover] Waiting 5 seconds before auto-resume...")
                threading.Thread(target=self.restart_timer, daemon=True).start()

    def restart_timer(self):
        time.sleep(5)
        if not self.user_stopped_flag and not self.is_moving:
            print("[MouseMover] Resuming movement...")
            self.start_movement()
        else:
            print("[MouseMover] Auto-resume cancelled by user.")

    def user_stopped(self):
        # Explicit user stop cancels auto-resume
        self.user_stopped_flag = True
        self.was_interrupted = False
        self.stop_movement()

    def on_close(self):
        # Ensure clean shutdown
        self.user_stopped_flag = True
        self.is_moving = False
        inhibitor.allow()
        try:
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=0.5)
        except Exception:
            pass
        self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MouseMoverApp(root)
    root.mainloop()