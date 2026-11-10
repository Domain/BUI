/* Integration tests for the D binding: the raw kit ABI, the idiomatic
 * wrappers, ownership and the event path.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
module run;

import bui;
import bui.internal.util : cslice;
import core.memory : GC;
import std.file : read;
import std.path : buildPath, dirName;
import std.stdio : writeln;

private void check(bool condition, string message) {
    if (!condition) {
        throw new Error("bui test failed: " ~ message);
    }
}

void main() {
    testVersion();
    testNodes();
    testRenderAndInput();
    testImage();
    testAnimation();
    testTextarea();
    testCanvas();
    testTree();
    testMenus();
    testCustom();
    testHostErrors();
    testTheme();
    testCapi();
    writeln("bindings/d: all tests passed");
}

private void testVersion() {
    check(BK_version() == BUI_KIT_VERSION, "BK_version matches the D constants");
    check(cslice(BK_version_string()) == BUI_KIT_VERSION_STRING,
          "BK_version_string matches the D constants");
}

private void testNodes() {
    auto root = new Node("frame");
    auto label = new Node("label");
    check(label.typeName() == "label", "node type name");

    label.set("text", "hello");
    check(label.str("text") == "hello", "string property round-trip");
    label.set("visible", false);
    check(label.num("visible") == 0, "boolean property round-trip");
    label.set("visible", true);
    check(label.num("visible") == 1, "boolean property round-trip");

    root.add(label);
    check(root.childCount() == 1, "child count");
    check(root.child(0) is label, "the kit returns the existing D wrapper");
    check(label.parent() is root, "parent wrapper");

    auto extra = new Node("label");
    root.add(extra);
    check(root.childCount() == 2, "second child");
    root.remove(extra);
    check(root.childCount() == 1, "remove detaches the child");
    check(extra.parent() is null, "removed child has no parent");
    extra.free();

    auto dropdown = new Node("dropdown");
    dropdown.setStrs("items", ["one", "two"]);
    check(dropdown.strs("items").length == 2, "string list count");
    check(dropdown.strs("items")[1] == "two", "string list value");

    root.free();
}

private void testRenderAndInput() {
    auto root = new Node("column");
    root.set("padding", 6);

    auto title = new Node("label");
    title.set("text", "D binding");
    root.add(title);

    int clicks;
    auto button = new Node("button");
    button.set("text", "Push");
    button.onClick((NodeEvent) {
        ++clicks;
    });
    root.add(button);
    button.pack("fill", 1);

    auto context = new Context(root);
    auto raster = new Raster(240, 140);

    context.render(raster, true);
    check(raster.width == 240 && raster.height == 140, "raster size");
    check(raster.pixels.length == 240 * 140, "raster pixels");

    const rect = button.rect();
    check(rect[2] > 0 && rect[3] > 0, "button was laid out");

    button.set("text", "Push again");
    check(context.needsRender(), "a property change requests a render");

    const x = rect[0] + rect[2] / 2;
    const y = rect[1] + rect[3] / 2;
    context.press(x, y, 0);
    context.release(x, y, 0);
    check(clicks == 1, "click callback");

    context.clipboard("from D");
    check(context.clipboard() == "from D", "clipboard round-trip");

    raster.free();
    context.free();
    root.free();
}

private void testImage() {
    const(ubyte)[] rgba = [
        255, 0, 0, 255,
        0, 255, 0, 255,
        0, 0, 255, 255,
        255, 255, 255, 255,
    ];
    auto image = Image.fromRgba(rgba, 2, 2);
    check(image.width == 2 && image.height == 2, "image size");
    check(image.pixels.length == 4, "image pixels");
    check(image.toRgba.length == 16, "RGBA copy");
    check(image.frames == 1, "still image frame count");

    auto root = new Node("column");
    auto node = new Node("image");
    node.setImage(image);
    root.add(node);
    node.pack("fill", 1);

    auto context = new Context(root);
    auto raster = new Raster(80, 60);
    context.render(raster, true);
    check(context.pendingError() is null, "image node rendered");

    raster.free();
    context.free();
    root.free();
    image.free();
}

private void testAnimation() {
    const data = read(buildPath(dirName(__FILE_FULL_PATH__), "..", "..", "..",
                             "tests", "images", "anim.gif"));
    auto animation = new Animation(data);
    const info = animation.info();
    check(info[3] > 1, "animated image frame count");

    int delayMs;
    auto frame = animation.next(delayMs);
    check(frame !is null && frame.handle !is null, "animation frame");
    check(frame.width > 0 && frame.height > 0, "animation frame size");
    frame.free();
    animation.free();
}

private void testTextarea() {
    auto textarea = new Node("textarea");
    textarea.set("value", "hello");
    check(textarea.str("value") == "hello", "textarea initial value");

    insertText(textarea, 0, "abc");
    check(textarea.str("value") == "abchello", "textarea insert");
    check(caret(textarea) == 3, "caret after insert");

    setCaret(textarea, 5);
    check(caret(textarea) == 5, "set caret");

    setSelection(textarea, 1, 4);
    check(selection(textarea) == [1, 4], "selection");

    deleteText(textarea, 1, 4);
    check(textarea.str("value") == "aello", "textarea delete");

    setSpans(textarea, [TextSpan.foreground(0, 2, [1, 0, 0, 1])]);
    see(textarea, 0);

    textarea.free();
}

private void testCanvas() {
    auto root = new Node("frame");
    auto canvas = new Node("canvas");
    root.add(canvas);
    canvas.pack("fill", 1);

    setItem(canvas, CanvasItem.rect(1, 4, 4, 60, 40, [0.2f, 0.4f, 0.8f, 1]));
    addItem(canvas, CanvasItem.oval(2, 10, 10, 50, 30, [0.8f, 0.4f, 0.2f, 1]));
    check(itemCount(canvas) == 2, "canvas item count");

    putItem(canvas, 0, CanvasItem.label(3, 8, 8, "label", [1, 1, 1, 1]));
    raiseItem(canvas, 3, true);
    deleteItem(canvas, 2);
    check(itemCount(canvas) == 1, "canvas delete");
    addItem(canvas, CanvasItem.rect(4, 2, 2, 10, 10, [1, 0, 0, 1]));
    check(itemCount(canvas) == 2, "canvas add after delete");
    truncate(canvas, 1);
    check(itemCount(canvas) == 1, "canvas truncate");

    auto styled = CanvasItem.label(5, 8, 24, "styled", [1, 1, 1, 1]);
    styled.family = "Segoe " ~ "UI"; /* a temporary heap string */
    setItem(canvas, styled);
    styled.family = null;
    GC.collect(); /* the canvas keeps the font family alive */

    auto context = new Context(root);
    auto raster = new Raster(100, 80);
    context.render(raster, true);
    check(context.pendingError() is null, "canvas node rendered");

    raster.free();
    context.free();
    root.free();
}

private void testTree() {
    auto tree = new Node("tree");
    auto rootItem = new TreeItem("Root");
    auto child = new TreeItem("Child");
    rootItem.add(child);

    check(rootItem.childCount() == 1, "tree item child count");
    check(rootItem.child(0) is child, "tree item child wrapper");
    check(child.parent() is rootItem, "tree item parent");

    setRoots(tree, [rootItem]);
    check(rowCount(tree) == 2, "visible tree rows");
    check(rowItem(tree, 0) is rootItem, "first row");
    check(rowItem(tree, 1) is child, "second row");

    select(tree, child);
    check(selected(tree) is child, "tree selection");
    select(tree, null);
    check(selected(tree) is null, "tree selection cleared");

    rootItem.free();
    check(rowCount(tree) == 2, "a tree root cannot be freed while the tree holds it");

    child.setValues(["a", "b"]);
    check(child.label == "Child", "tree item label");

    rootItem.expanded = false;
    check(!rootItem.expanded, "tree item collapse");
    check(rowCount(tree) == 1, "collapsed tree rows");
    rootItem.expanded = true;

    setRoots(tree, []);
    check(rowCount(tree) == 0, "empty tree");

    tree.free();
}

private void testMenus() {
    auto root = new Node("frame");
    auto context = new Context(root);
    auto raster = new Raster(320, 200);

    int clicks;
    context.openMenu(root, [new MenuItem("One", {
        ++clicks;
    })]);
    check(context.popupCount() == 1, "menu popup opened");

    auto menu = context.popup(0);
    check(menu !is null, "menu popup handle");
    check(context.menuRowCount(menu) == 1, "menu row count");
    check(context.menuRowText(menu, 0) == "One", "menu row text");

    context.render(raster, true);
    const row = context.menuRowRect(menu, 0);
    check(row[2] > 0 && row[3] > 0, "menu row laid out");
    context.press(row[0] + row[2] / 2, row[1] + row[3] / 2, 0);
    context.release(row[0] + row[2] / 2, row[1] + row[3] / 2, 0);
    check(clicks == 1, "menu callback");
    check(context.popupCount() == 0, "menu closed after picking");

    raster.free();
    context.free();
    root.free();
}

private void testCustom() {
    auto root = new Node("column");
    auto node = new Node("custom");
    root.add(node);
    node.pack("fill", 1);

    int events, frames, draws;
    auto custom = setCustom(node, CustomHandlers(
        (Node, CustomEvent) {
            ++events;
            return 1;
        },
        (Node) {
            ++frames;
        },
        (Node, Raster, const(int)*) {
            ++draws;
        },
        (Node) {}, 80, 40));

    auto context = new Context(root);
    auto raster = new Raster(160, 100);
    context.render(raster, true);
    check(frames >= 1, "custom frame callback");
    check(draws >= 1, "custom draw callback");
    check(custom.raster !is null, "custom draw raster");
    check(custom.pendingError() is null, "no custom callback exception");

    const rect = node.rect();
    context.press(rect[0] + rect[2] / 2, rect[1] + rect[3] / 2, 0);
    context.release(rect[0] + rect[2] / 2, rect[1] + rect[3] / 2, 0);
    check(events >= 1, "custom event callback");

    raster.free();
    context.free();
    root.free();
}

private void testHostErrors() {
    auto root = new Node("frame");
    auto label = new Node("label");
    root.add(label);

    auto context = new Context(root);
    context.setHost(Host(request: {
        throw new Exception("request failed");
    }));

    label.set("text", "changed");
    check(context.pendingError() !is null, "host exception stored");

    bool threw;
    try {
        context.check();
    }
    catch (Exception e) {
        threw = e.msg == "request failed";
    }
    check(threw, "host exception rethrown");
    check(context.pendingError() is null, "host exception cleared");

    context.free();
    root.free();
}

private void testTheme() {
    check(setTheme("dark"), "dark theme");
    check(themeName() == "dark", "theme name");

    float[4] color;
    check(themeColor("region_bg", color), "theme color");
    check(color[3] > 0, "theme color alpha");

    check(setTheme("light"), "light theme");
    check(themeColor("regular.inner", color), "light theme color");
    check(setTheme("dark"), "restore dark theme");

    setScale(1);
    check(scale() == 1.0f, "scale");
    check(unit() > 0, "widget unit");
    check(iconCount() > 0, "icon count");
    check(iconName(1).length > 0, "icon name");
}

private void testCapi() {
    int major, minor, patch;
    bui_get_version(&major, &minor, &patch);
    check(major == 0 && minor == 1 && patch == 0, "stable C API version");
    check(cslice(bui_version_string()) == "BUI 0.1.0", "stable C API version string");
}
