/**
 ******************************************************************************
 * @file           : DASH_Main.cpp
 * @brief          : DASH board bring-up
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "DASH_Main.h"
#include "DASH_CAN.h"
#include "feb_time.h"
#include "main.h"
#include "tim.h"

void DASH_Init(void)
{
  FEB_Time_Init();

  if (HAL_TIM_PWM_Start(&htim15, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  HAL_GPIO_WritePin(LCD_DISP_RESET_GPIO_Port, LCD_DISP_RESET_Pin, GPIO_PIN_SET);

  DASH_CAN_Init();
}
