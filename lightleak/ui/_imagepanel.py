from __future__ import annotations

import dataclasses
import functools
import pathlib
import time
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
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._icon = QtWidgets.QLabel()
        if isinstance(text, QtWidgets.QWidget):
            layout.addWidget(text)
        else:
            layout.addWidget(QtWidgets.QLabel(text))
        layout.addWidget(self._icon)

        self._icon.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight |
            QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self._icon.setSizePolicy(QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Minimum,
        ))

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

    def __init__(self, label_text):
        super().__init__()

        self._label_text = label_text
        self._enabled = True

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._button = QtWidgets.QPushButton(self._label_text)
        self._label = ChecklistLabel(self._button)
        layout.addWidget(self._label)

        self._button.clicked.connect(self._on_click)

        self.setChecked(self._label.checked())

    def _update_button(self):
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

    def __init__(self, label_text):
        super().__init__(label_text)

        self._canceled_time = time.time()

        app = QtWidgets.QApplication.instance()
        app.installEventFilter(self)

    def _update_button(self):
        self._button.setText(self._label_text)
        if self._button.isChecked():
            self._button.setText('Cancel')
        elif self._label.checked():
            self._button.setCheckable(False)
        else:
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
            self._canceled_time = time.time()
            self.canceled.emit()

        return False

    def _on_click(self, toggled):
        # no good very bad hack: ignore events after an eventFilter cancel
        # for a very short time
        if time.time() < self._canceled_time + 0.1:
            self._button.setChecked(False)
            return

        checkable = self._button.isCheckable()
        self._update_button()
        if checkable and not toggled:
            self.canceled.emit()
        else:
            super()._on_click()


class SaveWorker(QtCore.QObject):
    @dataclasses.dataclass
    class SaveParams:
        im: lightleak.image.Image
        path: pathlib.Path
        save_inverted: bool
        flip_inverted: bool
        linear_inverted: bool

    output_busy = QtCore.Signal(SaveParams)

    def __init__(self):
        super().__init__()

        self._thread = QtCore.QThread()
        self.moveToThread(self._thread)
        self._thread.start()

    def stop(self):
        self._thread.quit()

    @QtCore.Slot(SaveParams)
    def save_image(self, params):
        self.output_busy.emit(True)
        try:
            params.im.save(params.path)
            if params.save_inverted and params.im.inverted is not None:
                params.im.save_inverted(
                    params.path,
                    linear=params.linear_inverted,
                    flip=params.flip_inverted,
                )
        finally:
            self.output_busy.emit(False)


class ImagePanel(QtWidgets.QWidget):
    image_changed = QtCore.Signal(PIL.Image.Image)
    start_image_pick = QtCore.Signal(bool)
    image_flipped = QtCore.Signal(bool)
    _start_save_image = QtCore.Signal(SaveWorker.SaveParams)

    @property
    def output_busy(self):
        return self._worker.output_busy

    def __init__(self, processor):
        super().__init__()

        self._processor = processor
        self._input_busy = False
        self._image = None
        self._image_type = IMAGE_TYPES[0]
        self._image_picked_final = lambda *args: None
        self._worker = SaveWorker()

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        margins = layout.getContentsMargins()
        layout.setContentsMargins(margins[0], 0, margins[2], 0)

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

        display_layout.addSpacing(10)
        flipped = QtWidgets.QCheckBox('Flip Horizontally')
        flipped.toggled.connect(self.image_flipped)
        display_layout.addWidget(flipped)

        layout.addSpacing(20)

        self._neg_box = QtWidgets.QGroupBox('Negatives')
        self._neg_box.setCheckable(True)
        self._neg_box.setChecked(False)
        self._neg_box.toggled.connect(self._set_enableds)
        layout.addWidget(self._neg_box)

        neg_layout = QtWidgets.QVBoxLayout()
        self._neg_box.setLayout(neg_layout)

        gamma_layout = QtWidgets.QHBoxLayout()
        neg_layout.addLayout(gamma_layout)
        gamma_layout.addWidget(QtWidgets.QLabel('Gamma'))
        gamma = QtWidgets.QDoubleSpinBox()
        gamma_layout.addWidget(gamma)
        gamma.setStepType(
            QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        gamma.setMinimum(0.01)
        gamma.setMaximum(3.0)
        gamma.valueChanged.connect(self._processor.set_gamma)
        gamma.setValue(1.0)

        self._flat_field = ChecklistButton('Flat Field')
        self._flat_field.clicked.connect(self._set_flat_field)
        neg_layout.addWidget(self._flat_field)

        self._exposed = ChecklistButtonModal('Exposed')
        self._exposed.clicked.connect(
            functools.partial(
                self._set_exposure, self._exposed,
                self._processor.set_exposed))
        self._exposed.canceled.connect(self._cancel_image_pick)
        neg_layout.addWidget(self._exposed)

        self._unexposed = ChecklistButtonModal('Unexposed')
        self._unexposed.clicked.connect(
            functools.partial(
                self._set_exposure, self._unexposed,
                self._processor.set_unexposed))
        self._unexposed.canceled.connect(self._cancel_image_pick)
        neg_layout.addWidget(self._unexposed)

        layout.addSpacing(20)

        self._save_inverted = QtWidgets.QGroupBox('Save Inverted')
        self._save_inverted.setCheckable(True)
        self._save_inverted.setChecked(True)
        self._save_inverted.toggled.connect(self._set_enableds)
        layout.addWidget(self._save_inverted)

        save_inverted_layout = QtWidgets.QVBoxLayout()
        self._save_inverted.setLayout(save_inverted_layout)

        self._flip_inverted = QtWidgets.QCheckBox('Flip Horizontally')
        self._flip_inverted.setChecked(True)
        save_inverted_layout.addWidget(self._flip_inverted)

        self._linear_inverted = QtWidgets.QCheckBox('Linear Space')
        self._linear_inverted.setChecked(True)
        save_inverted_layout.addWidget(self._linear_inverted)

        layout.addStretch()

        self._start_save_image.connect(self._worker.save_image)
        self.set_image(None)

    def stop(self):
        self._worker.stop()

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

        self._save_inverted.setEnabled(
            bool(self._image) and self._image.inverted is not None and
            self._neg_box.isChecked(),
        )

    @QtCore.Slot(lightleak.image.Image)
    def set_image(self, image):
        self._image = image
        self._set_image_type(self._image_type, True)
        self._set_enableds()

    @QtCore.Slot(pathlib.Path)
    def save_image(self, path):
        if not self._image:
            return

        self._start_save_image.emit(SaveWorker.SaveParams(
            im=self._image,
            path=path,
            save_inverted=self._save_inverted.isChecked() and \
                self._save_inverted.isEnabled(),
            flip_inverted=self._flip_inverted.isChecked(),
            linear_inverted=self._linear_inverted.isChecked(),
        ))

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
