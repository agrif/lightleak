import concurrent.futures
import functools
import importlib.resources
import io
import os
import pathlib
import zlib

import numpy
import PIL.Image
import PIL.ImageFilter
import png
import rawpy
import scipy.ndimage


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


class PngChunkWriter(png.Writer):
    def __init__(self, extra_chunks=[], **kwargs):
        super().__init__(**kwargs)
        self._extra_chunks = extra_chunks

    def write_preamble(self, outfile):
        super().write_preamble(outfile)

        for chunk in self._extra_chunks:
            png.write_chunk(outfile, *chunk)


class Processor:
    def __init__(self):
        self._workers = min(32, os.cpu_count())
        self._min_chunk_size = 64
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._workers)

        self._flat_field = None
        self._unexposed = None
        self._unexposed_patch = None
        self._unexposed_rect = None
        self._exposed = None
        self._exposed_patch = None
        self._exposed_rect = None
        self._gamma = 1.0

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
        ], dtype=numpy.float32)

        xyz_to_cam = raw.rgb_xyz_matrix[0:3, 0:3].astype(numpy.float32)
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

        def process(rect, get_slice):
            srgb = get_slice(srgbi).astype(numpy.float32) / pixelmax
            return _srgb_to_lin(srgb)

        linear = self._parallel_array(srgbi, process)

        return (linear, satpixels)

    def set_flat_field(self, im):
        self._flat_field = im
        self._update_exposures()

    def set_unexposed(self, rect, patch):
        self._unexposed_rect = rect
        self._unexposed_patch = patch
        self._update_exposures()

    def set_exposed(self, rect, patch):
        self._exposed_rect = rect
        self._exposed_patch = patch
        self._update_exposures()

    def set_gamma(self, gamma):
        self._gamma = gamma

    def _update_exposures(self):
        def calc(rect, patch):
            if rect is None or patch is None:
                return None

            if self._flat_field:
                flat = self._flat_field.linear_patch(*rect)
                corrected = Image._flat_correct(patch, flat)
            else:
                corrected = patch

            return numpy.mean(corrected, axis=(0, 1))

        self._unexposed = calc(self._unexposed_rect, self._unexposed_patch)
        self._exposed = calc(self._exposed_rect, self._exposed_patch)

    def _parallel_array(self, arr, f):
        height, width, *_ = arr.shape
        chunksize = max(self._min_chunk_size, height // self._workers)

        def iter_chunks():
            y = 0
            while y < height:
                next_y = min(y + chunksize, height)
                yield (0, y, width, next_y)
                y = next_y

        def iter_slice():
            for rect in iter_chunks():
                # funny business with a function to rebind rect
                # to prevent it from changing inside the lambda
                def slice_factory(r):
                    x0, y0, x1, y1 = r
                    return lambda arr: arr[y0:y1, x0:x1]
                yield slice_factory(rect)

        chunks = self._executor.map(f, iter_chunks(), iter_slice())
        return numpy.vstack(list(chunks))


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
        self.inverted_preview

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

    def _preview_linear(self, linear, autoscale=False):
        if linear is None:
            return None

        if autoscale:
            # decimate before calculating 99'th percentile for speed
            k = 3
            small = linear[:-k:k, :-k:k]
            scale = numpy.percentile(small[numpy.isfinite(small)], 99)
        else:
            scale = 1.0

        def process(rect, get_slice):
            lin = get_slice(linear).copy()
            lin /= scale
            lin[~numpy.isfinite(lin)] = 1.0
            srgb = _lin_to_srgb(numpy.maximum(lin, 0.0))
            clipped = numpy.minimum(srgb, 1.0)
            preview = numpy.round(0xff * clipped).astype(numpy.uint8)
            return preview

        preview = self._processor._parallel_array(linear, process)
        return PIL.Image.fromarray(preview)

    @functools.cached_property
    def preview(self):
        return self._preview_linear(self._linear, autoscale=True)

    @functools.cached_property
    def clipped(self):
        clipped = numpy.array(self.preview)
        clipped[self._satpixels] = [255, 0, 0]
        return PIL.Image.fromarray(clipped)

    @functools.cached_property
    def focus(self):
        colormap = numpy.array([
            [0.0, 0.0, 0.0, 0.0, 0.0],
            [1.9, 0.0, 0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 1.0, 1.0],
            [4.0, 0.0, 1.0, 0.0, 1.0],
            [6.0, 1.0, 1.0, 0.0, 1.0],
        ], dtype=numpy.float32)

        # doing this in parallel breaks it into strips which technically
        # changes the convolutions, but this is acceptable for focus preview

        def process_mag(rect, get_slice):
            lin = get_slice(self.linear)
            mono = lin @ numpy.array([0.2125, 0.7154, 0.0721],
                                     dtype=numpy.float32)
            mono = scipy.ndimage.gaussian_filter(mono, 2.0)

            xs = scipy.ndimage.sobel(mono, axis=0, mode='nearest')
            ys = scipy.ndimage.sobel(mono, axis=1, mode='nearest')

            mag = numpy.sqrt(xs * xs + ys * ys)
            return mag

        magnitude = self._processor._parallel_array(self.linear, process_mag)
        std = numpy.std(magnitude)

        def process_color(rect, get_slice):
            mag = get_slice(magnitude) / std

            color = numpy.zeros((*mag.shape, 4), dtype=mag.dtype)
            color[:, :, 0] = numpy.interp(mag, colormap[:, 0], colormap[:, 1])
            color[:, :, 1] = numpy.interp(mag, colormap[:, 0], colormap[:, 2])
            color[:, :, 2] = numpy.interp(mag, colormap[:, 0], colormap[:, 3])
            color[:, :, 3] = numpy.interp(mag, colormap[:, 0], colormap[:, 4])

            colori = numpy.round(0xff * color).astype(numpy.uint8)
            return colori

        colori = self._processor._parallel_array(magnitude, process_color)
        focus = PIL.Image.fromarray(colori, 'RGBA')
        return PIL.Image.alpha_composite(self.preview.convert('RGBA'), focus)

    @classmethod
    def _flat_correct(cls, lin, flat):
        if lin.shape != flat.shape:
            return lin

        corrected = numpy.divide(
            lin, flat,
            out=numpy.zeros_like(lin),
            where=flat != 0,
        )
        corrected[flat == 0] = numpy.inf
        return corrected

    @functools.cached_property
    def _flat_corrected(self):
        flat = self._processor._flat_field
        if not flat:
            return None

        return self._flat_correct(self._linear, flat._linear)

    @functools.cached_property
    def flat_preview(self):
        return self._preview_linear(self._flat_corrected, autoscale=True)

    @functools.cached_property
    def inverted(self):
        unexposed = self._processor._unexposed
        exposed = self._processor._exposed
        gamma = self._processor._gamma

        if unexposed is None or exposed is None:
            return None

        source = self._flat_corrected
        if source is None:
            source = self._linear

        # convert to densities
        unexposed = -numpy.log10(unexposed)
        exposed = -numpy.log10(exposed)
        dmax = exposed - unexposed

        def process(rect, get_slice):
            # convert this to density
            density = -numpy.log10(get_slice(source))

            # calculate relative density
            density = density - unexposed
            density = numpy.clip(density, 0, dmax)

            # Film reacts to exposure E by creating density D according to
            # a curve that is *approximately* linear between log_10 E and D.
            # If that slope is gamma, then
            #     gamma * (D1 - D0) = log_10 E1 - log_10 E0,
            #     gamma * (D1 - D0) = log_10 (E1 / E0)
            #
            # We will rescale the resulting E anyway, so we will arbitrarily
            # work in units where an E = 1 exposure creates a D = 1 density.
            # Using that for D0 and E0,
            #     gamma * (D1 - 1) = log_10 E1,
            #     E1 = 10 ^ (gamma * D1 - gamma)
            # From now on we will drop the 1 subscripts and use plain D and E.
            #
            # We will use E directly for the linear image output, but first
            # it needs to be scaled so that E is in [0, 1] for D in [0, Dmax].
            # First, subtract off the value when D = 0 to force E = 0,
            #     E = 10 ^ (gamma * D - gamma) - 10 ^ -gamma,
            #     E = 10 ^ -gamma * (10 ^ (gamma * D) - 1).
            # Now, divide by the value of that when D = Dmax to force E = 1,
            #     E = (10 ^ (gamma * D) - 1) / (10 ^ (gamma * Dmax) - 1).
            #
            # This is what we use to calculate the linear image. Note that
            # (much like digital gamma) some texts choose to use gamma to
            # denote D / log_10 E, rather than log_10 E / D as we do here,
            # confusing e.g. gamma = 1.0 / 2.2 vs gamma = 2.2.

            # film curve, scaled to [0, 1]
            linear = numpy.power(10, density * gamma) - 1
            linear /= numpy.power(10, dmax * gamma) - 1

            return linear

        return self._processor._parallel_array(source, process)

    @functools.cached_property
    def inverted_preview(self):
        return self._preview_linear(self.inverted)

    def save_inverted(self, path, linear=True):
        inv = self.inverted.copy()
        inv[~numpy.isfinite(inv)] = 1.0
        if linear:
            inv = numpy.clip(inv, 0.0, 1.0)
        else:
            inv = _lin_to_srgb(numpy.maximum(inv, 0.0))
            inv = numpy.minimum(inv, 1.0)
        inv_i = numpy.round(0xffff * inv).astype(numpy.uint16)

        if linear:
            icc_filename = 'sRGB-elle-V2-g10.icc'
            gamma = 1.0
        else:
            icc_filename = 'sRGB-elle-V2-g22.icc'
            gamma = 1.0 / 2.2

        files = importlib.resources.files()
        icc = files.joinpath('icc').joinpath(icc_filename).read_bytes()
        icc_name_s = icc_filename
        icc_name = icc_name_s.strip().encode('latin-1', errors='replace')[:79]
        icc_chunk = (b'iCCP', icc_name + b'\0\0' + zlib.compress(icc))

        w = PngChunkWriter(
            width=self.width,
            height=self.height,
            bitdepth=16,
            greyscale=False,
            gamma=gamma,
            extra_chunks=[icc_chunk],
        )

        with open(str(path) + '.inv.png', 'wb') as f:
            w.write_array(f, inv_i.flatten('C'))
