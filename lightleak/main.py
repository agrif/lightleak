import enum

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.camera
import lightleak.imageview


class CameraWorker(QtCore.QObject):
    class State(enum.StrEnum):
        DISCONNECTED = enum.auto()
        READY = enum.auto()
        BUSY = enum.auto()

    state_changed = QtCore.Signal(State)
    error = QtCore.Signal(str)

    def __init__(self):
        super().__init__()

        self._cam = None

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
            self.state_changed.emit(self.State.READY)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self._connected = False

        self.setWindowTitle('lightleak')
        self.setMinimumSize(640, 480)

        self._status = QtWidgets.QStatusBar(self)
        self.setStatusBar(self._status)

        panels = QtWidgets.QHBoxLayout()
        left_panel = QtWidgets.QVBoxLayout()
        right_panel = QtWidgets.QVBoxLayout()
        image = lightleak.imageview.ImageView()
        image.set_image(PIL.Image.open('output.png'))

        panels.addLayout(left_panel)
        panels.addWidget(image)
        panels.addLayout(right_panel)

        self._connect = QtWidgets.QPushButton('Connect')
        left_panel.addWidget(self._connect)
        left_panel.addStretch()
        left_panel.addWidget(QtWidgets.QLabel('left'))

        right_panel.addWidget(QtWidgets.QLabel('right'))

        root = QtWidgets.QWidget()
        root.setLayout(panels)
        self.setCentralWidget(root)

        self._worker = CameraWorker()
        self._worker.state_changed.connect(self.state_changed)
        self._worker.error.connect(self.worker_error)
        self._connect.clicked.connect(self._worker.connect)
        self.state_changed(CameraWorker.State.DISCONNECTED)

    def closeEvent(self, event):
        self._worker.stop()

    @QtCore.Slot(CameraWorker.State)
    def state_changed(self, state):
        if state == CameraWorker.State.DISCONNECTED:
            self._connected = False
            self._status.showMessage(f'Camera disconnected.')
            self._connect.setText('Connect')
        elif state == CameraWorker.State.BUSY:
            self._connect.setText('Disconnect')
        elif state == CameraWorker.State.READY:
            if not self._connected:
                name = self._worker.name
                port = self._worker.port
                self._status.showMessage(f'Connected to {name} on {port}.')
            self._connected = True
            self._connect.setText('Disconnect')

    @QtCore.Slot(str)
    def worker_error(self, error):
        QtWidgets.QMessageBox.critical(self, 'Camera Error', error)


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
