#pragma once

#include <M5GFX.h>
#include <cstdint>

namespace slow_draw {

constexpr int kCanvasWidth = 960;
constexpr int kCanvasHeight = 540;
constexpr int kFooterHeight = 60;
constexpr uint32_t kGeneratorVersion = 15;

enum class System : uint8_t { CellularAggregate, PixelField, MirroredLattice, Subdivision, DitherPressure, Murmuration };

struct PrintInfo {
  uint32_t seed;
  uint32_t generatorVersion;
  System system;
  int dayOfYear;
  char identity[40];
};

PrintInfo makePrintInfo(int year, int month, int day, uint32_t variant = 0,
                        uint8_t recipeMode = 0, int hourSlot = -1);
PrintInfo makeSeedPrintInfo(uint32_t seed, uint32_t generatorVersion);
const char* systemName(System system);
void renderPrint(M5Canvas& canvas, const PrintInfo& info);

}  // namespace slow_draw
