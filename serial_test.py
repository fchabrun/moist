import serial
import time

serial_com = serial.Serial('/dev/ttyACM0', 9600)

last_send = time.time()

while True:
  serial_com.flushInput()
  serial_com.flushOutput()
  # output
  if time.time() - last_send > 1:
    serial_com = time.time()
    serial.print(b'1')
  # input
  rcom = serial_com.read()
  print(f"Received: <{rcom}>")
