from PySide6 import QtWidgets

import lightleak.ui


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('lightleak')
        self.setMinimumSize(800, 600)

        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)

        processor = lightleak.image.Processor()

        self._capture_panel = lightleak.ui.CapturePanel(status_bar, processor)
        self._file_select = lightleak.ui.FileSelect(processor)
        self._image_panel = lightleak.ui.ImagePanel()
        self._image_view = lightleak.ui.ImageView()

        self._capture_panel.captured.connect(self._image_panel.set_image)
        self._capture_panel.input_busy.connect(self._input_busy)
        self._file_select.loaded.connect(self._image_panel.set_image)
        self._file_select.saved.connect(self._image_panel.save_image)
        self._file_select.input_busy.connect(self._input_busy)
        self._image_panel.image_changed.connect(self._image_view.set_image)

        stack = QtWidgets.QVBoxLayout()
        panels = QtWidgets.QHBoxLayout()
        stack.setSpacing(0)
        stack.setContentsMargins(0, 0, 0, 0)

        stack.addWidget(self._file_select)
        stack.addLayout(panels)

        panels.addWidget(self._capture_panel)
        panels.addWidget(self._image_view)
        panels.addWidget(self._image_panel)

        root = QtWidgets.QWidget()
        root.setLayout(stack)
        self.setCentralWidget(root)

    def set_input(self, inputs):
        self._file_select.set_input(inputs)

    def set_output(self, output):
        self._file_select.set_output(output)

    def closeEvent(self, event):
        self._capture_panel.stop()
        self._file_select.stop()

    def _input_busy(self, busy):
        self._capture_panel.set_input_busy(busy)
        self._file_select.set_input_busy(busy)
