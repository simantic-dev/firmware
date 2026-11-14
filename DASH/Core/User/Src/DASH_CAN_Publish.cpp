/**
 ******************************************************************************
 * @file           : DASH_CAN_Publish.cpp
 * @brief          : Everything DASH transmits
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "feb_can.hpp"

namespace fc = feb::can;
namespace fm = feb::can::msg;

namespace
{
bool fill_dash_heartbeat(feb_can_dash_heartbeat_t &m)
{
  (void)m;
  return true;
}

fc::Publisher<fm::DashHeartbeat> heartbeat_tx{fill_dash_heartbeat};

} // namespace
