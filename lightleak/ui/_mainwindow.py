import enum

from PySide6 import QtWidgets

import lightleak.ui


class MainWindow(QtWidgets.QMainWindow):
    class ActionState(enum.StrEnum):
        UNSET = enum.auto()
        CAPTURE = enum.auto()
        LOAD = enum.auto()

    def __init__(self):
        super().__init__()

        self._input_busy = False
        self._output_busy = False
        self._action_state = self.ActionState.UNSET
        self._save_pending = False

        self.setWindowTitle('lightleak')
        height = 600
        self.setMinimumSize(int(round(16 * height / 9)), height)

        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)

        processor = lightleak.image.Processor()

        self._capture_panel = lightleak.ui.CapturePanel(status_bar, processor)
        self._file_select = lightleak.ui.FileSelect(processor)
        self._image_panel = lightleak.ui.ImagePanel(processor)
        self._histogram = lightleak.ui.Histogram()
        self._image_view = lightleak.ui.ImageView()
        self._next_button = QtWidgets.QPushButton()
        self._same_button = QtWidgets.QPushButton()

        self._capture_panel.captured.connect(self._image_panel.set_image)
        self._capture_panel.captured.connect(self._histogram.set_image)
        self._capture_panel.captured.connect(self._on_capture)
        self._capture_panel.input_busy.connect(self._set_input_busy)
        self._file_select.loaded.connect(self._image_panel.set_image)
        self._file_select.loaded.connect(self._histogram.set_image)
        self._file_select.loaded.connect(self._on_load)
        self._file_select.saved.connect(self._image_panel.save_image)
        self._file_select.input_busy.connect(self._set_input_busy)
        self._image_panel.image_changed.connect(self._image_view.set_image)
        self._image_panel.scale_changed.connect(self._image_view.set_scale)
        self._image_panel.scale_to_fit.connect(self._image_view.scale_to_fit)
        self._image_panel.start_image_pick.connect(
            self._image_view.start_image_pick)
        self._image_panel.output_busy.connect(self._set_output_busy)
        self._image_panel.image_flipped.connect(self._image_view.set_flipped)
        self._image_panel.image_histogram.connect(self._histogram.setVisible)
        self._image_view.scaled.connect(self._image_panel.set_scale)
        self._image_view.image_picked.connect(self._image_panel.image_picked)
        self._next_button.clicked.connect(self._next_action)
        self._same_button.clicked.connect(self._same_action)

        layout = QtWidgets.QVBoxLayout()
        panels = QtWidgets.QHBoxLayout()
        center = QtWidgets.QStackedLayout()
        right = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        center.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        right.setSpacing(self._image_panel.layout().spacing())
        right.setContentsMargins(
            *self._image_panel.layout().getContentsMargins())

        layout.addWidget(self._file_select)
        layout.addLayout(panels)

        panels.addWidget(self._image_panel)
        panels.addLayout(center)
        panels.addLayout(right)

        center.addWidget(self._image_view)
        center.addWidget(self._histogram)
        self._histogram.setVisible(False)

        right.addWidget(self._next_button)
        right.addWidget(self._same_button)
        right.addSpacing(20)
        right.addWidget(self._capture_panel)

        root = QtWidgets.QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self._update_action()

    def _update_action(self):
        if self._action_state == self.ActionState.CAPTURE:
            self._next_button.setText('Capture Next && Save')
            self._same_button.setText('Recapture && Save')
        else:
            self._next_button.setText('Load Next && Save')
            self._same_button.setText('Reload && Save')

        if self._action_state == self.ActionState.UNSET:
            self._next_button.setEnabled(False)
            self._same_button.setEnabled(False)
        else:
            busy = self._input_busy or self._output_busy
            self._next_button.setEnabled(not busy)
            self._same_button.setEnabled(not busy)
            if self._action_state == self.ActionState.LOAD:
                if not self._file_select.input_has_next:
                    self._next_button.setEnabled(False)

    def _next_action(self):
        self._save_pending = True
        self._set_output_busy(True)

        self._file_select.step_output(1)
        if self._action_state == self.ActionState.CAPTURE:
            self._capture_panel.capture()
        elif self._action_state == self.ActionState.LOAD:
            self._file_select.step_input(1)

    def _same_action(self):
        self._save_pending = True
        self._set_output_busy(True)

        if self._action_state == self.ActionState.CAPTURE:
            self._capture_panel.capture()
        elif self._action_state == self.ActionState.LOAD:
            self._file_select.reload_input()

    def _on_load(self, im):
        if self._save_pending and im is not None:
            self._file_select.save_output()
            self._save_pending = False
        self._action_state = self.ActionState.LOAD
        self._update_action()

    def _on_capture(self, im):
        if self._save_pending and im is not None:
            self._file_select.save_output()
            self._save_pending = False
        self._action_state = self.ActionState.CAPTURE
        self._update_action()

    def set_input(self, inputs):
        self._file_select.set_input(inputs)

    def set_output(self, output):
        self._file_select.set_output(output)

    def closeEvent(self, event):
        self._capture_panel.stop()
        self._file_select.stop()
        self._image_panel.stop()

    def _set_input_busy(self, busy):
        self._input_busy = busy
        self._update_action()
        self._capture_panel.set_input_busy(busy)
        self._file_select.set_input_busy(busy)
        self._image_panel.set_input_busy(busy)

    def _set_output_busy(self, busy):
        self._output_busy = busy
        self._update_action()
        self._file_select.set_output_busy(busy)
