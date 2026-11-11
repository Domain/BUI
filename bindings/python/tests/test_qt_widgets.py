"""Qt syntax beyond the basic widgets: containers (QStackedWidget, QToolBox, QSplitter, QToolBar,
QDockWidget, QTabBar, QMainWindow's docks and toolbars), model/view, QMessageBox / QInputDialog,
QSettings, QKeySequence / QShortcut, QClipboard and QObject / QWidget behavior. Headless: widgets
lay out and render into a raster, no window opens.

SPDX-License-Identifier: GPL-2.0-or-later
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bui  # noqa: E402,F401  (locates buipy)
import buipy  # noqa: E402
from bui import qtsyntax as q  # noqa: E402
from bui.components.core import EV_CHANGE, EV_DOUBLE, EV_MOTION, EV_PRESS  # noqa: E402


def render(widget, w=400, h=300):
    ctx = buipy.KitContext(widget)
    ctx.render(w, h, buipy.Raster(w, h), True)
    return ctx


def spy(signal):
    got = []
    signal.connect(lambda *a: got.append(a))
    return got


def test_stacked_widget():
    s = q.QStackedWidget()
    pages = [q.QLabel("page %d" % i) for i in range(3)]
    changed = spy(s.currentChanged)
    for p in pages:
        s.addWidget(p)
    assert s.count() == 3 and s.currentIndex() == 0 and s.currentWidget() is pages[0], "the first page is current"
    assert [p.isVisible() for p in pages] == [True, False, False]
    s.setCurrentWidget(pages[2])
    assert s.currentIndex() == 2 and [p.isVisible() for p in pages] == [False, False, True]
    assert changed == [(0,), (2,)]
    s.insertWidget(0, q.QLabel("front"))
    assert s.currentWidget() is pages[2] and s.currentIndex() == 3, "inserting before keeps the current page"
    removed = spy(s.widgetRemoved)
    s.removeWidget(pages[2])
    assert removed == [(3,)] and s.currentWidget() is pages[1], "removing the current page shows its neighbour"
    assert s.indexOf(pages[2]) == -1
    render(s)


def test_toolbox_is_blender_panels():
    box = q.QToolBox()
    a, b, c = q.QLabel("a"), q.QLabel("b"), q.QLabel("c")
    box.addItem(a, "Alpha")
    box.addItem(b, q.QIcon(), "Beta")
    box.insertItem(1, c, "Gamma")
    assert [box.itemText(i) for i in range(3)] == ["Alpha", "Gamma", "Beta"]
    assert box.currentIndex() == 0 and box.indexOf(b) == 2
    panels = [box._panel(i) for i in range(3)]
    assert all(p.type == "panel" for p in panels), "each item is a Blender panel"
    changed = spy(box.currentChanged)
    box.setCurrentWidget(b)
    assert [bool(p.get("collapsed")) for p in panels] == [True, True, False], "the Qt API keeps one open"
    assert changed == [(2,)] and box.currentWidget() is b
    panels[0].set("collapsed", False)  # a click on a header opens that panel on its own, as in Blender
    assert box.currentIndex() == 0, "currentIndex reads the panels"
    box.setItemEnabled(1, False)
    box.setItemToolTip(1, "tip")
    assert not box.isItemEnabled(1) and box.itemToolTip(1) == "tip"
    box.removeItem(0)
    assert box.count() == 2 and box.widget(0) is c
    render(box)


def test_splitter_sizes_and_dragging():
    split = q.QSplitter(q.Qt.Horizontal)
    left, right = q.QWidget(), q.QWidget()
    split.addWidget(left)
    split.addWidget(right)
    split.setSizes([120, 200])
    ctx = buipy.KitContext(split)
    r = buipy.Raster(400, 100)
    ctx.render(400, 100, r, True)
    assert left.width() == 120, left.width()
    assert left.width() + right.width() + split.handleWidth() == 400, "the last pane takes the rest"
    moved = spy(split.splitterMoved)
    sash = split._sashes[0]
    sash._on_event(EV_PRESS, None, 1, 1)
    sash._on_event(EV_MOTION, None, 41, 1)  # drag the region edge 40 px right
    ctx.render(400, 100, r, True)
    assert left.width() == 160 and moved and moved[-1] == (160, 1)
    split.setOrientation(q.Qt.Vertical)
    ctx.render(400, 300, buipy.Raster(400, 300), True)
    assert left.height() == 160 and left.width() == 400, "vertical: the size is the height"


def test_toolbar_actions():
    bar = q.QToolBar("Tools")
    hits, triggered = [], spy(bar.actionTriggered)
    save = bar.addAction("Save", lambda *a: hits.append("save"))
    bar.addSeparator()
    grid = q.QAction("Grid", bar)
    grid.setCheckable(True)
    bar.addAction(grid)
    assert [a.text() for a in bar.actions()] == ["Save", "", "Grid"]
    bar.widgetForAction(save).click()
    bar.widgetForAction(grid).click()
    assert hits == ["save"] and grid.isChecked() and [t[0] for t in triggered] == [save, grid]
    bar.removeAction(save)
    assert len(bar.actions()) == 2 and bar.widgetForAction(save) is None
    bar.setToolButtonStyle(q.Qt.ToolButtonTextOnly)
    assert bar.toolButtonStyle() == q.Qt.ToolButtonTextOnly
    render(bar, 300, 40)


def test_main_window_docks_toolbars_status():
    win = q.QMainWindow()
    central = q.QWidget()
    win.setCentralWidget(central)
    dock = q.QDockWidget("Outliner")
    dock.setWidget(q.QLabel("tree"))
    win.addDockWidget(q.Qt.LeftDockWidgetArea, dock)
    bar = win.addToolBar("Main")
    bar.addAction("New")
    win.statusBar().showMessage("Ready")
    render(win, 500, 300)
    assert win.dockWidgetArea(dock) == q.Qt.LeftDockWidgetArea and win.toolBarArea(bar) == q.Qt.TopToolBarArea
    assert bar.y() < central.y(), "the toolbar sits above the central widget"
    assert dock.x() < central.x() and dock.x() + dock.width() <= central.x(), "the dock sits to its left"
    status = win.statusBar()
    assert status.y() >= central.y() + central.height(), "the status bar is at the bottom"
    assert dock.windowTitle() == "Outliner" and dock.type == "panel"
    toggle = dock.toggleViewAction()
    seen = spy(dock.visibilityChanged)
    toggle.setChecked(False)
    assert not dock.isVisible() and seen == [(False,)] and not toggle.isChecked()
    assert win.takeCentralWidget() is central and win.centralWidget() is None


def test_tab_bar():
    tabs = q.QTabBar()
    changed = spy(tabs.currentChanged)
    tabs.addTab("One")
    tabs.addTab("Two")
    tabs.insertTab(0, "Zero")
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Zero", "One", "Two"]
    tabs.setCurrentIndex(2)
    assert tabs.currentIndex() == 2 and changed[-1] == (2,)
    clicked = spy(tabs.tabBarClicked)
    tabs._event(EV_CHANGE, None, 1, 0)
    assert clicked == [(1,)]
    tabs.removeTab(0)
    assert tabs.count() == 2


def test_model_view():
    model = q.QStandardItemModel()
    model.setHorizontalHeaderLabels(["Name", "Type"])
    scene = q.QStandardItem("Scene")
    cube = q.QStandardItem("Cube")
    scene.appendRow([cube, q.QStandardItem("Mesh")])
    model.appendRow([scene, q.QStandardItem("Collection")])
    model.appendRow([q.QStandardItem("Camera"), q.QStandardItem("Camera")])
    assert model.rowCount() == 2 and model.columnCount() == 2
    idx = model.index(0, 0)
    assert idx.data() == "Scene" and model.rowCount(idx) == 1 and model.index(0, 1, idx).data() == "Mesh"
    assert cube.index().parent() == idx and model.itemFromIndex(model.index(0, 0, idx)) is cube

    tree = q.QTreeView()
    tree.setModel(model)
    render(tree)
    assert len(tree._nodes) == 3, "two rows and a child, nested"
    current = spy(tree.selectionModel().currentChanged)
    tree.setCurrentIndex(model.index(1, 1))
    assert tree.currentIndex() == model.index(1, 0) and current, "a row is current (its first column)"
    clicks = spy(tree.clicked)
    tree._on_event(EV_PRESS, None, 0, 0)
    assert clicks == [(model.index(1, 0),)]
    cube.setText("Suzanne")  # the model reports the change; the view redraws it
    assert tree._nodes[cube.index()].label == "Suzanne"
    assert tree.currentIndex() == model.index(1, 0), "the current row survives a redraw"

    table = q.QTableView()
    table.setModel(model)
    assert len(table._nodes) == 2, "a table shows the top rows only"
    table.selectRow(0)
    assert table.selectionModel().selectedRows() == [model.index(0, 0)]

    names = q.QStringListModel(["Cube", "Light"])
    lst = q.QListView()
    lst.setModel(names)
    assert [n.label for n in lst._nodes.values()] == ["Cube", "Light"]
    names.insertRows(1, 1)
    names.setData(names.index(1), "Camera")
    assert [n.label for n in lst._nodes.values()] == ["Cube", "Camera", "Light"]
    double = spy(lst.doubleClicked)
    lst.setCurrentIndex(names.index(2))
    lst._on_event(EV_DOUBLE, None, 0, 0)
    assert double == [(names.index(2),)]
    assert names.match(names.index(0), q.Qt.DisplayRole, "am", -1, q.Qt.MatchContains) == [names.index(1)]
    assert [i.text() for i in model.findItems("Cam", q.Qt.MatchContains)] == ["Camera"]


def test_message_box_and_input_dialog():
    box = q.QMessageBox(q.QMessageBox.Question, "Quit", "Save changes?",
                        q.QMessageBox.Save | q.QMessageBox.Discard | q.QMessageBox.Cancel)
    box.setInformativeText("The file has unsaved changes.")
    assert [b.text() for b in box.buttons()] == ["Save", "Cancel", "Discard"] or \
        sorted(b.text() for b in box.buttons()) == ["Cancel", "Discard", "Save"]
    assert box.icon() == q.QMessageBox.Question and box._icon_label.isVisible(), "Blender's question icon"
    done = spy(box.finished)
    box.button(q.QMessageBox.Discard).click()
    assert box.result() == q.QMessageBox.Discard and box.clickedButton() is box.button(q.QMessageBox.Discard)
    assert done == [(q.QMessageBox.Discard,)]
    assert box.standardButtons() == q.QMessageBox.Save | q.QMessageBox.Discard | q.QMessageBox.Cancel
    render(box, 300, 120)

    d = q.QInputDialog()
    d.setInputMode(q.QInputDialog.IntInput)
    d.setIntRange(0, 10)
    d.setIntValue(42)
    assert d.intValue() == 10, "clamped to the range"
    picked = spy(d.intValueSelected)
    d.accept()
    assert picked == [(10,)] and d.result() == 1
    d2 = q.QInputDialog()
    d2.setComboBoxItems(["Low", "High"])
    d2._items.setCurrentIndex(1)
    assert d2.textValue() == "High"


def test_settings_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "app.ini")
        s = q.QSettings(path, q.QSettings.IniFormat)
        s.setValue("geometry/width", 640)
        s.beginGroup("view")
        s.setValue("grid", True)
        s.setValue("recent", ["a.blend", "b.blend"])
        s.endGroup()
        s.beginWriteArray("files")
        for i, name in enumerate(["x", "y"]):
            s.setArrayIndex(i)
            s.setValue("name", name)
        s.endArray()
        t = q.QSettings(path, q.QSettings.IniFormat)  # read back from the file
        assert t.value("geometry/width", type=int) == 640
        assert t.value("view/grid", type=bool) is True
        assert t.value("view/recent", type=list) == ["a.blend", "b.blend"]
        assert t.value("missing", "fallback") == "fallback" and not t.contains("missing")
        assert t.childGroups() == ["files", "geometry", "view"]
        n = t.beginReadArray("files")
        names = []
        for i in range(n):
            t.setArrayIndex(i)
            names.append(t.value("name"))
        t.endArray()
        assert names == ["x", "y"]
        t.beginGroup("view")
        assert t.childKeys() == ["grid", "recent"]
        t.remove("")
        t.endGroup()
        assert not q.QSettings(path, q.QSettings.IniFormat).contains("view/grid"), "remove persists"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert "[geometry]" in text and "width=640" in text, "Qt's INI layout"


def test_keys_shortcuts_clipboard():
    assert q.QKeySequence("ctrl+shift+s").toString() == "Ctrl+Shift+S"
    assert q.QKeySequence(q.QKeySequence.Copy) == "Ctrl+C" and q.QKeySequence("Ctrl+C") == q.QKeySequence.Copy
    assert q.QKeySequence("").isEmpty()

    w = q.QWidget()
    w._ctx = buipy.KitContext(w)  # the window's context, as QWidget.show makes it
    fired = []
    q.QShortcut(q.QKeySequence("Ctrl+K"), w, lambda: fired.append(1))
    button = q.QPushButton("Run", w)
    clicks = spy(button.clicked)
    button.setShortcut("Ctrl+R")
    assert button.shortcut() == "Ctrl+R"
    from bui.qtcore import bind_shortcuts
    bind_shortcuts(w)
    ctrl = 0x2  # BK_CTRL
    w._ctx.key("", "k", ctrl)
    w._ctx.key("", "r", ctrl)
    assert fired == [1] and len(clicks) == 1, "the kit's key binding ran both"

    cb = q.QApplication.clipboard()
    cb.setText("hello")
    assert cb.text() == "hello" and q.QApplication.clipboard() is cb


def test_object_and_widget_behavior():
    w = q.QWidget()
    w.setObjectName("root")
    lay = q.QVBoxLayout(w)
    a, b = q.QPushButton("A"), q.QLineEdit()
    b.setObjectName("field")
    lay.addWidget(a)
    lay.addWidget(b)
    render(w)
    assert w.findChild(q.QLineEdit) is b and w.findChild(name="field") is b
    assert w.findChildren(q.QPushButton) == [a]
    assert w.isAncestorOf(b) and not b.isAncestorOf(w)
    p = b.mapTo(w, q.QPoint(1, 2))
    assert (p.x(), p.y()) == (b.x() + 1, b.y() + 2) or (p.x(), p.y()) == (
        b.absolutePos()[0] - w.absolutePos()[0] + 1, b.absolutePos()[1] - w.absolutePos()[1] + 2)
    assert w.childAt(b.mapTo(w, q.QPoint(2, 2))) is b

    hits = spy(a.clicked)
    old = a.blockSignals(True)
    a.click()
    assert hits == [] and old is False and a.signalsBlocked()
    a.blockSignals(False)
    a.click()
    assert len(hits) == 1, "blocked signals don't reach their slots"

    w.setProperty("mode", "edit")
    assert w.property("mode") == "edit" and w.dynamicPropertyNames() == [b"mode"]
    assert b.property("text") == "", "a Qt property reads through its getter"
    assert w.inherits("QWidget") and not w.inherits("QLabel")
    w.setStatusTip("hint")
    w.setToolTip("tip")
    assert w.statusTip() == "hint" and w.toolTip() == "tip"
    w.setFocusPolicy(q.Qt.StrongFocus)
    assert w.focusPolicy() == q.Qt.StrongFocus, "the setter isn't a no-op any more"
    q.QApplication.setApplicationName("Demo")
    assert q.QApplication.applicationName() == "Demo"
    shown = []

    class Probe(q.QWidget):
        def showEvent(self, e):  # noqa: N802
            shown.append("show")

        def hideEvent(self, e):  # noqa: N802
            shown.append("hide")

    child = Probe(w)
    child.setVisible(False)
    child.setVisible(True)
    assert shown == ["hide", "show"]
    act = q.QAction("Copy", w)
    w.addAction(act)
    assert w.actions() == [act]
    w.removeAction(act)
    assert w.actions() == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ok")
