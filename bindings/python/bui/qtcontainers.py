"""Qt's container widgets on the kit, drawn the Blender way: QStackedWidget, QToolBox (Blender
panels), QSplitter (region edges you drag), QToolBar (a row of tool buttons), QDockWidget (a
panel beside the central widget of a QMainWindow) and QTabBar.

SPDX-License-Identifier: GPL-2.0-or-later
"""

import buipy

from bui.qtsyntax import (EV_CHANGE, EV_CLICK, PACK, QAction, QPushButton, QWidget, Qt, Signal)
from bui.tksyntax._widgets import _Sash


def _detach(w):
    if w.parent is not None:
        w.parent.remove(w)


class QStackedWidget(QWidget):
    """Pages on top of each other; only the current one shows."""
    KIND = "frame"
    currentChanged = Signal(int)
    widgetRemoved = Signal(int)

    def _setup(self):
        self._pages = []
        self._current = -1

    def addWidget(self, w):  # noqa: N802
        return self.insertWidget(len(self._pages), w)

    def insertWidget(self, index, w):  # noqa: N802
        if w in self._pages:
            return self._pages.index(w)
        _detach(w)
        index = max(0, min(int(index), len(self._pages)))
        self._pages.insert(index, w)
        self.add(w)
        w.geom(PACK, fill=3, expand=1)
        w.set("visible", False)
        if self._current < 0:
            self.setCurrentIndex(index)  # the first page becomes current, as in Qt
        elif index <= self._current:
            self._current += 1  # the current page stays current
        return index

    def removeWidget(self, w):  # noqa: N802
        if w not in self._pages:
            return
        index = self._pages.index(w)
        self._pages.pop(index)
        self.remove(w)
        if index < self._current:
            self._current -= 1
        elif index == self._current:
            self._current = -1
            if self._pages:
                self.setCurrentIndex(min(index, len(self._pages) - 1))
            else:
                self.currentChanged.emit(-1)
        self.widgetRemoved.emit(index)

    def count(self):
        return len(self._pages)

    def widget(self, index):
        return self._pages[index] if 0 <= index < len(self._pages) else None

    def indexOf(self, w):  # noqa: N802
        return self._pages.index(w) if w in self._pages else -1

    def currentIndex(self):  # noqa: N802
        return self._current

    def currentWidget(self):  # noqa: N802
        return self.widget(self._current)

    def setCurrentIndex(self, index):  # noqa: N802
        if not 0 <= index < len(self._pages) or index == self._current:
            return
        for i, page in enumerate(self._pages):
            page.set("visible", i == index)
        self._current = index
        self.currentChanged.emit(index)

    def setCurrentWidget(self, w):  # noqa: N802
        self.setCurrentIndex(self.indexOf(w))


class _Panel(QWidget):
    """A Blender panel: a header you click to open or close, and its contents."""
    KIND = "panel"


class QToolBox(QWidget):
    """Items as Blender panels. The Qt API keeps one open at a time (setCurrentIndex); clicking
    a header opens or closes that panel on its own, as in Blender, and currentIndex() reads it."""
    KIND = "column"
    currentChanged = Signal(int)

    def _setup(self):
        self._items = []  # (panel, widget)
        self._last = -1

    def addItem(self, w, *args):  # noqa: N802 - (widget, text) or (widget, icon, text)
        return self.insertItem(len(self._items), w, *args)

    def insertItem(self, index, w, *args):  # noqa: N802
        text = str(args[-1]) if args else ""
        panel = _Panel()
        panel.set("text", text)
        if len(args) > 1 and getattr(args[0], "name", ""):
            panel.set("icon", args[0].name)
        _detach(w)
        panel.add(w)
        index = max(0, min(int(index), len(self._items)))
        self._items.insert(index, (panel, w))
        self._order()
        if self._last < 0:
            self.setCurrentIndex(index)
        else:
            panel.set("collapsed", True)
        return index

    def _order(self):
        for panel, _ in self._items:
            if panel.parent is not None:
                self.remove(panel)
        for panel, _ in self._items:
            self.add(panel)

    def removeItem(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            panel, w = self._items.pop(index)
            panel.remove(w)
            self.remove(panel)
            if self.currentIndex() < 0 and self._items:
                self.setCurrentIndex(min(index, len(self._items) - 1))

    def count(self):
        return len(self._items)

    def widget(self, index):
        return self._items[index][1] if 0 <= index < len(self._items) else None

    def indexOf(self, w):  # noqa: N802
        return next((i for i, (_, x) in enumerate(self._items) if x is w), -1)

    def currentIndex(self):  # noqa: N802
        """The first open panel (the user may have opened others: Blender panels are independent)."""
        return next((i for i, (p, _) in enumerate(self._items) if not p.get("collapsed")), -1)

    def currentWidget(self):  # noqa: N802
        return self.widget(self.currentIndex())

    def setCurrentIndex(self, index):  # noqa: N802
        if not 0 <= index < len(self._items):
            return
        for i, (panel, _) in enumerate(self._items):
            panel.set("collapsed", i != index)
        if index != self._last:
            self._last = index
            self.currentChanged.emit(index)

    def setCurrentWidget(self, w):  # noqa: N802
        self.setCurrentIndex(self.indexOf(w))

    def _panel(self, index):
        return self._items[index][0]

    def itemText(self, index):  # noqa: N802
        return self._panel(index).get_str("text")

    def setItemText(self, index, text):  # noqa: N802
        self._panel(index).set("text", str(text))

    def itemToolTip(self, index):  # noqa: N802
        return self._panel(index).get_str("description")

    def setItemToolTip(self, index, tip):  # noqa: N802
        self._panel(index).set("description", str(tip))

    def isItemEnabled(self, index):  # noqa: N802
        return bool(self._panel(index).get("enabled"))

    def setItemEnabled(self, index, enabled):  # noqa: N802
        self._panel(index).set("enabled", bool(enabled))

    def setItemIcon(self, index, icon):  # noqa: N802
        if getattr(icon, "name", ""):
            self._panel(index).set("icon", icon.name)


class QSplitter(QWidget):
    """Widgets side by side (or stacked) with Blender's region edges between them to drag."""
    KIND = "frame"
    splitterMoved = Signal(int, int)

    def __init__(self, orientation=None, parent=None):
        if isinstance(orientation, QWidget):
            orientation, parent = None, orientation
        self._orientation = orientation or Qt.Horizontal
        super().__init__(parent)

    def _setup(self):
        self._panes = []
        self._sashes = []
        self._sizes = {}
        self._stretch = {}
        self._handle = 4
        self._collapsible = True

    def _horizontal(self):
        return self._orientation == Qt.Horizontal

    def orientation(self):
        return self._orientation

    def setOrientation(self, orientation):  # noqa: N802
        self._orientation = orientation
        self._relayout()

    def addWidget(self, w):  # noqa: N802
        self.insertWidget(len(self._panes), w)

    def insertWidget(self, index, w):  # noqa: N802
        if w in self._panes:
            self._panes.remove(w)
        _detach(w)
        self._panes.insert(max(0, min(int(index), len(self._panes))), w)
        self._relayout()

    def replaceWidget(self, index, w):  # noqa: N802
        old = self._panes[index]
        self.remove(old)
        self._sizes.pop(old, None)
        self._panes[index] = w
        _detach(w)
        self._relayout()
        return old

    def count(self):
        return len(self._panes)

    def widget(self, index):
        return self._panes[index] if 0 <= index < len(self._panes) else None

    def indexOf(self, w):  # noqa: N802
        return self._panes.index(w) if w in self._panes else -1

    def handleWidth(self):  # noqa: N802
        return self._handle

    def setHandleWidth(self, width):  # noqa: N802
        self._handle = int(width)
        self._relayout()

    def setStretchFactor(self, index, stretch):  # noqa: N802
        self._stretch[self._panes[index]] = int(stretch)
        self._relayout()

    def childrenCollapsible(self):  # noqa: N802
        return self._collapsible

    def setChildrenCollapsible(self, b):  # noqa: N802
        self._collapsible = bool(b)

    def sizes(self):
        return [p.width() if self._horizontal() else p.height() for p in self._panes]

    def setSizes(self, sizes):  # noqa: N802
        for i, size in enumerate(sizes[:len(self._panes)]):
            self._set_pane_size(i, size, emit=False)

    def _relayout(self):
        for node in self._sashes + [p for p in self._panes if p.parent is self]:
            self.remove(node)
        self._sashes = []
        h = self._horizontal()
        side = 2 if h else 0
        # without stretch factors the last pane takes the rest of the space, as Qt's does
        stretchy = [p for p in self._panes if self._stretch.get(p, 0)] or self._panes[-1:]
        for i, pane in enumerate(self._panes):
            if i:
                sash = _Sash(self, i - 1)
                sash.set("cursor", 1.0 if h else 2.0)
                self.add(sash)
                sash.geom(PACK, side=side, fill=2 if h else 1,
                          **{"reqwidth" if h else "reqheight": self._handle})
                self._sashes.append(sash)
            self.add(pane)
            pane.geom(PACK, side=side, fill=3, expand=1 if pane in stretchy else 0,
                      **{"reqwidth" if h else "reqheight": int(self._sizes.get(pane, 0))})

    def _set_pane_size(self, index, size, emit=True):
        pane = self._panes[index]
        size = max(0 if self._collapsible else 1, int(size))
        self._sizes[pane] = size
        pane.geom(PACK, **{"reqwidth" if self._horizontal() else "reqheight": size})
        if emit:
            self.splitterMoved.emit(size, index + 1)


class _ToolButton(QPushButton):
    """A toolbar's button for one action."""

    def __init__(self, bar, action):
        super().__init__(action.text())
        self._bar, self._action = bar, action
        icon = getattr(action, "_icon", None)
        if getattr(icon, "name", ""):
            self.set("icon", icon.name)
        self.set("enabled", action.isEnabled())

    def _event(self, kind, ref, a, b):
        if kind == EV_CLICK:
            a = self._action
            if a.isCheckable():
                a.setChecked(not a.isChecked())
            a.triggered.emit(a.isChecked())
            self._bar.actionTriggered.emit(a)


class QToolBar(QWidget):
    """A row of tool buttons, one per action (Blender's header row)."""
    KIND = "row"
    actionTriggered = Signal(object)
    toolButtonStyleChanged = Signal(int)

    def __init__(self, title="", parent=None):
        if isinstance(title, QWidget):
            title, parent = "", title
        super().__init__(parent)
        self.setWindowTitle(str(title))

    def _setup(self):
        self._items = {}  # action -> its node (a button, a separator or a widget)
        self._style = Qt.ToolButtonIconOnly

    def addAction(self, *args):  # noqa: N802 - (action) / (text[, slot]) / (icon, text[, slot])
        action = args[0] if isinstance(args[0], QAction) else None
        if action is None:
            icon = args[0] if not isinstance(args[0], str) else None
            rest = args[1:] if icon is not None else args
            action = QAction(str(rest[0]) if rest else "", self)
            action._icon = icon
            if len(rest) > 1 and callable(rest[1]):
                action.triggered.connect(rest[1])
        self._insert(None, action, _ToolButton(self, action))
        self._apply_style(self._items[action])
        return action

    def addWidget(self, w):  # noqa: N802
        action = QAction("", self)
        _detach(w)
        self._insert(None, action, w)
        return action

    def addSeparator(self):  # noqa: N802
        action = QAction("", self)
        action._separator = True
        self._insert(None, action, buipy.KitNode("separator"))
        return action

    def insertWidget(self, before, w):  # noqa: N802
        action = QAction("", self)
        _detach(w)
        self._insert(before, action, w)
        return action

    def _insert(self, before, action, node):
        QWidget.insertAction(self, before, action)
        self._items[action] = node
        order = self.actions()
        for a in order:
            n = self._items[a]
            if n.parent is self:
                self.remove(n)
        for a in order:
            self.add(self._items[a])

    def removeAction(self, action):  # noqa: N802
        node = self._items.pop(action, None)
        if node is not None:
            self.remove(node)
        QWidget.removeAction(self, action)

    def clear(self):
        for a in self.actions():
            self.removeAction(a)

    def widgetForAction(self, action):  # noqa: N802
        return self._items.get(action)

    def toolButtonStyle(self):  # noqa: N802
        return self._style

    def setToolButtonStyle(self, style):  # noqa: N802
        if style != self._style:
            self._style = style
            for node in self._items.values():
                self._apply_style(node)
            self.toolButtonStyleChanged.emit(style)

    def _apply_style(self, node):
        if isinstance(node, _ToolButton):
            # icon-only shows just the icon when the action has one (Qt's default for toolbars)
            has_icon = bool(node.get_str("icon"))
            node.set("icon_only", self._style == Qt.ToolButtonIconOnly and has_icon)

    def orientation(self):
        return Qt.Horizontal


class QDockWidget(QWidget):
    """A titled panel beside a QMainWindow's central widget (QMainWindow.addDockWidget)."""
    KIND = "panel"
    visibilityChanged = Signal(bool)
    featuresChanged = Signal(int)
    DockWidgetClosable, DockWidgetMovable, DockWidgetFloatable = 0x01, 0x02, 0x04
    NoDockWidgetFeatures = 0

    def __init__(self, title="", parent=None):
        if isinstance(title, QWidget):
            title, parent = "", title
        super().__init__(parent)
        self.setWindowTitle(str(title))

    def _setup(self):
        self._widget = None
        self._features = self.DockWidgetClosable | self.DockWidgetMovable | self.DockWidgetFloatable
        self._toggle = None

    def setWindowTitle(self, title):  # noqa: N802
        self._title = str(title)
        self.set("text", self._title)

    def windowTitle(self):  # noqa: N802
        return self._title

    def setWidget(self, w):  # noqa: N802
        if self._widget is not None:
            self.remove(self._widget)
        self._widget = w
        if w is not None:
            _detach(w)
            self.add(w)

    def widget(self):
        return self._widget

    def features(self):
        return self._features

    def setFeatures(self, features):  # noqa: N802
        if features != self._features:
            self._features = features
            self.featuresChanged.emit(features)

    def isFloating(self):  # noqa: N802
        return False  # docks stay docked in their window

    def setVisible(self, visible):  # noqa: N802
        was = self.isVisible()
        super().setVisible(visible)
        if self._toggle is not None:
            self._toggle._checked = bool(visible)
        if was != bool(visible):
            self.visibilityChanged.emit(bool(visible))

    def toggleViewAction(self):  # noqa: N802
        """A checkable action that shows and hides the dock (for a View menu)."""
        if self._toggle is None:
            self._toggle = QAction(self._title, self)
            self._toggle.setCheckable(True)
            self._toggle._checked = self.isVisible()
            self._toggle.toggled.connect(self.setVisible)
        return self._toggle


class QTabBar(QWidget):
    """Tabs without pages (QTabWidget has both)."""
    KIND = "tabs"
    currentChanged = Signal(int)
    tabBarClicked = Signal(int)

    def _setup(self):
        self._titles = []

    def addTab(self, *args):  # noqa: N802 - (text) or (icon, text)
        return self.insertTab(len(self._titles), *args)

    def insertTab(self, index, *args):  # noqa: N802
        index = max(0, min(int(index), len(self._titles)))
        self._titles.insert(index, str(args[-1]))
        self.set("items", self._titles)
        if len(self._titles) == 1:
            self.currentChanged.emit(0)  # Qt: the first tab becomes current
        return index

    def removeTab(self, index):  # noqa: N802
        if 0 <= index < len(self._titles):
            self._titles.pop(index)
            self.set("items", self._titles)

    def count(self):
        return len(self._titles)

    def currentIndex(self):  # noqa: N802
        return int(self.get("current")) if self._titles else -1

    def setCurrentIndex(self, index):  # noqa: N802
        if 0 <= index < len(self._titles) and index != self.currentIndex():
            self.set("current", float(index))
            self.currentChanged.emit(int(index))

    def tabText(self, index):  # noqa: N802
        return self._titles[index] if 0 <= index < len(self._titles) else ""

    def setTabText(self, index, text):  # noqa: N802
        self._titles[index] = str(text)
        self.set("items", self._titles)

    def _event(self, kind, ref, a, b):
        if kind == EV_CHANGE:
            self.tabBarClicked.emit(int(a))
            self.currentChanged.emit(int(a))
