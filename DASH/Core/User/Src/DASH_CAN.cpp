/**
 ******************************************************************************
 * @file           : DASH_CAN.cpp
 * @brief          : DASH CAN bring-up
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "DASH_CAN.h"
#include "fdcan.h"
#include "feb_can.hpp"
#include "main.h"

void DASH_CAN_Init()
{
  // Fails only on a build/config mistake: more subscribers than filters, or an unsupported .ioc mode.
  if (!feb::can::start(feb::can::Bus::k1, hfdcan1))
  {
    Error_Handler();
  }
}
