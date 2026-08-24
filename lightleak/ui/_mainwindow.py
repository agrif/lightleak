import functools

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.ui


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self._image = None
        self._display_attr = 'preview'

        self.setWindowTitle('lightleak')
        self.setMinimumSize(800, 600)

        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)

        panels = QtWidgets.QHBoxLayout()
        panels.setSpacing(0)
        panels.setContentsMargins(0, 0, 0, 0)

        self._capture_panel = lightleak.ui.CapturePanel(status_bar)
        right_panel = QtWidgets.QVBoxLayout()
        self._imageview = lightleak.ui.ImageView()

        panels.addWidget(self._capture_panel)
        panels.addWidget(self._imageview)
        panels.addLayout(right_panel)

        self._capture_panel.captured.connect(self._image_captured)

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

    def closeEvent(self, event):
        self._capture_panel.stop()

    @QtCore.Slot(PIL.Image.Image)
    def _image_captured(self, image):
        self._image = image
        self._imageview.set_image(getattr(image, self._display_attr))

    def change_display(self, attr, checked):
        if not checked:
            return
        self._display_attr = attr

        if not self._image:
            return
        self._imageview.set_image(getattr(self._image, self._display_attr))
