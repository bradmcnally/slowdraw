#include <M5Unified.h>
#include <Preferences.h>
#include "slow_draw/Renderer.h"

#include <cstdio>
#include <cstring>
#include <driver/uart.h>
#include <esp_sleep.h>

namespace {

M5Canvas printCanvas(&M5.Display);
Preferences preferences;
constexpr gpio_num_t kRockerPressPin = GPIO_NUM_38;
uint32_t variant = 0;
m5::rtc_date_t displayedDate;
char serialLine[24] = {};
size_t serialLineLength = 0;

uint32_t dateKey(const m5::rtc_date_t& date) {
  return static_cast<uint32_t>(date.year) * 10000u +
         static_cast<uint32_t>(date.month) * 100u + date.date;
}

void saveVariant(const m5::rtc_date_t& date) {
  preferences.putUInt("date", dateKey(date));
  preferences.putUInt("variant", variant);
}

bool validDate(const m5::rtc_date_t& date) {
  return date.year >= 2024 && date.year <= 2099 && date.month >= 1 && date.month <= 12 && date.date >= 1 && date.date <= 31;
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

uint32_t secondsUntilTomorrow(const m5::rtc_time_t& time) {
  const uint32_t elapsed = static_cast<uint32_t>(time.hours) * 3600u +
                           static_cast<uint32_t>(time.minutes) * 60u + time.seconds;
  return 86400u - elapsed + 5u;
}

bool sameDate(const m5::rtc_date_t& a, const m5::rtc_date_t& b) {
  return a.year == b.year && a.month == b.month && a.date == b.date;
}

void showPrint(const m5::rtc_date_t& date) {
  const auto info = slow_draw::makePrintInfo(date.year, date.month, date.date, variant);
  slow_draw::renderPrint(printCanvas, info);
  printCanvas.pushSprite(0, 0);
  Serial.printf("%s / %s\n", info.identity, slow_draw::systemName(info.system));
}

void sendFramebuffer() {
  constexpr size_t packedBytes =
      slow_draw::kCanvasWidth * slow_draw::kCanvasHeight / 2;
  // Discard repeated requests that may have accumulated while the display rendered.
  while (Serial.available()) Serial.read();
  Serial.printf("SDFRAME %d %d 4 %u\n", slow_draw::kCanvasWidth,
                slow_draw::kCanvasHeight, unsigned(packedBytes));

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
      if (std::strcmp(serialLine, "CAPTURE") == 0) sendFramebuffer();
      serialLineLength = 0;
    } else if (serialLineLength + 1 < sizeof(serialLine)) {
      serialLine[serialLineLength++] = ch;
    } else {
      serialLineLength = 0;
    }
  }
}

void sleepUntilPressOrTomorrow() {
  while (digitalRead(kRockerPressPin) == LOW) delay(10);
  const auto time = M5.Rtc.getTime();
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
  esp_sleep_enable_ext0_wakeup(kRockerPressPin, LOW);
  esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(secondsUntilTomorrow(time)) * 1000000ULL);
  uart_set_wakeup_threshold(UART_NUM_0, 3);
  esp_sleep_enable_uart_wakeup(UART_NUM_0);
  esp_light_sleep_start();
}

}  // namespace

void setup() {
  Serial.begin(115200);
  auto config = M5.config();
  config.clear_display = false;
  M5.begin(config);
  preferences.begin("slowdraw", false);
  M5.Display.setRotation(1);
  M5.Display.setEpdMode(epd_mode_t::epd_quality);
  pinMode(kRockerPressPin, INPUT);

  auto date = M5.Rtc.getDate();
  auto time = M5.Rtc.getTime();
  if (!validDate(date)) setRtcFromBuildTime(date, time);

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

  displayedDate = date;
  if (preferences.getUInt("date", 0) == dateKey(displayedDate)) {
    variant = preferences.getUInt("variant", 0);
  } else {
    variant = 0;
    saveVariant(displayedDate);
  }
  showPrint(displayedDate);
  delay(250);
}

void loop() {
  processSerial();
  sleepUntilPressOrTomorrow();
  delay(50);
  processSerial();

  const auto today = M5.Rtc.getDate();
  if (!sameDate(today, displayedDate)) {
    displayedDate = today;
    variant = 0;
    saveVariant(displayedDate);
    showPrint(displayedDate);
  } else if (digitalRead(kRockerPressPin) == LOW) {
    ++variant;
    saveVariant(displayedDate);
    showPrint(displayedDate);
  }
}
