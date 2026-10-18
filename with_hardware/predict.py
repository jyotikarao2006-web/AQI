import serial, time, re, joblib, pandas as pd

PORT = 'COM8'   # HC-05 Outgoing port from the Bluetooth COM Ports tab

clf = joblib.load('with_hardware/weather_clf.pkl')
le  = joblib.load('with_hardware/label_encoder.pkl')

ser = None
for attempt in range(1, 8):
    try:
        print(f"Connecting to {PORT}, attempt {attempt}...")
        ser = serial.Serial(PORT, 9600, timeout=1, write_timeout=2)
        break
    except Exception:
        time.sleep(5)
if ser is None:
    raise SystemExit("Could not connect to HC-05. Check power, LED and port.")

time.sleep(3)
ser.reset_input_buffer()
print("Ready. Press the button on the Arduino...")

try:
    while True:
        line = ser.readline().decode(errors='ignore').strip()   # READ
        if not line:
            continue

        nums = re.findall(r'-?\d+\.?\d*', line)                 # pull out the numbers
        if len(nums) != 2:
            print("Ignored:", repr(line))
            continue

        t, h = map(float, nums)
        if not (-40 <= t <= 80 and 0 <= h <= 100):              # sanity check
            print("Out of range, ignored:", repr(line))
            continue

        x = pd.DataFrame([[t, h]], columns=['Temperature_C', 'Humidity_pct'])
        code  = int(clf.predict(x)[0])                          # 0..7
        label = le.inverse_transform([code])[0]

        ser.write(f"{code}\n".encode())                          # SEND
        print(f"T={t:.1f}  RH={h:.1f}  ->  code {code} ({label})")

except KeyboardInterrupt:
    ser.close()
    print("Stopped.")