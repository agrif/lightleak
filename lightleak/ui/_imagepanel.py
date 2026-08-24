import functools

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.image


class ImagePanel(QtWidgets.QWidget):
    image_changed = QtCore.Signal(PIL.Image.Image)

    def __init__(self):
        super().__init__()

        self._image = None
        self._display_attr = 'preview'

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        display_box = QtWidgets.QGroupBox('Image Preview')
        layout.addWidget(display_box)
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
            radio.toggled.connect(
                functools.partial(self._set_display_attr, attr))
            display_layout.addWidget(radio)
        layout.addStretch()

    def _set_display_attr(self, attr, checked):
        if not checked:
            return
        self._display_attr = attr

        if not self._image:
            return
        self.image_changed.emit(getattr(self._image, self._display_attr))

    @QtCore.Slot(lightleak.image.Image)
    def set_image(self, image):
        self._image = image
        self._set_display_attr(self._display_attr, True)
