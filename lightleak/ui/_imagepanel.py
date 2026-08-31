from __future__ import annotations

import dataclasses
import functools
import pathlib
import typing

import PIL.Image

from PySide6 import QtCore, QtGui, QtWidgets

import lightleak.image


@dataclasses.dataclass
class ImageType:
    label: str
    get: typing.Callable[[lightleak.image.Image], PIL.Image.Image]
    enabled: typing.Callable[[lightleak.image.Image | None], bool] = \
        lambda _: True


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
    ImageType(
        label='Flat Corrected',
        get=lambda im: im.flat_preview,
        enabled=lambda im: im is not None and im.flat_preview is not None,
    ),
    ImageType(
        label='Inverted',
        get=lambda im: im.inverted_preview,
        enabled=lambda im: im is not None and im.inverted_preview is not None,
    ),
]


class ChecklistLabel(QtWidgets.QWidget):
    def __init__(self, text):
        super().__init__()

        self._checked = False

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

        self.setChecked(self._checked)

    def _set_standard(self, f):
        pixmap = self.style().standardPixmap(
            f(QtWidgets.QStyle.StandardPixmap),
        )
        self._icon.setPixmap(pixmap)

    def checked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = checked
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
        self._enabled = True

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._label = ChecklistLabel(label_text)
        self._button = QtWidgets.QPushButton(self._set_text)
        layout.addWidget(self._label)
        layout.addWidget(self._button)

        self._button.clicked.connect(self._on_click)

        self.setChecked(self._label.checked())

    def _update_button(self):
        if self._label.checked():
            self._button.setText('Unset')
        else:
            self._button.setText(self._set_text)
        self.setEnabled(self._enabled)

    def checked(self):
        return self._label.checked()

    def setChecked(self, checked):
        self._label.setChecked(checked)
        self._update_button()

    def setEnabled(self, enabled):
        self._enabled = enabled
        self._button.setEnabled(enabled or self._label.checked())

    def _on_click(self):
        if self._label.checked():
            answer = QtWidgets.QMessageBox.question(
                self,
                f'Unset {self._label_text}?',
                f'Are you sure you want to unset {self._label_text}?',
            )
            if answer & QtWidgets.QMessageBox.StandardButtons.Yes:
                self.clicked.emit(True)
        else:
            self.clicked.emit(False)


class ChecklistButtonModal(ChecklistButton):
    canceled = QtCore.Signal()

    def __init__(self, label_text, set_text):
        super().__init__(label_text, set_text)

        app = QtWidgets.QApplication.instance()
        app.installEventFilter(self)

    def _update_button(self):
        if self._button.isChecked():
            self._button.setText('Cancel')
        elif self._label.checked():
            self._button.setText('Unset')
            self._button.setCheckable(False)
        else:
            self._button.setText(self._set_text)
            self._button.setCheckable(True)

        self.setEnabled(self._enabled)

    def setEnabled(self, enabled):
        if not enabled and self._button.isChecked():
            self._button.setChecked(False)
            self._update_button()
            self.canceled.emit()
        else:
            super().setEnabled(enabled)

    def eventFilter(self, obj, event):
        cancel = False

        if isinstance(event, QtGui.QKeyEvent):
            cancel = (event.key() == QtCore.Qt.Key_Escape)
        elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
            cancel = True

        if cancel and self._button.isChecked():
            self._button.setChecked(False)
            self._update_button()
            self.canceled.emit()

        return False

    def _on_click(self, toggled):
        checkable = self._button.isCheckable()
        self._update_button()
        if checkable and not toggled:
            self.canceled.emit()
        else:
            super()._on_click()


class ImagePanel(QtWidgets.QWidget):
    image_changed = QtCore.Signal(PIL.Image.Image)
    start_image_pick = QtCore.Signal(bool)

    def __init__(self, processor):
        super().__init__()

        self._processor = processor
        self._input_busy = False
        self._image = None
        self._image_type = IMAGE_TYPES[0]
        self._image_picked_final = lambda *args: None

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        display_box = QtWidgets.QGroupBox('Image Preview')
        layout.addWidget(display_box)

        display_layout = QtWidgets.QVBoxLayout()
        display_box.setLayout(display_layout)
        self._image_type_buttons = []
        for ty in IMAGE_TYPES:
            radio = QtWidgets.QRadioButton(ty.label)
            if ty == self._image_type:
                radio.setChecked(True)
            radio.toggled.connect(
                functools.partial(self._set_image_type, ty))
            display_layout.addWidget(radio)
            self._image_type_buttons.append(radio)

        layout.addSpacing(20)
        self._flat_field = ChecklistButton('Flat Field', 'Use Current')
        self._flat_field.clicked.connect(self._set_flat_field)
        layout.addWidget(self._flat_field)

        gamma_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(gamma_layout)
        gamma_layout.addWidget(QtWidgets.QLabel('Gamma'))
        gamma = QtWidgets.QDoubleSpinBox()
        gamma_layout.addWidget(gamma)
        gamma.setStepType(
            QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        gamma.setMinimum(0.01)
        gamma.setMaximum(3.0)
        gamma.valueChanged.connect(self._processor.set_gamma)
        gamma.setValue(1.0)

        self._unexposed = ChecklistButtonModal('Unexposed', 'Select')
        self._unexposed.clicked.connect(
            functools.partial(
                self._set_exposure, self._unexposed,
                self._processor.set_unexposed))
        self._unexposed.canceled.connect(self._cancel_image_pick)
        layout.addWidget(self._unexposed)

        self._exposed = ChecklistButtonModal('Exposed', 'Select')
        self._exposed.clicked.connect(
            functools.partial(
                self._set_exposure, self._exposed,
                self._processor.set_exposed))
        self._exposed.canceled.connect(self._cancel_image_pick)
        layout.addWidget(self._exposed)

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
        for w in [self._flat_field, self._unexposed, self._exposed]:
            w.setEnabled(bool(self._image) and not self._input_busy)

        for ty, radio in zip(IMAGE_TYPES, self._image_type_buttons):
            en = ty.enabled(self._image)
            radio.setEnabled(en)
            if not en and radio.isChecked():
                self._image_type_buttons[0].setChecked(True)

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
        self._set_enableds()

    def _cancel_image_pick(self):
        self.start_image_pick.emit(False)

    def _set_exposure(self, button, setter, checked):
        if checked:
            setter(None, None)
            button.setChecked(False)
            self._set_enableds()
        elif self._image:
            self._image_picked_final = functools.partial(
                self._image_picked_final_for, button, setter)
            self.start_image_pick.emit(True)

    @QtCore.Slot(int, int, int, int)
    def image_picked(self, x0, y0, x1, y1):
        self._image_picked_final(x0, y0, x1, y1)

    def _image_picked_final_for(self, button, setter, x0, y0, x1, y1):
        if not self._image:
            return

        patch = self._image.linear_patch(x0, y0, x1, y1)
        if patch.shape[0] == 0 or patch.shape[1] == 0:
            return

        setter((x0, y0, x1, y1), patch)
        button.setChecked(True)
        self._set_enableds()
