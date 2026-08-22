import dataclasses
import enum
import functools

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.camera
import lightleak.imageview


SETTINGS = {
    '/main/imgsettings/imageformat': 'Format',
    '/main/imgsettings/iso': 'ISO',
    '/main/imgsettings/whitebalance': 'White Balance',
    '/main/capturesettings/aperture': 'Aperture',
    '/main/capturesettings/shutterspeed': 'Exposure',
}


class CameraWorker(QtCore.QObject):
    class State(enum.StrEnum):
        DISCONNECTED = enum.auto()
        READY = enum.auto()
        BUSY = enum.auto()

    @dataclasses.dataclass
    class ConfigChange:
        name: str
        value: str
        choices: list[str]

    state_changed = QtCore.Signal(State)
    error = QtCore.Signal(str)
    config_changed = QtCore.Signal(ConfigChange)
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
                self.config_changed.emit(
                    self.ConfigChange(name, c.value, c.choices))
                self._configs[name] = c
            self.state_changed.emit(self.State.READY)

    @QtCore.Slot(str, str)
    def set_config(self, name, value):
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


class MainWindow(QtWidgets.QMainWindow):
    change_setting = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()

        self._connected = False
        self._capture = None
        self._display_attr = 'preview'

        self.setWindowTitle('lightleak')
        self.setMinimumSize(800, 600)

        self._status = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._status)

        panels = QtWidgets.QHBoxLayout()
        left_panel = QtWidgets.QVBoxLayout()
        right_panel = QtWidgets.QVBoxLayout()
        self._imageview = lightleak.imageview.ImageView()

        panels.addLayout(left_panel)
        panels.addWidget(self._imageview)
        panels.addLayout(right_panel)

        self._connect_button = QtWidgets.QPushButton('Connect')
        left_panel.addWidget(self._connect_button)
        left_panel.addSpacing(20)
        self._settings = {}
        for name, label in SETTINGS.items():
            qlabel = QtWidgets.QLabel(label)
            combo = QtWidgets.QComboBox()
            combo.currentTextChanged.connect(
                functools.partial(self.setting_changed, name))
            left_panel.addWidget(qlabel)
            left_panel.addWidget(combo)
            self._settings[name] = (qlabel, combo)
        left_panel.addStretch()
        self._capture_button = QtWidgets.QPushButton('Capture')
        left_panel.addWidget(self._capture_button)

        display_box = QtWidgets.QGroupBox('Image Preview')
        right_panel.addWidget(display_box)
        display_layout = QtWidgets.QVBoxLayout()
        display_box.setLayout(display_layout)
        display_types = {
            'preview': 'Base',
            'clipped': 'Clip',
            'focus': 'Focus',
        }
        for i, (attr, name) in enumerate(display_types.items()):
            radio = QtWidgets.QRadioButton(name)
            if i == 0:
                radio.setChecked(True)
            radio.toggled.connect(functools.partial(self.change_display, attr))
            display_layout.addWidget(radio)
        right_panel.addStretch()

        root = QtWidgets.QWidget()
        root.setLayout(panels)
        self.setCentralWidget(root)

        self._worker = CameraWorker()
        self._worker.state_changed.connect(self.worker_state_changed)
        self._worker.error.connect(self.worker_error)
        self._worker.config_changed.connect(self.worker_config_changed)
        self._worker.captured.connect(self.worker_captured)
        self._connect_button.clicked.connect(self._worker.connect)
        self._capture_button.clicked.connect(self._worker.capture)
        self.change_setting.connect(self._worker.set_config)
        self.worker_state_changed(CameraWorker.State.DISCONNECTED)

    def closeEvent(self, event):
        self._worker.stop()

    @QtCore.Slot(CameraWorker.State)
    def worker_state_changed(self, state):
        if state == CameraWorker.State.DISCONNECTED:
            self._connected = False
            self._status.showMessage(f'Camera disconnected.')
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
                self._status.showMessage(f'Connected to {name} on {port}.')
            self._connected = True
            self._connect_button.setText('Disconnect')
            self._capture_button.setEnabled(True)
            for label, combo in self._settings.values():
                label.setEnabled(True)
                combo.setEnabled(True)

    @QtCore.Slot(str)
    def worker_error(self, error):
        QtWidgets.QMessageBox.critical(self, 'Camera Error', error)

    @QtCore.Slot(CameraWorker.ConfigChange)
    def worker_config_changed(self, change):
        _, combo = self._settings[change.name]
        combo.clear()
        combo.addItems(change.choices)
        combo.setCurrentText(change.value)

    def setting_changed(self, name, value):
        if not self._connected:
            return
        self.change_setting.emit(name, value)

    @QtCore.Slot(PIL.Image.Image)
    def worker_captured(self, capture):
        self._capture = capture
        self._imageview.set_image(getattr(capture, self._display_attr))

    def change_display(self, attr, checked):
        if not checked:
            return
        self._display_attr = attr

        if not self._capture:
            return
        self._imageview.set_image(getattr(self._capture, self._display_attr))


def interact():
    import code
    import readline
    import rlcompleter

    local = globals()

    readline.set_completer(rlcompleter.Completer(local).complete)
    readline.parse_and_bind('tab: complete')

    with lightleak.camera.Camera.default() as cam:
        local['cam'] = cam
        code.interact(local=local)


def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)

    parser = QtCore.QCommandLineParser()
    parser.addHelpOption()

    opt_interact= QtCore.QCommandLineOption(
        ['i', 'interact'],
        'open an interactive REPL',
    )
    parser.addOption(opt_interact)

    parser.process(app)

    if parser.isSet(opt_interact):
        interact()
        return

    window = MainWindow()
    window.show()

    app.exec()


if __name__ == '__main__':
    main()
