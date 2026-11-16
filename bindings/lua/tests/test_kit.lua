-- Kit API tests: the surface that follows the current kit header — font size and
-- shadows, theme keys, GPU effects, file dialog, recent searches, canvas
-- add/put/truncate with effects, ImBuf/Video/Anim, IME, configure, custom events.
-- SPDX-License-Identifier: GPL-2.0-or-later

local function check(cond, msg)
  if not cond then io.stderr:write("FAIL: " .. msg .. "\n"); os.exit(1) end
end

local bui = require("bui")

-- ── Font size, text shadow, text width ───────────────────────────────

local old_size = bui.font_size()
bui.set_font_size(11)
check(math.abs(bui.font_size() - 11) < 0.01, "set_font_size/font_size roundtrip")
bui.set_font_size(old_size)

local old_shadow = bui.text_shadow()
bui.set_text_shadow(false)
check(bui.text_shadow() == false, "set_text_shadow(false) roundtrip")
bui.set_text_shadow(old_shadow)

check(type(bui.text_width("Hello")) == "number", "text_width returns a number")
check(bui.text_width("Hello") > bui.text_width(""), "text_width grows with the text")

-- ── Theme introspection (own keys, generation, mode) ─────────────────

check(type(bui.theme_mode()) == "string", "theme_mode is a string")
check(type(bui.theme_generation()) == "number", "theme_generation returns a number")
local gen0 = bui.theme_generation()
bui.set_theme("light")
check(bui.theme_generation() > gen0, "theme_generation rises when the theme changes")
bui.set_theme("dark")
check(type(bui.theme_ignored()) == "number", "theme_ignored returns a number")

-- A key BUI has no field for is the theme's own and reads back while the theme is in use.
local json = '{"name":"T","themes":[{"name":"OwnKeys","mode":"dark","colors":' ..
             '{"muted.foreground":"#8696A0","bubble.radius":14}}]}'
local added = bui.load_theme(json)
check(added == 1, "load_theme added one theme, got " .. tostring(added))
check(bui.set_theme("OwnKeys") ~= 0, "set_theme switched to the custom theme")
local r, g, b = bui.theme_color("muted.foreground")
check(r and r > 0, "theme's own color reads back by key")
local br = bui.theme_value("bubble.radius")
check(br == 14, "theme's own number reads back by key, got " .. tostring(br))
bui.set_theme("dark")

-- ── GPU: default + effects ───────────────────────────────────────────

local gd = bui.gpu_default()
bui.set_gpu_default(gd)
check(type(gd) == "boolean", "gpu_default is a boolean")

local id = bui.effect_create("t", "vec4 effect(vec2 p) { return vec4(1.0, 0.0, 0.0, 1.0); }", 0, 1)
check(id > 0, "effect_create returns an id > 0")
local log = bui.effect_error(id)
check(log == nil or type(log) == "string", "effect_error is a string or nil")
bui.effect_free(id)
check(bui.effect_error(id) == nil, "effect_error is nil for a freed id")
check(bui.effect_create("t", "", 0, 0) == 0, "effect_create with no source returns 0")
check(bui.effect_create("t", "src", 99, 0) == 0, "effect_create with too many inputs returns 0")

-- ── File dialog (it opens a native window until answered: not run here) ──

check(type(bui.file_dialog) == "function", "file_dialog is a function")

-- ── Recent searches ──────────────────────────────────────────────────

bui.recent_searches_enable(true)
bui.recent_searches_clear()
bui.recent_searches_save(os.tmpname())
bui.recent_searches_enable(false)

-- ── Waking the loop (headless: no window host, still callable) ───────

local woke = false
check(type(bui.wake_init(function() woke = true end)) == "boolean", "wake_init returns a boolean")
bui.wake()
bui.set_keep_alive(false)
bui.set_stop_check(function() return false end)
bui.set_stop_check(nil)

-- ── node:ctx() ───────────────────────────────────────────────────────

local root = bui.Node("column")
check(root:ctx() == nil, "a detached node has no context")
local ctx = bui.Context(root)
check(root:ctx() == ctx, "node:ctx() finds the context the script made")

-- ── configure + IME ──────────────────────────────────────────────────

local changed = ctx:configure(320, 240)
check(type(changed) == "boolean", "configure returns a boolean")
check(ctx:configure(320, 240) == false, "configure again with the same size is false")
check(ctx:ime_composing() == false, "ime_composing is false with nothing composing")
check(ctx:ime_event(0, {composite = "n", cursor_pos = 1}) ~= nil, "ime_event returns a boolean")
local st = ctx:ime_state()
check(st == nil or type(st) == "table", "ime_state is nil or a table")

-- ── Canvas: add / put / truncate and effect items ────────────────────

local cnv = bui.Node("canvas")
root:add(cnv)
for i = 1, 3 do
  cnv:canvas_add{type = bui.ITEM_RECT, coords = {i * 4, i * 4, i * 4 + 20, i * 4 + 20},
                 fill = {1, 0, 0, 1}}
end
check(cnv:canvas_count() == 3, "canvas_add appended three items")
cnv:canvas_put(1, {type = bui.ITEM_RECT, coords = {0, 0, 10, 10}, fill = {0, 1, 0, 1}})
cnv:canvas_truncate(2)
check(cnv:canvas_count() == 2, "canvas_truncate dropped the third item")

-- An effect item: the shader id, its input textures and floats (the kit copies the floats).
local eid = bui.effect_create("e", "vec4 effect(vec2 p){return vec4(U[0]);}", 0, 1)
cnv:canvas_set{id = 7, type = bui.ITEM_EFFECT, coords = {0, 0, 50, 50},
               effect = eid, effect_floats = {1.0}}
check(cnv:canvas_count() == 3, "canvas_set added the effect item")
bui.effect_free(eid)

-- Image items keep their data alive.
local ib = bui.image_from_rgba(string.rep("\255\0\0\255", 4), 2, 2)
check(ib ~= nil, "image_from_rgba made an ImBuf")
local w, h, frames = ib:size()
check(w == 2 and h == 2 and frames == 1, "image_from_rgba size")
cnv:canvas_set{id = 8, type = bui.ITEM_IMAGE, coords = {0, 0, 2, 2}, imbuf = ib}
local tex = ib:texture(0)
check(type(tex) == "number", "imbuf:texture returns a number")
if tex > 0 then
  check(ib:texture_update(0, tex), "imbuf:texture_update")
  bui.texture_free(tex)
end
local argb = bui.image_from_argb(ib:pixels(0), 2, 2)
check(argb ~= nil, "image_from_argb roundtrip")

-- ── Video listener + texture ─────────────────────────────────────────

local v = bui.Video("nonexistent.mp4")
if v then
  local heard = nil
  v:set_listener(function(vid, state) heard = state end)
  check(v:texture(0, 64, 64) >= 0, "video:texture returns a number")
  v:set_listener(nil)
  v:free()
end

-- ── Anim stepping ────────────────────────────────────────────────────

check(bui.Anim("not an animation") == nil, "Anim with bad data is nil")

-- ── Custom node: on_event / on_frame / on_free dispatch ──────────────

local hits = {}
local cn = bui.Node("custom")
cn:custom_set{
  natural_w = 40, natural_h = 40,
  on_event = function(self, e) hits[#hits + 1] = e.type; return true end,
  on_frame = function(self) hits[#hits + 1] = "frame" end,
  on_free  = function(self) hits[#hits + 1] = "free" end,
}
root:add(cn)
ctx:configure(320, 240)
ctx:render(320, 240, 1)               -- the first render calls frame
check(#hits > 0 and hits[1] == "frame", "on_frame ran on the first render, got " .. tostring(hits[1]))
local nx, ny = cn:rect()
ctx:press(nx + 5, ny + 5, 0)
ctx:release(nx + 5, ny + 5, 0)
-- The kit gives custom nodes raw pointer events as bui.CUSTOM_PRESS, not EV_*:
local saw_custom_press = false
for _, t in ipairs(hits) do if t == bui.CUSTOM_PRESS then saw_custom_press = true end end
check(saw_custom_press, "on_event saw the press (bui.CUSTOM_PRESS)")

-- ── Custom on_draw + draw_widget (needs a native window for a raster) ──

if not bui.headless() and bui.window_supported() then
  local drew = 0
  local wroot = bui.Node("column")
  local wcn = bui.Node("custom")
  wcn:custom_set{
    natural_w = 40, natural_h = 20,
    on_draw = function(self, raster, x, y, w, h)
      drew = drew + 1
      bui.draw_widget(raster, {kind = bui.WIDGET_LABEL, rect = {x, y, w, h}, text = "hi"})
    end,
  }
  wroot:add(wcn)
  local wctx = bui.Context(wroot)
  local win = bui.Window(wctx, "bui-lua-kit-test", 120, 60)
  if win then
    local r = win:raster()
    check(r ~= nil, "win:raster() returns a raster")
    bui.draw_widget(r, {kind = bui.WIDGET_BUTTON, rect = {4, 4, 60, 20}, text = "Bl"})
    win:on_frame(function(w) bui.quit() end)
    win:request_frame(false)
    bui.run()
    check(drew > 0, "the custom node's on_draw ran")
    win:free()
  end
end

io.write("OK: test_kit.lua\n")
os.exit(0)
