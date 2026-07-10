#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import warnings

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import FITSFixedWarning, WCS
import astropy.units as u


def temp_cache_dir(name: str) -> str:
    path = Path(tempfile.gettempdir()) / "ds8-frame-plot" / name
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = temp_cache_dir("matplotlib")
if "XDG_CACHE_HOME" not in os.environ:
    os.environ["XDG_CACHE_HOME"] = temp_cache_dir("cache")

import matplotlib

if os.environ.get("DS8_FRAME_PLOT_INTERACTIVE") != "1":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle


SKY_COORD_SYSTEMS = {"fk5", "icrs"}
COORD_SYSTEMS = {*SKY_COORD_SYSTEMS, "image", "physical"}
ANGLE_PATTERN = re.compile(
    r"""^\s*
    (?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)
    \s*(?P<unit>deg|degree|degrees|d|arcsec|asec|\"|arcmin|amin|'|rad|r|pix|pixel|pixels)?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class FrameImage:
    counts: np.ndarray
    wcs: WCS | None
    event_header: fits.Header
    spatial_bin: int = 1
    x_low: float = 0.5
    y_low: float = 0.5


@dataclass(frozen=True)
class CircleRegion:
    label: str
    system: str
    x_text: str
    y_text: str
    radius_text: str


@dataclass(frozen=True)
class AnnulusRegion:
    label: str
    system: str
    x_text: str
    y_text: str
    inner_radius_text: str
    outer_radius_text: str


@dataclass(frozen=True)
class PixelCircle:
    label: str
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class PixelAnnulus:
    label: str
    x: float
    y: float
    inner_radius: float
    radius: float


ParsedRegion = CircleRegion | AnnulusRegion
PixelRegion = PixelCircle | PixelAnnulus


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot an EP/FXT full-frame event image with source/background region overlays.",
    )
    parser.add_argument("eventfile", help="FXT event FITS file")
    parser.add_argument(
        "--src-reg",
        default="src.reg",
        help="DS9 source region file (default: src.reg)",
    )
    parser.add_argument(
        "--bkg-reg",
        default="bkg.reg",
        help="DS9 background region file (default: bkg.reg)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output figure path (default: EVENTFILE-frame.png)",
    )
    parser.add_argument(
        "--extension",
        default="EVENTS",
        help="Event table or image extension to plot (default: EVENTS)",
    )
    parser.add_argument(
        "--x-column",
        default="X",
        help="Event table X column (default: X)",
    )
    parser.add_argument(
        "--y-column",
        default="Y",
        help="Event table Y column (default: Y)",
    )
    parser.add_argument(
        "--cmap",
        default="he",
        help="Matplotlib colormap name, or 'he' for the built-in high-energy map (default: he)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Output figure DPI (default: 300)",
    )
    parser.add_argument(
        "--zoom-factor",
        type=float,
        default=1.2,
        help="Zoom half-width in source-region radii (default: 1.2)",
    )
    parser.add_argument(
        "--main-size",
        type=float,
        default=400.0,
        help="Main panel square side length in image pixels (default: 400)",
    )
    return parser.parse_args(argv)


def resolve_cmap(name: str) -> matplotlib.colors.Colormap:
    if name.lower() != "he":
        return plt.get_cmap(name).copy()

    colors = [
        (0.00, "#000000"),
        (0.10, "#07124a"),
        (0.35, "#005dbe"),
        (0.52, "#00b8c8"),
        (0.68, "#78d64b"),
        (0.82, "#f5d742"),
        (0.94, "#ee4b2b"),
        (1.00, "#ffffff"),
    ]
    return LinearSegmentedColormap.from_list("he", colors).copy()


def column_number(header: fits.Header, column_name: str) -> int:
    target = column_name.strip().upper()
    for index in range(1, int(header.get("TFIELDS", 0)) + 1):
        if str(header.get(f"TTYPE{index}", "")).strip().upper() == target:
            return index
    raise ValueError(f"Column not found in EVENTS table: {column_name}")


def normalize_spatial_bin(value: int | str | None) -> int:
    if value is None:
        return 1
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def frame_limits(header: fits.Header, column_index: int, values: np.ndarray, spatial_bin: int = 1) -> tuple[float, float, int]:
    tmin = header.get(f"TLMIN{column_index}")
    tmax = header.get(f"TLMAX{column_index}")
    if tmin is not None and tmax is not None:
        low = float(tmin) - 0.5
        high = float(tmax) + 0.5
        bins = int(round(high - low))
        if bins > 0:
            binned_bins = int(math.ceil(bins / spatial_bin))
            return low, low + binned_bins * spatial_bin, binned_bins

    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("No finite event coordinates available for image binning.")
    low = math.floor(float(finite.min())) - 0.5
    high = math.ceil(float(finite.max())) + 0.5
    bins = int(round(high - low))
    binned_bins = int(math.ceil(bins / spatial_bin))
    return low, low + binned_bins * spatial_bin, binned_bins


def table_wcs_header(
    event_header: fits.Header,
    x_column_index: int,
    y_column_index: int,
    nx: int,
    ny: int,
    x_low: float = 0.5,
    y_low: float = 0.5,
    spatial_bin: int = 1,
) -> fits.Header:
    axis_map = {
        1: x_column_index,
        2: y_column_index,
    }
    image_header = fits.Header()
    image_header["NAXIS"] = 2
    image_header["NAXIS1"] = nx
    image_header["NAXIS2"] = ny

    for axis, column_index in axis_map.items():
        axis_low = x_low if axis == 1 else y_low
        for out_key, table_key in (
            ("CTYPE", "TCTYP"),
            ("CRPIX", "TCRPX"),
            ("CRVAL", "TCRVL"),
            ("CDELT", "TCDLT"),
            ("CUNIT", "TCUNI"),
        ):
            value = event_header.get(f"{table_key}{column_index}")
            if value is not None:
                if out_key == "CRPIX":
                    image_header[f"{out_key}{axis}"] = (float(value) - axis_low + 0.5 * spatial_bin) / spatial_bin
                elif out_key == "CDELT":
                    image_header[f"{out_key}{axis}"] = float(value) * spatial_bin
                else:
                    image_header[f"{out_key}{axis}"] = value

    if "RADECSYS" in event_header:
        image_header["RADESYS"] = event_header["RADECSYS"]
    if "EQUINOX" in event_header:
        image_header["EQUINOX"] = event_header["EQUINOX"]
    return image_header


def load_frame(
    eventfile: Path,
    extension: str,
    x_column: str,
    y_column: str,
    spatial_bin: int | str | None = 1,
) -> FrameImage:
    spatial_bin = normalize_spatial_bin(spatial_bin)
    with fits.open(eventfile) as hdul:
        hdu = hdul[extension]
        header = hdu.header.copy()

        if hdu.data is not None and getattr(hdu.data, "ndim", 0) == 2 and not hasattr(hdu.data, "names"):
            counts = np.asarray(hdu.data, dtype=float)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FITSFixedWarning)
                wcs = WCS(header)
            if not wcs.has_celestial:
                wcs = None
            return FrameImage(counts=counts, wcs=wcs, event_header=header)

        if hdu.data is None or not hasattr(hdu.data, "names"):
            raise ValueError(f"Extension {extension!r} is not an image or event table.")

        names = {name.upper(): name for name in hdu.data.names}
        if x_column.upper() not in names or y_column.upper() not in names:
            raise ValueError(f"Event table must contain {x_column!r} and {y_column!r} columns.")

        x_name = names[x_column.upper()]
        y_name = names[y_column.upper()]
        x = np.asarray(hdu.data[x_name], dtype=float)
        y = np.asarray(hdu.data[y_name], dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        x = x[finite]
        y = y[finite]
        if x.size == 0:
            raise ValueError("No finite event coordinates available for image binning.")

        x_index = column_number(header, x_name)
        y_index = column_number(header, y_name)
        xmin, xmax, nx = frame_limits(header, x_index, x, spatial_bin)
        ymin, ymax, ny = frame_limits(header, y_index, y, spatial_bin)
        counts, _, _ = np.histogram2d(
            y,
            x,
            bins=(ny, nx),
            range=((ymin, ymax), (xmin, xmax)),
        )

        image_header = table_wcs_header(header, x_index, y_index, nx, ny, xmin, ymin, spatial_bin)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FITSFixedWarning)
            wcs = WCS(image_header)
        if not wcs.has_celestial:
            wcs = None
        return FrameImage(counts=counts, wcs=wcs, event_header=header, spatial_bin=spatial_bin, x_low=xmin, y_low=ymin)


def parse_region_file(path: Path, label: str) -> ParsedRegion:
    if not path.is_file():
        raise FileNotFoundError(f"Region file not found: {path}")

    current_system = "image"
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.lower().startswith("global"):
            continue
        region_part = line.split("#", 1)[0].strip()
        for token in region_part.split(";"):
            token = token.strip()
            if not token:
                continue
            lower = token.lower()
            if lower in COORD_SYSTEMS:
                current_system = lower
                continue
            match = re.match(r"annulus\s*\((?P<body>[^)]*)\)", token, flags=re.IGNORECASE)
            if match is not None:
                values = [part.strip() for part in match.group("body").split(",")]
                if len(values) != 4:
                    raise ValueError(f"Unsupported annulus region in {path}: {token}")
                return AnnulusRegion(
                    label=label,
                    system=current_system,
                    x_text=values[0],
                    y_text=values[1],
                    inner_radius_text=values[2],
                    outer_radius_text=values[3],
                )
            match = re.match(r"circle\s*\((?P<body>[^)]*)\)", token, flags=re.IGNORECASE)
            if match is None:
                continue
            values = [part.strip() for part in match.group("body").split(",")]
            if len(values) != 3:
                raise ValueError(f"Unsupported circle region in {path}: {token}")
            return CircleRegion(
                label=label,
                system=current_system,
                x_text=values[0],
                y_text=values[1],
                radius_text=values[2],
            )

    raise ValueError(f"No circle or annulus region found in {path}")


def parse_angle_degrees(text: str) -> float:
    match = ANGLE_PATTERN.match(text)
    if match is None:
        raise ValueError(f"Unsupported angular radius: {text!r}")
    value = float(match.group("value"))
    unit = (match.group("unit") or "deg").lower()
    if unit in {"deg", "degree", "degrees", "d"}:
        return value
    if unit in {'"', "arcsec", "asec"}:
        return value / 3600.0
    if unit in {"'", "arcmin", "amin"}:
        return value / 60.0
    if unit in {"rad", "r"}:
        return math.degrees(value)
    raise ValueError(f"Radius is not angular: {text!r}")


def parse_sky_coord(region: ParsedRegion) -> SkyCoord:
    system = "fk5" if region.system == "fk5" else "icrs"
    ra_unit = u.hourangle if any(char in region.x_text.lower() for char in (":", "h")) else u.deg
    return SkyCoord(region.x_text, region.y_text, unit=(ra_unit, u.deg), frame=system)


def angular_radius_to_pixels(wcs: WCS, coord: SkyCoord, radius_deg: float) -> float:
    x0, y0 = wcs.world_to_pixel(coord)
    radius = radius_deg * u.deg
    east = coord.directional_offset_by(90.0 * u.deg, radius)
    north = coord.directional_offset_by(0.0 * u.deg, radius)
    x1, y1 = wcs.world_to_pixel(east)
    x2, y2 = wcs.world_to_pixel(north)
    return float(
        0.5
        * (
            math.hypot(float(x1 - x0), float(y1 - y0))
            + math.hypot(float(x2 - x0), float(y2 - y0))
        )
    )


def region_to_pixel_circle(
    region: CircleRegion,
    wcs: WCS | None,
    *,
    x_low: float = 0.5,
    y_low: float = 0.5,
    spatial_bin: int = 1,
) -> PixelCircle:
    spatial_bin = normalize_spatial_bin(spatial_bin)
    if region.system in {"fk5", "icrs"}:
        if wcs is None:
            raise ValueError(f"{region.label} region is sky-based, but the FITS file has no celestial WCS.")
        coord = parse_sky_coord(region)
        x, y = wcs.world_to_pixel(coord)
        radius = angular_radius_to_pixels(wcs, coord, parse_angle_degrees(region.radius_text))
        return PixelCircle(region.label, float(x), float(y), radius)
    raise ValueError(f"{region.label} region must be fk5/icrs, not {region.system!r}. Re-save the region in fk5 coordinates.")


def region_to_pixel_annulus(
    region: AnnulusRegion,
    wcs: WCS | None,
    *,
    x_low: float = 0.5,
    y_low: float = 0.5,
    spatial_bin: int = 1,
) -> PixelAnnulus:
    spatial_bin = normalize_spatial_bin(spatial_bin)
    if region.system in {"fk5", "icrs"}:
        if wcs is None:
            raise ValueError(f"{region.label} region is sky-based, but the FITS file has no celestial WCS.")
        coord = parse_sky_coord(region)
        x, y = wcs.world_to_pixel(coord)
        inner = angular_radius_to_pixels(wcs, coord, parse_angle_degrees(region.inner_radius_text))
        outer = angular_radius_to_pixels(wcs, coord, parse_angle_degrees(region.outer_radius_text))
        return PixelAnnulus(region.label, float(x), float(y), inner, outer)
    raise ValueError(f"{region.label} region must be fk5/icrs, not {region.system!r}. Re-save the region in fk5 coordinates.")


def region_to_pixel(
    region: ParsedRegion,
    wcs: WCS | None,
    *,
    x_low: float = 0.5,
    y_low: float = 0.5,
    spatial_bin: int = 1,
) -> PixelRegion:
    if isinstance(region, AnnulusRegion):
        return region_to_pixel_annulus(region, wcs, x_low=x_low, y_low=y_low, spatial_bin=spatial_bin)
    return region_to_pixel_circle(region, wcs, x_low=x_low, y_low=y_low, spatial_bin=spatial_bin)


def log_norm_for(counts: np.ndarray) -> LogNorm:
    positive = counts[np.isfinite(counts) & (counts > 0)]
    if positive.size == 0:
        raise ValueError("Frame image has no positive counts to plot on a log scale.")
    vmin = max(float(positive.min()) * 0.5, np.finfo(float).tiny)
    vmax = float(positive.max())
    if vmax <= vmin:
        vmax = vmin * 1.01
    return LogNorm(vmin=vmin, vmax=vmax)


def display_limits_for(
    counts: np.ndarray,
    regions: tuple[PixelRegion, ...],
    side_length: float | None = None,
) -> tuple[float, float, float, float]:
    y_indices, x_indices = np.nonzero(np.isfinite(counts) & (counts > 0))
    if x_indices.size == 0:
        return -0.5, counts.shape[1] - 0.5, -0.5, counts.shape[0] - 0.5

    x0 = float(x_indices.min()) - 0.5
    x1 = float(x_indices.max()) + 0.5
    y0 = float(y_indices.min()) - 0.5
    y1 = float(y_indices.max()) + 0.5

    for region in regions:
        x0 = min(x0, region.x - region.radius)
        x1 = max(x1, region.x + region.radius)
        y0 = min(y0, region.y - region.radius)
        y1 = max(y1, region.y + region.radius)

    pad = max(3.0, 0.025 * max(x1 - x0, y1 - y0))
    x0 = max(-0.5, x0 - pad)
    x1 = min(counts.shape[1] - 0.5, x1 + pad)
    y0 = max(-0.5, y0 - pad)
    y1 = min(counts.shape[0] - 0.5, y1 + pad)
    if side_length is None:
        return square_limits_around_bounds(x0, x1, y0, y1)

    x_center = 0.5 * (x0 + x1)
    y_center = 0.5 * (y0 + y1)
    return square_window_inside_frame(x_center, y_center, 0.5 * side_length, counts)


def square_limits_around_bounds(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
) -> tuple[float, float, float, float]:
    width = x1 - x0
    height = y1 - y0
    side = max(width, height)
    x_center = 0.5 * (x0 + x1)
    y_center = 0.5 * (y0 + y1)
    half_side = 0.5 * side
    return (
        x_center - half_side,
        x_center + half_side,
        y_center - half_side,
        y_center + half_side,
    )


def square_window_inside_frame(
    x_center: float,
    y_center: float,
    half_width: float,
    counts: np.ndarray,
) -> tuple[float, float, float, float]:
    frame_x0 = -0.5
    frame_x1 = counts.shape[1] - 0.5
    frame_y0 = -0.5
    frame_y1 = counts.shape[0] - 0.5
    side = min(2.0 * half_width, frame_x1 - frame_x0, frame_y1 - frame_y0)
    half_side = 0.5 * side

    x_center = min(max(x_center, frame_x0 + half_side), frame_x1 - half_side)
    y_center = min(max(y_center, frame_y0 + half_side), frame_y1 - half_side)
    return (
        x_center - half_side,
        x_center + half_side,
        y_center - half_side,
        y_center + half_side,
    )


def draw_region(ax, region: PixelRegion, color: str) -> tuple:
    outline = Circle((region.x, region.y), region.radius, fill=False, lw=2.0, ec="black", alpha=0.9)
    circle = Circle((region.x, region.y), region.radius, fill=False, lw=1.1, ec=color, label=region.label)
    ax.add_patch(outline)
    ax.add_patch(circle)
    if isinstance(region, PixelAnnulus) and region.inner_radius > 0:
        inner_outline = Circle((region.x, region.y), region.inner_radius, fill=False, lw=2.0, ec="black", alpha=0.9, ls="--")
        inner_circle = Circle((region.x, region.y), region.inner_radius, fill=False, lw=1.1, ec=color, ls="--")
        ax.add_patch(inner_outline)
        ax.add_patch(inner_circle)
        return outline, circle, inner_outline, inner_circle
    return outline, circle


def configure_wcs_axes(ax) -> None:
    if hasattr(ax, "coords"):
        ax.coords[0].set_axislabel("RA (J2000)", color="white")
        ax.coords[1].set_axislabel("Dec (J2000)", color="white")
        ax.coords[0].set_ticklabel(color="white")
        ax.coords[1].set_ticklabel(color="white")
        ax.coords[0].set_ticks(color="white")
        ax.coords[1].set_ticks(color="white")
        ax.coords.grid(color="white", alpha=0.25, linestyle=":", linewidth=0.6)
    else:
        ax.set_xlabel("X pixel")
        ax.set_ylabel("Y pixel")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(colors="white")


def apply_ds9_axes_style(ax) -> None:
    ax.set_facecolor("black")
    for spine in ax.spines.values():
        spine.set_color("white")
    ax.tick_params(colors="white")


def add_main_axes_frame(ax) -> None:
    frame = Rectangle(
        (0, 0),
        1,
        1,
        transform=ax.transAxes,
        fill=False,
        ec="white",
        lw=1.0,
        clip_on=False,
        zorder=10,
    )
    ax.add_patch(frame)


def interval_inside_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> tuple[float, float] | None:
    xmin, xmax, ymin, ymax = rect
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    t0 = 0.0
    t1 = 1.0

    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)

    return (t0, t1) if t0 < t1 else None


def subtract_interval(
    intervals: list[tuple[float, float]],
    removed: tuple[float, float] | None,
) -> list[tuple[float, float]]:
    if removed is None:
        return intervals

    cut0, cut1 = removed
    kept: list[tuple[float, float]] = []
    for t0, t1 in intervals:
        if cut1 <= t0 or cut0 >= t1:
            kept.append((t0, t1))
            continue
        if cut0 > t0:
            kept.append((t0, cut0))
        if cut1 < t1:
            kept.append((cut1, t1))
    return kept


def draw_masked_connector(
    ax,
    inset,
    xy_main: tuple[float, float],
    xy_inset: tuple[float, float],
    masks: list[tuple[float, float, float, float]],
    color: str,
    alpha: float,
) -> None:
    fig = ax.figure
    start = fig.transFigure.inverted().transform(ax.transData.transform(xy_main))
    end = fig.transFigure.inverted().transform(inset.transAxes.transform(xy_inset))
    start = (float(start[0]), float(start[1]))
    end = (float(end[0]), float(end[1]))

    intervals = [(0.0, 1.0)]
    for mask in masks:
        intervals = subtract_interval(intervals, interval_inside_rect(start, end, mask))

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    for t0, t1 in intervals:
        if t1 - t0 < 1e-4:
            continue
        line = Line2D(
            [start[0] + dx * t0, start[0] + dx * t1],
            [start[1] + dy * t0, start[1] + dy * t1],
            transform=fig.transFigure,
            color=color,
            lw=0.8,
            alpha=alpha,
            clip_on=False,
            zorder=7,
        )
        fig.add_artist(line)


def add_zoom_link(ax, inset, bounds: tuple[float, float, float, float]) -> None:
    x0, x1, y0, y1 = bounds
    link_color = "white"
    base_rect_style = {
        "fill": False,
        "ec": link_color,
        "lw": 1.0,
        "ls": "-",
        "zorder": 8,
    }

    main_rect = Rectangle((x0, y0), x1 - x0, y1 - y0, alpha=0.5, **base_rect_style)
    inset_rect = Rectangle(
        (0, 0),
        1,
        1,
        transform=inset.transAxes,
        clip_on=False,
        alpha=0.95,
        **base_rect_style,
    )
    ax.add_patch(main_rect)
    inset.add_patch(inset_rect)

    inset_box = inset.get_position()
    label_masks = [
        (inset_box.x0 - 0.070, inset_box.x0 + 0.012, inset_box.y0 - 0.018, inset_box.y1 + 0.018),
        (inset_box.x0 - 0.018, inset_box.x1 + 0.018, inset_box.y0 - 0.060, inset_box.y0 + 0.012),
    ]
    for xy_main, xy_inset in (((x0, y1), (0, 1)), ((x1, y0), (1, 0))):
        draw_masked_connector(ax, inset, xy_main, xy_inset, label_masks, link_color, alpha=0.5)

    ax.text(
        x1,
        y1,
        "Zoom",
        color=link_color,
        fontsize=8,
        ha="left",
        va="bottom",
        zorder=9,
    )


def make_title(eventfile: Path, header: fits.Header) -> str:
    pieces = [
        str(header.get("DETNAM", "")).strip(),
        str(header.get("OBJECT", "")).strip(),
        str(header.get("OBS_ID", "")).strip(),
    ]
    title = " ".join(piece for piece in pieces if piece)
    return title or eventfile.name


def plot_frame(
    frame: FrameImage,
    src_circle: PixelCircle,
    bkg_circle: PixelCircle,
    eventfile: Path,
    output: Path,
    cmap_name: str,
    dpi: int,
    zoom_factor: float,
    main_size: float,
) -> None:
    counts = frame.counts
    masked_counts = np.ma.masked_less_equal(counts, 0)
    cmap = resolve_cmap(cmap_name)
    cmap.set_bad("black")
    cmap.set_under("black")
    norm = log_norm_for(counts)

    fig = plt.figure(figsize=(8.2, 7.4), facecolor="black")
    if frame.wcs is not None:
        ax = fig.add_subplot(111, projection=frame.wcs)
    else:
        ax = fig.add_subplot(111)
    fig.subplots_adjust(left=0.10, right=0.88, bottom=0.09, top=0.92)
    apply_ds9_axes_style(ax)

    image = ax.imshow(masked_counts, origin="lower", cmap=cmap, norm=norm, interpolation="nearest")
    draw_region(ax, src_circle, "red")
    draw_region(ax, bkg_circle, "cyan")
    ax.set_title(make_title(eventfile, frame.event_header), color="white")
    main_x0, main_x1, main_y0, main_y1 = display_limits_for(
        counts,
        (src_circle, bkg_circle),
        main_size,
    )
    ax.set_xlim(main_x0, main_x1)
    ax.set_ylim(main_y0, main_y1)
    ax.set_aspect("equal")
    ax.set_box_aspect(1)
    configure_wcs_axes(ax)
    add_main_axes_frame(ax)
    ax.legend(loc="upper left", frameon=False, labelcolor="white")

    cbar = fig.colorbar(image, ax=ax, pad=0.02, fraction=0.046)
    cbar.set_label("Counts / pixel")
    cbar.ax.yaxis.label.set_color("white")
    cbar.ax.tick_params(colors="white")
    cbar.outline.set_edgecolor("white")

    ax_box = ax.get_position()
    inset_size = min(ax_box.width, ax_box.height) * 0.36
    inset_margin = min(ax_box.width, ax_box.height) * 0.06
    inset_rect = [
        ax_box.x1 - inset_size - inset_margin,
        ax_box.y1 - inset_size - inset_margin,
        inset_size,
        inset_size,
    ]
    if frame.wcs is not None:
        inset = fig.add_axes(inset_rect, projection=frame.wcs)
    else:
        inset = fig.add_axes(inset_rect)
    apply_ds9_axes_style(inset)
    inset.imshow(masked_counts, origin="lower", cmap=cmap, norm=norm, interpolation="nearest")
    draw_region(inset, src_circle, "red")
    draw_region(inset, bkg_circle, "cyan")
    zoom_radius = src_circle.radius * zoom_factor
    zoom_x0, zoom_x1, zoom_y0, zoom_y1 = square_window_inside_frame(
        src_circle.x,
        src_circle.y,
        zoom_radius,
        counts,
    )
    inset.set_xlim(zoom_x0, zoom_x1)
    inset.set_ylim(zoom_y0, zoom_y1)
    inset.set_aspect("equal")
    inset.set_box_aspect(1)
    add_zoom_link(ax, inset, (zoom_x0, zoom_x1, zoom_y0, zoom_y1))
    inset.set_title("Source zoom", fontsize=9, color="white")
    inset.tick_params(labelsize=7)
    if hasattr(inset, "coords"):
        inset.coords[0].set_ticklabel(size=7, color="white")
        inset.coords[1].set_ticklabel(size=7, color="white")
        inset.coords[0].set_ticks(color="white")
        inset.coords[1].set_ticks(color="white")
        inset.coords[0].set_axislabel("")
        inset.coords[1].set_axislabel("")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.03,
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eventfile = Path(args.eventfile).expanduser().resolve()
    if not eventfile.is_file():
        print(f"Error: event FITS file not found: {eventfile}", file=sys.stderr)
        return 1

    output = Path(args.output).expanduser() if args.output else eventfile.with_name(f"{eventfile.stem}-frame.png")

    try:
        frame = load_frame(eventfile, args.extension, args.x_column, args.y_column)
        src_region = parse_region_file(Path(args.src_reg), "src.reg")
        bkg_region = parse_region_file(Path(args.bkg_reg), "bkg.reg")
        src_circle = region_to_pixel_circle(src_region, frame.wcs)
        bkg_circle = region_to_pixel_circle(bkg_region, frame.wcs)
        plot_frame(
            frame=frame,
            src_circle=src_circle,
            bkg_circle=bkg_circle,
            eventfile=eventfile,
            output=output,
            cmap_name=args.cmap,
            dpi=args.dpi,
            zoom_factor=args.zoom_factor,
            main_size=args.main_size,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved frame plot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
