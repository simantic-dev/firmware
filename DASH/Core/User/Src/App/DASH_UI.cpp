/**
 ******************************************************************************
 * @file           : DASH_UI.cpp
 * @brief          : LVGL bring-up updating subjects
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "DASH_UI.h"
#include "feb_can.hpp"
#include "lvgl_port_display.h"
#include "lvgl_port_touch.h"
#include "UI.h"
#include "main.h"

namespace fc = feb::can;
namespace fm = feb::can::msg;

void DASH_UI_Init()
{
  lv_init();
  lv_tick_set_cb(HAL_GetTick);

  lvgl_display_init();
  lvgl_touchscreen_init();

  UI_init("A:");
  lv_screen_load(screen_components_create());
}

uint32_t DASH_UI_Update()
{
  lv_subject_set_int(&subject_wheel_speed, fc::rx<fm::WssRear>.fresh() ? fc::rx<fm::WssRear>.v().wss_left / 100 : 67);
  return lv_timer_handler();
}
