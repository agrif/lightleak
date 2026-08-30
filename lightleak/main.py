import pathlib
import sys

from PySide6 import QtCore, QtWidgets

import lightleak.camera
import lightleak.ui

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
    app = QtWidgets.QApplication(sys.argv)
    app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)

    parser = QtCore.QCommandLineParser()
    parser.addPositionalArgument(
        'input', 'Open files as input.', '[input ...]')
    parser.addHelpOption()

    opt_interact = QtCore.QCommandLineOption(
        ['interact'],
        'Open an interactive REPL.',
    )
    parser.addOption(opt_interact)

    opt_output = QtCore.QCommandLineOption(
        ['o', 'output'],
        'Use the specified output directory.',
        'dir',
    )
    parser.addOption(opt_output)

    parser.process(app)

    if parser.isSet(opt_interact):
        interact()
        return

    window = lightleak.ui.MainWindow()
    window.set_input(parser.positionalArguments())
    if parser.isSet(opt_output):
        output = pathlib.Path(parser.value(opt_output))
        output.mkdir(exist_ok=True)
        window.set_output(parser.value(opt_output))
    window.show()

    app.exec()


if __name__ == '__main__':
    main()
