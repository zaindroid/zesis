import serial
import time

ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.timeout = 3
ser.write_timeout = 3
ser.dsrdtr = False
ser.rtscts = False
ser.open()
print("opened, in_waiting=", ser.in_waiting)

t0 = time.time()
try:
    n = ser.write(b"I")
    print(f"wrote 1 byte, n={n}, dt={time.time()-t0:.2f}s")
except Exception as e:
    print(f"write raised: {e!r}, dt={time.time()-t0:.2f}s")

t0 = time.time()
line = ser.readline()
print(f"readline returned {line!r}, dt={time.time()-t0:.2f}s")

ser.close()
print("done")
