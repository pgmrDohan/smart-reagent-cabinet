import cv2
import pytesseract
import requests
import urllib.parse
import time
import serial
import json
import threading
import csv
from datetime import datetime, timedelta
import os

cap = cv2.VideoCapture(0)
if not cap.isOpened():
	raise RuntimeError("Can not open Camera. (/dev/video0)")

ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)
time.sleep(2)

data_ok = {
    "status":200,
    "stage": 0,
    "msg":"TASK_SUCCESS"
}

data_chemicals_scan_result = {
    "status":200,
    "msg":"CHEMICALS_SCAN_SUCCESS",
    "chemicals":""
}

stage = 0
csv_file = 'data.csv'

class IntervalRunner:
    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.stop_event = threading.Event()
        self.thread = None

    def _run(self):
        while not self.stop_event.is_set():
            start = time.time()
            self.function()
            elapsed = time.time() - start
            time_to_sleep = self.interval - elapsed
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        self.stop_event.set()

    def join(self):
        if self.thread is not None:
            self.thread.join()

def SCAN_CHEMICALS():
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Can not read frame. Please check the connection of camera.")
    lines = [l.strip() for l in pytesseract.image_to_string(frame).splitlines() if l.strip()]
    for line in lines:
        encoded = urllib.parse.quote(line)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/cids/JSON"
        resp = requests.get(url,timeout=5)
        if resp.status_code == 200 and 'Fault' not in resp.json():
            data_chemicals_scan_result["chemicals"] = line.title()
            json_chemicals_scan_result = json.dumps(data_chemicals_scan_result)+"\n"
            ser.write(json_chemicals_scan_result.encode('utf-8'))
SCAN_CHEMICALS_THREAD = IntervalRunner(1.0,SCAN_CHEMICALS)
SCAN_CHEMICALS_RUN = False

try:
    while True:
        line=ser.readline().decode('utf-8').strip()
        if line:
            print(line)
            data_in = json.loads(line)
            if data_in["msg"] == "CHEMICALS_SCAN_START":
                stage=data_in["stage"]
                data_ok["stage"]=stage
                json_ok=json.dumps(data_ok)+"\n"
                ser.write(json_ok.encode('utf-8'))
            if data_in["msg"] == "CHEMICALS_SCAN_END":
                stage=data_in["stage"]
                SCAN_CHEMICALS_THREAD.stop()
                SCAN_CHEMICALS_THREAD.join()
                SCAN_CHEMICALS_RUN = False
                chemicals = data_in["chemicals"].title()
                data_ok["stage"]=stage
                json_ok=json.dumps(data_ok)+"\n"
                ser.write(json_ok.encode('utf-8'))
            if data_in["msg"] == "WEIGHING_END":
                stage=data_in["stage"]
                weight = float(data_in["weight"])
                data_ok["stage"]=stage
                json_ok=json.dumps(data_ok)+"\n"
                ser.write(json_ok.encode('utf-8'))
        if stage==1:
            if not SCAN_CHEMICALS_RUN:
                SCAN_CHEMICALS_THREAD.start()
                SCAN_CHEMICALS_RUN = True
        elif stage == 3:
            korea_time = datetime.utcnow() + timedelta(hours=9)
            formatted_time = korea_time.strftime('%Y-%m-%d %H:%M:%S')
            previous_weight = None
            if os.path.exists(csv_file):
                with open(csv_file, 'r', newline='') as f:
                    reader = csv.reader(f)
                    for row in reversed(list(reader)):
                        if len(row) >= 3 and row[0].lower() == chemicals.lower():
                            try:
                                previous_weight = float(row[2])
                            except ValueError:
                                previous_weight = None
                            break
            weight_diff = "-"
            if previous_weight is not None:
                weight_diff = round(previous_weight-weight, 3)
            with open(csv_file, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([chemicals, formatted_time, weight, weight_diff])
            stage=0
            data_ok["stage"]=stage
            json_ok=json.dumps(data_ok)+"\n"
            ser.write(json_ok.encode('utf-8'))
        else:
            continue

except KeyboardInterrupt:
    print('\nStopping...')

finally:
    cap.release()
    ser.close()
