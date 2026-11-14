#pragma once

/**
 ******************************************************************************
 * @file           : DASH_Commands.h
 * @brief          : Console commands for DASH
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include <stddef.h>

#ifdef __cplusplus
extern "C"
{
#endif

  /* Not fed yet: the console transport (USB CDC) is a follow-up. */
  void DASH_Console_ProcessLine(const char *line, size_t len);

#ifdef __cplusplus
}
#endif
