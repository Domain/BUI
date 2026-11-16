/* BUI Lua binding: ImBuf, Video and Anim userdata wrappers.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "bui_internal.h"

/* Push a fresh wrapper for a live BKImBuf (the factories share this). */
static void push_imbuf(lua_State *L, BKImBuf *ib) {
  luabui_ImBuf *iud = (luabui_ImBuf *)lua_newuserdata(L, sizeof(luabui_ImBuf));
  iud->ib = ib;
  luaL_getmetatable(L, LUABUI_IMBUF_MT);
  lua_setmetatable(L, -2);
}

/* ------------------------------------------------------------------ */
/* ImBuf methods                                                      */
/* ------------------------------------------------------------------ */

static int l_imbuf_size(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  if (!iud->ib) return 0;
  int w, h;
  int frames = BK_imbuf_size(iud->ib, &w, &h);
  lua_pushinteger(L, w);
  lua_pushinteger(L, h);
  lua_pushinteger(L, frames);
  return 3;
}

static int l_imbuf_format(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  lua_pushinteger(L, iud->ib ? BK_imbuf_format(iud->ib) : BK_IMAGE_NONE);
  return 1;
}

static int l_imbuf_pixels(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  if (!iud->ib) return 0;
  int frame = (int)luaL_optinteger(L, 2, 0);
  int w, h;
  BK_imbuf_size(iud->ib, &w, &h);
  const uint32_t *pixels = BK_imbuf_pixels(iud->ib, frame);
  if (!pixels) return 0;
  lua_pushlstring(L, (const char *)pixels, (size_t)w * h * 4);
  return 1;
}

static int l_imbuf_delay(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  int frame = (int)luaL_optinteger(L, 2, 0);
  lua_pushinteger(L, iud->ib ? BK_imbuf_delay(iud->ib, frame) : 0);
  return 1;
}

static int l_imbuf_loops(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  lua_pushinteger(L, iud->ib ? BK_imbuf_loops(iud->ib) : 0);
  return 1;
}

/* imbuf:texture([frame]): a BUI_texture id (RGBA) for Dear ImGui, meshes and canvas
 * effect inputs; free it with bui.texture_free. 0 when it cannot be made. */
static int l_imbuf_texture(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  if (!iud->ib) { lua_pushinteger(L, 0); return 1; }
  int frame = (int)luaL_optinteger(L, 2, 0);
  lua_pushinteger(L, BK_imbuf_texture(iud->ib, frame));
  return 1;
}

/* imbuf:texture_update(frame, tex): replaces tex (same size) with a frame: an
 * animation's next one. */
static int l_imbuf_texture_update(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  if (!iud->ib) { lua_pushboolean(L, 0); return 1; }
  int frame = (int)luaL_checkinteger(L, 2);
  int tex = (int)luaL_checkinteger(L, 3);
  lua_pushboolean(L, BK_imbuf_texture_update(iud->ib, frame, tex));
  return 1;
}

static int l_imbuf_free(lua_State *L) {
  luabui_ImBuf *iud = CHECK_IMBUF(L, 1);
  if (iud->ib) {
    BK_imbuf_free(iud->ib);
    iud->ib = NULL;
  }
  return 0;
}

static int l_imbuf_gc(lua_State *L) {
  luabui_ImBuf *iud = (luabui_ImBuf *)luaL_checkudata(L, 1, LUABUI_IMBUF_MT);
  if (iud->ib) {
    BK_imbuf_free(iud->ib);
    iud->ib = NULL;
  }
  return 0;
}

static int l_imbuf_tostring(lua_State *L) {
  luabui_ImBuf *iud = (luabui_ImBuf *)luaL_checkudata(L, 1, LUABUI_IMBUF_MT);
  if (iud->ib) {
    int w, h;
    BK_imbuf_size(iud->ib, &w, &h);
    lua_pushfstring(L, "bui.ImBuf: %dx%d (%d frames)", w, h, BK_imbuf_size(iud->ib, NULL, NULL));
  } else {
    lua_pushfstring(L, "bui.ImBuf: (freed)");
  }
  return 1;
}

/* Factory: decode from data */
int l_image_decode(lua_State *L) {
  size_t len;
  const char *data = luaL_checklstring(L, 1, &len);
  int max_w = (int)luaL_optinteger(L, 2, 0);
  int max_h = (int)luaL_optinteger(L, 3, 0);

  BKImBuf *ib = BK_imbuf_decode(data, len, max_w, max_h);
  if (!ib) { lua_pushnil(L); return 1; }
  push_imbuf(L, ib);
  return 1;
}

/* Factory: load from file */
int l_image_load(lua_State *L) {
  const char *path = luaL_checkstring(L, 1);
  int max_w = (int)luaL_optinteger(L, 2, 0);
  int max_h = (int)luaL_optinteger(L, 3, 0);

  BKImBuf *ib = BK_imbuf_load(path, max_w, max_h);
  if (!ib) { lua_pushnil(L); return 1; }
  push_imbuf(L, ib);
  return 1;
}

/* Factory: straight RGBA bytes (w*h*4), the row pitch `stride` (0 = w*4). */
int l_image_from_rgba(lua_State *L) {
  size_t len;
  const unsigned char *rgba = (const unsigned char *)luaL_checklstring(L, 1, &len);
  int w = (int)luaL_checkinteger(L, 2);
  int h = (int)luaL_checkinteger(L, 3);
  int stride = (int)luaL_optinteger(L, 4, 0);
  if (w <= 0 || h <= 0) return luaL_error(L, "image_from_rgba: w and h must be positive");
  if (stride <= 0) stride = w * 4;
  if ((size_t)stride * (size_t)(h - 1) + (size_t)w * 4 > len) {
    return luaL_error(L, "image_from_rgba: not enough bytes (%d x %d, stride %d)", w, h, stride);
  }
  BKImBuf *ib = BK_imbuf_from_rgba(rgba, w, h, stride);
  if (!ib) { lua_pushnil(L); return 1; }
  push_imbuf(L, ib);
  return 1;
}

/* Factory: premultiplied 0xAARRGGBB words (a string of w*h*4 bytes, as pixels() returns). */
int l_image_from_argb(lua_State *L) {
  size_t len;
  const char *data = luaL_checklstring(L, 1, &len);
  int w = (int)luaL_checkinteger(L, 2);
  int h = (int)luaL_checkinteger(L, 3);
  if (w <= 0 || h <= 0) return luaL_error(L, "image_from_argb: w and h must be positive");
  if ((size_t)w * (size_t)h * 4 != len) {
    return luaL_error(L, "image_from_argb: %d x %d needs %d bytes, got %d", w, h, w * h * 4, (int)len);
  }
  BKImBuf *ib = BK_imbuf_from_argb((const uint32_t *)data, w, h);
  if (!ib) { lua_pushnil(L); return 1; }
  push_imbuf(L, ib);
  return 1;
}

/* ------------------------------------------------------------------ */
/* Video methods                                                      */
/* ------------------------------------------------------------------ */

static int l_video_play(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_play(vud->video);
  return 0;
}

static int l_video_pause(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_pause(vud->video);
  return 0;
}

static int l_video_seek(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_seek(vud->video, luaL_checknumber(L, 2));
  return 0;
}

static int l_video_set_rate(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_rate(vud->video, luaL_checknumber(L, 2));
  return 0;
}

static int l_video_set_loop(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_loop(vud->video, (int)lua_toboolean(L, 2));
  return 0;
}

static int l_video_set_muted(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_muted(vud->video, (int)lua_toboolean(L, 2));
  return 0;
}

static int l_video_muted(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushboolean(L, vud->video && BK_video_muted(vud->video));
  return 1;
}

static int l_video_set_volume(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_volume(vud->video, luaL_checknumber(L, 2));
  return 0;
}

static int l_video_volume(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushnumber(L, vud->video ? BK_video_volume(vud->video) : 0.0);
  return 1;
}

static int l_video_set_audio_effects(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_audio_effects(vud->video, (int)lua_toboolean(L, 2));
  return 0;
}

static int l_video_audio_effects(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushboolean(L, vud->video && BK_video_audio_effects(vud->video));
  return 1;
}

static int l_video_has_audio(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushboolean(L, vud->video && BK_video_has_audio(vud->video));
  return 1;
}

static int l_video_set_poster(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_poster(vud->video, luaL_checkstring(L, 2));
  return 0;
}

static int l_video_set_controls(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (vud->video) BK_video_set_controls(vud->video, (int)lua_toboolean(L, 2));
  return 0;
}

static int l_video_state(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushinteger(L, vud->video ? BK_video_state(vud->video) : BK_VIDEO_ERROR);
  return 1;
}

static int l_video_time(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushnumber(L, vud->video ? BK_video_time(vud->video) : 0);
  return 1;
}

static int l_video_duration(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  lua_pushnumber(L, vud->video ? BK_video_duration(vud->video) : 0);
  return 1;
}

static int l_video_size(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (!vud->video) return 0;
  int w, h;
  BK_video_size(vud->video, &w, &h);
  lua_pushinteger(L, w);
  lua_pushinteger(L, h);
  return 2;
}

/* The state listener runs on the UI thread (the kit's contract), so calling
 * Lua from it is as safe as from host_emit. */
static void video_heard_cb(BKVideo *v, int state, void *data) {
  (void)v;
  luabui_Video *vud = (luabui_Video *)data;
  lua_State *L = luabui_module_state();
  if (!L || vud->listener_ref == LUA_NOREF || vud->self_ref == LUA_NOREF) return;
  int top = lua_gettop(L);
  lua_rawgeti(L, LUA_REGISTRYINDEX, vud->listener_ref);
  if (!lua_isfunction(L, -1)) {
    lua_settop(L, top);
    return;
  }
  lua_rawgeti(L, LUA_REGISTRYINDEX, vud->self_ref);
  lua_pushinteger(L, state);
  if (lua_pcall(L, 2, 0, 0) != LUA_OK) luabui_report_error(L);
  lua_settop(L, top);
}

/* video:set_listener(fn): called on every state change with (video, state).
 * nil clears it. */
static int l_video_set_listener(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (!vud->video) return 0;
  if (vud->listener_ref != LUA_NOREF) {
    luaL_unref(L, LUA_REGISTRYINDEX, vud->listener_ref);
    vud->listener_ref = LUA_NOREF;
  }
  if (vud->self_ref != LUA_NOREF) {
    luaL_unref(L, LUA_REGISTRYINDEX, vud->self_ref);
    vud->self_ref = LUA_NOREF;
  }
  if (lua_isfunction(L, 2)) {
    lua_pushvalue(L, 2);
    vud->listener_ref = luaL_ref(L, LUA_REGISTRYINDEX);
    lua_pushvalue(L, 1);
    vud->self_ref = luaL_ref(L, LUA_REGISTRYINDEX);
    BK_video_set_listener(vud->video, video_heard_cb, vud);
  } else {
    BK_video_set_listener(vud->video, NULL, NULL);
  }
  return 0;
}

/* video:texture([tex, max_w, max_h]): the current frame in a BUI_texture (RGBA),
 * created when tex is 0 and updated in place with new frames; 0 before the first.
 * Calling it each frame is what keeps the video playing. */
static int l_video_texture(lua_State *L) {
  luabui_Video *vud = CHECK_VIDEO(L, 1);
  if (!vud->video) { lua_pushinteger(L, 0); return 1; }
  int tex = (int)luaL_optinteger(L, 2, 0);
  int max_w = (int)luaL_optinteger(L, 3, 0);
  int max_h = (int)luaL_optinteger(L, 4, 0);
  lua_pushinteger(L, BK_video_texture(vud->video, tex, max_w, max_h));
  return 1;
}

/* Take the listener off the video before it goes away (the callback holds a
 * pointer to this userdata). */
static void video_release(lua_State *L, luabui_Video *vud) {
  if (vud->video) {
    BK_video_set_listener(vud->video, NULL, NULL);
    BK_video_free(vud->video);
    vud->video = NULL;
  }
  if (vud->listener_ref != LUA_NOREF) {
    luaL_unref(L, LUA_REGISTRYINDEX, vud->listener_ref);
    vud->listener_ref = LUA_NOREF;
  }
  if (vud->self_ref != LUA_NOREF) {
    luaL_unref(L, LUA_REGISTRYINDEX, vud->self_ref);
    vud->self_ref = LUA_NOREF;
  }
}

static int l_video_free(lua_State *L) {
  video_release(L, CHECK_VIDEO(L, 1));
  return 0;
}

static int l_video_gc(lua_State *L) {
  video_release(L, (luabui_Video *)luaL_checkudata(L, 1, LUABUI_VIDEO_MT));
  return 0;
}

static int l_video_tostring(lua_State *L) {
  luabui_Video *vud = (luabui_Video *)luaL_checkudata(L, 1, LUABUI_VIDEO_MT);
  lua_pushfstring(L, "bui.Video (%p)", (void *)(vud->video));
  return 1;
}

/* Factory: create video from source */
int l_video_new(lua_State *L) {
  const char *src = luaL_checkstring(L, 1);
  BKVideo *video = BK_video_new(src);
  if (!video) { lua_pushnil(L); return 1; }

  luabui_Video *vud = (luabui_Video *)lua_newuserdata(L, sizeof(luabui_Video));
  vud->video = video;
  vud->listener_ref = LUA_NOREF;
  vud->self_ref = LUA_NOREF;
  luaL_getmetatable(L, LUABUI_VIDEO_MT);
  lua_setmetatable(L, -2);
  return 1;
}

/* ------------------------------------------------------------------ */
/* Registration                                                       */
/* ------------------------------------------------------------------ */

static const luaL_Reg imbuf_methods[] = {
  {"size",      l_imbuf_size},
  {"format",    l_imbuf_format},
  {"pixels",    l_imbuf_pixels},
  {"delay",     l_imbuf_delay},
  {"loops",     l_imbuf_loops},
  {"texture",   l_imbuf_texture},
  {"texture_update", l_imbuf_texture_update},
  {"free",      l_imbuf_free},
  {"__gc",      l_imbuf_gc},
  {"__tostring",l_imbuf_tostring},
  {NULL, NULL}
};

static const luaL_Reg video_methods[] = {
  {"play",        l_video_play},
  {"pause",       l_video_pause},
  {"seek",        l_video_seek},
  {"set_rate",    l_video_set_rate},
  {"set_loop",    l_video_set_loop},
  {"set_poster",  l_video_set_poster},
  {"set_muted",   l_video_set_muted},
  {"muted",       l_video_muted},
  {"set_volume",  l_video_set_volume},
  {"volume",      l_video_volume},
  {"set_audio_effects", l_video_set_audio_effects},
  {"audio_effects", l_video_audio_effects},
  {"has_audio",   l_video_has_audio},
  {"set_controls",l_video_set_controls},
  {"set_listener",l_video_set_listener},
  {"texture",     l_video_texture},
  {"state",       l_video_state},
  {"time",        l_video_time},
  {"duration",    l_video_duration},
  {"size",        l_video_size},
  {"free",        l_video_free},
  {"__gc",        l_video_gc},
  {"__tostring",  l_video_tostring},
  {NULL, NULL}
};

void luabui_register_imbuf(lua_State *L) {
  luaL_newmetatable(L, LUABUI_IMBUF_MT);
  luaL_setfuncs(L, imbuf_methods, 0);
  lua_pushvalue(L, -1);
  lua_setfield(L, -2, "__index");
  lua_pop(L, 1);
}

void luabui_register_video(lua_State *L) {
  luaL_newmetatable(L, LUABUI_VIDEO_MT);
  luaL_setfuncs(L, video_methods, 0);
  lua_pushvalue(L, -1);
  lua_setfield(L, -2, "__index");
  lua_pop(L, 1);
}

/* ------------------------------------------------------------------ */
/* Anim: a GIF / animated WebP stepped by the caller                   */
/* ------------------------------------------------------------------ */

/* anim:next(): the next ImBuf and how long to show it (ms), or nil at the end. */
static int l_anim_next(lua_State *L) {
  luabui_Anim *aud = CHECK_ANIM(L, 1);
  if (!aud->anim) return 0;
  int delay = 0;
  BKImBuf *ib = BK_anim_next(aud->anim, &delay);
  if (!ib) { lua_pushnil(L); return 1; }
  push_imbuf(L, ib);
  lua_pushinteger(L, delay);
  return 2;
}

/* anim:info(): width, height, loops (0 = forever) and the frame count. */
static int l_anim_info(lua_State *L) {
  luabui_Anim *aud = CHECK_ANIM(L, 1);
  if (!aud->anim) return 0;
  int w = 0, h = 0, loops = 0;
  int frames = BK_anim_info(aud->anim, &w, &h, &loops);
  lua_pushinteger(L, w);
  lua_pushinteger(L, h);
  lua_pushinteger(L, loops);
  lua_pushinteger(L, frames);
  return 4;
}

static void anim_release(luabui_Anim *aud) {
  if (aud->anim) {
    BK_anim_free(aud->anim);
    aud->anim = NULL;
  }
}

static int l_anim_free(lua_State *L) {
  anim_release(CHECK_ANIM(L, 1));
  return 0;
}

static int l_anim_gc(lua_State *L) {
  anim_release((luabui_Anim *)luaL_checkudata(L, 1, LUABUI_ANIM_MT));
  return 0;
}

static int l_anim_tostring(lua_State *L) {
  luabui_Anim *aud = (luabui_Anim *)luaL_checkudata(L, 1, LUABUI_ANIM_MT);
  lua_pushfstring(L, "bui.Anim (%p)", (void *)aud->anim);
  return 1;
}

/* bui.Anim(data, [max_w, max_h]): one frame at a time at the size drawn, looping.
 * nil when the data is not an animation BUI reads. */
int l_anim_open(lua_State *L) {
  size_t len;
  const char *data = luaL_checklstring(L, 1, &len);
  int max_w = (int)luaL_optinteger(L, 2, 0);
  int max_h = (int)luaL_optinteger(L, 3, 0);
  BKAnim *a = BK_anim_open(data, len, max_w, max_h);
  if (!a) { lua_pushnil(L); return 1; }
  luabui_Anim *aud = (luabui_Anim *)lua_newuserdata(L, sizeof(luabui_Anim));
  aud->anim = a;
  luaL_getmetatable(L, LUABUI_ANIM_MT);
  lua_setmetatable(L, -2);
  return 1;
}

static const luaL_Reg anim_methods[] = {
  {"next",       l_anim_next},
  {"info",       l_anim_info},
  {"free",       l_anim_free},
  {"__gc",       l_anim_gc},
  {"__tostring", l_anim_tostring},
  {NULL, NULL}
};

void luabui_register_anim_ud(lua_State *L) {
  luaL_newmetatable(L, LUABUI_ANIM_MT);
  luaL_setfuncs(L, anim_methods, 0);
  lua_pushvalue(L, -1);
  lua_setfield(L, -2, "__index");
  lua_pop(L, 1);
}
