/**
 ******************************************************************************
 * @file           : DASH_Commands.cpp
 * @brief          : Console commands for DASH
 * @author         : Formula Electric @ Berkeley
 ******************************************************************************
 */

#include "DASH_Commands.h"

#include "fdcan.h"
#include "feb_can.hpp"
#include "feb_commands_2.hpp"
#include "feb_console_2.hpp"

namespace fc = feb::can;
namespace fm = feb::can::msg;

using namespace feb::console;

namespace
{

void cmd_dash_wss(Interaction &io, std::span<char *const>)
{
  const auto &rx = fc::rx<fm::WssRear>;
  const auto wss = rx.snapshot();

  KVTable t(io, 14, 12, "Rear Wheel Speed");

  t.row("Left", "%u.%02u mph", (unsigned)(wss.wss_left / 100), (unsigned)(wss.wss_left % 100));
  t.row("Right", "%u.%02u mph", (unsigned)(wss.wss_right / 100), (unsigned)(wss.wss_right % 100));
  t.row("Direction", "0x%02X", (unsigned)wss.wss_dir_flags);
  t.row("Fresh", "%s", rx.fresh() ? "yes" : "no");
  t.row("Frames", "%lu", (unsigned long)rx.rx_count());
}

void cmd_dash_can(Interaction &io, std::span<char *const>)
{
  const fc::Stats s = fc::stats(fc::Bus::k1);

  KVTable t(io, 14, 12, "FDCAN1");

  t.row("TX", "%lu", (unsigned long)s.tx);
  t.row("TX dropped", "%lu", (unsigned long)s.tx_dropped);
  t.row("TX failed", "%lu", (unsigned long)s.tx_failed);
  t.row("RX", "%lu", (unsigned long)s.rx);
  t.row("RX lost", "%lu", (unsigned long)s.rx_lost);
  t.row("RX errors", "%lu", (unsigned long)s.rx_errors);
  t.row("Bus-off", "%lu", (unsigned long)s.bus_off);
  t.row("PSR", "0x%08lX", (unsigned long)hfdcan1.Instance->PSR);
  t.row("ECR", "0x%08lX", (unsigned long)hfdcan1.Instance->ECR);
}

constexpr std::array<Command, 2> kDashSubcommands = {{
    {.name = "wss", .description = "Rear wheel speeds from the rear sensor node", .handler = cmd_dash_wss},
    {.name = "can", .description = "FDCAN transport counters and last error state", .handler = cmd_dash_can},
}};

constexpr std::array<Command, 1> kDashCommands = {{
    group("dash", "DASH board commands", kDashSubcommands),
}};

} // namespace

namespace dash
{
inline constexpr auto kAll = concat(kSystemCommands, kDashCommands);
static_assert(!has_duplicate_names(kAll), "duplicate console command name");
static_assert(params_fit(kAll), "a command declares more params than kMaxParams");

inline constexpr Console kConsole{FEB_UART_INSTANCE_1, kAll};
} // namespace dash

extern "C" void DASH_Console_ProcessLine(const char *line, size_t len)
{
  dash::kConsole.process_line(line, len);
}
