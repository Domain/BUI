/* Global look: scale, font, themes and Blender's icon list.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
module bui.theme;

import bui.internal.util : cslice, cstr;
import bui.kit;

/// Blender's resolution scale (1 = 20 px widgets).
void setScale(float scale) {
    BK_set_scale(scale);
}

/// The current scale.
float scale() {
    return BK_scale();
}

/// U.widget_unit in pixels.
int unit() {
    return BK_unit();
}

/// Replace the UI font family.
void setFont(string family) {
    BK_set_font(family.length ? cstr(family) : null);
}

/// Switch themes ("dark" or "light"); false when the name is unknown.
bool setTheme(string name) {
    return BK_set_theme(cstr(name)) != 0;
}

/// The active theme name ("dark" or "light").
string themeName() {
    return cslice(BK_theme_name()).idup;
}

/// A theme color as RGBA 0..1, for example "region_bg" or "regular.inner".
bool themeColor(string key, out float[4] rgba) {
    return BK_theme_color(cstr(key), rgba.ptr) != 0;
}

/* -- icons ----------------------------------------------------------------- */

/// Blender's icon id for a name; 0 when unknown.
int iconId(string name) {
    return BK_icon_id(cstr(name));
}

/// The number of named icons.
int iconCount() {
    return BK_icon_count();
}

/// The name of icon `id`.
string iconName(int id) {
    return cslice(BK_icon_name(id)).idup;
}

/// The number of names in the listing (SVG icons, then BUI-only ones).
int iconListCount() {
    return BK_icon_list_count();
}

/// Listing entry `i`.
string iconListName(int i) {
    return cslice(BK_icon_list_name(i)).idup;
}
