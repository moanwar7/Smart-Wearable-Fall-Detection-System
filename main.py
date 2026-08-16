# =========================================================
# Smart Wearable Fall Detection System
# Author  : Mohamed Anwar
# Date    : 16 August 2026
# Platform: Raspberry Pi Pico | MicroPython | Wokwi
#
# Detects a fall only when 3 conditions occur IN SEQUENCE:
#   1) Sudden Impact  -> 2) Low Movement -> 3) within Time Window
# A single spike, or low movement outside the window, is a false alarm.
# =========================================================
from machine import Pin, I2C, PWM
import time, math
# ---------------- PIN CONFIGURATION ----------------
GREEN_LED_PIN, RED_LED_PIN, BUZZER_PIN, BUTTON_PIN = 16, 17, 13, 15
SDA_PIN, SCL_PIN = 0, 1
MPU_ADDRESS, LCD_ADDRESS = 0x68, 0x27
# ---------------- FALL DETECTION SETTINGS ----------------
IMPACT_THRESHOLD = 2.0        # g, Condition 1: sudden impact
LOW_MOVEMENT_THRESHOLD = 0.5  # g, Condition 2: low movement
TIME_WINDOW = 2000            # ms, Condition 3: time window after impact
LOW_MOVEMENT_SAMPLES = 3      # consecutive low readings to confirm stillness
# ---------------- STATES ----------------
MONITORING, POSSIBLE_IMPACT, CHECKING, FALL_DETECTED = 0, 1, 2, 3
state = MONITORING
# ---------------- GPIO INIT ----------------
green_led, red_led = Pin(GREEN_LED_PIN, Pin.OUT), Pin(RED_LED_PIN, Pin.OUT)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
buzzer = PWM(Pin(BUZZER_PIN)); buzzer.freq(1000); buzzer.duty_u16(0)
i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000)
# ---------------- LCD DRIVER (16x2 I2C) ----------------
class I2cLCD:
    def __init__(self, i2c, address):
        self.i2c, self.address, self.backlight = i2c, address, 0x08
        self.init_lcd()

    def write(self, data):
        self.i2c.writeto(self.address, bytes([data | self.backlight]))

    def pulse(self, data):
        self.write(data | 0x04); time.sleep_us(1)
        self.write(data & ~0x04); time.sleep_us(50)

    def send(self, value, rs):
        high, low = value & 0xF0, (value << 4) & 0xF0
        if rs:
            high |= 0x01; low |= 0x01
        self.pulse(high); self.pulse(low)

    def command(self, value):
        self.send(value, False)
        if value in (0x01, 0x02):
            time.sleep_ms(2)

    def clear(self):
        self.command(0x01)

    def move_to(self, col, row):
        self.command((0xC0 if row == 1 else 0x80) + col)

    def putstr(self, text):
        for char in text:
            self.send(ord(char), True)

    def init_lcd(self):
        time.sleep_ms(50); self.write(0x00)
        self.pulse(0x30); time.sleep_ms(5)
        self.pulse(0x30); time.sleep_us(150)
        self.pulse(0x30); self.pulse(0x20)
        self.command(0x28); self.command(0x0C); self.command(0x06)
        self.clear()
# ---------------- MPU6050 ACCELEROMETER ----------------
class MPU6050:
    def __init__(self, i2c, address):
        self.i2c, self.address = i2c, address
        self.i2c.writeto_mem(address, 0x6B, b'\x00')   # wake up sensor
        time.sleep_ms(100)
        self.i2c.writeto_mem(address, 0x1C, b'\x00')   # range = +/-2g

    def signed_value(self, high, low):
        value = (high << 8) | low
        return value - 65536 if value >= 32768 else value

    def read(self):
        data = self.i2c.readfrom_mem(self.address, 0x3B, 6)
        x = self.signed_value(data[0], data[1]) / 16384
        y = self.signed_value(data[2], data[3]) / 16384
        z = self.signed_value(data[4], data[5]) / 16384
        return x, y, z

    def magnitude(self):
        x, y, z = self.read()
        return math.sqrt(x * x + y * y + z * z)
# ---------------- INITIALIZE DEVICES ----------------
def blink_error(msg):
    print("ERROR:", msg)
    while True:
        red_led.on(); time.sleep_ms(300)
        red_led.off(); time.sleep_ms(300)

devices = i2c.scan()
if LCD_ADDRESS not in devices:
    blink_error("LCD not found")
if MPU_ADDRESS not in devices:
    blink_error("MPU6050 not found")

lcd = I2cLCD(i2c, LCD_ADDRESS)
mpu = MPU6050(i2c, MPU_ADDRESS)
# ---------------- LCD STATUS HELPER ----------------
def show_status(line1, line2=""):
    lcd.clear()
    lcd.move_to(0, 0); lcd.putstr(line1[:16])
    lcd.move_to(0, 1); lcd.putstr(line2[:16])
# ---------------- NORMAL MONITORING STATE ----------------
def monitoring_state():
    global state
    state = MONITORING
    green_led.on(); red_led.off()
    buzzer.duty_u16(0)
    show_status("Monitoring...", "System Ready")
# ---------------- FALL DETECTED / ALARM STATE ----------------
def fall_alarm():
    global state
    state = FALL_DETECTED
    green_led.off(); red_led.on()
    buzzer.freq(1000); buzzer.duty_u16(30000)
    show_status("FALL DETECTED!", "Press Reset")
    print("\n==== FALL DETECTED! ====")
# ---------------- START SYSTEM ----------------
monitoring_state()
print("SMART FALL DETECTION SYSTEM")
print("Impact:", IMPACT_THRESHOLD, "g | Low move:", LOW_MOVEMENT_THRESHOLD,
      "g | Window:", TIME_WINDOW, "ms")
impact_time = 0
low_movement_count = 0
last_display = 0
# ---------------- MAIN LOOP ----------------
while True:
    if button.value() == 0 and state == FALL_DETECTED:
        print("Reset button pressed.")
        monitoring_state()
        time.sleep_ms(500)
        continue
    if state == FALL_DETECTED:
        time.sleep_ms(50)
        continue
    magnitude = mpu.magnitude()
    # --- Condition 1: Sudden Impact -> move to checking stage ---
    if state == MONITORING:
        if magnitude >= IMPACT_THRESHOLD:
            state = POSSIBLE_IMPACT
            impact_time = time.ticks_ms()
            low_movement_count = 0
            show_status("Possible Impact!", "Checking...")
            print("\nPossible Impact! A =", round(magnitude, 2), "g")
    elif state == POSSIBLE_IMPACT:
        state = CHECKING
        show_status("Checking...", "Movement")
        print("Checking movement...")
    # --- Condition 2 + 3: Low Movement within Time Window ---
    elif state == CHECKING:
        elapsed = time.ticks_diff(time.ticks_ms(), impact_time)
        if magnitude <= LOW_MOVEMENT_THRESHOLD:
            low_movement_count += 1
        else:
            low_movement_count = 0
        if low_movement_count >= LOW_MOVEMENT_SAMPLES:
            # Fall confirmed: impact + stillness within window (Section 4)
            print("Low movement detected. A =", round(magnitude, 2), "g")
            fall_alarm()
            continue
        if elapsed >= TIME_WINDOW:
            # Time window expired without stillness -> false alarm (Section 5)
            print("False alarm - normal movement. A =", round(magnitude, 2), "g")
            monitoring_state()
    # --- Periodic serial monitor log ---
    now = time.ticks_ms()
    if time.ticks_diff(now, last_display) >= 500:
        print("State:", state, "| A:", round(magnitude, 2), "g")
        last_display = now
    time.sleep_ms(50)