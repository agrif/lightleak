import subprocess
import time

import gphoto2


class Camera:
    def __init__(self, cam: gphoto2.Camera):
        self._cam = cam

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cam:
            self.close()

    def open(self):
        try:
            self._cam.init()
            return
        except gphoto2.GPhoto2Error:
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

    def close(self):
        self._cam.exit()
        self._cam = None

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
