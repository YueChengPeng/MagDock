import RPi.GPIO as GPIO
import time

# GPIO pins for the motor
coil_A_1_pin = 17
coil_A_2_pin = 27
coil_B_1_pin = 23
coil_B_2_pin = 22
LED_pin = 2
button_pin = 3

# Motor specifications
FULL_ROTATION_STEPS = 945  # Total steps for 315 degrees at 1/3 degree per step
current_position = 0  # Current position of the motor

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(coil_A_1_pin, GPIO.OUT)
GPIO.setup(coil_A_2_pin, GPIO.OUT)
GPIO.setup(coil_B_1_pin, GPIO.OUT)
GPIO.setup(coil_B_2_pin, GPIO.OUT)
GPIO.setup(LED_pin, GPIO.OUT)
GPIO.setup(button_pin, GPIO.IN)


# Function to set the motor coils
def set_step(w1, w2, w3, w4):
    GPIO.output(coil_A_1_pin, w1)
    GPIO.output(coil_A_2_pin, w2)
    GPIO.output(coil_B_1_pin, w3)
    GPIO.output(coil_B_2_pin, w4)

def move_motor(steps):
    sequence = [[1,0,1,0],
                [0,1,1,0],
                [0,1,0,1],
                [1,0,0,1]]
    
    step_direction = 1 if steps > 0 else -1
    steps = abs(steps)

    for _ in range(steps):
        for step_pattern in sequence[::step_direction]:
            set_step(*step_pattern)
            time.sleep(0.002)  # Adjust delay to control speed

def setPosition(angle):
    angle = int(angle/6)
    global current_position

    # Check if the angle is within the motor's limit
    if angle < 0 or angle > 315:
        print("Angle out of range. Please enter a value between 0 and 315.")
        return

    # Calculate the target position in steps
    target_position = int(angle * 3)  # Convert angle to steps
    steps_to_move = target_position - current_position

    # Move the motor
    move_motor(steps_to_move)

    # Update the current position
    current_position = target_position

# Main loop
try:
    while True:
        # Example usage of setPosition
        setPosition(90)  # Move to 90 degrees
        print("Position: 90")

        time.sleep(2)
        setPosition(180)   # Move back to 0 degrees
        print("Position: 180")
        #turn off led
        time.sleep(2)
        print(GPIO.input(button_pin))
        if GPIO.input(button_pin):
            GPIO.output(LED_pin, GPIO.LOW)
        else:
            GPIO.output(LED_pin, GPIO.HIGH)

except KeyboardInterrupt:
    GPIO.cleanup()

GPIO.cleanup()