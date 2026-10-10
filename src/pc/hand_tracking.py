import cv2
import mediapipe as mp
import math
import sys
import socket
import json

# --- Network Setup ---
#Don't Forget Replace The IP Address
RPI_IP = "YOUR_RPI_IP"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

mp_holistic = mp.solutions.holistic
mp_draw = mp.solutions.drawing_utils
holistic = mp_holistic.Holistic(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7,
    model_complexity=1
)

cap = cv2.VideoCapture(0)
print(f"Running... IP: {RPI_IP} | Press 'q' to quit")

# Default angles
target_m5, target_m4, target_m3 = 90, 90, 90
target_m2, target_m1, target_m0 = 90, 90, 45

# Allow window resizing
cv2.namedWindow("Hand Tracking Control", cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret: break

    # Mirror effect
    frame = cv2.flip(frame, 1)
    h, w, c = frame.shape
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = holistic.process(rgb_frame)

    is_pinky_bent = False
    hand_detected = False
    active_hand_landmarks = None

    # --- Right hand tracking only ---
    if results.left_hand_landmarks:
        active_hand_landmarks = results.left_hand_landmarks
        hand_detected = True

    if results.pose_landmarks and hand_detected:
        mp_draw.draw_landmarks(frame, active_hand_landmarks, mp_holistic.HAND_CONNECTIONS)

        # Get landmarks
        nose_lm = results.pose_landmarks.landmark[0]
        nose_px = (int(nose_lm.x * w), int(nose_lm.y * h))

        hand = active_hand_landmarks.landmark
        lm0 = hand[0]    # Wrist
        lm4 = hand[4]    # Thumb
        lm5 = hand[5]    # Index base
        lm8 = hand[8]    # Index tip
        lm9 = hand[9]    # Palm center
        lm12 = hand[12]  # Middle tip
        lm17 = hand[17]  # Pinky base
        lm20 = hand[20]  # Pinky tip

        # Draw coordinates
        wrist_px = (int(lm0.x * w), int(lm0.y * h))
        thumb_px = (int(lm4.x * w), int(lm4.y * h))
        index_px = (int(lm8.x * w), int(lm8.y * h))
        middle_px = (int(lm12.x * w), int(lm12.y * h))
        pinky_base_px = (int(lm17.x * w), int(lm17.y * h))
        pinky_tip_px = (int(lm20.x * w), int(lm20.y * h))

        def dist_3d(p1, p2):
            return math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2 + (p2.z - p1.z) ** 2)

        # 1. X-axis movement (M5 & M1)
        X_SENSITIVITY = 2.5
        x_offset = lm0.x - 0.5
        calc_x_angle = int(max(0, min(180, 90 + (x_offset * 180 * X_SENSITIVITY))))

        # 2. Peace sign distance (M4)
        v_dist = dist_3d(lm8, lm12)
        ref_hand_size = dist_3d(lm0, lm9) + 1e-5
        v_ratio = v_dist / ref_hand_size

        MIN_V, MAX_V = 0.1, 0.6
        constrained_v = max(MIN_V, min(MAX_V, v_ratio))
        calc_m4 = int(15 + ((constrained_v - MIN_V) / (MAX_V - MIN_V)) * 150)

        # 3. Y-axis movement (M2 & M3)
        height_diff = nose_lm.y - lm0.y
        calc_y_angle = int(max(15, min(170, 90 + (height_diff * 200))))

        # 4. Gripper (M0)
        ref_dist_m0 = dist_3d(lm0, lm5) + 1e-5
        pinch_ratio = dist_3d(lm4, lm8) / ref_dist_m0
        CLOSE_RATIO, OPEN_RATIO = 0.18, 0.65
        ratio_constrained = max(CLOSE_RATIO, min(OPEN_RATIO, pinch_ratio))
        target_m0 = int(90 - (((ratio_constrained - CLOSE_RATIO) / (OPEN_RATIO - CLOSE_RATIO)) * 90))

        # --- Smart switch (Pinky) ---
        is_pinky_bent = dist_3d(lm0, lm20) < (dist_3d(lm0, lm17) * 1.28)

        if is_pinky_bent:
            target_m2 = calc_y_angle
            target_m1 = calc_x_angle
            pinky_color = (0, 0, 255)
        else:
            target_m5 = calc_x_angle
            target_m4 = calc_m4
            target_m3 = calc_y_angle
            pinky_color = (0, 255, 0)

        # --- Send to RPi ---
        payload = {
            "m5": target_m5, "m4": target_m4, "m3": target_m3,
            "m2": target_m2, "m1": target_m1, "m0": target_m0
        }
        try:
            sock.sendto(json.dumps(payload).encode('utf-8'), (RPI_IP, UDP_PORT))
        except Exception:
            pass

        # --- Draw on screen ---
        cv2.line(frame, nose_px, wrist_px, (255, 255, 0), 2)
        cv2.circle(frame, nose_px, 8, (255, 255, 0), -1)
        cv2.circle(frame, wrist_px, 6, (255, 255, 0), -1)

        cv2.line(frame, index_px, middle_px, (255, 165, 0), 2)
        cv2.circle(frame, middle_px, 6, (255, 165, 0), -1)

        cv2.circle(frame, thumb_px, 6, (255, 0, 255), -1)
        cv2.line(frame, pinky_base_px, pinky_tip_px, pinky_color, 3)

        grip_color = (0, 0, 255) if target_m0 > 75 else (0, 255, 0)
        cv2.line(frame, thumb_px, index_px, grip_color, 3)

        sys.stdout.write(
            f"\r M5:{target_m5:3}° | M4:{target_m4:3}° | M3:{target_m3:3}° | M2:{target_m2:3}° | M1:{target_m1:3}° | M0:{target_m0:3}°  "
        )
        sys.stdout.flush()

        cv2.rectangle(frame, (10, 10), (280, 230), (0, 0, 0), -1)
        state_text = "Pinky DOWN (M2, M1)" if is_pinky_bent else "Pinky UP (M5, M4, M3)"
        cv2.putText(frame, state_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, pinky_color, 2)
        cv2.putText(frame, f"M5 (Base)   : {target_m5}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"M4 (Pitch)  : {target_m4}", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"M3 (Extend) : {target_m3}", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"M2 (Height) : {target_m2}", (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255) if is_pinky_bent else (255, 255, 255), 2)
        cv2.putText(frame, f"M1 (Roll)   : {target_m1}", (20, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255) if is_pinky_bent else (255, 255, 255), 2)
        cv2.putText(frame, f"M0 (Grip)   : {target_m0}", (20, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, grip_color, 2)

    cv2.imshow("Hand Tracking Control", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

print("\nDone.")
cap.release()
cv2.destroyAllWindows()
