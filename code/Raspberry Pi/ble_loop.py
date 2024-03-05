
async def ble_read():
    global ble_data
    address = "48:27:E2:E7:58:61" # Device address
    char_uuid = "bff7f0c9-5fbf-4b63-8d83-b8e077176fbe" # Characteristic UUID to read from

    # async with BleakClient(address) as client:
    #     while True:
    #         try:
    #             value = await client.read_gatt_char(char_uuid)
    #             decoded_value = value.decode('utf-8').strip() # Decode the bytearray to a string
    #             print(decoded_value)
    #             # parts = decoded_value.split() # Split the string into a list of strings separated by space
    #             # data_dict = {"x": parts[0], "y": parts[1], "z": parts[2]} if len(parts) >= 3 else {} # Create a dictionary from the list
    #             # ble_data['joystick'] = data_dict
    #             # print(ble_data)
    #         except Exception as e:
    #             print(f'Error reading from BLE: {e}')
    #         await asyncio.sleep(0.1)

    while True:
        try:
            async with BleakClient(address) as client:
                print(f"Connected to {address}")
                while True:
                    try:
                        with data_lock:
                            value = await client.read_gatt_char(char_uuid)
                            decoded_value = value.decode('utf-8').strip()  # Decode the bytearray to a string
                            if decoded_value != 'none':
                                print(decoded_value)

                            if(decoded_value == 'none'):
                                ble_data['joystick'] = ""
                                ble_data['clear'] = False

                            else:
                                comp = decoded_value.split(' ')[0]
                                if(comp == 'S'): #if is the slider, adjust stroke width
                                    ble_data['stroke'] = int(decoded_value.split(' ')[1])
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

                            print(ble_data)
                            update_ble_data(ble_data)

                            await asyncio.sleep(0.2)
                    except Exception as e:
                        print(f'Error reading from BLE: {e}')
                        break  # Break from the inner loop to reconnect
        except Exception as e:
            print(f"Connection failed: {e}")
            # service_uuid = "453184cc-3737-47be-ab4b-9a6991a92d6d"
            # devices = await BleakScanner.discover()

            # for device in devices:
            #     print(f"Device: {device.name}, Address: {device.address}, UUIDs: {device.metadata['uuids']}")
            #     if service_uuid in device.metadata["uuids"]:
            #         print(f"Found device: {device.name}, Address: {device.address}")
            #         # Here you can connect to the device using its address
            #         break
            # else:
            #     print("No devices found offering the service.")
        print("Attempting to reconnect...")
        await asyncio.sleep(0.5)  # Wait for .2 seconds before attempting to reconnect


        # characteristic = (await client.get_services())[0].characteristics[0]
        # value = await client.read_gatt_char(characteristic.uuid)
        # print(type(client))
    

def start_ble_read():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ble_read())
