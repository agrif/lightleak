import dataclasses
import functools
import typing

import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.image


@dataclasses.dataclass
class ImageType:
    label: str
    get: typing.Callable[[lightleak.image.Image], PIL.Image.Image]


IMAGE_TYPES = [
    ImageType(
        label='Base',
        get=lambda im: im.preview,
    ),
    ImageType(
        label='Clip',
        get=lambda im: im.clipped,
    ),
    ImageType(
        label='Focus',
        get=lambda im: im.focus,
    ),
]


class ImagePanel(QtWidgets.QWidget):
    image_changed = QtCore.Signal(PIL.Image.Image)

    def __init__(self):
        super().__init__()

        self._image = None
        self._image_type = IMAGE_TYPES[0]

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        display_box = QtWidgets.QGroupBox('Image Preview')
        layout.addWidget(display_box)

        display_layout = QtWidgets.QVBoxLayout()
        display_box.setLayout(display_layout)
        for ty in IMAGE_TYPES:
            radio = QtWidgets.QRadioButton(ty.label)
            if ty == self._image_type:
                radio.setChecked(True)
            radio.toggled.connect(
                functools.partial(self._set_image_type, ty))
            display_layout.addWidget(radio)

        layout.addStretch()

    def _set_image_type(self, ty, checked):
        if not checked:
            return
        self._image_type = ty

        if not self._image:
            return
        self.image_changed.emit(self._image_type.get(self._image))

    @QtCore.Slot(lightleak.image.Image)
    def set_image(self, image):
        self._image = image
        self._set_image_type(self._image_type, True)
