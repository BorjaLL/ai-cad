"""Preview PNGs with matplotlib only (no OpenGL, works headless and in CI).

- draw_meshes(): flat-shaded 3D view of several parts, one colour each.
- draw_sections(): filled 2D section polygons (from mesh.section_yz / _xz).
- preview_png(): one figure = a 3D view + any number of section panels.
- autocrop(): trim a white border off an image array.

The agent cannot see the print, but it can look at these PNGs: always render
a section through every joint, not only a 3D view.
"""
from __future__ import annotations

import numpy as np

PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#DA8BC3", "#8C8C8C"]


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return matplotlib, plt


def draw_meshes(ax, parts, colours=None, light=(0.4, -0.5, 0.8), elev=35, azim=-60):
    """Add flat-shaded parts (Manifold or trimesh) to a 3D matplotlib axis."""
    matplotlib, _ = _mpl()
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from manifold3d import Manifold

    from .mesh import to_trimesh
    colours = colours or PALETTE
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for i, m in enumerate(parts):
        tm = to_trimesh(m) if isinstance(m, Manifold) else m
        shade = 0.45 + 0.55 * np.clip(tm.face_normals @ L, 0, 1)
        base = np.array(matplotlib.colors.to_rgb(colours[i % len(colours)]))
        ax.add_collection3d(Poly3DCollection(tm.vertices[tm.faces],
                                             facecolors=np.outer(shade, base), linewidths=0))
        lo = np.minimum(lo, tm.bounds[0])
        hi = np.maximum(hi, tm.bounds[1])
    span = np.maximum(hi - lo, 1e-3)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(span))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def draw_sections(ax, polys_per_part, colours=None, alpha=0.9):
    """Fill section polygons; polys_per_part = [list of (N, 2) arrays] per part."""
    _, _ = _mpl()
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    colours = colours or PALETTE
    for i, pls in enumerate(polys_per_part):
        if not pls:
            continue
        verts = np.concatenate([np.vstack([pl, pl[:1]]) for pl in pls])
        codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(pl) - 1) + [MPath.CLOSEPOLY]
                                for pl in pls])
        ax.add_patch(PathPatch(MPath(verts, codes), fc=colours[i % len(colours)], ec="k",
                               lw=0.4, alpha=alpha))
    ax.set_aspect("equal")
    ax.autoscale_view()


def preview_png(path, parts, title: str = "", sections: list | None = None, colours=None,
                elev=35, azim=-60, dpi=120) -> None:
    """3D view of `parts` plus section panels.

    sections: list of dicts {"title": str, "polys": [polys per part],
              "xlim": (a, b), "ylim": (a, b), "circles": [(x, y, r), ...]}
    """
    _, plt = _mpl()
    from matplotlib.patches import Circle
    sections = sections or []
    n = len(sections)
    per_row = 3
    rows = max(1, -(-n // per_row))
    cols = 2 + min(n, per_row)          # 3D view takes the first two columns
    fig = plt.figure(figsize=(4 * cols, 4.5 * rows))
    gs = fig.add_gridspec(rows, cols)
    ax = fig.add_subplot(gs[:, :2], projection="3d")
    draw_meshes(ax, parts, colours, elev=elev, azim=azim)
    ax.set_title(title)
    for k, s in enumerate(sections):
        axs = fig.add_subplot(gs[k // per_row, 2 + k % per_row])
        draw_sections(axs, s["polys"], colours)
        for (cx, cy, r) in s.get("circles", []):
            axs.add_patch(Circle((cx, cy), r, fill=False, ec="r", lw=0.7, ls="--"))
        if "xlim" in s:
            axs.set_xlim(*s["xlim"])
        if "ylim" in s:
            axs.set_ylim(*s["ylim"])
        axs.set_title(s.get("title", ""), fontsize=9)
        axs.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(str(path), dpi=dpi)
    plt.close(fig)


def autocrop(img: np.ndarray, pad: int = 10, white: int = 245) -> np.ndarray:
    """Trim near-white borders from an RGB(A) image array."""
    a = np.asarray(img)[:, :, :3].astype(int)
    mask = (a < white).any(axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    return img[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]
