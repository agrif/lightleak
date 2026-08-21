import subprocess
import time

import gphoto2


class Camera:
    def __init__(self, cam: gphoto2.Camera):
        self._cam = cam
        self._window = None
        self._configs = {}

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cam:
            self.close()

    def open(self):
        try:
            self._cam.init()
            self._window = self._cam.get_config()
            return
        except gphoto2.GPhoto2Error as e:
            pass

        # try to unmount gphoto2 and try again
        try:
            subprocess.run(
                ['gio', 'mount', '-s', 'gphoto2'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except Exception:
            pass

        self._cam.init()
        self._window = self._cam.get_config()

    def close(self):
        for v in self._configs.values():
            v.reset()
        self._configs = {}
        self._window = None

        self._cam.exit()
        self._cam = None

    @classmethod
    def default(cls):
        return cls(gphoto2.Camera())

    def get_config(self, name):
        if self._window is None:
            raise RuntimeError('camera not opened')

        widget = self._window
        parts = name.split('/')
        for part in parts:
            if not part:
                continue
            widget = widget.get_child_by_name(part)

        parts = []
        w = widget
        while w is not None:
            parts.append(w.get_name())
            w = w.get_parent()
        parts.reverse()
        normal = '/' + '/'.join(parts)

        try:
            return self._configs[normal]
        except KeyError:
            pass

        classes = {
            gphoto2.GP_WIDGET_RADIO: ConfigRadio,
        }

        cls = classes.get(widget.get_type(), Config)
        config = cls(normal, self._cam, self._window, widget)
        self._configs[normal] = config
        return config

    def get_summary(self):
        return self._cam.get_summary().text

    @property
    def name(self):
        return self._cam.get_abilities().model

    @property
    def port(self):
        return self._cam.get_port_info().get_path()

    def capture(self):
        path = self._cam.capture(gphoto2.GP_CAPTURE_IMAGE)
        f = self._cam.file_get(path.folder, path.name,
                               gphoto2.GP_FILE_TYPE_NORMAL)
        data = f.get_data_and_size().tobytes()
        self._cam.file_delete(path.folder, path.name)
        return data


class Config:
    def __init__(self, name, cam, window, widget):
        self._name = name
        self._cam = cam
        self._window = window
        self._widget = widget
        self._value = widget.get_value()
        self._initial = self._value
        self._readonly = bool(widget.get_readonly())

    @property
    def readonly(self):
        return self._readonly

    @property
    def value(self):
        return self._value

    def set(self, val):
        if self._readonly:
            raise ValueError(f'config {self._name} is read only')
        self._widget.set_value(val)
        self._cam.set_config(self._window)
        self._value = self._widget.get_value()

    def reset(self):
        self.set(self._initial)


class ConfigRadio(Config):
    def __init__(self, *args):
        super().__init__(*args)
        self._choices = list(self._widget.get_choices())

    @property
    def choices(self):
        return self._choices

    def set(self, val):
        if not val in self._choices:
            raise ValueError(f'value {val!r} not valid for {self._name}')
        super().set(val)
