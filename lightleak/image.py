import functools
import io
import pathlib

import numpy
import PIL.Image
import PIL.ImageFilter
import rawpy


def _srgb_to_lin(srgb):
    return numpy.where(
        srgb <= 0.04045,
        srgb * 0.0773993808,
        pow(srgb * 0.9478672986 + 0.0521327014, 2.4),
    )


def _lin_to_srgb(lin):
    return numpy.where(
        lin <= 0.0031308,
        lin * 12.92,
        1.055 * pow(lin, 0.41666) - 0.055,
    )


class Processor:
    def __init__(self):
        self._flat_field = None

    def open(self, path):
        path = pathlib.Path(path)
        with open(path, 'rb') as f:
            return self.load(f, extension=path.suffix)

    def load_bytes(self, data, extension=''):
        for loader in [self._load_raw, self._load_pillow]:
            try:
                linear, satpixels, whitebalance = loader(data)
                break
            except Exception:
                continue
        else:
            raise RuntimeError('no loader for image')

        return Image(data, extension, linear, satpixels, whitebalance)

    def load(self, f, extension=''):
        data = f.read()
        return self.load_bytes(data, extension=extension)

    def _load_raw(self, data):
        with io.BytesIO(data) as f:
            raw = rawpy.imread(f)
        linear = raw.postprocess(
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=16,
            user_flip=0,
            no_auto_scale=True,
            no_auto_bright=True,
            gamma=(1, 1),
        )

        satpixels = raw.raw_image_visible
        white_level = raw.white_level

        while satpixels.ndim > 2:
            satpixels = numpy.max(satpixels, axis=-1)
        satpixels = satpixels >= white_level

        return (linear / white_level, satpixels, raw.camera_whitebalance[:3])

    def _load_pillow(self, data):
        with io.BytesIO(data) as f:
            im = PIL.Image.open(f)
            srgbi = numpy.array(im.convert('RGB'))
        satpixels = numpy.max(srgbi, axis=-1)
        pixelmax = (1 << (8 * srgbi.dtype.itemsize)) - 1
        satpixels = satpixels >= pixelmax
        linear = _srgb_to_lin(srgbi / pixelmax)

        return (linear, satpixels, numpy.array([1.0, 1.0, 1.0]))

    def set_flat_field(self, im):
        self._flat_field = im


class Image:
    def __init__(self, data, extension, linear, satpixels, whitebalance):
        self._data = data
        self._extension = extension
        self._linear = linear
        self._satpixels = satpixels
        self._whitebalance = whitebalance / numpy.max(whitebalance)

        # preload some properties
        self.preview
        self.clipped
        self.focus

    def save(self, path):
        ext = self._extension
        if not ext:
            ext = '.raw'

        with open(str(path) + ext, 'wb') as f:
            f.write(self._data)

    @functools.cached_property
    def preview(self):
        lin = self._linear * self._whitebalance
        lin /= numpy.percentile(lin, 99)
        srgb = _lin_to_srgb(lin)
        clipped = numpy.clip(srgb, 0.0, 1.0)
        preview = numpy.round(255 * clipped).astype(numpy.uint8)
        return PIL.Image.fromarray(preview)

    @functools.cached_property
    def clipped(self):
        clipped = numpy.array(self.preview)
        clipped[self._satpixels] = [255, 0, 0]
        return PIL.Image.fromarray(clipped)

    @functools.cached_property
    def focus(self):
        return self.preview.convert('L').filter(PIL.ImageFilter.FIND_EDGES)
