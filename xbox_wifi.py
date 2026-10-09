import pygame
import time
import socket
import json
import sys

# --- Network Setup ---
#Don't Forget Replace The IP Address
RPI_IP = "YOUR_RPI_IP"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# --- Controller Setup ---
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Oops! No Xbox controller found. Plug it in first.")
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()

# --- Movement Settings ---
STEP_SIZE = 1.5
DEADZONE = 0.2

# Default starting angles
angles = {
    5: 90.0,  # Base
    4: 90.0,  # Pitch
    3: 90.0,  # Extend
    2: 90.0,  # Height
    1: 90.0,  # Roll
    0: 45.0   # Grip
}

# Safe limits so we don't break the motors
limits = {
    5: (0, 180),
    4: (15, 165),
    3: (15, 165),
    2: (10, 170),
    1: (0, 180),
    0: (0, 90)
}

print(f"Connected to: {joystick.get_name()}! Ready to go.")
print(f"Sending data to RPi ({RPI_IP})... Hit Ctrl+C to stop.")

try:
    while True:
        pygame.event.pump()

        # 1. Gripper (M0) - Custom buttons
        lt_val = joystick.get_button(2)
        rt_val = joystick.get_button(0)

        if lt_val > 0.0:  # Open
            angles[0] -= (STEP_SIZE * 2)
        if rt_val > 0.0:  # Close
            angles[0] += (STEP_SIZE * 2)

        # 2. Base Rotation (M5) - Bumpers
        if joystick.get_button(4):  # LB
            angles[5] -= STEP_SIZE
        if joystick.get_button(5):  # RB
            angles[5] += STEP_SIZE

        # 3. Middle & Lower Arm (M3, M4) - Right Stick
        right_x = joystick.get_axis(3)
        right_y = joystick.get_axis(4)

        if abs(right_x) > DEADZONE:
            angles[3] -= right_x * STEP_SIZE
        if abs(right_y) > DEADZONE:
            angles[4] -= right_y * STEP_SIZE

        # 4. Upper Arm & Gripper Roll (M2, M1) - Left Stick
        left_x = joystick.get_axis(0)
        left_y = joystick.get_axis(1)

        if abs(left_x) > DEADZONE:
            angles[1] -= left_x * STEP_SIZE
        if abs(left_y) > DEADZONE:
            angles[2] -= left_y * STEP_SIZE

        # 5. Apply limits and send data
        payload = {}
        for i in range(6):
            angles[i] = max(limits[i][0], min(limits[i][1], angles[i]))
            payload[f"m{i}"] = int(angles[i])

        try:
            sock.sendto(json.dumps(payload).encode('utf-8'), (RPI_IP, UDP_PORT))
        except Exception:
            pass

        # Print angles live
        sys.stdout.write(
            f"\r M5:{payload['m5']:3}° | M4:{payload['m4']:3}° | M3:{payload['m3']:3}° | M2:{payload['m2']:3}° | M1:{payload['m1']:3}° | M0:{payload['m0']:3}°  "
        )
        sys.stdout.flush()

        time.sleep(0.02)

except KeyboardInterrupt:
    # 6. Safe Parking
    print("\n\nCtrl+C detected! Parking the arm slowly so it doesn't break...")
    target_angles = {5: 90.0, 4: 90.0, 3: 90.0, 2: 90.0, 1: 90.0, 0: 45.0}

    # Step-by-step return to default
    for _ in range(150):
        reached_target = True
        for i in range(6):
            if abs(angles[i] - target_angles[i]) > STEP_SIZE:
                reached_target = False
                if angles[i] < target_angles[i]:
                    angles[i] += STEP_SIZE
                else:
                    angles[i] -= STEP_SIZE
            else:
                angles[i] = target_angles[i]

        payload = {f"m{i}": int(angles[i]) for i in range(6)}
        try:
            sock.sendto(json.dumps(payload).encode('utf-8'), (RPI_IP, UDP_PORT))
        except Exception:
            pass

        if reached_target:
            break

        time.sleep(0.02)

    print("All good, arm parked safely. See ya!")
    pygame.quit()