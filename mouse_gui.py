import tkinter as tk
import pyautogui
import threading
import time
import math

class MouseMoverApp:
    def __init__(self, master):
        self.master = master
        master.title("Mouse Mover")
        master.geometry("250x150")
        master.resizable(False, False)

        self.is_moving = False
        self.was_interrupted = False
        self.user_stopped_flag = False
        self.thread = None

        self.activate_button = tk.Button(master, text="Activate", command=self.start_movement, width=25)
        self.activate_button.pack(pady=10)

        self.stop_button = tk.Button(master, text="Stop", command=self.user_stopped, width=25)
        self.stop_button.pack(pady=5)

        self.status_label = tk.Label(master, text="Status: Stopped", fg="red")
        self.status_label.pack(pady=5)

    def move_mouse_in_circle(self, radius=100, interval=0.01, sensitivity=50):
        center_x, center_y = pyautogui.position()
        angle = 0
        first_move = True

        while self.is_moving:
            x = center_x + int(radius * math.cos(angle))
            y = center_y + int(radius * math.sin(angle))

            if not first_move:
                current_pos = pyautogui.position()
                dist = math.hypot(current_pos[0] - x, current_pos[1] - y)
                if dist > sensitivity:
                    print("Mouse moved manually. Stopping.")
                    self.was_interrupted = True
                    self.stop_movement()
                    return
            else:
                first_move = False

            pyautogui.moveTo(x, y)
            angle += 0.1
            time.sleep(interval)

    def start_movement(self):
        if not self.is_moving:
            self.user_stopped_flag = False  # reset manual stop flag
            self.is_moving = True
            self.was_interrupted = False
            self.status_label.config(text="Status: Running", fg="green")
            self.thread = threading.Thread(target=self.move_mouse_in_circle, daemon=True)
            self.thread.start()

    def stop_movement(self):
        if self.is_moving:
            self.is_moving = False
            self.status_label.config(text="Status: Stopped", fg="red")

            if self.was_interrupted:
                print("Waiting 5 seconds before restart...")
                threading.Thread(target=self.restart_timer, daemon=True).start()

    def restart_timer(self):
        time.sleep(5)
        if not self.user_stopped_flag and not self.is_moving:
            print("Resuming movement...")
            self.start_movement()
        else:
            print("Auto-resume cancelled by user.")

    def user_stopped(self):
        self.user_stopped_flag = True
        self.was_interrupted = False
        self.stop_movement()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseMoverApp(root)
    root.mainloop()
