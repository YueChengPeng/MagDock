from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread, Lock
import asyncio
from bleak import BleakClient, BleakError, BleakScanner
import time
import logging
import RPi.GPIO as GPIO

coil_A_1_pin = 17
coil_A_2_pin = 27
coil_B_1_pin = 23
coil_B_2_pin = 22
LED_pin = 2
button_pin = 3
button_pressed = False  # Track the state of the button

# drive the motor directly from 4 GPIO pins
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
# initialize the motor
stepper_motor = Motor(9, 25, 11, 8)
stepper_motor.home_motor()

def map_value(x, A=1, B=7, C=0, D=135):
    """
    Maps a value x from range A-B to range C-D.

    Parameters:
    - x: The input value to map.
    - A: The minimum value of the input range.
    - B: The maximum value of the input range.
    - C: The minimum value of the output range.
    - D: The maximum value of the output range.

    Returns:
    - The value of x mapped from range A-B to range C-D.
    """
    # Ensure x is within the range A to B
    if x < A or x > B:
        raise ValueError(f"x ({x}) is out of the input range [{A}, {B}]")

    # Perform the mapping
    y = (x - A) * (D - C) / (B - A) + C
    return y

GPIO.setmode(GPIO.BCM)  # Use Broadcom pin-numbering scheme
GPIO.setup(LED_pin, GPIO.OUT)
GPIO.setup(button_pin, GPIO.IN)
def button_callback(channel):
    global button_pressed
    if not button_pressed:
        button_pressed = True
        print("Button pressed")
        GPIO.output(LED_pin, GPIO.HIGH)  # Turn on LED
        socketio.emit('screenshot', {'message': 'capture'})  # Emit message to frontend

# Add event detection for button press
GPIO.add_event_detect(button_pin, GPIO.FALLING, callback=button_callback, bouncetime=300)
# when button released, turn off LED
def monitor_button():
    while True:
        if GPIO.input(button_pin):  # Button released
            global button_pressed
            button_pressed = False
            GPIO.output(LED_pin, GPIO.LOW)  # Turn off LED
        # Sleep for a short time to prevent high CPU usage
        time.sleep(1)

# Start the monitoring in a separate thread
button_thread = Thread(target=monitor_button)
button_thread.start()
client = None
current_task = None  #ble_read task
data_lock = Lock()
connect_lock = asyncio.Lock()

app = Flask(__name__) # create an instance of the Flask class
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)
app.logger.setLevel(logging.ERROR)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

address = "48:27:E2:E7:58:61"  # Device address
char_uuid = "bff7f0c9-5fbf-4b63-8d83-b8e077176fbe"  # Characteristic UUID to read from

ble_data = {
    "stroke": 1, # stroke width, 1-7
    "color": 1, # brsuh color
    "joystick": "", # unit vector angle direction; if not moving, empty string
    "clear": False,
    "draw": False,
}


# clear button toggle
clearTogglePushed = False
clearTogglePushedTime = 0

async def handle_reconnect(client):
    global current_task
    # if current_task and not current_task.done():
    #     current_task.cancel()
    if current_task:
        current_task.cancel()
    await asyncio.sleep(2)  # Short delay before attempting to reconnect
    print("Attempting to reconnect...")
    current_task = asyncio.create_task(ble_read())

# Define the disconnected callback
def disconnected_callback(client):
    # global current_task

    print("Disconnected, attempting to reconnect...")
    # Schedule the handle_reconnect coroutine to be run on the event loop
    # if not(current_task and not current_task.done()):
    asyncio.create_task(handle_reconnect(client))

    # This ensures disconnected_callback does not directly call ble_read(),
    # but schedules a reconnect attempt, allowing for cleanup.
    # asyncio.get_event_loop().call_later(5, asyncio.create_task, ble_read())

def update_ble_data(data):
    print(f'Updating ble data: {data}')
    socketio.emit('bledata', data)

# a callback function that gets called every time the specified characteristic (identified by char_uuid) is updated
async def notification_handler(sender, data):
    global ble_data
    global clearTogglePushed
    global clearTogglePushedTime

    with data_lock:
        decoded_value = data.decode('utf-8').strip()

        if decoded_value == 'none':
            ble_data['joystick'] = ""
            ble_data['clear'] = False
        else:
            # print(decoded_value)
            comp = decoded_value.split(' ')[0]
            if(comp == 'S'): #if is the slider, adjust stroke width
                ble_data['stroke'] = int(decoded_value.split(' ')[1])
                stepper_motor.setPosition(map_value(ble_data['stroke']))
                print(f'Slider value: {ble_data["stroke"]}, mapped value: {map_value(ble_data["stroke"])}')
            elif(comp == 'R'): #if is the rotator, adjust color
                ble_data['color'] = int(decoded_value.split(' ')[1])
            elif(comp == 'J'): #if is the joystick, adjust mouse direction
                ble_data['joystick'] = decoded_value.split(' ')[1]
                ble_data['draw'] = False
            elif(comp == 'JD'): #if is the joystick down, start drawing
                ble_data['joystick'] = decoded_value.split(' ')[1]
                ble_data['draw'] = True
            elif(comp == 'T'): #if is the clear button, and last for 3 seconds, clear the canvas
                if decoded_value.split(' ')[1] == '1': #not pressed
                    clearTogglePushed = False
                    clearTogglePushedTime = 0
                    ble_data['clear'] = False
                else: #if pressed the toggle switch
                    if clearTogglePushed == False:
                        clearTogglePushed = True
                        clearTogglePushedTime = time.time()
                    else:
                        if time.time() - clearTogglePushedTime > 2: # if pressed for 2 seconds
                            ble_data['clear'] = True

        update_ble_data(ble_data)

async def ble_read():
    global client, current_task
    # client = None  # Initialize client here to ensure it's in the function's scope

    while True:
        try:
            async with connect_lock:
                if (client is None) or (not client.is_connected):
                    client = BleakClient(address, disconnected_callback=disconnected_callback)
                    await client.connect()
                    print(f"Connected to {address}")
                    await client.start_notify(char_uuid, notification_handler)

            while client.is_connected:
                await asyncio.sleep(1)

        except (BleakError, Exception) as e:
            print(f"BLE connection error in ble_read(): {e}")
            # if client.is_connected:
            #     await client.disconnect()
            # client = None  # Reset client to None after disconnecting
        #     print(f"BLE connection error: {e}")
        #     await asyncio.sleep(5)  # Wait before retrying
        #     await ble_read()  # Retry connection

        finally:
            if client and client.is_connected:
                await client.disconnect()
            client = None
            await asyncio.sleep(4)  # Retry delay



def start_ble_read():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    current_task = loop.run_until_complete(ble_read())



@app.route('/') # use the route() decorator to tell Flask what URL should trigger our function
def index():
    return render_template('index.html')

# @app.route('/get_raw')
# def getRawData():
#     with data_lock:
#         print(f'{ble_data}')
#         return jsonify(ble_data)
    # cannot!!! variable sync problem

@socketio.on('connect')
def test_connect():
    socketio.emit('welcome', {'message': 'Welcome!'})
    print('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')




if __name__ == '__main__':
    thread = Thread(target=start_ble_read)
    thread.start()
    socketio.run(app, debug=True) # run the application

