import sys

import gphoto2
import PIL.Image
import PIL.ImageQt

from PySide6 import QtCore, QtGui, QtWidgets


class Camera:
    def __init__(self, cam: gphoto2.Camera):
        self._cam = cam

    def __enter__(self):
        self._cam.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cam.exit()

    @classmethod
    def default(cls):
        return cls(gphoto2.Camera())

    def _get_config(self, name):
        widget = self._cam.get_config()
        for part in name.split('/'):
            if not part:
                continue
            widget = widget.get_child_by_name(part)

        return widget.get_value()

    def get_summary(self):
        return self._cam.get_summary().text

    def capture(self):
        path = self._cam.capture(gphoto2.GP_CAPTURE_IMAGE)
        f = self._cam.file_get(path.folder, path.name,
                               gphoto2.GP_FILE_TYPE_NORMAL)
        data = f.get_data_and_size().tobytes()
        self._cam.file_delete(path.folder, path.name)
        return data


class ImageView(QtWidgets.QGraphicsView):
    scale_factor = 1.25

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

        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50)))
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

    def set_image(self, im):
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

        self._zoom = 0
        self.set_scale(1)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta:
            return

        step = delta // abs(delta)
        zoom = max(-10, self._zoom + int(step))
        if zoom == self._zoom:
            return

        self._zoom = zoom
        if zoom:
            factor = self.scale_factor ** step
            self.scale(factor, factor)
        else:
            self.set_scale(self.scale_factor ** zoom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.set_scale(self.scale_factor ** self._zoom)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('scanner.py')
        self.setMinimumSize(640, 480)

        status = QtWidgets.QStatusBar(self)
        self.setStatusBar(status)

        panels = QtWidgets.QHBoxLayout()
        left_panel = QtWidgets.QVBoxLayout()
        right_panel = QtWidgets.QVBoxLayout()
        image = ImageView()
        image.set_image(PIL.Image.open('output.png'))

        panels.addLayout(left_panel)
        panels.addWidget(image)
        panels.addLayout(right_panel)

        camera = QtWidgets.QLabel('Not Connected')
        left_panel.addWidget(camera)
        connect = QtWidgets.QPushButton('Connect')
        left_panel.addWidget(connect)
        left_panel.addStretch()
        left_panel.addWidget(QtWidgets.QLabel('left'))

        right_panel.addWidget(QtWidgets.QLabel('right'))

        root = QtWidgets.QWidget()
        root.setLayout(panels)
        self.setCentralWidget(root)


def interact():
    import code
    import readline
    import rlcompleter

    local = globals()

    readline.set_completer(rlcompleter.Completer(local).complete)
    readline.parse_and_bind('tab: complete')

    with Camera.default() as cam:
        local['cam'] = cam
        code.interact(local=local)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)

    parser = QtCore.QCommandLineParser()
    parser.addHelpOption()

    opt_interact= QtCore.QCommandLineOption(
        ['i', 'interact'],
        'open an interactive REPL',
    )
    parser.addOption(opt_interact)

    parser.process(app)

    if parser.isSet(opt_interact):
        interact()
        return

    window = MainWindow()
    window.show()

    app.exec()


if __name__ == '__main__':
    main()
