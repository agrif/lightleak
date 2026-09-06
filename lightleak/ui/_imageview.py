import PIL.Image
import PIL.ImageQt

from PySide6 import QtCore, QtGui, QtWidgets


class ImageView(QtWidgets.QGraphicsView):
    # per mouse wheel degree, wheels usually have detents at 15 deg
    _scale_factor = 1.25 ** (1 / 15)
    # mouse wheel events use 8 steps per degree
    _steps_per_degree = 8

    scaled = QtCore.Signal(float)
    image_picked = QtCore.Signal(int, int, int, int)

    def __init__(self):
        super().__init__()

        self._has_image = False
        self._scale = 1.0
        self._flipped = False

        self._scene = QtWidgets.QGraphicsScene(self)
        self._image = QtWidgets.QGraphicsPixmapItem()
        self._image.setShapeMode(
            QtWidgets.QGraphicsPixmapItem.ShapeMode.BoundingRectShape,
        )
        self._scene.addItem(self._image)
        self.setScene(self._scene)

        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setResizeAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(20, 20, 20)))

        self._rubber_band = None
        self.rubberBandChanged.connect(self._rubber_band_changed)

    def set_scale(self, scale):
        scale = min(max(scale, 1e-2), 1e2)

        if self._has_image:
            self.resetTransform()
            if self._flipped:
                self.scale(-scale, scale)
            else:
                self.scale(scale, scale)

        if scale == self._scale:
            return

        self._scale = scale
        self.scaled.emit(scale)

    def scale_to_fit(self):
        scene = self.sceneRect()
        view = self.viewport().rect()
        scale = min(
            view.width() / scene.width(),
            view.height() / scene.height(),
        )
        self.set_scale(scale)

    def set_flipped(self, flipped):
        self._flipped = flipped
        self.set_scale(self._scale)

    @QtCore.Slot(PIL.Image.Image)
    def set_image(self, im):
        had_image = self._has_image

        if im:
            qtim = PIL.ImageQt.ImageQt(im)
            pixmap = QtGui.QPixmap.fromImage(qtim)

            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            self._has_image = True
            self._image.setPixmap(pixmap)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
            self._has_image = False
            self._image.setPixmap(QtGui.QPixmap())

        self._scene.setSceneRect(self._image.pixmap().rect())

        if not had_image:
            self.scale_to_fit()

    def wheelEvent(self, event):
        step = event.angleDelta().y()
        if not step:
            return

        scale = self._scale
        scale *= self._scale_factor ** (step / self._steps_per_degree)

        self.set_scale(scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.set_scale(self._scale)

    @QtCore.Slot()
    def start_image_pick(self, start):
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)

    def _rubber_band_changed(self, rect, a, b):
        if rect.isNull():
            if self._has_image:
                self.setDragMode(
                    QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            else:
                self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)

            a, b = self._rubber_band
            rect = [int(round(x)) for x in [*a.toTuple(), *b.toTuple()]]
            self.image_picked.emit(*rect)
        else:
            self._rubber_band = (a, b)
