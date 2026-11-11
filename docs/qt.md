# Qt syntax on BUI

`bui.qtsyntax` lets you write Qt-style Python (`QApplication`, `QWidget`,
layouts, `clicked.connect(...)`) that runs on BUI's C kit, with Blender's
look. Neither Qt nor PySide is needed.

> **Status: partial.** Measured against Qt's own headers by
> `tools/qt_coverage.py`: 482 of 1,555 public methods, signals, slots and event handlers on 36 core widget classes (31%), and 573 of 3,205 across all 142 exported widget and GUI classes (18%).
> See [Coverage](#coverage) for what's missing.

![Qt syntax on BUI](images/qt.png)

## Example

```python
from bui.qtsyntax import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                          QHBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
                          QSlider, QProgressBar, QPushButton, QTreeWidget,
                          QTreeWidgetItem, QMessageBox, Qt)

app = QApplication([])
win = QMainWindow()
win.setWindowTitle("Qt syntax on BUI")

central = QWidget()
layout = QVBoxLayout(central)

form = QFormLayout()
name = QLineEdit()
name.setPlaceholderText("name")
kind = QComboBox()
kind.addItems(["Mesh", "Light", "Camera"])
level = QSlider(Qt.Horizontal)
level.setRange(0, 100)
form.addRow("Name:", name)
form.addRow("Kind:", kind)
form.addRow("Level:", level)
layout.addLayout(form)

bar = QProgressBar()
level.valueChanged.connect(bar.setValue)        # signals connect to any callable
layout.addWidget(bar)

tree = QTreeWidget()
tree.setHeaderLabels(["Name", "Kind"])
layout.addWidget(tree)

buttons = QHBoxLayout()
add = QPushButton("Add")
add.clicked.connect(lambda: QTreeWidgetItem(tree, [name.text(), kind.currentText()]))
buttons.addWidget(add)
layout.addLayout(buttons)

menu = win.menuBar().addMenu("File")
menu.addAction("Quit", app.quit, "Ctrl+Q")
win.statusBar().showMessage("Ready")

win.setCentralWidget(central)
win.resize(420, 420)
win.show()
app.exec()
```

## GPU rendering

Call `bui.set_gpu(True)` before creating windows, or run with `BUI_GPU=1`, to
draw them on the GPU (Direct3D 11 on Windows, OpenGL on Linux). The pixels are the same and the CPU cost
is much lower. See [getting-started.md](getting-started.md#gpu-rendering).

## How it maps

| Qt | On BUI |
|---|---|
| `QWidget` | A kit frame. A subclass that overrides `paintEvent` becomes a kit canvas, and `QPainter` records into its display list. |
| `QVBoxLayout` / `QHBoxLayout` | Tk's packer in C, with Qt semantics: stretch factors, expanding size policies, spacing between items only, margins on top-level layouts only |
| `QGridLayout` / `QFormLayout` | Tk's gridder in C (`setColumnStretch` maps to column weights) |
| Signals | Plain Python (`Signal` / `pyqtSignal`). Slots that take fewer arguments than the signal sends get fewer. |
| `QApplication.exec()` | `bui.host.run()`: a native window (Win32, X11, Cocoa), or a Tk-hosted window with `BUI_HOST=tk` |
| `QTimer`, `QPropertyAnimation` | Window timers; animations step at 120 Hz with easing curves |

## Supported classes

| Area | Classes |
|---|---|
| Application | `QApplication` (`exec`, `quit`, `processEvents`), `QTimer` (`singleShot`, `start`, `stop`, `timeout`), `QPropertyAnimation`, `QEasingCurve` |
| Windows | `QWidget`, `QMainWindow` (`setCentralWidget`, `menuBar`, `statusBar`), `QDialog` (`exec`, `accept`, `reject`), `QFrame` |
| Layouts | `QVBoxLayout`, `QHBoxLayout` (`addWidget(stretch)`, `addLayout`, `addStretch`, `addSpacing`, `insertWidget`, `setSpacing`, `setContentsMargins`), `QGridLayout` (spans, alignment, stretch), `QFormLayout.addRow`, `QStackedLayout` |
| Widgets | `QLabel` (text, alignment, pixmap), `QPushButton` / `QToolButton`, `QCheckBox`, `QRadioButton` + `QButtonGroup` (auto-exclusive), `QLineEdit` (`textChanged`, `returnPressed`, `editingFinished`), `QTextEdit` / `QPlainTextEdit`, `QSlider` / `QDial`, `QSpinBox` / `QDoubleSpinBox`, `QProgressBar` (format), `QComboBox` (items, data, `currentIndexChanged`) |
| Views | `QListWidget` / `QListWidgetItem`, `QTreeWidget` / `QTreeWidgetItem` (columns, expand), `QTableWidget` / `QTableWidgetItem` |
| Containers | `QTabWidget`, `QGroupBox` (a Blender panel), `QScrollArea`, `QStatusBar` |
| Menus | `QMenuBar`, `QMenu` (`addAction(text, slot, shortcut)`, submenus, separators, `popup`), `QAction` (checkable, shortcuts) |
| Painting | `QPainter` (`fillRect`, `drawRect`, `drawRoundedRect`, `drawEllipse`, `drawLine`, `drawPolyline`, `drawPolygon`, `drawArc`, `drawPie`, `drawText`, `drawPixmap`, `translate`, `save`, `restore`, `setOpacity`), `QPen`, `QBrush`, `QColor`, `QFont`, `QPixmap` / `QImage` |
| Events | Override `mousePressEvent`, `mouseReleaseEvent`, `mouseMoveEvent`, `mouseDoubleClickEvent`, `keyPressEvent`, `wheelEvent`, `enterEvent`, `leaveEvent`, `closeEvent`, `paintEvent`. Event types: `QMouseEvent`, `QKeyEvent`, `QWheelEvent`, `QPaintEvent`, `QCloseEvent`. |
| Values | `Qt` constants (alignment, keys, orientation, check states), `QPoint`, `QSize`, `QRect`, `QMargins`, `QSizePolicy`, `QIcon` |
| Dialogs | `QMessageBox` (static calls return immediately; not drawn yet), `QFileDialog` (`getOpenFileName(s)`, `getSaveFileName`, `getExistingDirectory`: Blender's File Browser; `BUI_FILEDIALOG=native` for the OS dialogs) |

Member-by-member tables: [../SYNTAX_COVERAGE.md](../SYNTAX_COVERAGE.md#qt-syntax-buiqtsyntax).

### Custom painting

```python
from bui.qtsyntax import QApplication, QWidget, QPainter, QColor, QPen

class Gauge(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.6

    def paintEvent(self, event):
        p = QPainter(self)
        p.setBrush(QColor("#282828"))
        p.drawRoundedRect(0, 0, self.width(), 24, 6, 6)
        p.setBrush(QColor("#4772b3"))
        p.drawRoundedRect(0, 0, int(self.width() * self.value), 24, 6, 6)
        p.setPen(QPen(QColor("white")))
        p.drawText(8, 17, "%d%%" % (self.value * 100))
        p.end()

    def mousePressEvent(self, e):
        self.value = e.x() / max(1, self.width())
        self.update()                  # repaints the display list
```

## Containers, models and dialogs

```python
from bui.qtsyntax import (QMainWindow, QDockWidget, QSplitter, QToolBox, QTreeView,
                          QStandardItemModel, QStandardItem, QMessageBox, QSettings, Qt)

win = QMainWindow()
bar = win.addToolBar("Main")
bar.addAction("Save", save)                      # a row of tool buttons
model = QStandardItemModel()
model.setHorizontalHeaderLabels(["Name", "Type"])
model.appendRow([QStandardItem("Cube"), QStandardItem("Mesh")])
tree = QTreeView()
tree.setModel(model)                             # redraws when the model changes
dock = QDockWidget("Outliner")
dock.setWidget(tree)
win.addDockWidget(Qt.LeftDockWidgetArea, dock)   # a Blender panel left of the central widget
split = QSplitter(Qt.Vertical)                   # Blender's region edges, dragged
win.setCentralWidget(split)
if QMessageBox.question(win, "Quit", "Save changes?") == QMessageBox.Yes:
    QSettings("Studio", "App").setValue("geometry/width", win.width())
```

- **Containers:** `QStackedWidget`, `QToolBox` (Blender panels: the Qt API keeps one open,
  while a click on a header opens or closes that panel on its own, as in Blender), `QSplitter`
  (region edges you drag), `QToolBar`, `QDockWidget`, `QTabBar`, and `QMainWindow.addToolBar`,
  `addDockWidget`, `setStatusBar`, `takeCentralWidget`.
- **Model/view:** `QStandardItemModel`, `QStringListModel`, the abstract models to subclass
  (`QAbstractItemModel`, `QAbstractListModel`, `QAbstractTableModel`), `QModelIndex`,
  `QItemSelectionModel`, and `QListView`, `QTreeView`, `QTableView`, drawn in Blender's tree
  list. One row is selected at a time; views don't edit cells.
- **Dialogs:** `QMessageBox` (Blender's info, question, warning and cancel icons; the static
  helpers return the button clicked) and `QInputDialog` (`getText`, `getInt`, `getDouble`,
  `getItem`).
- **Core:** `QSettings` (an INI file per application with Qt's groups and arrays; on Windows Qt's
  native format is the registry, here it's `%APPDATA%\<org>\<app>.ini`), `QKeySequence`,
  `QShortcut` (the kit's key bindings; buttons' `setShortcut` uses it), `QClipboard`.
- **QObject / QWidget:** `blockSignals`, dynamic properties (`setProperty` / `property`),
  `findChild` / `findChildren`, `mapTo` / `mapFrom` / `childAt` / `childrenRect`, `adjustSize`,
  `hasFocus` / `clearFocus`, `showEvent` / `hideEvent`, widget actions, and the descriptive
  properties (`statusTip`, `whatsThis`, accessible names, focus and context-menu policies).

## Coverage

`py tools/qt_coverage.py` counts it from Qt's own headers in `reference/qtbase` (there's no Qt in
the test environment): every exported class's public methods, slots, signals and overridable
`*Event` handlers, and whether the `bui.qtsyntax` class of the same name has each one. It writes
the per-class table to [qt-coverage.md](qt-coverage.md). Today: 482 of 1,555 public methods, signals, slots and event handlers on 36 core widget classes (31%), and 573 of 3,205 across all 142 exported widget and GUI classes (18%). (The earlier
"220 of 920" figure came from a looser count over 25 classes.)

Missing names raise `AttributeError`. A few setters are accepted and ignored: window flags and icons, frame shapes, word wrap, echo mode, validators, scroll-bar policies, maximum sizes and the like. The
accepted-but-ignored setters today: `setWindowFlags`, `setWindowIcon`, `setAttribute`,
`setContentsMargins`, `setCursor`, `setFocus`, `setMouseTracking`, `setAutoFillBackground`,
`installEventFilter`, `setMaximumSize` / `Width` / `Height`, `setMinimumSize` (on QWidget);
`setFrameShape`, `setFrameShadow`, `setLineWidth` (QFrame); `setWordWrap`, `setTextFormat`,
`setOpenExternalLinks` (QLabel); `setEchoMode`, `setMaxLength`, `setValidator`, `setAlignment`,
`setClearButtonEnabled` (QLineEdit); `setEditable` (QComboBox); `setPageStep`, `setTickPosition`,
`setTickInterval`, `setTracking`, `setOrientation` (sliders); `setDefault`, `setAutoDefault`,
`setFlat` (QPushButton); scroll-bar policies and `setWidgetResizable` (QScrollArea);
`setLineWrapMode`, `setWordWrapMode`, `setPlaceholderText` (QTextEdit); `setStyle` and
`setStyleSheet` (QApplication); `setRenderHint(s)` (QPainter); item colors, flags and data on
`QListWidgetItem`, `QTreeWidgetItem` and `QTableWidgetItem`; `setIcon`, `setToolTip`,
`setStatusTip` (QAction).

**Missing:** `QDateEdit` and friends, `QCalendarWidget`, `QThread`, drag and drop, delegates and editing inside views, multi-selection, floating docks, `QGraphicsScene`, OpenGL widgets, rich text, stylesheet selectors and `QPalette`.

**Plan.** Reach parity with the tkinter layer:

1. Measure against PySide6 itself, and run the same programs on real Qt
   and on BUI to compare, as `bindings/python/tests/test_tk_compat.py` does
   for tkinter.
2. Make widgets wrap kit nodes instead of being them (as `bui.tksyntax`
   does), which removes name clashes like `rect()` and `children()`.
3. Fill in the classes above, then add `install()` so `import PySide6`
   programs run unchanged.
