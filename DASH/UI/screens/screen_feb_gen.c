/**
 * @file screen_feb_gen.c
 * @brief Template source file for LVGL objects
 */

/*********************
 *      INCLUDES
 *********************/

#include "screen_feb_gen.h"
#include "../UI.h"

/*********************
 *      DEFINES
 *********************/

/**********************
 *      TYPEDEFS
 **********************/

/***********************
 *  STATIC VARIABLES
 **********************/

/***********************
 *  STATIC PROTOTYPES
 **********************/

/**********************
 *   GLOBAL FUNCTIONS
 **********************/

lv_obj_t * screen_feb_create(void)
{
    LV_TRACE_OBJ_CREATE("begin");

    static bool screen_created = false;
    if (screen_created) {
        LV_LOG_WARN("`screen_feb` is already initialized as a permanent screen. Returning with no change.");
        return screen_feb;
    }

    static lv_style_t style_bar_ind;

    static bool style_inited = false;

    if (!style_inited) {
        /*Init all styles*/
        lv_style_init(&style_bar_ind);

        lv_style_set_bg_color(&style_bar_ind, lv_color_hex(0xffffff));

        style_inited = true;
    }


    lv_obj_t * the_root = NULL;

    #if UI_CHECK_COMPILE_TARGET(UI_TARGET_ALL)
    if (UI_check_target(UI_TARGET_ALL)) {
        lv_obj_t * lv_obj_0 = screen_feb;
        lv_obj_set_name_static(lv_obj_0, "screen_feb_#");
        lv_obj_set_style_bg_color(lv_obj_0, lv_color_hex(0x000000), 0);

        lv_obj_add_style(lv_obj_0, &style_scrollbar, LV_PART_SCROLLBAR);
        lv_obj_t * column_0 = column_create(lv_obj_0, 0, 0, 0, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
        lv_obj_set_height(column_0, lv_pct(100));
        lv_obj_set_width(column_0, lv_pct(100));
        lv_obj_t * lv_bar_0 = lv_bar_create(column_0);
        lv_obj_set_height(lv_bar_0, 50);
        lv_obj_set_width(lv_bar_0, lv_pct(100));
        lv_bar_bind_value(lv_bar_0, subject_torque_percent);
        lv_obj_set_style_bg_color(lv_bar_0, lv_color_hex(0x000000), 0);
        lv_obj_set_style_arc_color(lv_bar_0, lv_color_hex(0xffffff), 0);
        lv_obj_add_style(lv_bar_0, &style_bar_ind, LV_PART_INDICATOR);

        lv_obj_t * row_0 = row_create(column_0, 0, 0, 0, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
        lv_obj_set_width(row_0, lv_pct(100));
        lv_obj_set_style_pad_top(row_0, 50, 0);
        lv_obj_set_style_pad_bottom(row_0, 50, 0);
        lv_obj_t * h1_0 = h1_create(row_0, "Heading 1");
        lv_label_bind_text(h1_0, subject_wheel_speed, "%d%");
        lv_obj_set_style_text_font(h1_0, font_guage_lg, 0);
        lv_obj_set_style_text_color(h1_0, lv_color_hex(0xffffff), 0);

        lv_obj_t * row_1 = row_create(column_0, 0, 0, 0, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
        lv_obj_set_width(row_1, lv_pct(100));
        lv_obj_t * button_0 = button_create(row_1, "other page", NULL, COLOR_ACCENT, COLOR_ACCENT_TEXT, RADIUS_DEFAULT);
        lv_obj_add_screen_create_event(button_0, LV_EVENT_CLICKED, screen_components_create, LV_SCREEN_LOAD_ANIM_MOVE_LEFT, 2000, 0);

        the_root = lv_obj_0;
    }
    #endif

    if (the_root) screen_created = true;

    LV_TRACE_OBJ_CREATE("finished");

    return the_root;
}

/**********************
 *   STATIC FUNCTIONS
 **********************/

