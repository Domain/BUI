"""QMessageBox and QInputDialog: real dialogs, built from Qt's own widgets and shown as BUI windows
with Blender's icons (info, question, the warning triangle, cancel).

SPDX-License-Identifier: GPL-2.0-or-later
"""

from bui.qtsyntax import (QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
                          QPushButton, QSpinBox, QVBoxLayout, QWidget, Signal)


class QMessageBox(QDialog):
    NoIcon, Information, Warning, Critical, Question = 0, 1, 2, 3, 4
    NoButton = 0
    Ok, Save, SaveAll, Open, Yes, YesToAll, No, NoToAll = (0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000,
                                                          0x10000, 0x20000)
    Abort, Retry, Ignore, Close, Cancel, Discard, Help = (0x40000, 0x80000, 0x100000, 0x200000, 0x400000,
                                                         0x800000, 0x1000000)
    Apply, Reset, RestoreDefaults = 0x2000000, 0x4000000, 0x8000000
    StandardButton = int
    AcceptRole, RejectRole, DestructiveRole, ActionRole, HelpRole, YesRole, NoRole, ApplyRole, ResetRole = range(9)
    buttonClicked = Signal(object)

    _TEXT = {Ok: "OK", Save: "Save", SaveAll: "Save All", Open: "Open", Yes: "Yes", YesToAll: "Yes to All",
             No: "No", NoToAll: "No to All", Abort: "Abort", Retry: "Retry", Ignore: "Ignore", Close: "Close",
             Cancel: "Cancel", Discard: "Discard", Help: "Help", Apply: "Apply", Reset: "Reset",
             RestoreDefaults: "Restore Defaults"}
    _ICON = {Information: "INFO", Warning: "ERROR", Critical: "CANCEL", Question: "QUESTION"}
    _ESCAPE = (Cancel, No, Close, Abort, Ignore)

    def __init__(self, icon=0, title="", text="", buttons=0, parent=None):
        if isinstance(icon, QWidget):
            icon, parent = 0, icon
        super().__init__(parent)
        self._buttons = []  # (button, standard code or None, role)
        self._clicked = None
        self._default = None
        self._escape = None
        self._detail = ""
        root = QVBoxLayout(self)
        body = QHBoxLayout()
        self._icon_label = QLabel("")
        self._text = QLabel(str(text))
        self._info = QLabel("")
        self._info.setVisible(False)
        texts = QVBoxLayout()
        texts.addWidget(self._text)
        texts.addWidget(self._info)
        body.addWidget(self._icon_label)
        body.addLayout(texts)
        root.addLayout(body)
        self._row = QHBoxLayout()
        root.addLayout(self._row)
        self.setIcon(icon)
        self.setWindowTitle(str(title))
        self.setStandardButtons(buttons)

    # -- content ---------------------------------------------------------------------------------------
    def text(self):
        return self._text.text()

    def setText(self, text):  # noqa: N802
        self._text.setText(str(text))

    def informativeText(self):  # noqa: N802
        return self._info.text()

    def setInformativeText(self, text):  # noqa: N802
        self._info.setText(str(text))
        self._info.setVisible(bool(text))

    def detailedText(self):  # noqa: N802
        return self._detail

    def setDetailedText(self, text):  # noqa: N802
        self._detail = str(text)

    def icon(self):
        return self._icon

    def setIcon(self, icon):  # noqa: N802
        self._icon = icon
        self._icon_label.set("icon", self._ICON.get(icon, ""))
        self._icon_label.setVisible(icon in self._ICON)

    # -- buttons -----------------------------------------------------------------------------------------
    def addButton(self, button, role=None):  # noqa: N802 - (standard code) / (text, role) / (button, role)
        code = None
        if isinstance(button, int):
            code, button, role = button, QPushButton(self._TEXT.get(button, "")), self._role(button)
        elif isinstance(button, str):
            button = QPushButton(button)
        button.clicked.connect(lambda *_: self._click(button))
        self._buttons.append((button, code, role))
        self._row.addWidget(button)
        return button

    def _role(self, code):
        if code in (self.Yes, self.YesToAll):
            return self.YesRole
        if code in (self.No, self.NoToAll):
            return self.NoRole
        if code in self._ESCAPE:
            return self.RejectRole
        return self.AcceptRole

    def setStandardButtons(self, buttons):  # noqa: N802
        for entry in [x for x in self._buttons if x[1] is not None]:
            entry[0].setParent(None)
            self._buttons.remove(entry)
        for code in sorted(self._TEXT):
            if buttons & code:
                self.addButton(code)
        if not self._buttons:
            self.addButton(self.Ok)

    def standardButtons(self):  # noqa: N802
        out = 0
        for _, code, _ in self._buttons:
            out |= code or 0
        return out

    def standardButton(self, button):  # noqa: N802
        return next((code or self.NoButton for b, code, _ in self._buttons if b is button), self.NoButton)

    def button(self, code):
        return next((b for b, c, _ in self._buttons if c == code), None)

    def buttons(self):
        return [b for b, _, _ in self._buttons]

    def buttonRole(self, button):  # noqa: N802
        return next((r for b, _, r in self._buttons if b is button), -1)

    def clickedButton(self):  # noqa: N802
        return self._clicked

    def defaultButton(self):  # noqa: N802
        return self._default

    def setDefaultButton(self, button):  # noqa: N802
        self._default = self.button(button) if isinstance(button, int) else button

    def escapeButton(self):  # noqa: N802
        return self._escape

    def setEscapeButton(self, button):  # noqa: N802
        self._escape = self.button(button) if isinstance(button, int) else button

    def _click(self, button):
        self._clicked = button
        self.buttonClicked.emit(button)
        code = self.standardButton(button)
        self.done(code if code else self._buttons.index(next(x for x in self._buttons if x[0] is button)))

    def _close_requested(self):
        # closing the window picks the escape button: Cancel, No ... as Qt does
        esc = self._escape or next((b for b, c, _ in self._buttons if c in self._ESCAPE), None)
        if esc is not None and self._clicked is None:
            self._clicked = esc
            self.setResult(self.standardButton(esc))
        super()._close_requested()

    # -- the static helpers --------------------------------------------------------------------------------
    @classmethod
    def _ask(cls, icon, parent, title, text, buttons, default):
        box = cls(icon, title, text, buttons, parent)
        if default:
            box.setDefaultButton(default)
        return box.exec()

    @classmethod
    def information(cls, parent, title, text, buttons=None, default=0):
        return cls._ask(cls.Information, parent, title, text, buttons or cls.Ok, default)

    @classmethod
    def warning(cls, parent, title, text, buttons=None, default=0):
        return cls._ask(cls.Warning, parent, title, text, buttons or cls.Ok, default)

    @classmethod
    def critical(cls, parent, title, text, buttons=None, default=0):
        return cls._ask(cls.Critical, parent, title, text, buttons or cls.Ok, default)

    @classmethod
    def question(cls, parent, title, text, buttons=None, default=0):
        return cls._ask(cls.Question, parent, title, text, buttons or (cls.Yes | cls.No), default)

    @classmethod
    def about(cls, parent, title, text):
        cls._ask(cls.Information, parent, title, text, cls.Ok, 0)


class QInputDialog(QDialog):
    """A label, one editor (text, integer, number or a list) and OK / Cancel."""
    TextInput, IntInput, DoubleInput = 0, 1, 2
    textValueChanged = Signal(str)
    intValueChanged = Signal(int)
    doubleValueChanged = Signal(float)
    textValueSelected = Signal(str)
    intValueSelected = Signal(int)
    doubleValueSelected = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.TextInput
        root = QVBoxLayout(self)
        self._label = QLabel("")
        root.addWidget(self._label)
        self._text = QLineEdit()
        self._int = QSpinBox()
        self._int.setRange(-2147483647, 2147483647)
        self._double = QDoubleSpinBox()
        self._double.setRange(-2147483647.0, 2147483647.0)
        self._items = QComboBox()
        for editor in (self._text, self._int, self._double, self._items):
            root.addWidget(editor)
        self._text.textChanged.connect(self.textValueChanged.emit)
        self._int.valueChanged.connect(self.intValueChanged.emit)
        self._double.valueChanged.connect(self.doubleValueChanged.emit)
        row = QHBoxLayout()
        ok, cancel = QPushButton("OK"), QPushButton("Cancel")
        ok.clicked.connect(lambda *_: self.accept())
        cancel.clicked.connect(lambda *_: self.reject())
        row.addWidget(ok)
        row.addWidget(cancel)
        root.addLayout(row)
        self._list_mode = False
        self._show_editor()

    def _show_editor(self):
        self._text.setVisible(self._mode == self.TextInput and not self._list_mode)
        self._items.setVisible(self._mode == self.TextInput and self._list_mode)
        self._int.setVisible(self._mode == self.IntInput)
        self._double.setVisible(self._mode == self.DoubleInput)

    def accept(self):
        if self._mode == self.IntInput:
            self.intValueSelected.emit(self.intValue())
        elif self._mode == self.DoubleInput:
            self.doubleValueSelected.emit(self.doubleValue())
        else:
            self.textValueSelected.emit(self.textValue())
        super().accept()

    def inputMode(self):  # noqa: N802
        return self._mode

    def setInputMode(self, mode):  # noqa: N802
        self._mode = mode
        self._show_editor()

    def labelText(self):  # noqa: N802
        return self._label.text()

    def setLabelText(self, text):  # noqa: N802
        self._label.setText(str(text))

    def textValue(self):  # noqa: N802
        return self._items.currentText() if self._list_mode else self._text.text()

    def setTextValue(self, text):  # noqa: N802
        self._text.setText(str(text))

    def comboBoxItems(self):  # noqa: N802
        return [self._items.itemText(i) for i in range(self._items.count())]

    def setComboBoxItems(self, items):  # noqa: N802
        self._items.clear()
        self._items.addItems([str(i) for i in items])
        self._list_mode = True
        self._show_editor()

    def intValue(self):  # noqa: N802
        return int(self._int.value())

    def setIntValue(self, v):  # noqa: N802
        self._int.setValue(int(v))

    def setIntRange(self, lo, hi):  # noqa: N802
        self._int.setRange(int(lo), int(hi))

    def setIntMinimum(self, lo):  # noqa: N802
        self._int.setRange(int(lo), self._int.maximum())

    def setIntMaximum(self, hi):  # noqa: N802
        self._int.setRange(self._int.minimum(), int(hi))

    def doubleValue(self):  # noqa: N802
        return float(self._double.value())

    def setDoubleValue(self, v):  # noqa: N802
        self._double.setValue(float(v))

    def setDoubleRange(self, lo, hi):  # noqa: N802
        self._double.setRange(float(lo), float(hi))

    def setDoubleDecimals(self, decimals):  # noqa: N802
        self._double.setDecimals(int(decimals))

    # -- the static helpers: (value, ok) -------------------------------------------------------------------------
    @classmethod
    def _run(cls, parent, title, label, mode):
        d = cls(parent)
        d.setWindowTitle(str(title))
        d.setLabelText(label)
        d.setInputMode(mode)
        return d

    @classmethod
    def getText(cls, parent, title, label, echo=0, text="", *a, **kw):  # noqa: N802
        d = cls._run(parent, title, label, cls.TextInput)
        d.setTextValue(text)
        ok = bool(d.exec())
        return (d.textValue() if ok else "", ok)

    @classmethod
    def getInt(cls, parent, title, label, value=0, minValue=-2147483647, maxValue=2147483647,  # noqa: N802,N803
               step=1, *a, **kw):
        d = cls._run(parent, title, label, cls.IntInput)
        d.setIntRange(minValue, maxValue)
        d.setIntValue(value)
        ok = bool(d.exec())
        return (d.intValue() if ok else value, ok)

    @classmethod
    def getDouble(cls, parent, title, label, value=0.0, minValue=-2147483647.0,  # noqa: N802,N803
                  maxValue=2147483647.0, decimals=1, *a, **kw):
        d = cls._run(parent, title, label, cls.DoubleInput)
        d.setDoubleRange(minValue, maxValue)
        d.setDoubleDecimals(decimals)
        d.setDoubleValue(value)
        ok = bool(d.exec())
        return (d.doubleValue() if ok else value, ok)

    @classmethod
    def getItem(cls, parent, title, label, items, current=0, editable=True, *a, **kw):  # noqa: N802
        d = cls._run(parent, title, label, cls.TextInput)
        d.setComboBoxItems(items)
        d._items.setCurrentIndex(int(current))
        ok = bool(d.exec())
        return (d.textValue() if ok else (str(items[current]) if items else ""), ok)
