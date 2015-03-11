import numpy as np
import matplotlib
import pybedtools
from docutils.core import publish_string
from pybedtools.contrib.bigbed import bigbed
from pybedtools.featurefuncs import add_color
import bleach
from metaseq.colormap_adjust import smart_colormap

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
