import dataclasses
import functools
import os
import pathlib
import re

from PySide6 import QtCore, QtWidgets

import lightleak.image


@dataclasses.dataclass
class Row:
    open: QtWidgets.QPushButton
    path: QtWidgets.QLineEdit
    name: QtWidgets.QLineEdit | QtWidgets.QComboBox
    left: QtWidgets.QPushButton
    right: QtWidgets.QPushButton
    action: QtWidgets.QPushButton


class ImageWorker(QtCore.QObject):
    loaded = QtCore.Signal(lightleak.image.Image)

    def __init__(self, processor):
        super().__init__()

        self._processor = processor

        self._thread = QtCore.QThread()
        self.moveToThread(self._thread)
        self._thread.start()

    def stop(self):
        self._thread.quit()

    @QtCore.Slot(pathlib.Path)
    def load_image(self, path):
        try:
            im = self._processor.open(path)
        except Exception:
            self.loaded.emit(None)
        else:
            self.loaded.emit(im)


class FileSelect(QtWidgets.QWidget):
    _input_changed = QtCore.Signal(pathlib.Path)
    saved = QtCore.Signal(pathlib.Path)
    input_busy = QtCore.Signal(bool)

    @property
    def loaded(self):
        return self._worker.loaded

    def __init__(self, processor):
        super().__init__()

        self._input_busy = False
        self._input_paths = []
        self._input_i = 0

        self._digit_re = re.compile(r'\d+')
        self._output_path = None
        self._output_template = None
        self._output_i = None

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)

        self._input = self._add_row(layout, 0, combo=True)
        self._output = self._add_row(layout, 1)
        self._worker = ImageWorker(processor)

        self._input.open.setText('Open Input')
        self._input.action.setText('Load')

        self._output.open.setText('Open Output')
        self._output.action.setText('Save')

        self._input.open.clicked.connect(self._open_input)
        self._input.name.currentIndexChanged.connect(self._set_input_index)
        self._input.left.clicked.connect(
            functools.partial(self.step_input, -1))
        self._input.right.clicked.connect(
            functools.partial(self.step_input, 1))
        self._input.action.clicked.connect(self._reload_input)

        self._output.open.clicked.connect(self._open_output)
        self._output.name.editingFinished.connect(self._set_output_name)
        self._output.left.clicked.connect(
            functools.partial(self.step_output, -1))
        self._output.right.clicked.connect(
            functools.partial(self.step_output, 1))
        self._output.action.clicked.connect(self.save_output)

        self._input_changed.connect(self._worker.load_image)
        self._worker.loaded.connect(self._image_loaded)

        self._set_enableds()
        self.set_output(pathlib.Path.cwd())

    def stop(self):
        self._worker.stop()

    def set_input_busy(self, busy):
        self._input_busy = busy
        self._set_enableds()

    def _add_row(self, layout, row, combo=False):

        def icon(f):
            return self.style().standardIcon(
                f(QtWidgets.QStyle.StandardPixmap),
            )

        open_button = QtWidgets.QPushButton()
        layout.addWidget(open_button, row, 0)

        path = QtWidgets.QLineEdit()
        path.setEnabled(False)
        path.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight |
            QtCore.Qt.AlignmentFlag.AlignBaseline,
        )
        layout.addWidget(path, row, 1)

        if combo:
            name = QtWidgets.QComboBox()
        else:
            name = QtWidgets.QLineEdit()
        layout.addWidget(name, row, 2)

        left = QtWidgets.QPushButton(icon(lambda e: e.SP_ArrowLeft), '')
        layout.addWidget(left, row, 3)

        right = QtWidgets.QPushButton(icon(lambda e: e.SP_ArrowRight), '')
        layout.addWidget(right, row, 4)

        action = QtWidgets.QPushButton()
        layout.addWidget(action, row, 5)

        return Row(
            open=open_button,
            path=path,
            name=name,
            left=left,
            right=right,
            action=action,
        )

    def _set_enableds(self):
        self._input.open.setEnabled(not self._input_busy)
        self._input.left.setEnabled(
            bool(self._input_paths) and
            self._input_i > 0 and
            not self._input_busy,
        )
        self._input.right.setEnabled(
            bool(self._input_paths) and
            self._input_i < len(self._input_paths) - 1 and
            not self._input_busy,
        )
        self._input.name.setEnabled(
            bool(self._input_paths) and not self._input_busy)
        self._input.action.setEnabled(
            bool(self._input_paths) and not self._input_busy)

        self._output.left.setEnabled(
            bool(self._output_path) and
            self._output_i is not None and self._output_i > 0)
        self._output.right.setEnabled(
            bool(self._output_path) and self._output_i is not None)
        self._output.name.setEnabled(bool(self._output_path))
        self._output.action.setEnabled(
            bool(self._output_path) and not self._input_busy)

    def _open_input(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            caption='Open Images',
        )
        if paths:
            self.set_input(paths)

    def _open_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            caption='Select Output Directory',
        )
        if path:
            self.set_output(path)

    def set_input(self, paths):
        self._input_paths = [pathlib.Path(p).absolute() for p in paths]
        self._input_i = 0
        self._input.name.clear()
        self._input.name.addItems([p.name for p in self._input_paths])
        self.step_input(0)

    def _set_input_index(self, index):
        if index < 0:
            self._input_i = 0
            self.loaded.emit(None)
        else:
            self._input_i = index
            self._input_changed.emit(self._input_paths[self._input_i])
            self.input_busy.emit(True)

        self._set_enableds()

    def _reload_input(self):
        if self._input_paths:
            self._set_input_index(self._input.name.currentIndex())

    @QtCore.Slot(lightleak.image.Image)
    def _image_loaded(self, im):
        self.input_busy.emit(False)

    def step_input(self, step):
        if self._input_paths:
            self._input_i += step
            self._input_i = min(
                max(self._input_i, 0), len(self._input_paths) - 1)

            path = self._input_paths[self._input_i]
            self._input.path.setText(str(path.parent) + os.path.sep)
            self._input.name.setCurrentIndex(self._input_i)
        else:
            self._input.path.setText('')
            self._input.name.setCurrentText('')

        self._set_enableds()

    def set_output(self, path):
        path = pathlib.Path(path).absolute()
        name = self._output.name.text()
        if path.is_file():
            name = path.stem
            path = path.parent

        self._output_path = path
        self._set_output_name(name)
        self.step_output(0)

    def _set_output_name(self, name=None):
        if name is None:
            name = self._output.name.text()
        if not name:
            name = 'capture-00'

        start = end = len(name)
        digits = ''
        for m in self._digit_re.finditer(name):
            start = m.start()
            end = m.end()
            digits = m.group()

        head = name[:start]
        tail = name[end:]
        num_digits = len(digits)

        if num_digits:
            self._output_template = lambda i: f'{head}{i:0{num_digits}d}{tail}'
            self._output_i = int(digits)
        else:
            self._output_template = lambda _: name
            self._output_i = None

        self._output.name.setText(self._output_template(self._output_i))
        self._output.name.clearFocus()
        self._set_enableds()

    def step_output(self, step):
        if self._output_path:
            if self._output_i is not None:
                self._output_i = max(self._output_i + step, 0)
            self._output.path.setText(str(self._output_path) + os.path.sep)
            self._output.name.setText(self._output_template(self._output_i))
        else:
            self._output.path.setText('')
            self._output.name.setText('')

        self._set_enableds()

    def save_output(self):
        if not self._output_path:
            return
        path = self._output_path / self._output_template(self._output_i)
        self.saved.emit(path)
