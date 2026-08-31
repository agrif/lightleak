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
        self._unexposed_patch = None
        self._unexposed_rect = None
        self._exposed_patch = None
        self._exposed_rect = None

    def open(self, path):
        path = pathlib.Path(path)
        with open(path, 'rb') as f:
            return self.load(f, extension=path.suffix)

    def load_bytes(self, data, extension=''):
        for loader in [self._load_raw, self._load_pillow]:
            try:
                linear, satpixels = loader(data)
                break
            except Exception:
                continue
        else:
            raise RuntimeError('no loader for image')

        return Image(self, data, extension, linear, satpixels)

    def load(self, f, extension=''):
        data = f.read()
        return self.load_bytes(data, extension=extension)

    def _load_raw(self, data):
        with io.BytesIO(data) as f:
            raw = rawpy.imread(f)

        linear = raw.postprocess(
            output_color=rawpy.ColorSpace.raw,
            output_bps=16,
            user_flip=0,
            no_auto_scale=True,
            no_auto_bright=True,
            gamma=(1, 1),
        )

        xyz_to_srgb = numpy.array([
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ])

        xyz_to_cam = raw.rgb_xyz_matrix[0:3, 0:3]
        convert = xyz_to_srgb @ numpy.linalg.inv(xyz_to_cam)
        linear = linear @ convert.T

        satpixels = raw.raw_image_visible
        white_level = raw.white_level

        while satpixels.ndim > 2:
            satpixels = numpy.max(satpixels, axis=-1)
        satpixels = satpixels >= white_level

        return (linear / white_level, satpixels)

    def _load_pillow(self, data):
        with io.BytesIO(data) as f:
            im = PIL.Image.open(f)
            srgbi = numpy.array(im.convert('RGB'))
        satpixels = numpy.max(srgbi, axis=-1)
        pixelmax = (1 << (8 * srgbi.dtype.itemsize)) - 1
        satpixels = satpixels >= pixelmax
        linear = _srgb_to_lin(srgbi / pixelmax)

        return (linear, satpixels)

    def set_flat_field(self, im):
        self._flat_field = im

    def set_unexposed(self, rect, patch):
        self._unexposed_rect = rect
        self._unexposed_patch = patch

    def set_exposed(self, rect, patch):
        self._exposed_rect = rect
        self._exposed_patch = patch


class Image:
    def __init__(self, processor, data, extension, linear, satpixels):
        self._processor = processor
        self._data = data
        self._extension = extension
        self._linear = linear
        self._satpixels = satpixels

        # preload some properties
        self.preview
        self.clipped
        self.focus
        self.flat_preview

    def save(self, path):
        ext = self._extension
        if not ext:
            ext = '.raw'

        with open(str(path) + ext, 'wb') as f:
            f.write(self._data)

    @property
    def width(self):
        return self._linear.shape[1]

    @property
    def height(self):
        return self._linear.shape[0]

    @property
    def linear(self):
        return self._linear

    def linear_patch(self, x0, y0, x1, y1):
        def clamp(a, m, n):
            return min(max(a, m), n)

        height, width, _ = self._linear.shape

        xs = [clamp(x, 0, width) for x in [x0, x1]]
        xs.sort()
        ys = [clamp(y, 0, height) for y in [y0, y1]]
        ys.sort()

        return self._linear[ys[0]:ys[1],xs[0]:xs[1]]

    def _preview_linear(self, lin):
        lin /= numpy.percentile(lin[numpy.isfinite(lin)], 99)
        lin[~numpy.isfinite(lin)] = 1.0
        srgb = _lin_to_srgb(numpy.maximum(lin, 0.0))
        clipped = numpy.minimum(srgb, 1.0)
        preview = numpy.round(255 * clipped).astype(numpy.uint8)
        return PIL.Image.fromarray(preview)

    @functools.cached_property
    def preview(self):
        return self._preview_linear(self._linear)

    @functools.cached_property
    def clipped(self):
        clipped = numpy.array(self.preview)
        clipped[self._satpixels] = [255, 0, 0]
        return PIL.Image.fromarray(clipped)

    @functools.cached_property
    def focus(self):
        return self.preview.convert('L').filter(PIL.ImageFilter.FIND_EDGES)

    @functools.cached_property
    def _flat_corrected(self):
        flat = self._processor._flat_field
        if not flat:
            return self._linear
        if flat._linear.shape != self._linear.shape:
            return self._linear

        corrected = numpy.divide(
            self._linear, flat._linear,
            out=numpy.zeros_like(self._linear),
            where=flat._linear != 0,
        )
        corrected[flat._linear == 0] = numpy.inf
        return corrected

    @functools.cached_property
    def flat_preview(self):
        return self._preview_linear(self._flat_corrected)
