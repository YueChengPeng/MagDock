import RPi.GPIO as GPIO
import time

class Motor:
    # Motor specifications
    FULL_ROTATION_STEPS = 945  # Total steps for 315 degrees at 1/3 degree per step
    current_position = 0  # Current position of the motor

    def __init__(self, coil_A_1_pin, coil_A_2_pin, coil_B_1_pin, coil_B_2_pin):
        self.coil_A_1_pin = coil_A_1_pin
        self.coil_A_2_pin = coil_A_2_pin
        self.coil_B_1_pin = coil_B_1_pin
        self.coil_B_2_pin = coil_B_2_pin
        self.setup()

    def setup(self):
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.coil_A_1_pin, GPIO.OUT)
        GPIO.setup(self.coil_A_2_pin, GPIO.OUT)
        GPIO.setup(self.coil_B_1_pin, GPIO.OUT)
        GPIO.setup(self.coil_B_2_pin, GPIO.OUT)

    def set_step(self, w1, w2, w3, w4):
        GPIO.output(self.coil_A_1_pin, w1)
        GPIO.output(self.coil_A_2_pin, w2)
        GPIO.output(self.coil_B_1_pin, w3)
        GPIO.output(self.coil_B_2_pin, w4)

    def move_motor(self, steps):
        sequence = [[1,0,1,0],
                    [0,1,1,0],
                    [0,1,0,1],
                    [1,0,0,1]]
        
        step_direction = 1 if steps > 0 else -1
        steps = abs(steps)

        for _ in range(steps):
            for step_pattern in sequence[::step_direction]:
                self.set_step(*step_pattern)
                time.sleep(0.002)  # Adjust delay to control speed

    def setPosition(self, angle):
        angle = int(angle / 6)
        # Check if the angle is within the motor's limit
        if angle < 0 or angle > 315:
            print("Angle out of range. Please enter a value between 0 and 315.")
            return

        # Calculate the target position in steps
        target_position = int(angle * 3)  # Convert angle to steps
        steps_to_move = target_position - Motor.current_position

        # Move the motor
        self.move_motor(steps_to_move)

        # Update the current position
        Motor.current_position = target_position

    def home_motor(self):
        Motor.current_position = 0
        print("Motor homed. Current position set to 0 degrees.")

# Example usage
try:
    stepper_motor = Motor(9, 25, 11, 8)
    stepper_motor.home_motor()

    while True:
        stepper_motor.setPosition(0)  # Move to 90 degrees
        time.sleep(2)
        stepper_motor.setPosition(315)   # Move back to 0 degrees
        time.sleep(2)

except KeyboardInterrupt:
    GPIO.cleanup()