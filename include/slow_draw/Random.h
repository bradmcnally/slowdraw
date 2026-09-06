#pragma once

#include <cstdint>

namespace slow_draw {

class Random {
 public:
  explicit Random(uint32_t seed) : state_(seed ? seed : 0x6d2b79f5u) {}

  uint32_t next() {
    uint32_t x = state_;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return state_ = x;
  }

  int range(int low, int high) {
    return low + static_cast<int>(next() % static_cast<uint32_t>(high - low));
  }

  float unit() { return (next() >> 8) * (1.0f / 16777216.0f); }
  bool chance(float probability) { return unit() < probability; }

 private:
  uint32_t state_;
};

inline uint32_t mix32(uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352du;
  value ^= value >> 15;
  value *= 0x846ca68bu;
  return value ^ (value >> 16);
}

inline uint32_t dateSeed(int year, int month, int day, uint32_t version) {
  const uint32_t packed = static_cast<uint32_t>(year) * 10000u +
                          static_cast<uint32_t>(month) * 100u + day;
  return mix32(packed ^ mix32(version));
}

}  // namespace slow_draw
