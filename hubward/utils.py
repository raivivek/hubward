import gzip
import numpy as np
import matplotlib
import pybedtools
from docutils.core import publish_string
from pybedtools.contrib.bigbed import bigbed
from pybedtools.featurefuncs import add_color
import bleach


# copied over from metaseq.colormap_adjust to avoid pulling in all of
# metaseq...
def smart_colormap(vmin, vmax, color_high='#b11902', hue_low=0.6):
    """
    Creates a "smart" colormap that is centered on zero, and accounts for
    asymmetrical vmin and vmax by matching saturation/value of high and low
    colors.

    It works by first creating a colormap from white to `color_high`.  Setting
    this color to the max(abs([vmin, vmax])), it then determines what the color
    of min(abs([vmin, vmax])) should be on that scale.  Then it shifts the
    color to the new hue `hue_low`, and finally creates a new colormap with the
    new hue-shifted as the low, `color_high` as the max, and centered on zero.

    :param color_high: a matplotlib color -- try "#b11902" for a nice red
    :param hue_low: float in [0, 1] -- try 0.6 for a nice blue
    :param vmin: lowest value in data you'll be plotting
    :param vmax: highest value in data you'll be plotting
    """
    # first go from white to color_high
    orig_cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'test', ['#FFFFFF', color_high], N=2048)

    # For example, say vmin=-3 and vmax=9.  If vmin were positive, what would
    # its color be?
    vmin = float(vmin)
    vmax = float(vmax)
    mx = max([vmin, vmax])
    mn = min([vmin, vmax])
    frac = abs(mn / mx)
    rgb = orig_cmap(frac)[:-1]

    # Convert to HSV and shift the hue
    hsv = list(colorsys.rgb_to_hsv(*rgb))
    hsv[0] = hue_low
    new_rgb = colorsys.hsv_to_rgb(*hsv)
    new_hex = matplotlib.colors.rgb2hex(new_rgb)

    zeropoint = -vmin / (vmax - vmin)

    # Create a new colormap using the new hue-shifted color as the low end
    new_cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        'test', [(0, new_rgb), (zeropoint, '#FFFFFF'), (1, color_high)],
        N=2048)

    return new_cmap



def fix_macs_wig(fn, genome, output=None, add_chr=False, to_ignore=None):
    """
    wig files created by MACS often are extended outside the chromsome ranges.
    This function edits an input WIG file to fit within the chromosome
    boundaries defined by `genome`.

    If `add_chr` is True, then prefix each chromosome name with "chr".

    Also gets rid of any track lines.

    Returns the output filename.

    fn : str
        Input WIG filename. Can be gzipped, if extension ends in .gz.

    genome : str or dict

    output : str or None
        If None, writes to temp file

    to_ignore : list
        List of chromosomes to ignore.
    """

    if output is None:
        output = pybedtools.BedTool._tmp()
    if to_ignore is None:
        to_ignore = []
    genome = pybedtools.chromsizes(genome)
    with open(output, 'w') as fout:
        if fn.endswith('.gz'):
            f = gzip.open(fn)
        else:
            f = open(fn)
        for line in f:
            if line.startswith('track'):
                continue
            if line.startswith('variableStep'):
                a, b, c = line.strip().split()
                prefix, chrom = b.split('=')
                if add_chr:
                    chrom = 'chr' + chrom
                if chrom in to_ignore:
                    continue
                fout.write(' '.join([a, prefix + '=' + chrom, c]) + '\n')
                span = int(c.split('=')[1])
                continue
            pos, val = line.strip().split()
            if chrom in to_ignore:
                continue
            if (int(pos) + span) >= genome[chrom][1]:
                continue
            fout.write(line)
    return output


def colored_bigbed(x, color, genome, target, autosql=None, bedtype=None):
    """
    if color is "smart", then use metaseq's smart colormap centered on zero.

    otherwise, use singlecolormap.

    assumes that you have scores in BedTool x; this will zero all scores in the
    final bigbed
    """
    norm = x.colormap_normalize()
    if color == 'smart':
        cmap = smart_colormap(norm.vmin, norm.vmax)
    else:
        cmap = singlecolormap(color)

    def func(f):
        f = add_color(f, cmap, norm)
        f.score = '0'
        return f

    x = x\
        .sort()\
        .each(func)\
        .saveas()
    bigbed(x, genome=genome, output=target, _as=autosql, bedtype=bedtype)


def singlecolormap(color, func=None, n=64):
    """
    Creates a linear colormap where `color` is the top, and func(color) is the
    bottom.

    `func` should take an RGB tuple as its only input.  If `func` is None, then
    use a light gray as the min.

    `n` is the number of levels.
    """
    if func is None:
        def func(x):
            return '0.9'

    rgb = np.array(matplotlib.colors.colorConverter.to_rgb(color))
    return matplotlib.colors.LinearSegmentedColormap.from_list(
        name='colormap',
        colors=[func(rgb), rgb],
        N=n,
    )


def colortuple(col):
    rgb = np.array(matplotlib.colors.colorConverter.to_rgb(col))
    rgb = [int(i * 255) for i in rgb]
    return ','.join(map(str, rgb))


def reSTify(s):
    html = publish_string(
        source=s,
        writer_name='html',
        settings=None,
        settings_overrides={'embed_stylesheet': False},
    )
    safe = bleach.ALLOWED_TAGS[:]
    for i in range(1, 5):
        safe.append('h%s' % i)

    safe.extend([
        'p',
        'img',
        'pre',
        'tt',
        'a',
    ]
    )

    attributes = {
        'img': ['alt', 'src'],
        'a': ['href'],
    }

    return bleach.clean(html, tags=safe, strip=True, attributes=attributes)


def add_chr(f):
    f.chrom = 'chr' + f.chrom
    return f


if __name__ == "__main__":
    text = """

Raw data
--------
The original data is a flat text file in GFF format
(http://www.sanger.ac.uk/Software/formats/GFF) listing the positions of all 412
LADs (Drosophila melanogaster genome sequence release 4.3).

Score (column 6) indicates the fraction of array probes inside the LAD with
a positive LAM DamID logratio, after applying a running median filter with
window size 5.

Processing
----------
Features were converted to BED format, and converted from the dm2 to the dm3
assembly using UCSC's liftOver.  Grayscale colors were assigned based on the
original scores, with black being the highest.
"""
    html = reSTify(text)
    print html
