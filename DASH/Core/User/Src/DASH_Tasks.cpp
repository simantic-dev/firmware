/**
 ******************************************************************************
 * @file           : DASH_Tasks.cpp
 * @brief          : DASH FreeRTOS Tasks
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "DASH_UI.h"
#include "cmsis_os2.h"
#include "feb_can.hpp"
#include "lvgl/lvgl.h"

extern "C"
{
  void StartDisplayTask(void *argument)
  {
    (void)argument;

    DASH_UI_Init();

    for (;;)
    {
      uint32_t idle_ms = DASH_UI_Update();
      if (idle_ms == LV_NO_TIMER_READY || idle_ms > LV_DEF_REFR_PERIOD)
      {
        idle_ms = LV_DEF_REFR_PERIOD;
      }
      osDelay(idle_ms > 0 ? idle_ms : 1);
    }
  }

  void StartCanPubTask(void *argument)
  {
    (void)argument;
    feb::can::run_publishers();
  }
}
