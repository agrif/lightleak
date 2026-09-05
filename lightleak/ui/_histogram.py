import matplotlib
import matplotlib.backends.backend_qtagg
import matplotlib.figure
import matplotlib.style

from PySide6 import QtCore, QtGui, QtWidgets

import lightleak.image


class PlotView(matplotlib.backends.backend_qtagg.FigureCanvasQTAgg):
    def __init__(self):
        dpi = 80
        px = 1 / dpi

        self._fig = matplotlib.figure.Figure(
            figsize=(500 * px, 200 * px), dpi=dpi)
        self._fig.set_tight_layout(True)
        self._fig.set_facecolor((0.0, 0.0, 0.0, 0.5))

        super().__init__(self._fig)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet('background-color: rgba(0, 0, 0, 0);')

        self.axes = self._fig.add_subplot()
        self.axes.set_facecolor((1.0, 1.0, 1.0, 0.1))
        self.axes.tick_params(color='white', labelcolor='white', which='both')
        for spine in self.axes.spines.values():
            spine.set_edgecolor((0.0, 0.0, 0.0, 0.0))


class Histogram(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        layout = QtWidgets.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 1)
        self.setLayout(layout)

        self._plot = PlotView()
        layout.addWidget(self._plot, 1, 0)

    @QtCore.Slot(lightleak.image.Image)
    def set_image(self, im):
        self._plot.axes.cla()
        if im is None:
            self._plot.draw()
            return

        hists, colors, edges = im.histogram
        self._plot.axes.cla()
        self._plot.axes.set_xlim(edges[0], edges[-1])
        self._plot.axes.set_yscale('log')
        self._plot.axes.minorticks_off()
        width = edges[1] - edges[0]
        for hist, color in zip(hists, colors):
            self._plot.axes.bar(edges[:-1], hist, width=width, align='edge',
                                color=color)
        self._plot.draw()
