import PIL.Image
import PIL.ImageQt

from PySide6 import QtCore, QtGui, QtWidgets


class ImageView(QtWidgets.QGraphicsView):
    # per mouse wheel degree, wheels usually have detents at 15 deg
    scale_factor = 1.25 ** (1 / 15)

    def __init__(self):
        super().__init__()

        self._has_image = False
        self._zoom = 0

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
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    def set_scale(self, scale):
        rect = QtCore.QRectF(self._image.pixmap().rect())
        if not rect or rect.isNull():
            return

        self.setSceneRect(rect)
        if not self._has_image:
            return

        unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
        self.scale(1 / unity.width(), 1 / unity.height())
        view = self.viewport().rect()
        scene = self.transform().mapRect(rect)
        factor = min(
            view.width() / scene.width(),
            view.height() / scene.height(),
        )
        factor *= scale
        self.scale(factor, factor)

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

        if not had_image:
            self._zoom = 0
            self.set_scale(1)

    def wheelEvent(self, event):
        step_per_degree = 8
        step = event.angleDelta().y()
        if not step:
            return

        zoom = max(-10 * 15 * step_per_degree, self._zoom + int(step))
        if zoom == self._zoom:
            return

        self._zoom = zoom
        if zoom:
            factor = self.scale_factor ** (step / step_per_degree)
            self.scale(factor, factor)
        else:
            self.set_scale(self.scale_factor ** (zoom / step_per_degree))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.set_scale(self.scale_factor ** self._zoom)
