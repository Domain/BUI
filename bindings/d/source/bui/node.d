/* A node in the kit's retained tree: layouts, widgets, views, editors.
 *
 * `new Node("button")` owns its C node; `free()` releases it (the destructor
 * does it too). Nodes attached to a parent are kept alive by the kit's
 * reference hooks, exactly like Python wrappers: dropping the D reference is
 * safe while the parent holds the node.
 *
 * A node the kit owns (a panel body, a popup, a picker part) gets one cached
 * borrowed wrapper, retained by the kit for the node's lifetime, so handlers
 * added through `parent().child(i)` see the node's events too. Those handlers
 * are stored on the topmost D-owned wrapper, not on the rooted borrowed
 * wrapper, so a handler closure cannot keep the owning tree alive.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
module bui.node;

import bui.errors : BuiException;
import bui.image : Image;
import bui.internal.refs : ensureRefHooks;
import bui.internal.util : cslice, cstr;
import bui.kit;
import bui.menu : MenuItem, setMenuItems;
import bui.video : Video;

/// One event from the kit, delivered to a node's handlers.
struct NodeEvent {
    /// The node that received it.
    Node node;
    /// `BK_EV_*`.
    int kind;
    /// The kit's payload: a callback object, a C string for raw key events, or null.
    void* ref_;
    double a;
    double b;
    /// The key text for `BK_EV_KEY` / `BK_EV_KEYRELEASE`, else empty.
    const(char)[] text;
}

alias NodeHandler = void delegate(NodeEvent event);

/// A live view of a node's string list property (`BK_strs_*`), without copying.
struct Strs {
    Node node;
    string key;

    int length() const {
        return BK_strs_count(node.handle, cstr(key));
    }

    const(char)[] opIndex(size_t i) const {
        return cslice(BK_strs_get(node.handle, cstr(key), cast(int) i));
    }

    int opApply(scope int delegate(const(char)[] value) dg) const {
        const auto n = length;
        foreach (i; 0 .. n) {
            if (auto r = dg(opIndex(i))) {
                return r;
            }
        }
        return 0;
    }
}

/// Handlers for one node plus the wrapper epoch they were registered under.
/// `Node.free()` bumps a borrowed wrapper's epoch, which invalidates those
/// handlers even though the kit still owns the native node.
private struct HandlerSet {
    NodeHandler[] handlers;
    size_t epoch;
}

private __gshared size_t g_handlerEpoch;

private size_t nextHandlerEpoch() {
    return ++g_handlerEpoch;
}

private struct HandlerEntry {
    BKNode* node;
    HandlerSet set;
}

/// Event handlers registered on kit-owned nodes, keyed by the node they
/// belong to. The store lives on the topmost D-owned wrapper, so a borrowed
/// wrapper rooted by the kit stays free of handler closures.
///
/// A flat array keeps removal allocation-free: `Node.free()` also runs from
/// the GC finalizer, where allocating is not allowed. Handler lists are short.
private final class HandlerStore {
    private HandlerEntry[] entries;

    private ptrdiff_t indexOf(BKNode* node) {
        foreach (i, entry; entries) {
            if (entry.node is node) {
                return cast(ptrdiff_t) i;
            }
        }
        return -1;
    }

    void add(BKNode* node, NodeHandler handler, size_t epoch) {
        auto i = indexOf(node);
        if (i < 0) {
            entries ~= HandlerEntry(node, HandlerSet([handler], epoch));
        }
        else if (entries[i].set.epoch != epoch) {
            entries[i].set = HandlerSet([handler], epoch);
        }
        else {
            entries[i].set.handlers ~= handler;
        }
    }

    void addAll(BKNode* node, HandlerSet set) {
        auto i = indexOf(node);
        if (i < 0) {
            entries ~= HandlerEntry(node, set);
        }
        else if (entries[i].set.epoch != set.epoch) {
            entries[i].set = set;
        }
        else {
            entries[i].set.handlers ~= set.handlers;
        }
    }

    HandlerSet take(BKNode* node) {
        auto i = indexOf(node);
        if (i < 0) {
            return HandlerSet.init;
        }
        auto set = entries[i].set;
        erase(cast(size_t) i);
        return set;
    }

    HandlerSet get(BKNode* node) {
        auto i = indexOf(node);
        return i < 0 ? HandlerSet.init : entries[cast(size_t) i].set;
    }

    /// Drop handlers for `node` and the C-owned children the kit frees with
    /// it. Wrapper-owned children detach and keep their entries.
    void removeTree(BKNode* node) {
        remove(node);
        for (int i = 0, n = BK_node_child_count(node); i < n; ++i) {
            auto child = BK_node_child(node, i);
            if (BK_node_ref(child) is null) {
                removeTree(child);
            }
        }
    }

    private void remove(BKNode* node) {
        auto i = indexOf(node);
        if (i >= 0) {
            erase(cast(size_t) i);
        }
    }

    /// Shift later entries down; handler order stays registration order.
    private void erase(size_t i) {
        foreach (j; i + 1 .. entries.length) {
            entries[j - 1] = entries[j];
        }
        entries = entries[0 .. $ - 1];
    }
}

/// The existing wrapper for a C node, owned or borrowed, if any.
private Node wrapperAt(BKNode* h) {
    if (h is null) {
        return null;
    }
    if (auto ref_ = BK_node_ref(h)) {
        return cast(Node) ref_;
    }
    if (auto ref_ = BK_node_borrowed_ref(h)) {
        return cast(Node) ref_;
    }
    return null;
}

/// Wrap a C node: the existing wrapper when the kit has one, else a borrowed one.
package Node wrapNode(BKNode* h) {
    if (h is null) {
        return null;
    }
    if (auto wrapper = wrapperAt(h)) {
        return wrapper;
    }
    auto wrapper = new Node(h, false);
    BK_node_set_borrowed_ref(h, cast(void*) wrapper);
    return wrapper;
}

/// A wrapper's C handle; throws when the wrapper has no node.
package BKNode* requireHandle(Node node, string context, string message) {
    if (node is null || node.handle is null) {
        throw new BuiException(context, message);
    }
    return node.handle;
}

/// A node in the kit's tree.
final class Node {
    /// The C handle, for calls into the raw `bui.kit` API.
    BKNode* handle;

    private {
        bool owned;
        bool freeing;
        size_t handlerEpoch_;
        bool hasHandlers_;
        HandlerStore store_;
        Image keepImage;
        Video keepVideo;
        Object[] keepAlive_;
        const(char)[][] keepStrings_;
    }

    /// Create a node of `type` (`"frame"`, `"button"`, `"slider"`, ...).
    this(string type) {
        ensureRefHooks();
        handle = BK_node_new(cstr(type));
        if (handle is null) {
            throw new BuiException("Node", "unknown node type '" ~ type ~ "'");
        }
        owned = true;
        handlerEpoch_ = nextHandlerEpoch();
        BK_node_set_ref(handle, cast(void*) this);
    }

    /// Wrap an existing C node. `owned` wrappers free it; borrowed ones don't.
    package this(BKNode* existing, bool owned) {
        ensureRefHooks();
        this.handle = existing;
        this.owned = owned;
        handlerEpoch_ = nextHandlerEpoch();
        if (owned) {
            BK_node_set_ref(handle, cast(void*) this);
        }
    }

    ~this() {
        free();
    }

    /// Free the C node. A rooted tree's C-owned children are freed by the kit;
    /// wrapper-owned children are detached and live on until their wrappers go.
    /// A borrowed wrapper only drops its handlers here; the kit owns its node.
    void free() {
        auto h = handle;
        if (h is null || freeing) {
            return;
        }
        freeing = true;
        if (!owned) {
            // The kit may have freed the native node before this wrapper's
            // destructor runs; never dereference `h` here. A new epoch makes
            // the owning wrapper ignore handlers registered through this
            // borrowed wrapper, and a later `on()` replaces them.
            handlerEpoch_ = nextHandlerEpoch();
            store_ = null;
            hasHandlers_ = false;
            freeing = false;
            return;
        }
        dropHandlers(h);
        if (auto parent = BK_node_parent(h)) {
            BK_node_remove(parent, h);
        }
        else if (auto ctx = BK_node_context(h)) {
            // A root skips `node_detach`, so the kit cannot drop popups
            // whose parent lives in this tree. Close them before the
            // parent pointer dangles.
            if (BK_popup_count(ctx) > 0) {
                BK_close_popups(ctx);
            }
        }
        BK_node_free(h);
        handle = null;
        keepImage = null;
        keepVideo = null;
        keepAlive_ = null;
        keepStrings_ = null;
        freeing = false;
    }

    /// The topmost D-owned wrapper above this node. Handlers live there so a
    /// borrowed wrapper rooted by the kit does not keep the owning panel alive.
    private Node handlerOwner() {
        Node owner;
        for (auto h = handle; h !is null; h = BK_node_parent(h)) {
            if (auto ref_ = BK_node_ref(h)) {
                owner = cast(Node) ref_;
            }
        }
        return owner;
    }

    /// Move handlers registered before the node gained an owner into the
    /// owner's store, so one list holds them and registration order survives.
    private void moveHandlersTo(Node owner) {
        bool moved;
        for (auto h = handle; h !is null; h = BK_node_parent(h)) {
            auto wrapper = wrapperAt(h);
            if (wrapper is owner) {
                break;
            }
            if (wrapper is null || wrapper.store_ is null) {
                continue;
            }
            auto set = wrapper.store_.take(handle);
            if (set.handlers.length && set.epoch == handlerEpoch_) {
                if (owner.store_ is null) {
                    owner.store_ = new HandlerStore();
                }
                owner.store_.addAll(handle, set);
                moved = true;
            }
        }
        if (moved) {
            // The wrappers between this node and its owner now guard a subtree
            // with handlers too, so a later move of any of them keeps them.
            markHandlerAncestors();
        }
    }

    /// Remember that this node's subtree holds handlers, so moving it knows
    /// to migrate them. Stale `true` values only cost a walk on the next move.
    private void markHandlerAncestors() {
        for (auto h = handle; h !is null; h = BK_node_parent(h)) {
            if (auto wrapper = wrapperAt(h)) {
                wrapper.hasHandlers_ = true;
            }
        }
    }

    /// Take this node's handlers out of their stores and keep them locally,
    /// so a move cannot leave them in the old owner.
    private void stashHandlers() {
        if (handle is null) {
            return;
        }
        HandlerSet collected;
        for (auto h = handle; h !is null; h = BK_node_parent(h)) {
            auto wrapper = wrapperAt(h);
            if (wrapper is null || wrapper.store_ is null) {
                continue;
            }
            auto set = wrapper.store_.take(handle);
            if (set.handlers.length && set.epoch == handlerEpoch_) {
                collected.handlers ~= set.handlers;
                collected.epoch = set.epoch;
            }
        }
        if (collected.handlers.length) {
            if (store_ is null) {
                store_ = new HandlerStore();
            }
            store_.addAll(handle, collected);
        }
    }

    /// A D-owned child survives its parent's native free, so point each
    /// detached survivor root at the store that still holds its handlers and
    /// stop there: a surviving root owns the wrappers below it, and sharing
    /// with them would let a kit-retained descendant pin the root through a
    /// handler closure. Kit-owned nodes stay part of the tree being freed, so
    /// their surviving descendants are still found.
    private static void shareStoreWithSurvivors(BKNode* h, HandlerStore store) {
        for (int i = 0, n = BK_node_child_count(h); i < n; ++i) {
            auto child = BK_node_child(h, i);
            if (BK_node_ref(child) is null) {
                shareStoreWithSurvivors(child, store);
            }
            else if (auto wrapper = wrapperAt(child)) {
                wrapper.store_ = store;
            }
        }
    }

    /// Put this node's local handlers on its current owner, if it has one.
    private void rehomeHandlers() {
        auto owner = handlerOwner();
        if (owner !is null && owner !is this) {
            moveHandlersTo(owner);
        }
    }

    /// Snapshot the handlers of a subtree before it leaves its owner.
    private void stashSubtreeHandlers() {
        if (hasHandlers_ && handle !is null) {
            stashSubtree(handle);
        }
    }

    private static void stashSubtree(BKNode* h) {
        if (auto wrapper = wrapperAt(h)) {
            wrapper.stashHandlers();
        }
        for (int i = 0, n = BK_node_child_count(h); i < n; ++i) {
            stashSubtree(BK_node_child(h, i));
        }
    }

    /// Give a subtree's handlers to its new owner after a move.
    private void rehomeSubtreeHandlers() {
        if (hasHandlers_ && handle !is null) {
            rehomeSubtree(handle);
        }
    }

    private static void rehomeSubtree(BKNode* h) {
        if (auto wrapper = wrapperAt(h)) {
            wrapper.rehomeHandlers();
        }
        for (int i = 0, n = BK_node_child_count(h); i < n; ++i) {
            rehomeSubtree(BK_node_child(h, i));
        }
    }

    /// This node's handlers: the owning wrapper's store, then any store left
    /// on a wrapper that gained handlers before it was attached.
    private NodeHandler[] handlersOf() {
        for (auto h = handle; h !is null; h = BK_node_parent(h)) {
            if (auto wrapper = wrapperAt(h)) {
                if (wrapper.store_ !is null) {
                    auto found = wrapper.store_.get(handle);
                    if (found.handlers.length && found.epoch == handlerEpoch_) {
                        return found.handlers;
                    }
                }
            }
        }
        if (store_ is null) {
            return null;
        }
        auto found = store_.get(handle);
        return found.epoch == handlerEpoch_ ? found.handlers : null;
    }

    /// Drop this node's and its subtree's handlers before the native node goes
    /// away. Only an owned node reaches here; a borrowed wrapper has no say
    /// over the kit's native node.
    private void dropHandlers(BKNode* h) {
        auto owner = handlerOwner();
        if (owner !is null && owner.store_ !is null) {
            shareStoreWithSurvivors(h, owner.store_);
            owner.store_.removeTree(h);
            if (owner is this) {
                store_ = null;
            }
        }
        dropSubtreeStores(h);
    }

    private static void dropSubtreeStores(BKNode* h) {
        if (auto wrapper = wrapperAt(h)) {
            wrapper.store_ = null;
            wrapper.hasHandlers_ = false;
        }
        for (int i = 0, n = BK_node_child_count(h); i < n; ++i) {
            auto child = BK_node_child(h, i);
            // The kit detaches wrapper-owned children and leaves them alive.
            if (BK_node_ref(child) is null) {
                dropSubtreeStores(child);
            }
        }
    }

    /// Keep `object` alive for as long as this node holds it (custom nodes).
    package void keepAlive(Object object) {
        if (object !is null) {
            keepAlive_ ~= object;
        }
    }

    /// Keep a C string the kit stores without copying (a canvas item's font
    /// family) alive, and return the pointer to hand to the kit. A string with
    /// the same contents reuses the retained copy.
    package const(char)* keepCString(const(char)* value) {
        if (value is null) {
            return null;
        }
        const slice = cslice(value);
        foreach (existing; keepStrings_) {
            if (existing == slice) {
                return existing.ptr;
            }
        }
        keepStrings_ ~= slice;
        return value;
    }

    /// The node's type name.
    string typeName() const {
        return cslice(BK_node_type(handle)).idup;
    }

    /* -- tree -------------------------------------------------------------- */

    /// Add `child`; returns this node for chaining.
    Node add(Node child, int index = -1) {
        if (child is null || child.handle is null) {
            throw new BuiException("Node.add", "no child");
        }
        child.stashSubtreeHandlers();
        if (BK_node_add(handle, child.handle, index) == 0) {
            child.rehomeSubtreeHandlers();
            throw new BuiException("Node.add", "the kit refused the child");
        }
        child.rehomeSubtreeHandlers();
        return this;
    }

    /// Remove `child`; the child wrapper stays valid as a detached node.
    void remove(Node child) {
        if (child is null || child.handle is null) {
            return;
        }
        child.stashSubtreeHandlers();
        BK_node_remove(handle, child.handle);
        child.rehomeSubtreeHandlers();
    }

    int childCount() const {
        return BK_node_child_count(handle);
    }

    /// The child at `i`; a C-owned child comes back as a cached borrowed wrapper.
    Node child(int i) const {
        return wrapNode(BK_node_child(handle, i));
    }

    /// The parent, if there is one.
    Node parent() const {
        return wrapNode(BK_node_parent(handle));
    }

    /// x, y, w, h in window pixels.
    int[4] rect() const {
        int[4] r;
        BK_node_rect(handle, r.ptr);
        return r;
    }

    /// The size the node wants (width, height) in pixels.
    int[2] natural() {
        int[2] s;
        BK_node_natural(handle, s.ptr);
        return s;
    }

    void invalidate() {
        BK_node_invalidate(handle);
    }

    void relayout() {
        BK_node_relayout(handle);
    }

    /* -- properties -------------------------------------------------------- */

    Node set(string key, double value) {
        BK_set_num(handle, cstr(key), value);
        return this;
    }

    Node set(string key, bool value) {
        BK_set_num(handle, cstr(key), value ? 1 : 0);
        return this;
    }

    Node set(string key, const(char)[] value) {
        BK_set_str(handle, cstr(key), cstr(value));
        return this;
    }

    Node set(string key, const float[4] rgba) {
        BK_set_color(handle, cstr(key), rgba.ptr);
        return this;
    }

    /// A string list property (`"items"`, `"headers"`, `"filters"`, ...).
    Node setStrs(string key, const(char)[][] values) {
        auto ptrs = new const(char)*[values.length];
        foreach (i, v; values) {
            ptrs[i] = cstr(v);
        }
        BK_set_strs(handle, cstr(key), ptrs.ptr, cast(int) values.length);
        return this;
    }

    double num(string key) const {
        return BK_get_num(handle, cstr(key));
    }

    const(char)[] str(string key) const {
        return cslice(BK_get_str(handle, cstr(key)));
    }

    bool color(string key, out float[4] rgba) const {
        return BK_get_color(handle, cstr(key), rgba.ptr) != 0;
    }

    /// A zero-copy view of a string list property.
    Strs strs(string key) const {
        return Strs(cast(Node) this, key);
    }

    /// Link number fields so Alt-dragging one edits them together.
    Node linkFields(Node[] fields) {
        auto ptrs = new BKNode*[fields.length];
        foreach (i, f; fields) {
            ptrs[i] = f.handle;
        }
        BK_link_fields(ptrs.ptr, cast(int) fields.length);
        return this;
    }

    /* -- geometry managers ------------------------------------------------- */

    Node geom(int manager) {
        BK_geom_set_manager(handle, manager);
        return this;
    }

    Node geom(string key, double value) {
        BK_geom_set(handle, cstr(key), value);
        return this;
    }

    double geom(string key) const {
        return BK_geom_get(handle, cstr(key));
    }

    /// Tk's packer: `pack("fill", 1)`.
    Node pack(string key, double value) {
        BK_geom_set_manager(handle, BK_GEOM_PACK);
        BK_geom_set(handle, cstr(key), value);
        return this;
    }

    /// Tk's grid: `grid("row", 0)`, `grid("column", 1)`, ...
    Node grid(string key, double value) {
        BK_geom_set_manager(handle, BK_GEOM_GRID);
        BK_geom_set(handle, cstr(key), value);
        return this;
    }

    /// Tk's place: `place("x", 10)`, `place("relwidth", 0.5)`.
    Node place(string key, double value) {
        BK_geom_set_manager(handle, BK_GEOM_PLACE);
        BK_geom_set(handle, cstr(key), value);
        return this;
    }

    /// A frame's grid column/row weight (`column_axis` 0 = column, 1 = row).
    Node frameGridWeight(int columnAxis, int index, double weight, int minsize = 0) {
        BK_frame_grid_weight(handle, columnAxis, index, weight, minsize);
        return this;
    }

    /* -- events ------------------------------------------------------------ */

    /// Add an event handler; all handlers see every event.
    Node on(NodeHandler handler) {
        if (handler !is null) {
            auto owner = handlerOwner();
            if (owner is null) {
                owner = this;
            }
            if (owner is this) {
                if (store_ is null) {
                    store_ = new HandlerStore();
                }
            }
            else {
                moveHandlersTo(owner);
                if (owner.store_ is null) {
                    owner.store_ = new HandlerStore();
                }
            }
            owner.store_.add(handle, handler, handlerEpoch_);
            markHandlerAncestors();
        }
        return this;
    }

    /// Add a handler for one `BK_EV_*` kind.
    Node on(int kind, NodeHandler handler) {
        return on(delegate (NodeEvent e) {
            if (e.kind == kind) {
                handler(e);
            }
        });
    }

    Node onClick(NodeHandler handler) {
        return on(BK_EV_CLICK, handler);
    }

    Node onChange(NodeHandler handler) {
        return on(BK_EV_CHANGE, handler);
    }

    Node onSubmit(NodeHandler handler) {
        return on(BK_EV_SUBMIT, handler);
    }

    Node onActivate(NodeHandler handler) {
        return on(BK_EV_ACTIVATE, handler);
    }

    Node onToggle(NodeHandler handler) {
        return on(BK_EV_TOGGLE, handler);
    }

    Node onBrowse(NodeHandler handler) {
        return on(BK_EV_BROWSE, handler);
    }

    /// The kit's `BKHost.emit` path: dispatch one event to this node's handlers.
    void dispatch(int kind, void* ref_, double a, double b) {
        NodeHandler[] handlers = handlersOf();
        if (handlers.length == 0) {
            return;
        }
        const(char)[] text;
        if (kind == BK_EV_KEY || kind == BK_EV_KEYRELEASE) {
            text = cslice(cast(const(char)*) ref_);
        }
        auto event = NodeEvent(this, kind, ref_, a, b, text);
        foreach (h; handlers) {
            h(event);
        }
    }

    /* -- menus ------------------------------------------------------------- */

    /// Fill a menu button; each row's `onClick` runs on `BK_EV_CALL`.
    Node setMenu(MenuItem[] items) {
        setMenuItems(handle, items);
        return this;
    }

    /* -- images and video -------------------------------------------------- */

    /// Straight RGBA pixels, copied by the kit.
    Node setImage(const(ubyte)[] rgba, int w, int h) {
        if (rgba.length < w * h * 4) {
            throw new BuiException("Node.setImage", "rgba is smaller than w * h * 4");
        }
        BK_node_set_image(handle, rgba.ptr, w, h);
        return this;
    }

    /// A decoded image; the node borrows it, so this keeps it alive.
    Node setImage(Image image) {
        keepImage = image;
        BK_node_set_imbuf(handle, image.handle);
        return this;
    }

    /// A file or URL decoded through the shared cache at the drawn size.
    Node setImageSource(string src, int fit = BK_FIT_CONTAIN) {
        BK_node_set_image_source(handle, cstr(src), fit);
        return this;
    }

    /// An animated source: 0 plays, n > 0 shows frame n - 1 (paused).
    Node setImageFrame(int frame) {
        BK_node_set_image_frame(handle, frame);
        return this;
    }

    /// A player on an `"image"` or `"video"` node; the node borrows it.
    Node setVideo(Video video, int fit = BK_FIT_CONTAIN) {
        keepVideo = video;
        BK_node_set_video(handle, video.handle, fit);
        return this;
    }

    /* -- color ramps, curves, histograms ----------------------------------- */

    int rampCount() {
        return BK_ramp_count(handle);
    }

    void rampGet(int i, out float pos, out float[4] rgba) {
        BK_ramp_get(handle, i, &pos, rgba.ptr);
    }

    void rampSet(const float[] pos, const float[] rgba) {
        if (rgba.length < pos.length * 4) {
            throw new BuiException("Node.rampSet", "rgba needs 4 values per stop");
        }
        BK_ramp_set(handle, pos.ptr, rgba.ptr, cast(int) pos.length);
    }

    int rampActive() {
        return BK_ramp_active(handle);
    }

    void rampEvaluate(float t, out float[4] rgba) {
        BK_ramp_evaluate(handle, t, rgba.ptr);
    }

    void rampSetActiveColor(const float[4] rgba) {
        BK_ramp_set_active_color(handle, rgba.ptr);
    }

    int curveCount(int channel) {
        return BK_curve_count(handle, channel);
    }

    void curveGet(int channel, int i, out float[2] xy) {
        BK_curve_get(handle, channel, i, xy.ptr);
    }

    void curveSet(int channel, const float[] xy) {
        if (xy.length % 2) {
            throw new BuiException("Node.curveSet", "xy needs x/y pairs");
        }
        BK_curve_set(handle, channel, xy.ptr, cast(int) (xy.length / 2));
    }

    float curveEvaluate(int channel, float x) {
        return BK_curve_evaluate(handle, channel, x);
    }

    void histogramSet(const float[] bins, int channels = 1) {
        BK_histogram_set(handle, bins.ptr, cast(int) bins.length, channels);
    }

    void gridviewSetColors(const float[] colors) {
        if (colors.length % 4) {
            throw new BuiException("Node.gridviewSetColors", "colors needs RGBA values");
        }
        BK_gridview_set_colors(handle, colors.ptr, cast(int) (colors.length / 4));
    }
}
