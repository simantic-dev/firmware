#pragma once

/**
 ******************************************************************************
 * @file           : DASH_Main.h
 * @brief          : DASH Application Header
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#ifdef __cplusplus
extern "C"
{
#endif

  /* Board bring-up before the scheduler starts (called from MX_FREERTOS_Init). */
  void DASH_Init(void);

#ifdef __cplusplus
}
#endif
