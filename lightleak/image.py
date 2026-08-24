import io

import numpy
import PIL.Image
import PIL.ImageFilter
import rawpy


class Image:
    def __init__(self, data):
        self._data = data

        with open('capture.cr2', 'wb') as f:
            f.write(data)

        self._pixels, satpixels, white_level = self._load_image()
        shift = 8 * (self._pixels.dtype.itemsize - 1)
        pixels8 = (self._pixels >> shift).astype(numpy.uint8)

        self._preview = PIL.Image.fromarray(pixels8)

        if satpixels.ndim > 2:
            satpixels = numpy.max(satpixels, axis=-1)
        pixels8[satpixels >= white_level] = [255, 0, 0]
        self._clipped = PIL.Image.fromarray(pixels8)

        self._focus = self._preview.convert('L').filter(
            PIL.ImageFilter.FIND_EDGES)

    def _load_image(self):
        try:
            with io.BytesIO(self._data) as f:
                raw = rawpy.imread(f)
                pixels = raw.postprocess(output_bps=16, user_flip=0)
                satpixels = raw.raw_image_visible
                white_level = raw.white_level
            return (pixels, satpixels, white_level)
        except rawpy.LibRawFileUnsupportedError:
            pass

        im = PIL.Image.open(io.BytesIO(self._data))
        pixels = numpy.array(im.convert('RGB'))
        satpixels = pixels
        white_level = (1 << (8 * pixels.dtype.itemsize)) - 1
        return (pixels, satpixels, white_level)

    @property
    def data(self):
        return self._data

    @property
    def pixels(self):
        return self._pixels

    @property
    def preview(self):
        return self._preview

    @property
    def clipped(self):
        return self._clipped

    @property
    def focus(self):
        return self._focus
