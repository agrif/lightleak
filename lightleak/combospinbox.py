from PySide6 import QtCore, QtWidgets


class SpinButton(QtWidgets.QPushButton):
    def __init__(self, text):
        super().__init__(text)

        self.setSizePolicy(QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.ControlType.PushButton,
        ))

    def sizeHint(self):
        hint = super().sizeHint()
        return QtCore.QSize(hint.height(), hint.height() // 2)


class ComboSpinBox(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self._enabled = True

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        policy = self.sizePolicy()
        policy.setControlType(QtWidgets.QSizePolicy.ControlType.ComboBox)
        self.setSizePolicy(policy)

        self._combo = QtWidgets.QComboBox()
        self._combo.currentIndexChanged.connect(self.update_spin_buttons)
        layout.addWidget(self._combo)

        buttons = QtWidgets.QVBoxLayout()
        buttons.setSpacing(0)
        buttons.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(buttons)

        self._inc = SpinButton('+')
        self._dec = SpinButton('-')
        buttons.addWidget(self._inc)
        buttons.addWidget(self._dec)
        self._inc.clicked.connect(self.increment)
        self._dec.clicked.connect(self.decrement)

    @QtCore.Slot()
    def increment(self):
        i = self._combo.currentIndex()
        i += 1
        if i < self._combo.count():
            self._combo.setCurrentIndex(i)

    @QtCore.Slot()
    def decrement(self):
        i = self._combo.currentIndex()
        i -= 1
        if i >= 0:
            self._combo.setCurrentIndex(i)

    @QtCore.Slot()
    def update_spin_buttons(self, i):
        count = self._combo.count()
        self._inc.setEnabled(self._enabled and i < count - 1)
        self._dec.setEnabled(self._enabled and i > 0)

    @property
    def currentTextChanged(self):
        return self._combo.currentTextChanged

    def setEnabled(self, enabled):
        self._enabled = enabled
        self._combo.setEnabled(enabled)
        self.update_spin_buttons(self._combo.currentIndex())

    def clear(self):
        self._combo.clear()

    def addItems(self, items):
        self._combo.addItems(items)

    def setCurrentText(self, text):
        self._combo.setCurrentText(text)
