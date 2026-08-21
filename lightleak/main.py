import PIL.Image

from PySide6 import QtCore, QtWidgets

import lightleak.camera
import lightleak.imageview


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('lightleak')
        self.setMinimumSize(640, 480)

        status = QtWidgets.QStatusBar(self)
        self.setStatusBar(status)

        panels = QtWidgets.QHBoxLayout()
        left_panel = QtWidgets.QVBoxLayout()
        right_panel = QtWidgets.QVBoxLayout()
        image = lightleak.imageview.ImageView()
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

    with lightleak.camera.Camera.default() as cam:
        local['cam'] = cam
        code.interact(local=local)


def main():
    import sys
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
