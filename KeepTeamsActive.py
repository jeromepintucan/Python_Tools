# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pyautogui",
# ]
# ///
"""
Teams Status Keeper

A script to keep Microsoft Teams status active by simulating user activity.
Works on Windows, macOS, and Linux platforms.

Usage:
    python keep-teams-alive.py [interval_seconds] [duration_hours]
    
    - interval_seconds: Time between activity simulations (default: 180 seconds / 3 minutes)
    - duration_hours: How long to run (default: 8 hours, 0 for indefinite)
"""

import os
import sys
import time
import random
import signal
import datetime
import argparse
from threading import Event

# Try importing platform-specific modules
try:
    import pyautogui
    HAVE_PYAUTOGUI = True
except ImportError:
    HAVE_PYAUTOGUI = False

try:
    if os.name == 'nt':  # Windows
        import ctypes
        HAVE_CTYPES = True
    elif sys.platform == 'darwin':  # macOS
        import subprocess
        HAVE_SUBPROCESS = True
    else:  # Linux
        import subprocess
        HAVE_SUBPROCESS = True
except ImportError:
    HAVE_CTYPES = False
    HAVE_SUBPROCESS = False

# Define stop event for clean shutdown
stop_event = Event()

def signal_handler(sig, frame):
    """Handle interrupt signals for clean shutdown"""
    print("\nStopping Teams Status Keeper...")
    stop_event.set()

def simulate_activity_pyautogui():
    """Simulate user activity using pyautogui"""
    if not HAVE_PYAUTOGUI:
        return False
    
    try:
        # Get screen size
        screen_width, screen_height = pyautogui.size()
        
        # Choose random activity
        activity = random.choice([
            'mouse_move',
            'key_press',
            'scroll'
        ])
        
        if activity == 'mouse_move':
            # Move mouse slightly (not enough to disrupt work)
            current_x, current_y = pyautogui.position()
            offset_x = random.randint(-10, 10)
            offset_y = random.randint(-10, 10)
            
            # Ensure we stay within screen bounds
            new_x = max(0, min(screen_width, current_x + offset_x))
            new_y = max(0, min(screen_height, current_y + offset_y))
            
            pyautogui.moveTo(new_x, new_y, duration=0.5)
            time.sleep(0.5)
            # Move back to original position so it's not disruptive
            pyautogui.moveTo(current_x, current_y, duration=0.5)
            
        elif activity == 'key_press':
            # Press a modifier key that won't type anything
            # Choose from: shift, ctrl, alt keys
            key = random.choice(['shift', 'ctrl', 'alt'])
            pyautogui.keyDown(key)
            time.sleep(0.1)
            pyautogui.keyUp(key)
            
        elif activity == 'scroll':
            # Scroll slightly up and then back down
            pyautogui.scroll(5)
            time.sleep(0.5)
            pyautogui.scroll(-5)
        
        return True
    except Exception as e:
        print(f"PyAutoGUI error: {e}")
        return False

def simulate_activity_windows():
    """Simulate user activity using Windows-specific methods"""
    if os.name != 'nt' or not HAVE_CTYPES:
        return False
    
    try:
        # Windows-specific: simulate input using SendInput
        # This simulates a null input event which can reset idle timers
        ctypes.windll.user32.SendInputA(0, None, ctypes.sizeof(ctypes.c_int))
        
        # Alternative: prevent screen saver/sleep
        # ES_CONTINUOUS = 0x80000000
        # ES_SYSTEM_REQUIRED = 0x00000001
        # ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            0x80000000 | 0x00000001 | 0x00000002
        )
        return True
    except Exception as e:
        print(f"Windows-specific error: {e}")
        return False

def simulate_activity_macos():
    """Simulate user activity using macOS-specific methods"""
    if sys.platform != 'darwin' or not HAVE_SUBPROCESS:
        return False
    
    try:
        # Use macOS-specific caffeinate command to prevent sleep
        subprocess.call(['caffeinate', '-i', '-t', '59'])
        
        # AppleScript to simulate keypress
        script = '''
        tell application "System Events"
            key code 63 # F9 key
            delay 0.1
            key code 63
        end tell
        '''
        subprocess.run(['osascript', '-e', script], 
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"macOS-specific error: {e}")
        return False

def simulate_activity_linux():
    """Simulate user activity using Linux-specific methods"""
    if not (sys.platform.startswith('linux') and HAVE_SUBPROCESS):
        return False
    
    try:
        # Try xdotool if available (for X11 sessions)
        try:
            # Simulate key press (Shift key)
            subprocess.run(['xdotool', 'key', 'shift'], 
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        # Try DBUS method for GNOME
        try:
            cmd = "dbus-send --session --dest=org.gnome.ScreenSaver "
            cmd += "--type=method_call /org/gnome/ScreenSaver "
            cmd += "org.gnome.ScreenSaver.SimulateUserActivity"
            subprocess.run(cmd.split(), 
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        return False
    except Exception as e:
        print(f"Linux-specific error: {e}")
        return False

def keep_teams_alive(interval=180, duration_hours=8):
    """Main function to keep Teams alive"""
    print("Teams Status Keeper")
    print("--------------------")
    print(f"Platform: {sys.platform} ({os.name})")
    print(f"Interval: {interval} seconds")
    if duration_hours > 0:
        print(f"Duration: {duration_hours} hours")
        end_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        print(f"Will stop at: {end_time.strftime('%H:%M:%S')}")
    else:
        print("Duration: Indefinite (until Ctrl+C)")
        end_time = None
    print("")
    
    # Check available methods
    methods = []
    if HAVE_PYAUTOGUI:
        methods.append("cross-platform (pyautogui)")
    if os.name == 'nt' and HAVE_CTYPES:
        methods.append("Windows-specific")
    if sys.platform == 'darwin' and HAVE_SUBPROCESS:
        methods.append("macOS-specific")
    if sys.platform.startswith('linux') and HAVE_SUBPROCESS:
        methods.append("Linux-specific")
    
    if not methods:
        print("Error: No activity simulation methods available.")
        print("Please install pyautogui: pip install pyautogui")
        return
    
    print(f"Available methods: {', '.join(methods)}")
    print("")
    print("Press Ctrl+C to stop")
    print("")
    
    cycle_count = 0
    start_time = datetime.datetime.now()
    
    # Main loop
    while not stop_event.is_set():
        cycle_count += 1
        current_time = datetime.datetime.now()
        elapsed = current_time - start_time
        elapsed_str = str(elapsed).split('.')[0]  # remove microseconds
        
        # Check if we've reached the duration
        if end_time and current_time >= end_time:
            print(f"\nReached specified duration of {duration_hours} hours.")
            break
        
        print(f"Cycle {cycle_count} - {current_time.strftime('%H:%M:%S')} (Running: {elapsed_str})")
        
        # Try all available methods until one succeeds
        success = False
        
        if not success and HAVE_PYAUTOGUI:
            if simulate_activity_pyautogui():
                print("  ✓ Activity simulated (cross-platform)")
                success = True
        
        if not success and os.name == 'nt':
            if simulate_activity_windows():
                print("  ✓ Activity simulated (Windows-specific)")
                success = True
        
        if not success and sys.platform == 'darwin':
            if simulate_activity_macos():
                print("  ✓ Activity simulated (macOS-specific)")
                success = True
        
        if not success and sys.platform.startswith('linux'):
            if simulate_activity_linux():
                print("  ✓ Activity simulated (Linux-specific)")
                success = True
        
        if not success:
            print("  ✗ Failed to simulate activity using any method")
        
        # Wait for the next cycle
        try:
            stop_event.wait(timeout=interval)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Keep Microsoft Teams status active')
    parser.add_argument('interval', nargs='?', type=int, default=180,
                        help='Time between activity simulations in seconds (default: 180)')
    parser.add_argument('duration', nargs='?', type=int, default=8,
                        help='How long to run in hours, 0 for indefinite (default: 8)')
    args = parser.parse_args()
    
    # Run the main function
    try:
        keep_teams_alive(args.interval, args.duration)
        print("Teams Status Keeper stopped.")
    except Exception as e:
        print(f"Error: {e}")