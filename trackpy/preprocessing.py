from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six
import numpy as np
from scipy.ndimage.filters import uniform_filter1d
from scipy.ndimage.fourier import fourier_gaussian

from .utils import print_update, validate_tuple


# When loading module, try to use pyFFTW ("Fastest Fourier Transform in the
# West") if it is available.
try:
    import pyfftw
except ImportError:
    # Use numpy.
    USING_FFTW = False
    fftn = np.fft.fftn
    ifftn = np.fft.ifftn
else:
    USING_FFTW = True
    pyfftw.interfaces.cache.enable()
    planned = False

    def fftn(a):
        global planned
        if not planned:
            print_update("Note: FFTW is configuring itself. This will take " +
                         "several seconds, but subsequent calls will run " +
                         "*much* faster.")
            planned = True
        a = pyfftw.n_byte_align(a, a.dtype.alignment)
        return pyfftw.interfaces.numpy_fft.fftn(a).astype(np.complex128)

    def ifftn(a):
        a = pyfftw.n_byte_align(a, a.dtype.alignment)
        return pyfftw.interfaces.numpy_fft.ifftn(a)


def bandpass(image, lshort, llong, threshold=None, analyze_background=False):
    """Convolve with a Gaussian to remove short-wavelength noise,
    and subtract out long-wavelength variations,
    retaining features of intermediate scale.

    Parmeters
    ---------
    image : ndarray
    lshort : small-scale cutoff (noise)
    llong : large-scale cutoff
    for both lshort and llong:
        give a tuple value for different sizes per dimension
        give int value for same value for all dimensions
        when 2*lshort >= llong, no noise filtering is applied

    threshold : float or integer
        By default, 1 for integer images and 1/256. for float images.

    Returns
    -------
    ndarray, the bandpassed image
    """
    lshort = validate_tuple(lshort, image.ndim)
    llong = validate_tuple(llong, image.ndim)
    if np.any([x*2 >= y for (x, y) in zip(lshort, llong)]):
        raise ValueError("The smoothing length scale must be more" +
                         "than twice the noise length scale.")
    if threshold is None:
        if np.issubdtype(image.dtype, np.integer):
            threshold = 1
        else:
            threshold = 1/256.
    settings = dict(mode='nearest', cval=0)
    axes = range(image.ndim)
    sizes = [x*2+1 for x in llong]
    boxcar = np.asarray(image)
    for (axis, size) in zip(axes, sizes):
        boxcar = uniform_filter1d(boxcar, size, axis, **settings)
    gaussian = ifftn(fourier_gaussian(fftn(image), lshort)).real
    result = gaussian - boxcar
    signal = result > threshold
    if not analyze_background:
        return np.where(signal, result, 0)
    background = image[~signal]
    return np.where(signal, result, 0), background.mean(), background.std()


def scale_to_gamut(image, original_dtype, return_scale_factor=False):
    scale_factor = np.iinfo(original_dtype).max / image.max()
    scaled = (scale_factor * image.clip(min=0.)).astype(original_dtype)
    if return_scale_factor:
        return scaled, scale_factor
    return scaled
