import socket
import json
import time
import math
from adafruit_servokit import ServoKit

# --- Hardware Setup ---
kit = ServoKit(channels=16)

# --- Network Setup ---
UDP_IP = "0.0.0.0"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

# Small timeout (0.02s) to keep the smoothing active even without data
sock.settimeout(0.02) 

print(f"Server is up on port {UDP_PORT}...")
print("Waiting for commands...")

# --- Motor Config & Smoothing ---
motors = {
    "m5": {"channel": 5, "current": 90.0, "min": 0, "max": 180, "alpha": 0.15},
    "m4": {"channel": 4, "current": 90.0, "min": 15, "max": 165, "alpha": 0.10},
    "m3": {"channel": 3, "current": 90.0, "min": 15, "max": 165, "alpha": 0.10},
    "m2": {"channel": 2, "current": 90.0, "min": 10, "max": 170, "alpha": 0.10},
    "m1": {"channel": 1, "current": 90.0, "min": 0, "max": 180, "alpha": 0.20},
    "m0": {"channel": 0, "current": 45.0, "min": 0, "max": 90, "alpha": 0.35},
}

# Set motors to standby
for key, config in motors.items():
    kit.servo[config["channel"]].angle = config["current"]

# Safety tracking variables
last_receive_time = time.time()
TIMEOUT_LIMIT = 20.0
is_parked = True
payload = {"m5": 90, "m4": 90, "m3": 90, "m2": 90, "m1": 90, "m0": 45}

def validate_payload(message):
    """Accept only finite numeric angles for known motors."""
    if not isinstance(message, dict):
        raise ValueError("Motor commands must be a JSON object")

    commands = {}
    for key, angle in message.items():
        if key not in motors:
            continue
        if isinstance(angle, bool) or not isinstance(angle, (int, float)):
            raise ValueError(f"Invalid angle for {key}")
        try:
            angle = float(angle)
        except (OverflowError, ValueError):
            raise ValueError(f"Invalid angle for {key}") from None
        if not math.isfinite(angle):
            raise ValueError(f"Invalid angle for {key}")
        commands[key] = angle

    if not commands:
        raise ValueError("No recognized motor commands")
    return commands


# --- Main Loop ---
while True:
    try:
        data, addr = sock.recvfrom(1024)
        commands = validate_payload(json.loads(data.decode('utf-8')))
        payload = commands
        
        if is_parked:
            print("Connection established! Arm is active.")
            is_parked = False
            
        last_receive_time = time.time()

    except socket.timeout:
        # Trigger safety parking if 20 seconds passed without signal
        if not is_parked and (time.time() - last_receive_time) > TIMEOUT_LIMIT:
            print("Connection lost for 20s! Parking the arm safely...")
            payload = {"m5": 90, "m4": 90, "m3": 90, "m2": 90, "m1": 90, "m0": 45}
            is_parked = True
            
            # Uncomment the next line if you want the script to completely close!
            # break 
            
    except (ValueError, UnicodeDecodeError):
        pass  # Invalid packets must not replace targets or reset the timeout
    except Exception as e:
        print(f"Error: {e}")
        pass

    # --- Apply Safety Limits and Smoothing ---
    for key, target_angle in payload.items():
        if key in motors:
            config = motors[key]
            
            # Apply safety limits
            target_angle = max(config["min"], min(config["max"], target_angle))
            
            # Apply exponential smoothing
            config["current"] += config["alpha"] * (target_angle - config["current"])
            
            # Move servo
            kit.servo[config["channel"]].angle = config["current"]
