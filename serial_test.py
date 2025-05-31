import serial
import time

serial = serial.Serial('/dev/ttyACM0', 9600)

last_send = time.time()

while True:
  serial.flushInput()
  serial.flushOutput()
  # output
  if time.time() - last_send > 1:
    last_send = time.time()
    serial.print(b'1')
  # input
  rcom = serial.read()
  print(f"Received: <{rcom}>")
