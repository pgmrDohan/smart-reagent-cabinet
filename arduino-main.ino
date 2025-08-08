#include "HX711.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Thread.h>
#include <SoftwareSerial.h>
#include <ArduinoJson.h>
SoftwareSerial rasp(6, 7);
LiquidCrystal_I2C lcd(0x27, 16, 2);

#define DT 3   // HX711 데이터 핀 (DOUT)
#define SCK 2  // HX711 클럭 핀 (CLK)

HX711 scale;  // HX711 객체 선언

float calibration_factor = -433.28; // 보정값, 테스트하면서 조정
Thread myThread = Thread();

static int stage = 0;
int buttonstate = HIGH;
int lastbuttonstate = HIGH;

StaticJsonDocument<256> doc;
StaticJsonDocument<256> resp;
String out;

String chemicals = "";
float mass = 0;

void weight() {
    float weight = scale.get_units(10);  // 10번 평균값 측정
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(-weight);
    mass = -weight;
    lcd.print("g");
}

void setup() {
    Serial.begin(9600);
    rasp.begin(9600);
    
    lcd.begin(); // lcd 설정
    lcd.clear();
    lcd.backlight();
    lcd.setCursor(0,0);
    
    scale.begin(DT, SCK); // 🔹 여기에서 핀 설정
    
    pinMode(4, INPUT_PULLUP);  // 버튼 pin 설정
    pinMode(8, OUTPUT); // 부저 pin 설정
    
    scale.tare();
    scale.set_scale(calibration_factor);
    
    myThread.onRun(weight);
	myThread.setInterval(100);
}

void loop() {
    buttonstate = digitalRead(4);
    if(lastbuttonstate == LOW && buttonstate == HIGH) {
        switch(stage) {
            case 0:
                resp.clear();
                resp["msg"] = "CHEMICALS_SCAN_START";
                resp["stage"]=stage+1;
                serializeJson(resp,out);
                rasp.println(out);
                break;
            case 1:
                resp.clear();
                resp["msg"] = "CHEMICALS_SCAN_END";
                resp["chemicals"] = chemicals;
                resp["stage"]=stage+1;
                serializeJson(resp,out);
                rasp.println(out);
                break;
            case 2:
                resp.clear();
                resp["msg"] = "WEIGHING_END";
                resp["weight"] = mass;
                resp["stage"]=stage+1;
                serializeJson(resp,out);
                rasp.println(out);
                break;
            default:
                stage = 0;
                break;
        } 
    }
    lastbuttonstate = buttonstate;

    if(rasp.available()){
        String line = rasp.readStringUntil('\n');
        line.trim();
        if(line.length() == 0) return;

        deserializeJson(doc,line);
        if(doc["status"]==200) {
            Serial.println(doc["msg"].as<const char*>());
            if(strcmp( doc["msg"].as<const char*>(), "TASK_SUCCESS" ) == 0) {
                stage=doc["stage"].as<int>();
                lcd.clear();
            } else if(strcmp( doc["msg"].as<const char*>(), "CHEMICALS_SCAN_SUCCESS" ) == 0) {
                lcd.clear();
                chemicals=doc["chemicals"].as<String>();
            }
        }
    }

    switch(stage){
        case 0:
            lcd.setCursor(0,0);
            lcd.print("DoYouManyCereal");
            break;
        case 1:
            lcd.setCursor(0,0);
            if(chemicals!=""){
                lcd.print(chemicals);   // lcd에 이름 출력
            }
            else{
                lcd.print("Scanning...");
            }
            break;
        case 2:
            Serial.print("무게 측정");
            if(myThread.shouldRun())
		        myThread.run();
            break;
        case 3:
            lcd.setCursor(0,0);
            lcd.print("Complete!");
            break;
        default:
            break;
    }
}
