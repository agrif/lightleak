from PySide6 import QtWidgets

import lightleak.ui


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('lightleak')
        self.setMinimumSize(800, 600)

        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)

        panels = QtWidgets.QHBoxLayout()
        panels.setSpacing(0)
        panels.setContentsMargins(0, 0, 0, 0)

        self._capture_panel = lightleak.ui.CapturePanel(status_bar)
        self._image_panel = lightleak.ui.ImagePanel()
        self._image_view = lightleak.ui.ImageView()

        panels.addWidget(self._capture_panel)
        panels.addWidget(self._image_view)
        panels.addWidget(self._image_panel)

        self._capture_panel.captured.connect(self._image_panel.set_image)
        self._image_panel.image_changed.connect(self._image_view.set_image)

        root = QtWidgets.QWidget()
        root.setLayout(panels)
        self.setCentralWidget(root)

    def closeEvent(self, event):
        self._capture_panel.stop()
