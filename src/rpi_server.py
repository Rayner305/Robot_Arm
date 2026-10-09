import socket
import json
import time
from adafruit_servokit import ServoKit

# --- Hardware Setup ---
kit = ServoKit(channels=16)

# --- Network Setup ---
UDP_IP = "0.0.0.0"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

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

# --- Main Loop ---
while True:
    try:
        data, addr = sock.recvfrom(1024)
        payload = json.loads(data.decode('utf-8'))

        for key, target_angle in payload.items():
            if key in motors:
                config = motors[key]

                # Apply safety limits
                target_angle = max(config["min"], min(config["max"], target_angle))

                # Apply smoothing filter
                config["current"] += config["alpha"] * (target_angle - config["current"])

                # Move servo
                kit.servo[config["channel"]].angle = config["current"]

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"Error: {e}")
