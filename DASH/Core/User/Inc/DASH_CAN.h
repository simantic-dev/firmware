#pragma once

/**
 ******************************************************************************
 * @file           : DASH_CAN.h
 * @brief          : DASH CAN bring-up
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 *
 * Received values are read from feb::can::rx<M> at the point of use.
 */

// Before the scheduler starts (from DASH_Init).
void DASH_CAN_Init();
