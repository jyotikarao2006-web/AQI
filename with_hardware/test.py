import serial, time

PORT = 'COM8'
ser = None
for attempt in range(1, 8):
    try:
        print(f"Attempt {attempt}...")
        ser = serial.Serial(PORT, 9600, timeout=1, write_timeout=2)
        print("Connected!")
        break
    except Exception as e:
        print("  failed, retrying in 5 s")
        time.sleep(5)

if ser is None:
    raise SystemExit("Could not connect. Check the HC-05 LED and power.")

time.sleep(3)
print("Type a message, press Enter. Ctrl+C to quit.")
try:
    while True:
        msg = input("Send: ")
        try:
            ser.write(msg.encode())
        except serial.SerialTimeoutException:
            print("Write timed out")
            continue
        time.sleep(0.5)
        while ser.in_waiting:
            print("Received:", ser.read(ser.in_waiting).decode(errors='ignore'))
except KeyboardInterrupt:
    ser.close()