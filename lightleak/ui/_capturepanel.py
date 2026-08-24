import dataclasses
import enum
import functools

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.camera
import lightleak.ui

SETTINGS = {
    '/main/imgsettings/imageformat': (
        'Format', QtWidgets.QComboBox,
    ),
    '/main/imgsettings/whitebalance': (
        'White Balance', QtWidgets.QComboBox,
    ),
    '/main/imgsettings/iso': (
        'ISO', lambda: lightleak.ui.ComboSpinBox(),
    ),
    '/main/capturesettings/aperture': (
        'Aperture', lambda: lightleak.ui.ComboSpinBox(),
    ),
    '/main/capturesettings/shutterspeed': (
        'Exposure', lambda: lightleak.ui.ComboSpinBox(),
    ),
}


class CameraWorker(QtCore.QObject):
    class State(enum.StrEnum):
        DISCONNECTED = enum.auto()
        READY = enum.auto()
        BUSY = enum.auto()

    @dataclasses.dataclass
    class SettingChange:
        name: str
        value: str
        choices: list[str]

    state_changed = QtCore.Signal(State)
    error = QtCore.Signal(str)
    setting_changed = QtCore.Signal(SettingChange)
    captured = QtCore.Signal(PIL.Image.Image)

    def __init__(self):
        super().__init__()

        self._cam = None
        self._configs = {}

        self._thread = QtCore.QThread()
        self.moveToThread(self._thread)
        self._thread.start()

    def stop(self):
        self.reset()
        self._thread.quit()

    def reset(self):
        if self._cam:
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None
            self._configs = {}
            self.state_changed.emit(self.State.DISCONNECTED)

    @property
    def name(self):
        if self._cam:
            return self._cam.name
        return '<none>'

    @property
    def port(self):
        if self._cam:
            return self._cam.port
        return '<none>'

    @QtCore.Slot()
    def connect(self):
        if self._cam:
            self.reset()
            return

        self.state_changed.emit(self.State.BUSY)
        try:
            self._cam = lightleak.camera.Camera.default()
            self._cam.open()
        except Exception as e:
            self._cam = None
            self.state_changed.emit(self.State.DISCONNECTED)
            self.error.emit(f'Failed to open camera: {e}')
        else:
            for name in SETTINGS:
                c = self._cam.get_config(name)
                self.setting_changed.emit(
                    self.SettingChange(name, c.value, c.choices))
                self._configs[name] = c
            self.state_changed.emit(self.State.READY)

    @QtCore.Slot(str, str)
    def change_setting(self, name, value):
        if self._cam and self._configs:
            c = self._configs[name]
            c.set(value)

    @QtCore.Slot()
    def capture(self):
        if self._cam:
            self.state_changed.emit(self.State.BUSY)
            try:
                cap = self._cam.capture()
            except Exception as e:
                self.error.emit(f'Failed to capture frame: {e}')
                self.state_changed.emit(self.State.READY)
            else:
                self.state_changed.emit(self.State.READY)
                self.captured.emit(cap)


class CapturePanel(QtWidgets.QWidget):
    _change_setting = QtCore.Signal(str, str)

    @property
    def captured(self):
        return self._worker.captured

    def __init__(self, status_bar):
        super().__init__()

        self._status_bar = status_bar
        self._connected = False

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self._connect_button = QtWidgets.QPushButton('Connect')
        layout.addWidget(self._connect_button)
        layout.addSpacing(20)
        self._settings = {}
        for name, (label, widget) in SETTINGS.items():
            qlabel = QtWidgets.QLabel(label)
            combo = widget()
            combo.currentTextChanged.connect(
                functools.partial(self._set_setting, name))
            layout.addWidget(qlabel)
            layout.addWidget(combo)
            self._settings[name] = (qlabel, combo)
        layout.addStretch()
        self._capture_button = QtWidgets.QPushButton('Capture')
        layout.addWidget(self._capture_button)

        self._worker = CameraWorker()

        self._worker.state_changed.connect(self._state_changed)
        self._worker.error.connect(self._error)
        self._worker.setting_changed.connect(self._setting_changed)

        self._connect_button.clicked.connect(self._worker.connect)
        self._capture_button.clicked.connect(self._worker.capture)
        self._change_setting.connect(self._worker.change_setting)
        self._state_changed(CameraWorker.State.DISCONNECTED)

    def stop(self):
        self._worker.stop()

    @QtCore.Slot(CameraWorker.State)
    def _state_changed(self, state):
        if state == CameraWorker.State.DISCONNECTED:
            self._connected = False
            self._status_bar.showMessage(f'Camera disconnected.')
            self._connect_button.setText('Connect')
            self._capture_button.setEnabled(False)
            for label, combo in self._settings.values():
                label.setEnabled(False)
                combo.setEnabled(False)
        elif state == CameraWorker.State.BUSY:
            self._connect_button.setText('Disconnect')
            self._capture_button.setEnabled(False)
            for label, combo in self._settings.values():
                label.setEnabled(False)
                combo.setEnabled(False)
        elif state == CameraWorker.State.READY:
            if not self._connected:
                name = self._worker.name
                port = self._worker.port
                self._status_bar.showMessage(f'Connected to {name} on {port}.')
            self._connected = True
            self._connect_button.setText('Disconnect')
            self._capture_button.setEnabled(True)
            for label, combo in self._settings.values():
                label.setEnabled(True)
                combo.setEnabled(True)

    @QtCore.Slot(str)
    def _error(self, error):
        QtWidgets.QMessageBox.critical(self, 'Camera Error', error)

    @QtCore.Slot(CameraWorker.SettingChange)
    def _setting_changed(self, change):
        # called by camera on change
        _, combo = self._settings[change.name]
        combo.clear()
        combo.addItems(change.choices)
        combo.setCurrentText(change.value)

    def _set_setting(self, name, value):
        # called by ui on change
        if not self._connected:
            return
        self._change_setting.emit(name, value)
