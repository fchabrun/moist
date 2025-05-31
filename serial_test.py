import serial
import time

if __name__ == "__main__":

  serial_com = serial.Serial('/dev/ttyACM0', 9600)
  serial_com.reset_input_buffer()
  
  last_send = -1
  awaiting_reply = False
  
  while True:
    # output
    if (not awaiting_reply) and (time.time() - last_send > 1):
      last_send = time.time()
      serial_com.write(b'1')
      awaiting_reply = True
    # input
    if serial_com.in_waiting > 0:
        awaiting_reply = False
        rcom = serial_com.readline().decode('utf-8').rstrip()
        print(f"Received: <{rcom}>")
