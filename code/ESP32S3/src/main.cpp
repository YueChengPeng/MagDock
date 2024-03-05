#include <Arduino.h>

#include <Tlv493d.h>
#include <cmath> // For sqrt and pow functions
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <array>
#include <Wire.h>

// Predefined vectors
float rotateVectors[10][3] = {
    {-5.340588235294119, -0.9870588235294119, -1.2223529411764704},
    {-6.059047619047618, -2.2523809523809524, -1.1876190476190474},
    {-7.556666666666666, -3.123333333333333, -1.1826666666666665},
    {-9.646315789473684, -3.0915789473684203, -1.1752631578947366},
    {-11.774210526315791, -1.3026315789473684, -1.3921052631578945},
    {-12.215238095238094, 0.782857142857143, -1.382380952380952},
    {-11.097142857142856, 3.028571428571428, -1.437619047619048},
    {-8.288, 3.7155, -1.4175},
    {-6.781052631578947, 3.178421052631579, -1.394210526315790},
    {-5.531052631578947, 1.687894736842105, -1.291052631578948}};

float slideVectors[7][3] = {
    {8.469629629629630, -2.277407407407407, 2.011111111111111},
    {8.465862068965516, -3.506551724137930, 4.272068965517242},
    {8.336250000000001, -2.719583333333334, 7.440833333333334},
    {8.110322580645160, 1.042903225806451, 9.067096774193546},
    {7.972799999999999, 4.898799999999999, 6.993600000000002},
    {8.08269230769231, 5.234999999999999, 3.648846153846155},
    {8.161818181818182, 3.991363636363636, 1.840909090909091}};

float switchVectors[2][3] = {
    {-2.486785714285714, -0.478928571428571, -15.351428571428571},
    {-6.5392, 0.0584, -5.2292}};

float joystickOnOff[] = {
    -5.1, // off state
    -3.2  // on state
};

int identifier[] = {4095, 3650, 990, 2000, 2950};                      // null, rotary, slider, joystick, switch
const int identifierSize = sizeof(identifier) / sizeof(identifier[0]); // Calculate size of the identifier array

const float joystickMaxY = 14.04;
const float joystickMinY = 4.35;
const float joystickA = (joystickMaxY - joystickMinY) / 2;
const float joystickD = (joystickMaxY + joystickMinY) / 2;
float joystickF0 = -0.84;

// button pin
const int buttonPin = D0;

// setup bluetooth
BLEServer *pServer = NULL;
BLECharacteristic *pCharacteristic_IO = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;
#define SERVICE_UUID "453184cc-3737-47be-ab4b-9a6991a92d6d"
#define CHARACTERISTIC_IO_UUID "bff7f0c9-5fbf-4b63-8d83-b8e077176fbe"

class MyServerCallbacks : public BLEServerCallbacks
{
  void onConnect(BLEServer *pServer)
  {
    deviceConnected = true;
  };

  void onDisconnect(BLEServer *pServer)
  {
    deviceConnected = false;
  }
};

// function to calculate the joystick angle
float joystickDecodeAngle(float y, float f)
{
  float cosInput = (y - joystickD) / joystickA;
  float x = acos(cosInput);

  // if f > joystickF0, return [pi, 2pi] angle
  if (f > joystickF0)
  {
    x = 2 * PI - x;
  }

  if (isnan(x))
    x = PI;

  return x; // 返回x值（弧度）
}

int ifJoystickOn(int zVal)
{
  int onOffId = 0;                                  // 0: off; 1: on
  int minDifference = abs(zVal - joystickOnOff[0]); // Initialize with the difference from the first element

  for (int i = 1; i < 2; i++)
  {
    int difference = abs(zVal - joystickOnOff[i]);
    if (difference < minDifference)
    {
      minDifference = difference;
      onOffId = i;
    }
  }

  return onOffId; // Return the index of the closest identifier
}

// Function to find the index of the closest identifier (to identify which input component)
int findClosestIdentifierIndex(int idVal)
{
  int closestIndex = 0;                           // Initialize with the first index
  int minDifference = abs(idVal - identifier[0]); // Initialize with the difference from the first element

  for (int i = 1; i < identifierSize; i++)
  {
    int difference = abs(idVal - identifier[i]);
    if (difference < minDifference)
    {
      minDifference = difference;
      closestIndex = i;
    }
  }

  return closestIndex; // Return the index of the closest identifier
}

// Function to calculate Euclidean distance between two vectors
float euclideanDistance(float vec1[3], float vec2[3])
{
  return sqrt(pow(vec1[0] - vec2[0], 2) + pow(vec1[1] - vec2[1], 2) + pow(vec1[2] - vec2[2], 2));
}

// Function to find the closest vector index for the rotator
int rotaryDecode(float currentVec[3])
{
  int closestIndex = 0;
  float minDistance = euclideanDistance(currentVec, rotateVectors[0]);

  for (int i = 1; i < 10; i++)
  {
    float distance = euclideanDistance(currentVec, rotateVectors[i]);
    if (distance < minDistance)
    {
      minDistance = distance;
      closestIndex = i;
    }
  }

  return closestIndex + 1; // Return index + 1 to match vector numbering
}

// Function to find the closest vector index for the slider
int slideDecode(float currentVec[3])
{
  int closestIndex = 0;
  float minDistance = euclideanDistance(currentVec, slideVectors[0]);

  for (int i = 1; i < 7; i++)
  {
    float distance = euclideanDistance(currentVec, slideVectors[i]);
    if (distance < minDistance)
    {
      minDistance = distance;
      closestIndex = i;
    }
  }

  return closestIndex + 1; // Return index + 1 to match vector numbering
}

// Function to find the closest vector index for the switch
int switchDecode(float currentVec[3])
{
  int closestIndex = 0;
  float minDistance = euclideanDistance(currentVec, switchVectors[0]);

  for (int i = 1; i < 2; i++)
  {
    float distance = euclideanDistance(currentVec, switchVectors[i]);
    if (distance < minDistance)
    {
      minDistance = distance;
      closestIndex = i;
    }
  }

  return closestIndex + 1; // Return index + 1 to match vector numbering
}

// Tlv493d Object
Tlv493d Tlv493dMagnetic3DSensor = Tlv493d();

// Define the size of the moving average window
const int windowSize = 4;
float xWindow[windowSize];
float yWindow[windowSize];
float zWindow[windowSize];
int windowIndex = 0;

// Function to calculate the moving average
float movingAverage(float window[], float newVal)
{
  window[windowIndex % windowSize] = newVal;
  float sum = 0.0;
  for (int i = 0; i < windowSize; i++)
  {
    sum += window[i];
  }
  return sum / windowSize;
}

void setup()
{
  Serial.begin(115200);
  // while (!Serial)
  //   ;
  Tlv493dMagnetic3DSensor.begin();
  pinMode(D3, OUTPUT);
  pinMode(A8, INPUT);

  // Initialize window arrays
  for (int i = 0; i < windowSize; i++)
  {
    xWindow[i] = 0.0;
    yWindow[i] = 0.0;
    zWindow[i] = 0.0;
  }

  pinMode(buttonPin, INPUT);

  // Create the BLE Device
  Serial.println("Starting BLE work!");

  // TODO: add codes for handling your sensor setup (pinMode, etc.)

  BLEDevice::init("MagDocker"); // Give it a name
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // cannot write like BLECharacteristic *pCharacteristic_IO1. Or later pCharacteristic_IO1->setValue(combined.c_str()); will reboot the chip
  pCharacteristic_IO = pService->createCharacteristic(
      CHARACTERISTIC_IO_UUID,
      BLECharacteristic::PROPERTY_READ |
          BLECharacteristic::PROPERTY_WRITE |
          BLECharacteristic::PROPERTY_NOTIFY);

  pCharacteristic_IO->addDescriptor(new BLE2902());
  pCharacteristic_IO->setValue("");
  pService->addCharacteristic(pCharacteristic_IO);

  pService->start();
  // BLEAdvertising *pAdvertising = pServer->getAdvertising();  // this still is working for backward compatibility
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06); // functions that help with iPhone connections issue
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  Serial.println("Characteristic defined! Now you can read it in your phone!");
}

void loop()
{
  Tlv493dMagnetic3DSensor.updateData();
  delay(100);
  int componentId = findClosestIdentifierIndex(analogRead(A8));
  Serial.print("identifier: ");
  Serial.println(componentId);
  // Apply moving average filter
  float smoothX = movingAverage(xWindow, Tlv493dMagnetic3DSensor.getX());
  float smoothY = movingAverage(yWindow, Tlv493dMagnetic3DSensor.getY());
  float smoothZ = movingAverage(zWindow, Tlv493dMagnetic3DSensor.getZ());
  windowIndex++;
  // Print smoothed values
  Serial.print(smoothX);
  Serial.print(" ");
  Serial.print(smoothY);
  Serial.print(" ");
  Serial.println(smoothZ);
  // Serial.print(" ");
  // Serial.print(smoothX / smoothY);
  // Serial.print(" ");
  // Serial.println(smoothY / smoothX);

  float currentVector[3] = {smoothX, smoothY, smoothZ};
  if (deviceConnected)
  {
    // handle different input cases
    switch (componentId)
    {
    case 0: // if the component is empty
    {
      int rotaryPos = rotaryDecode(currentVector);
      Serial.print("empty: ");
      Serial.println(rotaryPos);

      String combined = "none";
      delay(100);
      pCharacteristic_IO->setValue(combined.c_str());
      pCharacteristic_IO->notify();
      break;
    }
    case 1: // if the component is the rotator
    {
      int rotaryPos = rotaryDecode(currentVector);
      Serial.print("rotary: ");
      Serial.println(rotaryPos);

      String combined = "R " + String(rotaryPos);
      pCharacteristic_IO->setValue(combined.c_str());
      pCharacteristic_IO->notify();
      break;
    }
    case 2: // if the component is the slider
    {
      int slidePos = slideDecode(currentVector);
      Serial.print("slide: ");
      Serial.println(slidePos);

      String combined = "S " + String(slidePos);
      pCharacteristic_IO->setValue(combined.c_str());
      pCharacteristic_IO->notify();
      break;
    }
    case 3: // if the component is the joystick
    {
      if (ifJoystickOn(smoothZ)) // if joystick is activated
      {
        float xRadians = joystickDecodeAngle(smoothX, smoothY); // radian angle
        float xDegrees = xRadians * (180 / PI);                 // change to degrees
        Serial.println(xDegrees);

        Serial.print("button: ");
        Serial.println(digitalRead(buttonPin));

        // read button state: push to drop the pen
        if (digitalRead(buttonPin)) // not pressed
        {
          String combined = "J " + String(xDegrees); // joystick
          pCharacteristic_IO->setValue(combined.c_str());
          pCharacteristic_IO->notify();
        }
        else // pressed
        {
          String combined = "JD " + String(xDegrees); // joystick down
          pCharacteristic_IO->setValue(combined.c_str());
          pCharacteristic_IO->notify();
        }
      }
      else
      {
        String combined = "none";
        pCharacteristic_IO->setValue(combined.c_str());
        pCharacteristic_IO->notify();
        delay(100);
      }
      break;
    }
    case 4: // if the component is the toggle switch
    {
      int switchPos = switchDecode(currentVector);
      Serial.print("switch: ");
      Serial.println(switchPos);

      String combined = "T " + String(switchPos);
      pCharacteristic_IO->setValue(combined.c_str());
      pCharacteristic_IO->notify();
      break;
    }
    }
  }
  // disconnecting
  if (!deviceConnected && oldDeviceConnected)
  {
    delay(500);                  // give the bluetooth stack the chance to get things ready
    pServer->startAdvertising(); // advertise again
    Serial.println("Start advertising");
    oldDeviceConnected = deviceConnected;
  }
  // connecting
  if (deviceConnected && !oldDeviceConnected)
  {
    // do stuff here on connecting
    oldDeviceConnected = deviceConnected;
  }

  delay(100);
}