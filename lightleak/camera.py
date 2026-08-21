import gphoto2


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
