#include <M5Unified.h>
#include <Preferences.h>
#include "slow_draw/Renderer.h"

#include <cstdio>
#include <cstring>
#include <driver/uart.h>
#include <esp_sleep.h>
#include <esp_system.h>

namespace {

M5Canvas printCanvas(&M5.Display);
Preferences preferences;
constexpr gpio_num_t kRockerPressPin = GPIO_NUM_38;
constexpr gpio_num_t kTouchWakePin = GPIO_NUM_36;
constexpr uint8_t kDeskStartHour = 7;
constexpr uint8_t kDeskEndHour = 19;
uint32_t variant = 0;
uint8_t recipeMode = 0;
uint8_t cadenceMode = 0;  // 0 = daily, 1 = hourly
m5::rtc_date_t displayedDate;
uint8_t displayedHour = 0;
char serialLine[40] = {};
size_t serialLineLength = 0;
char renderedReplayCode[11] = {};
bool bootRtcAlarm = false;
esp_reset_reason_t bootResetReason = ESP_RST_UNKNOWN;

uint32_t dateKey(const m5::rtc_date_t& date) {
  return static_cast<uint32_t>(date.year) * 10000u +
         static_cast<uint32_t>(date.month) * 100u + date.date;
}

uint32_t periodKey(const m5::rtc_date_t& date, uint8_t hour) {
  return dateKey(date) * 100u + (cadenceMode ? hour : 24u);
}

void saveVariant(const m5::rtc_date_t& date, uint8_t hour) {
  preferences.putUInt("period", periodKey(date, hour));
  preferences.putUInt("variant", variant);
}

void saveRecipeMode() { preferences.putUChar("recipe", recipeMode); }
void saveCadenceMode() { preferences.putUChar("cadence", cadenceMode); }

slow_draw::System selectedSystem() {
  static const slow_draw::System systems[] = {
      slow_draw::System::CellularAggregate, slow_draw::System::CellularAggregate,
      slow_draw::System::PixelField, slow_draw::System::Subdivision,
      slow_draw::System::DitherPressure, slow_draw::System::Murmuration};
  return systems[recipeMode];
}

bool validDate(const m5::rtc_date_t& date) {
  if (date.year < 2024 || date.year > 2099 || date.month < 1 || date.month > 12) return false;
  static const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  uint8_t maximum = days[date.month - 1];
  const bool leap = (date.year % 4 == 0 && date.year % 100 != 0) || date.year % 400 == 0;
  if (date.month == 2 && leap) maximum = 29;
  return date.date >= 1 && date.date <= maximum;
}

bool validTime(const m5::rtc_time_t& time) {
  return time.hours < 24 && time.minutes < 60 && time.seconds < 60;
}

m5::rtc_date_t previousDate(m5::rtc_date_t date) {
  static const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (date.date > 1) { --date.date; return date; }
  if (date.month > 1) --date.month; else { date.month=12;--date.year; }
  uint8_t maximum=days[date.month-1];
  const bool leap=(date.year%4==0&&date.year%100!=0)||date.year%400==0;
  if(date.month==2&&leap)maximum=29;
  date.date=maximum;date.weekDay=(date.weekDay+6)%7;return date;
}

void currentPrintPeriod(const m5::rtc_date_t& today,const m5::rtc_time_t& now,
                        m5::rtc_date_t& date,uint8_t& hour) {
  date=today;hour=now.hours;
  if(!cadenceMode)return;
  if(now.hours<kDeskStartHour){date=previousDate(today);hour=kDeskEndHour;}
  else if(now.hours>kDeskEndHour)hour=kDeskEndHour;
}

int weekDay(int year, int month, int day) {
  static const int offsets[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  if (month < 3) --year;
  return (year + year / 4 - year / 100 + year / 400 + offsets[month - 1] + day) % 7;
}

bool setRtcFromBuildTime(m5::rtc_date_t& date, m5::rtc_time_t& time) {
  static const char* months = "JanFebMarAprMayJunJulAugSepOctNovDec";
  char monthName[4] = {};
  int day = 0, year = 0, hours = 0, minutes = 0, seconds = 0;
  if (std::sscanf(__DATE__, "%3s %d %d", monthName, &day, &year) != 3 ||
      std::sscanf(__TIME__, "%d:%d:%d", &hours, &minutes, &seconds) != 3) return false;

  const char* found = std::strstr(months, monthName);
  if (!found) return false;
  const int month = static_cast<int>((found - months) / 3) + 1;
  date = m5::rtc_date_t(year, month, day, weekDay(year, month, day));
  time = m5::rtc_time_t(hours, minutes, seconds);
  M5.Rtc.setDateTime(&date, &time);
  delay(20);
  return true;
}

uint32_t secondsUntilNextPrint(const m5::rtc_time_t& time) {
  const uint32_t elapsed = static_cast<uint32_t>(time.hours) * 3600u +
                           static_cast<uint32_t>(time.minutes) * 60u + time.seconds;
  if (cadenceMode) {
    if(time.hours<kDeskStartHour)return kDeskStartHour*3600u-elapsed+5u;
    if(time.hours<kDeskEndHour)return 3600u-(elapsed%3600u)+5u;
    return 86400u-elapsed+kDeskStartHour*3600u+5u;
  }
  return 86400u - elapsed + 5u;
}

bool sameDate(const m5::rtc_date_t& a, const m5::rtc_date_t& b) {
  return a.year == b.year && a.month == b.month && a.date == b.date;
}

m5::rtc_time_t timeAfterMinutes(const m5::rtc_time_t& time,uint16_t minutes) {
  const uint16_t total=(static_cast<uint16_t>(time.hours)*60u+time.minutes+minutes)%1440u;
  return m5::rtc_time_t(total/60u,total%60u,0);
}

void waitForDisplaySettle() {
  M5.Display.waitDisplay();
}

void pushCanvas() {
  waitForDisplaySettle();
  M5.Display.setEpdMode(epd_mode_t::epd_quality);
  printCanvas.pushSprite(0, 0);
  waitForDisplaySettle();
}

void showPrint(const m5::rtc_date_t& date) {
  auto info = slow_draw::makePrintInfo(date.year, date.month, date.date, variant,
                                       recipeMode, cadenceMode ? displayedHour : -1);
  if (recipeMode != 0) info.system = selectedSystem();
  std::snprintf(renderedReplayCode,sizeof(renderedReplayCode),"%02X%08X",
                unsigned(info.generatorVersion),unsigned(info.seed));
  slow_draw::renderPrint(printCanvas, info);
  pushCanvas();
  Serial.printf("%s / %s\n", info.identity, slow_draw::systemName(info.system));
}

void drawSettings() {
  printCanvas.fillScreen(15);
  auto button=[](int x,int y,int w,int h,const char* label,bool selected){
    printCanvas.fillRoundRect(x,y,w,h,10,selected?2:15);
    printCanvas.drawRoundRect(x,y,w,h,10,selected?2:7);
    printCanvas.setTextColor(selected?15:0,selected?2:15);
    printCanvas.setTextSize(2);printCanvas.setTextDatum(middle_center);
    printCanvas.drawString(label,x+w/2,y+h/2);
  };
  printCanvas.setTextColor(0,15);printCanvas.setTextDatum(middle_left);printCanvas.setTextSize(3);
  printCanvas.drawString("OPTIONS",50,45);
  const auto info=slow_draw::makePrintInfo(displayedDate.year,displayedDate.month,
      displayedDate.date,variant,recipeMode,cadenceMode?displayedHour:-1);
  char replayLabel[16];std::snprintf(replayLabel,sizeof(replayLabel),"%02X%08X",
      unsigned(info.generatorVersion),unsigned(info.seed));
  const int batteryLevel=M5.Power.getBatteryLevel();
  char batteryLabel[20];
  if(batteryLevel>=0&&batteryLevel<=100)
    std::snprintf(batteryLabel,sizeof(batteryLabel),"BATTERY %d%%",batteryLevel);
  else
    std::snprintf(batteryLabel,sizeof(batteryLabel),"BATTERY --%%");
  printCanvas.setTextColor(5,15);printCanvas.setTextSize(2);printCanvas.setTextDatum(middle_center);
  printCanvas.drawString(batteryLabel,slow_draw::kCanvasWidth/2,45);
  printCanvas.setTextDatum(middle_right);
  printCanvas.drawString(replayLabel,910,45);
  const auto today=M5.Rtc.getDate();const auto now=M5.Rtc.getTime();
  char clockLabel[64];
  if(!cadenceMode)std::snprintf(clockLabel,sizeof(clockLabel),"%04d.%02d.%02d  %02d:%02d  /  NEXT 00:00",today.year,today.month,today.date,now.hours,now.minutes);
  else if(now.hours>=kDeskEndHour)std::snprintf(clockLabel,sizeof(clockLabel),"%04d.%02d.%02d  %02d:%02d  /  NEXT 07:00 TOMORROW",today.year,today.month,today.date,now.hours,now.minutes);
  else std::snprintf(clockLabel,sizeof(clockLabel),"%04d.%02d.%02d  %02d:%02d  /  NEXT %02d:00",today.year,today.month,today.date,now.hours,now.minutes,now.hours<kDeskStartHour?kDeskStartHour:now.hours+1);
  printCanvas.setTextColor(0,15);printCanvas.setTextSize(2);printCanvas.setTextDatum(middle_left);printCanvas.drawString("NEW ARTWORK",50,95);
  button(50,120,410,70,"DAILY",cadenceMode==0);button(500,120,410,70,"HOURLY",cadenceMode==1);
  printCanvas.setTextColor(5,15);printCanvas.setTextDatum(middle_center);
  printCanvas.drawString(clockLabel,slow_draw::kCanvasWidth/2,220);
  printCanvas.setTextColor(0,15);printCanvas.setTextDatum(middle_left);printCanvas.drawString("RECIPE",50,250);
  static const char* labels[]={"ALL","CELLULAR","PIXEL FIELD","SUBDIVISION","DITHER","MURMURATION"};
  for(int i=0;i<6;++i){const int col=i%3,row=i/3;button(50+col*300,275+row*70,270,58,labels[i],recipeMode==i);}
  button(50,435,860,70,"DONE",false);
  pushCanvas();
}

void showSettings() {
  drawSettings();const uint32_t started=millis();
  while(M5.Touch.getCount()){M5.update();delay(10);}
  while(millis()-started<60000u){
    M5.update();
    if(M5.Touch.getCount()){
      const auto touch=M5.Touch.getDetail();
      if(touch.wasClicked()){
        const int x=touch.x,y=touch.y;
        if(y>=120&&y<190){cadenceMode=x<480?0:1;saveCadenceMode();variant=0;currentPrintPeriod(M5.Rtc.getDate(),M5.Rtc.getTime(),displayedDate,displayedHour);saveVariant(displayedDate,displayedHour);drawSettings();}
        else if(y>=275&&y<403&&x>=50&&x<920){const int col=(x-50)/300,row=(y-275)/70,index=row*3+col;if(index>=0&&index<6){recipeMode=index;saveRecipeMode();variant=0;saveVariant(displayedDate,displayedHour);drawSettings();}}
        else if(y>=435&&y<505&&x>=50&&x<910)break;
      }
    }
    delay(10);
  }
  showPrint(displayedDate);
}

void showSeed(uint32_t seed, uint32_t generatorVersion) {
  const auto info = slow_draw::makeSeedPrintInfo(seed, generatorVersion);
  std::snprintf(renderedReplayCode,sizeof(renderedReplayCode),"%02X%08X",
                unsigned(generatorVersion),unsigned(seed));
  slow_draw::renderPrint(printCanvas, info);
  pushCanvas();
  Serial.printf("SDREADY SEED %02X%08X\n", unsigned(generatorVersion), unsigned(seed));
  Serial.flush();
  delay(1000);
}

void showWakeTestResult() {
  const auto actual=M5.Rtc.getDateTime();
  const uint8_t targetHour=preferences.getUChar("wakeHour",0);
  const uint8_t targetMinute=preferences.getUChar("wakeMinute",0);
  preferences.putBool("wakeLastOk",bootRtcAlarm);
  preferences.putUInt("wakeActualD",dateKey(actual.date));
  preferences.putUInt("wakeActualT",static_cast<uint32_t>(actual.time.hours)*10000u+
      static_cast<uint32_t>(actual.time.minutes)*100u+actual.time.seconds);
  preferences.putUChar("wakeReset",static_cast<uint8_t>(bootResetReason));
  preferences.putUShort("wakeLastBat",static_cast<uint16_t>(M5.Power.getBatteryVoltage()));
  printCanvas.fillScreen(15);
  printCanvas.setTextColor(0,15);printCanvas.setTextDatum(middle_center);
  printCanvas.setTextSize(3);printCanvas.drawString(bootRtcAlarm?"RTC WAKE PASS":"RTC WAKE FAILED",480,100);
  char line[80];printCanvas.setTextSize(2);
  std::snprintf(line,sizeof(line),"TARGET %02d:%02d  /  ACTUAL %04d.%02d.%02d %02d:%02d:%02d",
      targetHour,targetMinute,actual.date.year,actual.date.month,actual.date.date,
      actual.time.hours,actual.time.minutes,actual.time.seconds);
  printCanvas.drawString(line,480,210);
  std::snprintf(line,sizeof(line),"ALARM FLAG %s  /  RESET %d",bootRtcAlarm?"YES":"NO",int(bootResetReason));
  printCanvas.drawString(line,480,270);
  std::snprintf(line,sizeof(line),"BATTERY %d mV  /  %d%%",
      int(M5.Power.getBatteryVoltage()),int(M5.Power.getBatteryLevel()));
  printCanvas.drawString(line,480,330);
  printCanvas.setTextColor(5,15);
  printCanvas.drawString("Returning to artwork in 10 seconds",480,430);
  pushCanvas();delay(10000);
  M5.Display.waitDisplay();
  preferences.putBool("wakePending",false);
}

void startWakeTest(uint16_t minutes) {
  const auto now=M5.Rtc.getDateTime();
  const auto target=timeAfterMinutes(now.time,minutes);
  preferences.putBool("wakePending",true);
  preferences.putUChar("wakeHour",target.hours);
  preferences.putUChar("wakeMinute",target.minutes);
  preferences.putUInt("wakeStart",dateKey(now.date));
  preferences.putUShort("wakeBat",static_cast<uint16_t>(M5.Power.getBatteryVoltage()));
  Serial.printf("SDACCEPT WAKE_TEST target=%02d:%02d unplug-within=15s\n",
                target.hours,target.minutes);Serial.flush();
  printCanvas.fillScreen(15);
  printCanvas.setTextColor(0,15);printCanvas.setTextDatum(middle_center);
  printCanvas.setTextSize(3);printCanvas.drawString("RTC WAKE TEST",480,110);
  char line[64];printCanvas.setTextSize(2);
  std::snprintf(line,sizeof(line),"TARGET %02d:%02d",target.hours,target.minutes);
  printCanvas.drawString(line,480,220);
  printCanvas.drawString("UNPLUG USB NOW",480,300);
  printCanvas.setTextColor(5,15);
  printCanvas.drawString("Shutdown begins in 15 seconds",480,380);
  pushCanvas();delay(15000);
  M5.Display.waitDisplay();
  M5.Power.timerSleep(target);
}

void sendFramebuffer() {
  constexpr size_t packedBytes =
      slow_draw::kCanvasWidth * slow_draw::kCanvasHeight / 2;
  // Discard repeated requests that may have accumulated while the display rendered.
  while (Serial.available()) Serial.read();
  Serial.printf("SDFRAME %d %d 4 %u %s\n", slow_draw::kCanvasWidth,
                slow_draw::kCanvasHeight, unsigned(packedBytes),renderedReplayCode);

  uint8_t row[slow_draw::kCanvasWidth / 2];
  for (int y = 0; y < slow_draw::kCanvasHeight; ++y) {
    for (int x = 0; x < slow_draw::kCanvasWidth; x += 2) {
      const uint8_t left = printCanvas.readPixelValue(x, y) & 0x0F;
      const uint8_t right = printCanvas.readPixelValue(x + 1, y) & 0x0F;
      row[x / 2] = static_cast<uint8_t>((left << 4) | right);
    }
    Serial.write(row, sizeof(row));
  }
  Serial.print("\nSDEND\n");
  Serial.flush();
}

void processSerial() {
  while (Serial.available()) {
    const char ch = static_cast<char>(Serial.read());
    if (ch == '\r') continue;
    if (ch == '\n') {
      serialLine[serialLineLength] = '\0';
      if (std::strcmp(serialLine, "CAPTURE") == 0) {
        sendFramebuffer();
      } else if (std::strcmp(serialLine,"WAKE_STATUS")==0) {
        if(preferences.isKey("wakeLastOk")){
          const uint32_t actualDate=preferences.getUInt("wakeActualD",0);
          const uint32_t actualTime=preferences.getUInt("wakeActualT",0);
          Serial.printf("SDWAKESTATUS %s target=%02d:%02d actual=%08u-%06u reset=%u battery=%umV\n",
              preferences.getBool("wakeLastOk",false)?"PASS":"FAIL",
              preferences.getUChar("wakeHour",0),preferences.getUChar("wakeMinute",0),
              unsigned(actualDate),unsigned(actualTime),
              unsigned(preferences.getUChar("wakeReset",0)),
              unsigned(preferences.getUShort("wakeLastBat",0)));
        }else Serial.println("SDWAKESTATUS NONE");
        Serial.flush();
      } else if (std::strncmp(serialLine, "VARIANT ", 8) == 0) {
        char* end = nullptr;
        const unsigned long requested = std::strtoul(serialLine + 8, &end, 10);
        if (end != serialLine + 8 && *end == '\0') {
          Serial.printf("SDACCEPT VARIANT %lu\n", requested);
          Serial.flush();
          variant = static_cast<uint32_t>(requested);
          saveVariant(displayedDate, displayedHour);
          showPrint(displayedDate);
          Serial.printf("SDREADY VARIANT %u\n", unsigned(variant));
          Serial.flush();
          // Keep the command window open for the capture request that follows.
          delay(1000);
        }
      } else if (std::strncmp(serialLine, "SEED ", 5) == 0) {
        unsigned version = 0, requested = 0;
        char trailing = 0;
        if (std::sscanf(serialLine + 5, "%2X%8X%c", &version, &requested, &trailing) == 2 &&
            version == slow_draw::kGeneratorVersion) {
          Serial.printf("SDACCEPT SEED %02X%08X\n", version, requested);
          Serial.flush();
          showSeed(static_cast<uint32_t>(requested), version);
        }
      } else if (std::strncmp(serialLine, "CLOCK ", 6) == 0) {
        int year=0,month=0,day=0,hours=0,minutes=0,seconds=0;char trailing=0;
        if(std::sscanf(serialLine+6,"%d.%d.%d %d:%d:%d%c",&year,&month,&day,
                       &hours,&minutes,&seconds,&trailing)==6){
          m5::rtc_date_t requestedDate(year,month,day,weekDay(year,month,day));
          m5::rtc_time_t requestedTime(hours,minutes,seconds);
          if(validDate(requestedDate)&&validTime(requestedTime)){
            while(Serial.available())Serial.read();
            Serial.printf("SDACCEPT CLOCK %04d.%02d.%02d %02d:%02d:%02d\n",
                          year,month,day,hours,minutes,seconds);Serial.flush();
            M5.Rtc.setDateTime(&requestedDate,&requestedTime);delay(20);
            currentPrintPeriod(requestedDate,requestedTime,displayedDate,displayedHour);
            variant=0;saveVariant(displayedDate,displayedHour);showPrint(displayedDate);
            Serial.printf("SDREADY CLOCK %04d.%02d.%02d %02d:%02d:%02d\n",
                          year,month,day,hours,minutes,seconds);Serial.flush();
          }
        }
      } else if (std::strncmp(serialLine,"WAKE_TEST ",10)==0) {
        char* end=nullptr;const unsigned long requested=std::strtoul(serialLine+10,&end,10);
        if(end!=serialLine+10&&*end=='\0'&&requested>=1&&requested<=30)
          startWakeTest(static_cast<uint16_t>(requested));
      }
      serialLineLength = 0;
    } else if (serialLineLength + 1 < sizeof(serialLine)) {
      serialLine[serialLineLength++] = ch;
    } else {
      serialLineLength = 0;
    }
  }
}

esp_sleep_wakeup_cause_t sleepUntilInputOrNextPrint() {
  constexpr uint32_t kInputReleaseTimeoutMs = 1000;
  const uint32_t releaseStarted = millis();
  while (digitalRead(kRockerPressPin) == LOW || digitalRead(kTouchWakePin) == LOW) {
    // Reading the touch controller also clears its latched interrupt.
    M5.update();
    if (millis() - releaseStarted >= kInputReleaseTimeoutMs) break;
    delay(10);
  }
  const auto time = M5.Rtc.getTime();
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
  gpio_wakeup_disable(kRockerPressPin);
  gpio_wakeup_disable(kTouchWakePin);
  const esp_err_t centerWakeResult=
      esp_sleep_enable_ext0_wakeup(kRockerPressPin,LOW);
  esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH,ESP_PD_OPTION_AUTO);
  esp_err_t touchWakeResult=gpio_wakeup_enable(kTouchWakePin,GPIO_INTR_LOW_LEVEL);
  if(touchWakeResult==ESP_OK)touchWakeResult=esp_sleep_enable_gpio_wakeup();
  if(centerWakeResult!=ESP_OK||touchWakeResult!=ESP_OK){
    Serial.printf("SDSLEEP wake config center=%d touch=%d\n",
        int(centerWakeResult),int(touchWakeResult));
  }
  const uint32_t scheduledSeconds=secondsUntilNextPrint(time);
  esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(scheduledSeconds)*1000000ULL);
  uart_set_wakeup_threshold(UART_NUM_0, 3);
  esp_sleep_enable_uart_wakeup(UART_NUM_0);
  M5.Display.waitDisplay();
  M5.Display.sleep();
  esp_light_sleep_start();
  M5.Display.wakeup();
  const auto wakeCause = esp_sleep_get_wakeup_cause();
  const auto wakeDate=M5.Rtc.getDate();const auto wakeTime=M5.Rtc.getTime();
  Serial.printf("SDWAKE cause=%d rtc=%04d.%02d.%02d %02d:%02d:%02d battery=%d%%\n",
      int(wakeCause),wakeDate.year,wakeDate.month,wakeDate.date,
      wakeTime.hours,wakeTime.minutes,wakeTime.seconds,int(M5.Power.getBatteryLevel()));
  return wakeCause;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  auto config = M5.config();
  config.clear_display = true;
  config.disable_rtc_irq = false;
  M5.begin(config);
  bootResetReason=esp_reset_reason();
  bootRtcAlarm=M5.Rtc.getIRQstatus();
  M5.Rtc.disableIRQ();M5.Rtc.clearIRQ();
  preferences.begin("slowdraw", false);
  M5.Display.setRotation(1);
  M5.Display.setEpdMode(epd_mode_t::epd_quality);
  pinMode(kRockerPressPin, INPUT);
  pinMode(kTouchWakePin, INPUT);

  auto date = M5.Rtc.getDate();
  auto time = M5.Rtc.getTime();
  if (!validDate(date) || !validTime(time)) setRtcFromBuildTime(date, time);

  printCanvas.setPsram(true);
  printCanvas.setColorDepth(4);
  for (int level = 0; level < 16; ++level) {
    const uint8_t value = static_cast<uint8_t>(level * 17);
    printCanvas.setPaletteColor(level, (value << 16) | (value << 8) | value);
  }
  if (!printCanvas.createSprite(slow_draw::kCanvasWidth, slow_draw::kCanvasHeight)) {
    M5.Display.fillScreen(TFT_WHITE);
    M5.Display.setTextColor(TFT_BLACK);
    M5.Display.drawString("Canvas allocation failed", 24, 24);
    return;
  }

  if(preferences.getBool("wakePending",false))showWakeTestResult();

  recipeMode = preferences.getUChar("recipe", 0);
  if (recipeMode > 5) recipeMode = 0;
  cadenceMode = preferences.getUChar("cadence", 0);
  if (cadenceMode > 1) cadenceMode = 0;
  currentPrintPeriod(date, time, displayedDate, displayedHour);
  if (preferences.getUInt("period", 0) == periodKey(displayedDate, displayedHour)) {
    variant = preferences.getUInt("variant", 0);
  } else {
    variant = 0;
    saveVariant(displayedDate, displayedHour);
  }
  showPrint(displayedDate);
  delay(250);
}

void loop() {
  processSerial();
  const auto wakeCause = sleepUntilInputOrNextPrint();
  const bool pressWake = digitalRead(kRockerPressPin) == LOW ||
      wakeCause == ESP_SLEEP_WAKEUP_EXT0;
  const bool touchWake = digitalRead(kTouchWakePin) == LOW ||
      wakeCause == ESP_SLEEP_WAKEUP_GPIO;
  delay(50);
  M5.update();
  processSerial();

  const auto today = M5.Rtc.getDate();
  const auto now = M5.Rtc.getTime();
  m5::rtc_date_t targetDate;uint8_t targetHour;
  currentPrintPeriod(today,now,targetDate,targetHour);
  if (!sameDate(targetDate, displayedDate) || (cadenceMode && targetHour != displayedHour)) {
    displayedDate = targetDate;
    displayedHour = targetHour;
    variant = 0;
    saveVariant(displayedDate, displayedHour);
    showPrint(displayedDate);
  } else if (pressWake || digitalRead(kRockerPressPin) == LOW) {
    ++variant;
    saveVariant(displayedDate, displayedHour);
    showPrint(displayedDate);
  } else if (touchWake || M5.Touch.getCount()) {
    showSettings();
  }
}
