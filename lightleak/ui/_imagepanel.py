import dataclasses
import functools
import pathlib
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


class ChecklistLabel(QtWidgets.QWidget):
    def __init__(self, text):
        super().__init__()

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._icon = QtWidgets.QLabel()
        layout.addWidget(QtWidgets.QLabel(text))
        layout.addWidget(self._icon)

        self._icon.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight |
            QtCore.Qt.AlignmentFlag.AlignBaseline,
        )

        self.setChecked(False)

    def _set_standard(self, f):
        pixmap = self.style().standardPixmap(
            f(QtWidgets.QStyle.StandardPixmap),
        )
        self._icon.setPixmap(pixmap)

    def setChecked(self, checked):
        if checked:
            self._set_standard(lambda e: e.SP_DialogApplyButton)
        else:
            self._set_standard(lambda e: e.SP_DialogCancelButton)


class ChecklistButton(QtWidgets.QWidget):
    clicked = QtCore.Signal(bool)

    def __init__(self, label_text, set_text):
        super().__init__()

        self._label_text = label_text
        self._set_text = set_text
        self._checked = False
        self._enabled = True

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._label = ChecklistLabel(label_text)
        self._button = QtWidgets.QPushButton(self._set_text)
        layout.addWidget(self._label)
        layout.addWidget(self._button)

        self._button.clicked.connect(self._on_click)

        self.setChecked(self._checked)

    def setChecked(self, checked):
        self._checked = checked
        self.setEnabled(self._enabled)
        self._label.setChecked(checked)
        if checked:
            self._button.setText('Unset')
        else:
            self._button.setText(self._set_text)

    def setEnabled(self, enabled):
        self._enabled = enabled
        self._button.setEnabled(enabled or self._checked)

    def _on_click(self):
        if self._checked:
            answer = QtWidgets.QMessageBox.question(
                self,
                f'Unset {self._label_text}?',
                f'Are you sure you want to unset {self._label_text}?',
            )
            if answer & QtWidgets.QMessageBox.StandardButtons.Yes:
                self.clicked.emit(self._checked)
        else:
            self.clicked.emit(self._checked)


class ImagePanel(QtWidgets.QWidget):
    image_changed = QtCore.Signal(PIL.Image.Image)

    def __init__(self, processor):
        super().__init__()

        self._processor = processor
        self._input_busy = False
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

        layout.addSpacing(20)
        self._flat_field = ChecklistButton('Flat Field', 'Use Current')
        self._flat_field.clicked.connect(self._set_flat_field)
        layout.addWidget(self._flat_field)

        layout.addStretch()

        self.set_image(None)

    def _set_image_type(self, ty, checked):
        if not checked:
            return
        self._image_type = ty

        if self._image:
            self.image_changed.emit(self._image_type.get(self._image))
        else:
            self.image_changed.emit(None)

    def set_input_busy(self, busy):
        self._input_busy = busy
        self._set_enableds()

    def _set_enableds(self):
        for w in [self._flat_field]:
            w.setEnabled(bool(self._image) and not self._input_busy)

    @QtCore.Slot(lightleak.image.Image)
    def set_image(self, image):
        self._image = image
        self._set_image_type(self._image_type, True)
        self._set_enableds()

    @QtCore.Slot(pathlib.Path)
    def save_image(self, path):
        if self._image:
            self._image.save(path)

    def _set_flat_field(self, checked):
        if checked:
            self._processor.set_flat_field(None)
            self._flat_field.setChecked(False)
        elif self._image:
            self._processor.set_flat_field(self._image)
            self._flat_field.setChecked(True)
