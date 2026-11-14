# DASH — Driver Dashboard

Driver display on the Riverdi 5" STM32 Embedded Display (800×480, capacitive touch). The UI is an LVGL Pro project; the firmware brings up the display and feeds the UI from CAN through LVGL subjects.

## MCU

| Part | Core | Flash | RAM | FreeRTOS |
|---|---|---|---|---|
| STM32U599NJH6Q | Cortex-M33 (FPU, no TrustZone), 160 MHz | 4 MB | 2.5 MB (750 KB of it is the LTDC framebuffer) | Yes (X-CUBE-FREERTOS 1.4.0 / FreeRTOS 11.2.0, heap_4, 110 KB, FPU context saving on) |

## Where things live

| Path | What | Owned by |
|---|---|---|
| `DASH.ioc`, `Core/Src`, `Core/Inc`, `Drivers/`, `Middlewares/` | Board bring-up, generated from the vendor `.ioc` of [lv_port_riverdi_stm32u5](https://github.com/lvgl/lv_port_riverdi_stm32u5) | STM32CubeMX (`./scripts/cubemx.sh -g -b DASH`) |
| `UI/` | The LVGL Pro editor project: screens, components, `globals.xml` (styles and subjects), fonts, images, and the C it exports | LVGL Pro editor |
| `LVGL/lvgl` | LVGL, git submodule pinned to the version `UI/project.xml` targets (9.6.0) | Bump together with the editor |
| `LVGL/lv_conf.defaults` → `lv_conf.h` | LVGL config: the vendor's defaults plus what LVGL 9.6 and LVGL Pro need | Edit `.defaults`, then regenerate (below) |
| `Core/User/` | Firmware logic (`DASH_Main`, `DASH_Tasks`, `DASH_CAN`, `DASH_CAN_Publish`, `DASH_Commands`, `App/`) | Us |

## UI workflow

1. Open `DASH/UI` in the LVGL Pro editor, edit, and export (Ctrl+B). Commit the XML **and** the exported `*_gen.c/h`; the firmware build does not run the editor. The editor names the project after its folder, so the entry point is `UI_init()` in `UI.h` (`UI.c` is the hand-editable stub, `UI_gen.c/h` are regenerated).
2. The firmware never touches widgets. It writes subjects declared in `UI/globals.xml`, and the UI binds to them:

   | Subject | Type | Written by | Value |
   |---|---|---|---|
   | `subject_wheel_speed` | int | `App/DASH_UI.cpp` | Rear-left wheel speed, whole mph (`wss_rear.wss_left`), 0 while the rear sensor node is silent |

   If you give it a `max` in `globals.xml`, keep it at 150 or more; LVGL clamps writes to the subject's range.
3. The screen DASH loads at boot is chosen in `DASH_UI_Init()` with `lv_screen_load(<screen>_create())`, like `UI/sim/main.c` does for the simulator. Use the create function, not the screen's global: the exported init only pre-creates permanent screens when `LV_USE_XML` is defined to 0, which LVGL 9.5+ no longer does.

LVGL runs on the display task only (`LV_USE_OS = LV_OS_NONE`); do not call LVGL from other tasks.

### Regenerating lv_conf.h

```bash
cd DASH/LVGL && python3 lvgl/scripts/generate_lv_conf.py
```

## Peripherals

From [`DASH.ioc`](DASH.ioc), as configured by the vendor port unless noted:

- **LTDC + DMA2D + GPU2D (NemaGFX)** — display path; LVGL's ST LTDC driver flushes with DMA2D, NemaGFX accelerates drawing
- **OCTOSPI1** — external NOR flash (MX25LM51245G) in memory-mapped mode
- **I2C1** — touch controller (interrupt on EXTI6)
- **TIM15 CH1** — backlight PWM
- **FDCAN1** — vehicle CAN on PB8/PB9. *Changed from the vendor:* classic frames at 500 kbit/s (prescaler 16, 15+4 tq, 80% sample point, matching the F446 nodes), auto-retransmission on, 14 standard / 8 extended filters, IT0 interrupt enabled
- USART1/2/3/6, USB OTG HS, SDMMC1, SPI1/2, ADC, DAC, … — configured by the vendor, unused so far

## CubeMX notes

These keep regeneration reproducing the init sequence that ran on the screen:

- **Functions not called from `main()`** (Project Manager → Advanced Settings → *Do Not Generate Function Call*): `MX_DCACHE2_Init`, `MX_FLASH_Init` (the vendor notes NemaGFX cannot read images and fonts from flash with it), `MX_GTZC_Init`, `MX_ADF1_Init`, `MX_TIM1_Init`, `MX_USART2_UART_Init`. The vendor's `main.c` skipped all six.
- **LTDC register callbacks** are enabled (Project Manager → Advanced Settings → Register Callback); LVGL's LTDC driver needs them.
- **LVGL lives in `DASH/LVGL`, not `Middlewares/`**: regeneration deletes folders in `Middlewares/` that CubeMX does not manage.
- **X-CUBE-FREERTOS 1.4.0**, upgraded from the vendor's 1.0.1: CubeMX 6.18's `main.c` includes `app_freertos.h`, which only the newer pack generates. `configENABLE_FPU` is 1 (the vendor had 0), so tasks that use the FPU do not corrupt each other's registers.
- Tasks are created in the USER CODE sections of `Core/Src/app_freertos.c`; X-CUBE-FREERTOS has no task editor.

## Tasks

| Task | Priority | Stack | Body |
|---|---|---|---|
| `displayTask` | Normal | 16 KB | `DASH_UI_Init()`, then `DASH_UI_Update()` (subjects + `lv_timer_handler`) |
| `canPubTask` | High1 | 2 KB | `feb::can::run_publishers()` |
| `defaultTask` | Normal | 16 KB | Vendor idle loop |

## CAN

FDCAN1 is `feb::can::Bus::k1` through [FEB_CAN](../common/FEB_CAN/Library/README.md). `DASH_Init` starts it before the scheduler; frames are received in the FDCAN interrupt, so there are no CAN RX/TX tasks or queues.

- Receives: `wss_rear`
- Sends: `dash_heartbeat`. `dash_state` (buttons, switches, ready-to-drive) is not sent yet; LVPDB turns its DASH-switched rails off while it is missing.

## Console

`DASH_Commands.cpp` defines `dash wss` and `dash can`, but nothing feeds the console yet: it will run over USB CDC on the USB OTG HS port, which needs a transport hook in the serial library first. Logging (`LOG_*`) is a no-op until then.

## Build & Flash

```bash
./scripts/build.sh -b DASH
./scripts/flash.sh -b DASH
```

The LVGL submodule must be checked out (`git submodule update --init --recursive`).

## See Also

- [`README.md`](../README.md) — repo overview
- [`common/README.md`](../common/README.md) — library index
- [`UI/README.md`](UI/README.md) — LVGL Pro project template notes
