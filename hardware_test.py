from machine import Pin, I2C, PWM
import time


# =========================================================
# PIN CONFIGURATION
# =========================================================

GREEN_LED_PIN = 16
RED_LED_PIN = 17
BUZZER_PIN = 13
BUTTON_PIN = 15

I2C_SDA_PIN = 0
I2C_SCL_PIN = 1

MPU6050_ADDRESS = 0x68
LCD_ADDRESS = 0x27


# =========================================================
# GPIO INIT
# =========================================================

green_led = Pin(GREEN_LED_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

buzzer = PWM(Pin(BUZZER_PIN))
buzzer.duty_u16(0)

i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)

lcd = None


# =========================================================
# LCD DRIVER (same original driver, slightly trimmed)
# =========================================================

class I2cLCD:
    def __init__(self, i2c, address, rows=2, cols=16):
        self.i2c = i2c
        self.address = address
        self.rows = rows
        self.cols = cols
        self.backlight = 0x08
        self._init_lcd()

    def _write(self, data):
        self.i2c.writeto(self.address, bytes([data | self.backlight]))

    def _pulse_enable(self, data):
        self._write(data | 0x04)
        time.sleep_us(1)
        self._write(data & ~0x04)
        time.sleep_us(50)

    def _write_nibble(self, nibble, rs):
        data = nibble & 0xF0
        if rs:
            data |= 0x01
        self._pulse_enable(data)

    def _send(self, value, rs):
        high = value & 0xF0
        low = (value << 4) & 0xF0
        if rs:
            high |= 0x01
            low |= 0x01
        self._pulse_enable(high)
        self._pulse_enable(low)

    def command(self, value):
        self._send(value, False)
        if value in (0x01, 0x02):
            time.sleep_ms(2)

    def write_char(self, value):
        self._send(value, True)

    def clear(self):
        self.command(0x01)
        time.sleep_ms(2)

    def move_to(self, col, row):
        address = (0x80 if row == 0 else 0xC0) + col
        self.command(address)

    def putstr(self, text):
        for char in text:
            self.write_char(ord(char))

    def _init_lcd(self):
        time.sleep_ms(50)
        self._write(0x00)
        self._write_nibble(0x30, False)
        time.sleep_ms(5)
        self._write_nibble(0x30, False)
        time.sleep_us(150)
        self._write_nibble(0x30, False)
        self._write_nibble(0x20, False)
        self.command(0x28)  # 4-bit, 2 lines
        self.command(0x0C)  # display ON
        self.command(0x06)  # entry mode
        self.clear()


# =========================================================
# MPU6050 DRIVER
# =========================================================

class MPU6050:
    PWR_MGMT_1 = 0x6B
    ACCEL_CONFIG = 0x1C
    ACCEL_XOUT_H = 0x3B
    WHO_AM_I = 0x75

    def __init__(self, i2c, address=0x68):
        self.i2c = i2c
        self.address = address
        self.i2c.writeto_mem(self.address, self.PWR_MGMT_1, b'\x00')
        time.sleep_ms(100)
        self.i2c.writeto_mem(self.address, self.ACCEL_CONFIG, b'\x00')

    def who_am_i(self):
        return self.i2c.readfrom_mem(self.address, self.WHO_AM_I, 1)[0]

    def _to_signed(self, high, low):
        value = (high << 8) | low
        if value >= 32768:
            value -= 65536
        return value

    def read_acceleration(self):
        data = self.i2c.readfrom_mem(self.address, self.ACCEL_XOUT_H, 6)
        ax = self._to_signed(data[0], data[1]) / 16384
        ay = self._to_signed(data[2], data[3]) / 16384
        az = self._to_signed(data[4], data[5]) / 16384
        return ax, ay, az


def lcd_message(line1, line2=""):
    if lcd is None:
        return
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr(line1[:16])
    lcd.move_to(0, 1)
    lcd.putstr(line2[:16])


# =========================================================
# 1) Turn on LEDs and buzzer for 5 seconds, then turn off
# =========================================================

green_led.on()
red_led.on()
buzzer.freq(1000)
buzzer.duty_u16(20000)

time.sleep(5)

green_led.off()
red_led.off()
buzzer.duty_u16(0)


# =========================================================
# 2) Initialize I2C devices (LCD + MPU6050) if present
# =========================================================

devices = i2c.scan()

if LCD_ADDRESS in devices:
    try:
        lcd = I2cLCD(i2c, LCD_ADDRESS, 2, 16)
    except Exception:
        lcd = None

mpu = None

if MPU6050_ADDRESS in devices:
    try:
        mpu = MPU6050(i2c, MPU6050_ADDRESS)
    except Exception:
        mpu = None

lcd_message("System Ready", "Monitoring...")


# =========================================================
# 3) Main loop: print only button state and accelerometer
# =========================================================

while True:

    button_state = "PRESSED" if button.value() == 0 else "RELEASED"
    print("Button:", button_state)

    if mpu is not None:
        ax, ay, az = mpu.read_acceleration()
        print("AX:", round(ax, 2), "g | AY:", round(ay, 2), "g | AZ:", round(az, 2), "g")

        lcd_message(
            "Btn: " + button_state,
            "Z: " + str(round(az, 2)) + "g"
        )
    else:
        lcd_message("Btn: " + button_state, "No MPU6050")

    time.sleep_ms(500)