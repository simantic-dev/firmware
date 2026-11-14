cmake_minimum_required(VERSION 3.22)

# ── Project identity (derived from directory name) ───────────────────
get_filename_component(PROJ_NAME ${CMAKE_CURRENT_SOURCE_DIR} NAME)

# ── Compiler settings ────────────────────────────────────────────────
set(CMAKE_C_STANDARD                11)
set(CMAKE_C_STANDARD_REQUIRED       ON)
set(CMAKE_CXX_STANDARD              20)
set(CMAKE_CXX_STANDARD_REQUIRED     ON)
set(CMAKE_C_EXTENSIONS              ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS   TRUE)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

project(${PROJ_NAME} C CXX ASM)
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")

# ── Compile definitions ──────────────────────────────────────────────
add_compile_definitions(
    USE_HAL_DRIVER
    STM32U599xx
    $<$<CONFIG:Debug>:DEBUG>
)

# ══════════════════════════════════════════════════════════════════════
#  SOURCE COLLECTION
# ══════════════════════════════════════════════════════════════════════

# Core application sources (CubeMX-generated + user code)
file(GLOB_RECURSE CORE_SOURCES "Core/*.c" "Core/*.cpp")

# Startup assembly
file(GLOB STARTUP_ASM "startup_*.s")

# HAL/LL driver sources (CubeMX copies only the modules the .ioc uses)
file(GLOB HAL_SOURCES "Drivers/STM32U5xx_HAL_Driver/Src/*.c")
list(FILTER HAL_SOURCES EXCLUDE REGEX "_template\\.c$")

# FreeRTOS (X-CUBE-FREERTOS, Cortex-M33 without TrustZone)
set(FREERTOS_DIR "Middlewares/Third_Party/FreeRTOS/Source")
file(GLOB FREERTOS_SOURCES
    "${FREERTOS_DIR}/*.c"
    "${FREERTOS_DIR}/CMSIS_RTOS_V2/*.c"
    "${FREERTOS_DIR}/portable/GCC/ARM_CM33_NTZ/non_secure/*.c"
    "${FREERTOS_DIR}/portable/MemMang/heap_4.c"
)

# CAN definitions: generated pack/unpack source (common/FEB_CAN_Definitions)
set(CAN_DEFS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../common/FEB_CAN_Definitions")

set(ALL_SOURCES ${CORE_SOURCES} ${STARTUP_ASM} ${HAL_SOURCES} ${FREERTOS_SOURCES} "${CAN_DEFS_DIR}/gen/feb_can_db.c")

# ══════════════════════════════════════════════════════════════════════
#  INCLUDE DIRECTORIES
# ══════════════════════════════════════════════════════════════════════

set(MCU_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/Core/Inc
    ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/STM32U5xx_HAL_Driver/Inc
    ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/STM32U5xx_HAL_Driver/Inc/Legacy
    ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/CMSIS/Device/ST/STM32U5xx/Include
    ${CMAKE_CURRENT_SOURCE_DIR}/Drivers/CMSIS/Include
)

set(BASE_INCLUDES
    ${MCU_INCLUDES}
    ${FREERTOS_DIR}/include
    ${FREERTOS_DIR}/portable/GCC/ARM_CM33_NTZ/non_secure
    ${FREERTOS_DIR}/CMSIS_RTOS_V2
    Middlewares/Third_Party/CMSIS/RTOS2/Include
    "${CAN_DEFS_DIR}/.."         # resolves #include "FEB_CAN_Definitions/gen/feb_can_db.h"
    "${CAN_DEFS_DIR}/gen"        # resolves #include "feb_can.h" directly
    Core/User/Inc                # standard: <BOARD>_Main / _Tasks / _CAN / _CAN_Publish / _Commands
    Core/User/Inc/App            # board-specific modules
)

# ══════════════════════════════════════════════════════════════════════
#  LVGL + UI
# ══════════════════════════════════════════════════════════════════════

set(LVGL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/LVGL")
if(NOT EXISTS "${LVGL_ROOT}/lvgl/lvgl.h")
    message(FATAL_ERROR "LVGL submodule missing. Run: git submodule update --init --recursive")
endif()

file(GLOB_RECURSE LVGL_SOURCES "${LVGL_ROOT}/lvgl/src/*.c" "${LVGL_ROOT}/lvgl/src/*.S")
add_library(lvgl STATIC ${LVGL_SOURCES})
feb_target_mcu(lvgl M33)
target_include_directories(lvgl
    PUBLIC
        ${LVGL_ROOT}
        ${LVGL_ROOT}/lvgl
        ${LVGL_ROOT}/lvgl/include
    PRIVATE
        ${MCU_INCLUDES}
)

add_library(nemagfx STATIC IMPORTED)
set_target_properties(nemagfx PROPERTIES
    IMPORTED_LOCATION "${LVGL_ROOT}/lvgl/libs/nema_gfx/lib/core/cortex_m33_revC/gcc/libnemagfx-float-abi-hard.a"
    INTERFACE_LINK_LIBRARIES lvgl
)
target_link_libraries(lvgl PUBLIC nemagfx)

add_subdirectory(UI)
target_compile_definitions(lib-ui PUBLIC LV_LVGL_H_INCLUDE_SIMPLE)

# ══════════════════════════════════════════════════════════════════════
#  EXECUTABLE TARGET
# ══════════════════════════════════════════════════════════════════════

add_executable(${PROJECT_NAME} ${ALL_SOURCES})
feb_target_mcu(${PROJECT_NAME} M33)

target_include_directories(${PROJECT_NAME} PRIVATE ${BASE_INCLUDES})

target_link_libraries(${PROJECT_NAME} PRIVATE
    m
    lib-ui
    lvgl
    feb_can_cxx
    feb_string_utils
    feb_time
    feb_uart
    feb_log
    feb_version
    feb_console_2
    feb_commands_2
    feb_rtos_utils
)

# Embed CalVer version + build provenance from git (generates feb_build_info.c)
include(${CMAKE_SOURCE_DIR}/cmake/FEB_Version.cmake)
feb_apply_version(${PROJECT_NAME} ${CMAKE_CURRENT_SOURCE_DIR})

# Enable floating-point printf/scanf for newlib-nano
target_link_options(${PROJECT_NAME} PRIVATE
    "LINKER:-u,_printf_float"
    "LINKER:-u,_scanf_float"
)

# Linker script and map file (project-specific, not in shared toolchain)
file(GLOB LINKER_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/STM32U5*_FLASH.ld")
if(LINKER_SCRIPT)
    list(GET LINKER_SCRIPT 0 LINKER_SCRIPT)
    target_link_options(${PROJECT_NAME} PRIVATE -T "${LINKER_SCRIPT}")
endif()
target_link_options(${PROJECT_NAME} PRIVATE
    -Wl,-Map=$<TARGET_FILE_DIR:${PROJECT_NAME}>/${PROJECT_NAME}.map
)

# Remove wrong libob.a dependency
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# ── Post-build: .bin, .hex, size ─────────────────────────────────────
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${PROJECT_NAME}>
            ${PROJECT_NAME}.bin
    COMMAND ${CMAKE_OBJCOPY} -O ihex   $<TARGET_FILE:${PROJECT_NAME}>
            ${PROJECT_NAME}.hex
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${PROJECT_NAME}>
    COMMENT "Generating .bin/.hex for ${PROJECT_NAME}"
)

set_target_properties(${PROJECT_NAME} PROPERTIES
    ADDITIONAL_CLEAN_FILES "${PROJECT_NAME}.map;${PROJECT_NAME}.bin;${PROJECT_NAME}.hex"
)
