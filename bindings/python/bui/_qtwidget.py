"""QObject and QWidget behavior beyond geometry and painting, for `bui.qtsyntax.QWidget`.

Signal blocking, dynamic properties, finding children, mapping points between widgets, actions,
show / hide events, and the descriptive properties Qt only stores (status tip, what's this,
accessible name). Everything here acts on the widget's kit node or is Qt's own stored state.

SPDX-License-Identifier: GPL-2.0-or-later
"""

from bui._qtprops import QtProperty, qt_properties


def _name(n):
    return n.decode() if isinstance(n, bytes) else str(n)


class _KitView:
    """A QWidget seen as a plain kit node, for code shared with the tkinter layer: `rect` is the
    node's (x, y, w, h), not Qt's rect() method; everything else is the widget's."""
    __slots__ = ("_w",)

    def __init__(self, w):
        self._w = w

    @property
    def rect(self):
        return self._w._r

    def __getattr__(self, name):
        return getattr(self._w, name)


@qt_properties(
    statusTip=QtProperty(default=""), whatsThis=QtProperty(default=""),
    accessibleName=QtProperty(default=""), accessibleDescription=QtProperty(default=""),
    accessibleIdentifier=QtProperty(default=""), windowIconText=QtProperty(default=""),
    windowFilePath=QtProperty(default=""), windowRole=QtProperty(default=""),
    toolTipDuration=QtProperty(default=-1), focusPolicy=QtProperty(default=0),
    contextMenuPolicy=QtProperty(default=1), layoutDirection=QtProperty(default=0),
    inputMethodHints=QtProperty(default=0), windowModality=QtProperty(default=0),
)
class QWidgetMore:
    @property
    def _node(self):
        return _KitView(self)

    # -- QObject -----------------------------------------------------------------------------------
    def blockSignals(self, block):  # noqa: N802
        """Stop (or resume) this object's signals; returns the previous state, as Qt does."""
        old = self.__dict__.get("_blocked", False)
        self.__dict__["_blocked"] = bool(block)
        return old

    def signalsBlocked(self):  # noqa: N802
        return self.__dict__.get("_blocked", False)

    def setProperty(self, name, value):  # noqa: N802
        """A dynamic property (Qt returns False for those: they aren't declared ones)."""
        self.__dict__.setdefault("_dyn", {})[_name(name)] = value
        return False

    def property(self, name):
        name = _name(name)
        dyn = self.__dict__.get("_dyn", {})
        if name in dyn:
            return dyn[name]
        getter = getattr(type(self), name, None)
        return getter(self) if callable(getter) else None

    def dynamicPropertyNames(self):  # noqa: N802
        return [n.encode() for n in self.__dict__.get("_dyn", {})]

    def inherits(self, class_name):
        return any(c.__name__ == _name(class_name) for c in type(self).__mro__)

    def isWidgetType(self):  # noqa: N802
        return True

    def findChildren(self, type_=None, name=""):  # noqa: N802
        """Descendant widgets (through layouts too), filtered by class and object name."""
        from bui.qtsyntax import QWidget, _kids
        out, stack = [], list(_kids(self))
        while stack:
            node = stack.pop(0)
            if isinstance(node, QWidget) and (type_ is None or isinstance(node, type_)) and (
                    not name or node.objectName() == name):
                out.append(node)
            stack.extend(_kids(node))
        return out

    def findChild(self, type_=None, name=""):  # noqa: N802
        found = self.findChildren(type_, name)
        return found[0] if found else None

    def deleteLater(self):  # noqa: N802
        parent = self.parent
        if parent is not None:
            parent.remove(self)

    # -- tree and state ------------------------------------------------------------------------------
    def toolTip(self):  # noqa: N802
        return self.get_str("description")

    def isHidden(self):  # noqa: N802
        return not self.isVisible()

    def setHidden(self, hidden):  # noqa: N802
        self.setVisible(not hidden)

    def setDisabled(self, disabled):  # noqa: N802
        self.setEnabled(not disabled)

    def isTopLevel(self):  # noqa: N802
        return self.isWindow()

    def isAncestorOf(self, child):  # noqa: N802
        w = child.parentWidget() if child is not None else None
        while w is not None:
            if w is self:
                return True
            w = w.parentWidget()
        return False

    def _up_to(self, ancestor):
        w = self
        while w is not None and w is not ancestor:
            yield w
            w = w.parentWidget()

    def isVisibleTo(self, ancestor):  # noqa: N802
        return all(w.isVisible() for w in self._up_to(ancestor))

    def isEnabledTo(self, ancestor):  # noqa: N802
        return all(w.isEnabled() for w in self._up_to(ancestor))

    def isLeftToRight(self):  # noqa: N802
        return self.layoutDirection() == 0

    def isRightToLeft(self):  # noqa: N802
        return self.layoutDirection() == 1

    # -- geometry between widgets -------------------------------------------------------------------------
    def _origin(self):
        x, y = self.absolutePos()
        return x, y

    def mapTo(self, parent, pos):  # noqa: N802
        from bui.qtsyntax import QPoint
        (ax, ay), (bx, by) = self._origin(), parent._origin()
        return QPoint(pos.x() + ax - bx, pos.y() + ay - by)

    def mapFrom(self, parent, pos):  # noqa: N802
        from bui.qtsyntax import QPoint
        (ax, ay), (bx, by) = self._origin(), parent._origin()
        return QPoint(pos.x() - ax + bx, pos.y() - ay + by)

    def mapToParent(self, pos):  # noqa: N802
        from bui.qtsyntax import QPoint
        return QPoint(pos.x() + self.x(), pos.y() + self.y())

    def mapFromParent(self, pos):  # noqa: N802
        from bui.qtsyntax import QPoint
        return QPoint(pos.x() - self.x(), pos.y() - self.y())

    def childAt(self, x, y=None):  # noqa: N802
        """The deepest child widget at a point of this widget, or None."""
        if y is None:
            x, y = x.x(), x.y()
        ox, oy = self._origin()
        hit = None
        for w in self.findChildren():
            if not w.isVisibleTo(self):
                continue
            wx, wy = w._origin()
            if wx <= ox + x < wx + w.width() and wy <= oy + y < wy + w.height():
                hit = w  # findChildren lists parents before their children: the last hit is deepest
        return hit

    def childrenRect(self):  # noqa: N802
        from bui.qtsyntax import QRect
        kids = [w for w in self.children() if w.isVisible()]
        if not kids:
            return QRect(0, 0, 0, 0)
        x0, y0 = min(w.x() for w in kids), min(w.y() for w in kids)
        x1 = max(w.x() + w.width() for w in kids)
        y1 = max(w.y() + w.height() for w in kids)
        return QRect(x0, y0, x1 - x0, y1 - y0)

    def adjustSize(self):  # noqa: N802
        """Resize to the size the contents need (the natural size)."""
        self.resize(*self.natural())

    def minimumSizeHint(self):  # noqa: N802
        return self.sizeHint()

    def hasFocus(self):  # noqa: N802
        """Whether this widget has the keyboard (text) focus of its window."""
        ctx = self.window()._ctx
        return ctx is not None and ctx.focus is self

    def clearFocus(self):  # noqa: N802
        if self.hasFocus():
            self.window()._ctx.focus_node(None)

    # -- actions (Qt keeps them on the widget for toolbars and context menus) --------------------------------
    def actions(self):
        return list(self.__dict__.get("_actions", []))

    def addAction(self, action):  # noqa: N802
        self.insertAction(None, action)
        return action

    def addActions(self, actions):  # noqa: N802
        for a in actions:
            self.addAction(a)

    def insertAction(self, before, action):  # noqa: N802
        acts = self.__dict__.setdefault("_actions", [])
        if action in acts:
            acts.remove(action)
        acts.insert(acts.index(before) if before in acts else len(acts), action)

    def insertActions(self, before, actions):  # noqa: N802
        for a in actions:
            self.insertAction(before, a)

    def removeAction(self, action):  # noqa: N802
        acts = self.__dict__.get("_actions", [])
        if action in acts:
            acts.remove(action)

    # -- show / hide hooks (QWidget.show, hide and setVisible call them) ------------------------------------
    def showEvent(self, event):  # noqa: N802
        pass

    def hideEvent(self, event):  # noqa: N802
        pass
