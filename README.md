# Smart Wearable Fall Detection System

A wearable fall detection system based on a **Raspberry Pi Pico** and **MPU6050 accelerometer**. It detects falls by checking three conditions **in sequence** — sudden impact, followed by low movement, within a set time window — to reduce false alarms.

---

## How It Works

1. **Sudden Impact** — acceleration magnitude `A = √(X² + Y² + Z²) ≥ 2.0 g`
2. **Low Movement** — `A ≤ 0.5 g` for 3 consecutive readings
3. **Time Window** — low movement must occur within `2000 ms` of the impact

If low movement isn't confirmed in time, it's treated as a **false alarm** and the system resets to monitoring.

## State Machine

| State             | Description                       |
| ----------------- | ---------------------------------- |
| `MONITORING`      | Normal operation                   |
| `POSSIBLE_IMPACT`  | Impact detected                    |
| `CHECKING`         | Checking for low movement          |
| `FALL_DETECTED`    | Fall confirmed, alarm active       |

```text
MONITORING → (impact ≥ 2.0g) → POSSIBLE_IMPACT → CHECKING
CHECKING → (3 low readings) → FALL_DETECTED → (reset button) → MONITORING
CHECKING → (2000ms expired) → MONITORING (false alarm)
```

## Hardware & Pins

| Component    | GPIO   |
| ------------ | -----: |
| Green LED    | GP16   |
| Red LED      | GP17   |
| Buzzer       | GP13   |
| Reset Button | GP15   |
| I2C SDA      | GP0    |
| I2C SCL      | GP1    |
| MPU6050      | `0x68` |
| LCD          | `0x27` |

## Parameters

```text
Impact Threshold       = 2.0 g
Low Movement Threshold = 0.5 g
Time Window            = 2000 ms
Low Movement Samples   = 3
```

## Indicators

- **Monitoring:** Green LED ON, LCD "Monitoring..."
- **Possible Impact:** LCD "Possible Impact!"
- **Fall Detected:** Red LED + Buzzer ON, LCD "FALL DETECTED!" (locked until reset)
- **False Alarm:** auto-returns to monitoring, no alarm

## Error Handling

At startup, the system checks the I2C bus for the MPU6050 (`0x68`) and LCD (`0x27`). If either is missing, it prints an error and blinks the red LED.

## Pseudocode

```text
Set state = MONITORING

WHILE running:
    IF FALL_DETECTED and reset pressed: state = MONITORING
    IF state == FALL_DETECTED: keep alarm active; continue

    Read accelerometer → calculate magnitude

    IF state == MONITORING and magnitude >= IMPACT_THRESHOLD:
        state = POSSIBLE_IMPACT

    ELIF state == POSSIBLE_IMPACT:
        state = CHECKING

    ELIF state == CHECKING:
        IF magnitude <= LOW_MOVEMENT_THRESHOLD: low_count += 1
        ELSE: low_count = 0

        IF low_count >= 3: state = FALL_DETECTED
        ELIF elapsed_time >= TIME_WINDOW: state = MONITORING
```

## Development Environment

- **MCU:** Raspberry Pi Pico | **Language:** MicroPython
- **Simulation:** Wokwi | **IDE:** VS Code | **VCS:** Git & GitHub

## Project Structure

```text
Smart-Fall-Detection/
├── README.md
└── main.py
```

## Getting Started

1. `git clone https://github.com/moanwar7/Smart-Wearable-Fall-Detection-System.git`
2. Wire components per the pin table above.
3. Run on Wokwi `main.py` to the Pico.
4. Watch the serial monitor for state transitions and test the fall sequence.
