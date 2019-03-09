import numpy as np
from spatialmaps.tools import autocorrelation, fftcorrelate2d, masked_corrcoef2d
from spatialmaps.maps import find_peaks, peak_to_peak_distance

def rotate_corr(acorr, mask):
    import numpy.ma as ma
    from scipy.ndimage.interpolation import rotate
    m_acorr = ma.masked_array(acorr, mask=mask)
    angles = range(30, 180+30, 30)
    corr = []
    # Rotate and compute correlation coefficient
    for angle in angles:
        rot_acorr = rotate(acorr, angle, reshape=False)
        rot_acorr = ma.masked_array(rot_acorr, mask=mask)
        corr.append(masked_corrcoef2d(rot_acorr, m_acorr)[0, 1])
    r60 = corr[1::2]
    r30 = corr[::2]
    return r30, r60


def gridness(rate_map, return_mask=False):
    '''
    Calculates gridness based on the autocorrelation of a rate map.
    The Pearson's product-moment correlation coefficients are calculated between A and A_r,
    where A_r is the rotated version of A at 30, 60, 90, 120, and 150 degrees.
    Finally the gridness is calculated as the
    difference between the minimum of coefficients at 60 and 120 degrees (r60),
    and the maximum of coefficients at 30, 90, and 150 degrees (r30).
    That is, gridness = min(r60) - max(r30).

    Parameters
    ----------
    rate_map_acorr : numpy.ndarray
        autocorrelation of rate map
    box_xlen : float
        side length of quadratic box

    Returns
    -------
    out : gridness
    '''
    import numpy.ma as ma

    acorr = autocorrelation(rate_map, mode='full', normalize=True)

    acorr_maxima = find_peaks(acorr)
    inner_radius = 0.5 * peak_to_peak_distance(acorr_maxima, 0, 1)
    outer_radius = inner_radius + peak_to_peak_distance(acorr_maxima, 0, 6)

    # limit radius to smallest side of map and ensure inner < outer
    outer_radius = np.clip(outer_radius, 0.0, min(acorr.shape) / 2)
    inner_radius = np.clip(inner_radius, 0.0, outer_radius)

    # Speed up the calculation by limiting the autocorr map to the outer area
    center = np.array(acorr.shape) / 2
    lower = (center - outer_radius).astype(int)
    upper = (center + outer_radius).astype(int)
    acorr = acorr[lower[0]:upper[0], lower[1]:upper[1]]

    # create a mask
    ylen, xlen = acorr.shape  # ylen, xlen is the correct order for meshgrid
    x = np.linspace(- xlen / 2., xlen / 2., xlen)
    y = np.linspace(- ylen / 2., ylen / 2., ylen)
    X, Y = np.meshgrid(x, y)
    distance_map = np.sqrt(X**2 + Y**2)
    mask = (distance_map < inner_radius) | (distance_map > outer_radius)

    # calculate the correlation with the rotated maps
    r30, r60 = rotate_corr(acorr, mask=mask)
    gridscore = float(np.min(r60) - np.max(r30))

    if return_mask:
        return gridscore, ma.masked_array(acorr, mask=mask)

    return gridscore


def spacing_and_orientation(peaks, box_size):
    """
    Fits a hex grid to a given set of peaks and returns the orientation.

    Parameters
    ----------
    peaks : Nx2 np.array
                x,y positions of peak centers in real units
    box_size: 1x2 np.array
                size of box in real units (needs to be size of autocorrelogram if that is used)
    Returns
    -------
    spacing : float
                   mean distance to six closest peaks in real units
    orientation : float
                  orientation of hexagon (in radians)

    If the number of peaks is less than seven,
    the function returns NaN for both spacing and orientation.
    """

    peaks = np.array(peaks)

    if len(peaks) < 7:
        return np.nan, np.nan

    # sort by distance to center
    d = np.linalg.norm(peaks - box_size / 2, axis=1)
    d_sort = np.argsort(d)
    center_peak = peaks[d_sort][0]

    # distances to center peak
    relpos = peaks - center_peak
    reldist = np.linalg.norm(relpos, axis=1)

    rel_sort = np.argsort(reldist)

    # index 0 is center
    closest_peaks = peaks[rel_sort][1:7]
    closest_relpos = relpos[rel_sort][1:7]
    closest_distances = reldist[rel_sort][1:7]

    # spacing is distance to six closest peaks
    spacing = np.mean(closest_distances)

    # sort by angle
    a = np.arctan2(closest_relpos[:,0], closest_relpos[:,1])%(2*np.pi)
    a_sort = np.argsort(a)

    # extract lowest angle and convert to degrees
    orientation = a[a_sort][0]

    return spacing, orientation
