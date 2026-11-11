"""The Qt API of the input widgets beyond their basics, for `bui.qtsyntax`'s classes: line edits
(length limits, validators, modified state), spin boxes (prefix, suffix, wrapping, special value),
sliders (page steps and slider actions), progress bars (format and text), combo boxes (item data,
limits, a model), tab widgets, labels, and buttons (checkable, down, auto-exclusive, flat, default, with a menu).

SPDX-License-Identifier: GPL-2.0-or-later
"""


class LineEditMore:
    """QLineEdit: the text is checked when the user changes it (QLineEdit._on_event asks
    _accept_edit): longer than maxLength is cut, and a validator's Invalid is refused."""

    def maxLength(self):  # noqa: N802
        return self.__dict__.get("_max_len", 32767)

    def setMaxLength(self, n):  # noqa: N802
        self.__dict__["_max_len"] = int(n)
        if len(self.text()) > int(n):
            self.setText(self.text()[:int(n)])

    def validator(self):
        return self.__dict__.get("_validator")

    def setValidator(self, v):  # noqa: N802
        self.__dict__["_validator"] = v

    def hasAcceptableInput(self):  # noqa: N802
        v = self.validator()
        return v is None or v.validate(self.text(), 0)[0] == v.Acceptable

    def isModified(self):  # noqa: N802
        return self.__dict__.get("_modified_text", False)

    def setModified(self, b):  # noqa: N802
        self.__dict__["_modified_text"] = bool(b)

    def placeholderText(self):  # noqa: N802
        return self.__dict__.get("_placeholder", "")

    def setPlaceholderText(self, t):  # noqa: N802
        self.__dict__["_placeholder"] = str(t)  # the kit takes it but doesn't read it back
        self.set("placeholder", str(t))

    def isReadOnly(self):  # noqa: N802
        return not self.isEnabled()

    def displayText(self):  # noqa: N802
        return self.text()

    def _accept_edit(self):
        """What the user typed, cut to maxLength; the last good text instead when the validator says
        Invalid. Returns whether the text changed (QLineEdit emits textChanged only then)."""
        text, good = self.text(), self.__dict__.get("_good", "")
        kept = text[:self.maxLength()]
        v = self.validator()
        if v is not None and v.validate(kept, 0)[0] == v.Invalid:
            kept = good
        if kept != text:
            self.set("set_value", kept)
            self.inputRejected.emit()
        self.__dict__["_good"] = kept
        if kept != good:
            self.__dict__["_modified_text"] = True
        return kept != good


class SpinBoxMore:
    """QSpinBox / QDoubleSpinBox (prefix is the Blender number field's label)."""

    def prefix(self):
        return self.__dict__.get("_prefix_text", "")

    def setPrefix(self, p):  # noqa: N802
        self.__dict__["_prefix_text"] = str(p)
        self.set("label", str(p).rstrip(": "))

    def suffix(self):
        return self.__dict__.get("_suffix", "")

    def setSuffix(self, s):  # noqa: N802
        self.__dict__["_suffix"] = str(s)
        self.set("suffix", str(s))

    def singleStep(self):  # noqa: N802
        return self._num(self.get("step"))

    def wrapping(self):
        return self.__dict__.get("_wrap", False)

    def setWrapping(self, b):  # noqa: N802
        self.__dict__["_wrap"] = bool(b)

    def specialValueText(self):  # noqa: N802
        return self.__dict__.get("_special", "")

    def setSpecialValueText(self, t):  # noqa: N802
        self.__dict__["_special"] = str(t)

    def isReadOnly(self):  # noqa: N802
        return not self.isEnabled()

    def setReadOnly(self, b):  # noqa: N802
        self.setEnabled(not b)

    def stepBy(self, steps):  # noqa: N802
        lo, hi = self.minimum(), self.maximum()
        v = self.value() + steps * self.singleStep()
        if self.wrapping() and hi > lo:
            span = hi - lo + (1 if isinstance(self._num(1), int) else 0)
            v = lo + (v - lo) % span
        self.setValue(max(lo, min(hi, v)))

    def stepUp(self):  # noqa: N802
        self.stepBy(1)

    def stepDown(self):  # noqa: N802
        self.stepBy(-1)

    def textFromValue(self, v):  # noqa: N802
        return str(int(v))

    def valueFromText(self, text):  # noqa: N802
        return int(float(text))

    def cleanText(self):  # noqa: N802
        return self.textFromValue(self.value())

    def text(self):
        if self.specialValueText() and self.value() == self.minimum():
            return self.specialValueText()
        return self.prefix() + self.cleanText() + self.suffix()

    @staticmethod
    def _num(v):
        return int(round(v))


class DoubleSpinBoxMore(SpinBoxMore):
    def decimals(self):
        return self.__dict__.get("_decimals", 2)

    def setDecimals(self, d):  # noqa: N802
        self.__dict__["_decimals"] = int(d)  # the kit's precision isn't read back
        self.set("precision", int(d))

    def textFromValue(self, v):  # noqa: N802
        return "%.*f" % (self.decimals(), float(v))

    def valueFromText(self, text):  # noqa: N802
        return float(text)

    def minimum(self):
        return float(self.get("min"))

    def maximum(self):
        return float(self.get("max"))

    @staticmethod
    def _num(v):
        return float(v)


class SliderMore:
    """QAbstractSlider: steps and the slider actions."""
    (SliderNoAction, SliderSingleStepAdd, SliderSingleStepSub, SliderPageStepAdd, SliderPageStepSub,
     SliderToMinimum, SliderToMaximum, SliderMove) = range(8)

    def singleStep(self):  # noqa: N802
        return int(round(self.get("step")))

    def pageStep(self):  # noqa: N802
        return self.__dict__.get("_page", 10)

    def setPageStep(self, s):  # noqa: N802
        self.__dict__["_page"] = int(s)

    def sliderPosition(self):  # noqa: N802
        return self.value()

    def setSliderPosition(self, v):  # noqa: N802
        self.setValue(v)

    def triggerAction(self, action):  # noqa: N802
        step = {1: self.singleStep(), 2: -self.singleStep(), 3: self.pageStep(), 4: -self.pageStep()}
        if action in step:
            v = self.value() + step[action]
        elif action == 5:
            v = self.minimum()
        elif action == 6:
            v = self.maximum()
        else:
            return
        self.actionTriggered.emit(action)
        self.setValue(max(self.minimum(), min(self.maximum(), v)))


class ProgressBarMore:
    def format(self):
        return self._format

    def resetFormat(self):  # noqa: N802
        self.setFormat("%p%")

    def isTextVisible(self):  # noqa: N802
        return self._text_visible

    def text(self):
        """The text Qt would show: the format with %p (percent), %v (value) and %m (maximum)."""
        span = (self._max - self._min) or 1
        pct = int(round(max(0.0, min(1.0, (self._value - self._min) / span)) * 100))
        return self._format.replace("%p", str(pct)).replace("%v", str(self._value)).replace("%m", str(self._max))


class ComboBoxMore:
    """QComboBox: item data and text, a maximum count, and a model (the items follow it)."""

    def setItemText(self, i, text):  # noqa: N802
        self._items[i] = str(text)
        self.set("items", self._items)

    def setItemData(self, i, value, role=None):  # noqa: N802
        self._data[i] = value

    def findData(self, value, role=None, flags=None):  # noqa: N802
        return next((i for i, d in enumerate(self._data) if d == value), -1)

    def insertItems(self, index, texts):  # noqa: N802
        for k, t in enumerate(texts):
            self.insertItem(index + k, t)

    def maxCount(self):  # noqa: N802
        return self.__dict__.get("_max_count", 2147483647)

    def setMaxCount(self, n):  # noqa: N802
        self.__dict__["_max_count"] = int(n)
        while self.count() > int(n):
            self.removeItem(self.count() - 1)

    def isEditable(self):  # noqa: N802
        return False  # Blender's dropdowns choose; they don't type

    def model(self):
        return self.__dict__.get("_model")

    def modelColumn(self):  # noqa: N802
        return self.__dict__.get("_model_col", 0)

    def setModelColumn(self, c):  # noqa: N802
        self.__dict__["_model_col"] = int(c)
        self._from_model()

    def setModel(self, model):  # noqa: N802
        old = self.model()
        signals = ("dataChanged", "rowsInserted", "rowsRemoved", "modelReset", "layoutChanged")
        if old is not None:
            for s in signals:
                getattr(old, s).disconnect(self._from_model)
        self.__dict__["_model"] = model
        for s in signals:
            getattr(model, s).connect(self._from_model)
        self._from_model()

    def _from_model(self, *_):
        m = self.model()
        if m is None:
            return
        from bui.qtsyntax import Qt
        col = self.modelColumn()
        rows = [m.index(r, col) for r in range(m.rowCount())]
        self._items = ["" if m.data(i, Qt.DisplayRole) is None else str(m.data(i, Qt.DisplayRole)) for i in rows]
        self._data = [m.data(i, Qt.UserRole) for i in rows]
        self.set("items", self._items)


class TabWidgetMore:
    def currentWidget(self):  # noqa: N802
        i = self.currentIndex()
        return self._pages[i] if 0 <= i < len(self._pages) else None

    def setCurrentWidget(self, w):  # noqa: N802
        if w in self._pages:
            self.setCurrentIndex(self._pages.index(w))

    def indexOf(self, w):  # noqa: N802
        return self._pages.index(w) if w in self._pages else -1

    def insertTab(self, index, w, *args):  # noqa: N802 - (index, widget, label) or (index, widget, icon, label)
        index = max(0, min(int(index), len(self._pages)))
        if w.parent is not None:
            w.parent.remove(w)
        self._pages.insert(index, w)
        self._titles.insert(index, str(args[-1]))
        for p in self._pages:
            if p.parent is self:
                self.remove(p)
        for p in self._pages:
            self.add(p)
        self.set("items", self._titles)
        return index

    def removeTab(self, index):  # noqa: N802
        if 0 <= index < len(self._pages):
            self.remove(self._pages.pop(index))
            self._titles.pop(index)
            self.set("items", self._titles)

    def clear(self):
        while self._pages:
            self.removeTab(0)

    def tabToolTip(self, index):  # noqa: N802
        return self.__dict__.get("_tips", {}).get(index, "")

    def setTabToolTip(self, index, tip):  # noqa: N802
        self.__dict__.setdefault("_tips", {})[index] = str(tip)

    def isTabEnabled(self, index):  # noqa: N802
        return self._pages[index].isEnabled()

    def setTabEnabled(self, index, enabled):  # noqa: N802
        self._pages[index].setEnabled(enabled)


class LabelMore:
    def alignment(self):
        from bui.qtsyntax import Qt
        return {"right": Qt.AlignRight, "center": Qt.AlignHCenter}.get(
            self.get_str("text_align"), Qt.AlignLeft) | Qt.AlignVCenter

    def setNum(self, n):  # noqa: N802
        self.setText(("%g" % n) if isinstance(n, float) else str(int(n)))

    def clear(self):
        self.setText("")

    def pixmap(self):
        return self.__dict__.get("_pixmap")


class AbstractButtonMore:
    """QAbstractButton: checkable (a checked button is drawn pressed in, Blender's UI_SELECT), down,
    auto-exclusive siblings and its group. QCheckBox and QRadioButton keep their check in the kit."""
    _AUTO_EXCLUSIVE = False

    def isCheckable(self):  # noqa: N802
        return self.__dict__.get("_checkable", False)

    def setCheckable(self, b):  # noqa: N802
        self.__dict__["_checkable"] = bool(b)
        if not b:
            self.setChecked(False)

    def isChecked(self):  # noqa: N802
        return self.__dict__.get("_checked", False)

    def setChecked(self, b):  # noqa: N802
        if (b and not self.isCheckable()) or bool(b) == self.isChecked():
            return
        self.__dict__["_checked"] = bool(b)
        self.set("select", bool(b) or self.isDown())
        if b:
            for other in self._exclusive_siblings():
                other.setChecked(False)
        self.toggled.emit(bool(b))

    def toggle(self):
        self.setChecked(not self.isChecked())

    def isDown(self):  # noqa: N802
        return self.__dict__.get("_down", False)

    def setDown(self, b):  # noqa: N802
        self.__dict__["_down"] = bool(b)
        self.set("select", bool(b) or self.isChecked())

    def autoExclusive(self):  # noqa: N802
        return self.__dict__.get("_auto_exclusive", self._AUTO_EXCLUSIVE)

    def setAutoExclusive(self, b):  # noqa: N802
        self.__dict__["_auto_exclusive"] = bool(b)

    def group(self):
        return self.__dict__.get("_group")

    def _exclusive_siblings(self):
        """Checked buttons that turn off when this one turns on: in its group (QButtonGroup does it),
        else auto-exclusive siblings in the same parent."""
        parent = self.parent
        if self.group() is not None or not self.autoExclusive() or parent is None:
            return []
        from bui.qtsyntax import _kids
        return [c for c in _kids(parent) if c is not self and isinstance(c, AbstractButtonMore)
                and c.group() is None and c.autoExclusive() and c.isChecked()]

    def icon(self):
        from bui.qtsyntax import QIcon
        return self.__dict__.get("_icon") or QIcon()


class ButtonMenuMore:
    """A button's menu (QPushButton and QToolButton): opened below the button."""

    def menu(self):
        return self.__dict__.get("_menu")

    def setMenu(self, menu):  # noqa: N802
        self.__dict__["_menu"] = menu
        if menu is not None and menu._parent is None:
            menu._parent = self

    def showMenu(self):  # noqa: N802
        menu = self.menu()
        if menu is not None:
            from bui.qtsyntax import QPoint
            x, y = self.absolutePos()
            menu.popup(QPoint(x, y + self.height()))


class PushButtonMore(ButtonMenuMore):
    """QPushButton: flat (Blender's emboss off), default, and a menu."""

    def isFlat(self):  # noqa: N802
        return self.__dict__.get("_flat", False)

    def setFlat(self, b):  # noqa: N802
        self.__dict__["_flat"] = bool(b)
        self.set("emboss", not b)

    def isDefault(self):  # noqa: N802
        return self.__dict__.get("_default", False)

    def setDefault(self, b):  # noqa: N802
        self.__dict__["_default"] = bool(b)
        self.set("active_default", bool(b))

    def autoDefault(self):  # noqa: N802
        return self.__dict__.get("_auto_default", False)

    def setAutoDefault(self, b):  # noqa: N802
        self.__dict__["_auto_default"] = bool(b)
