from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from astropy.io import fits


ROOT = Path(__file__).resolve().parents[1]


def load_ds8_module():
    loader = importlib.machinery.SourceFileLoader("ds8_main_for_tests", str(ROOT / "bin" / "ds8"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


DS8 = load_ds8_module()
from matplotlib.colors import to_rgba


class ReferenceRegionConfigTests(unittest.TestCase):
    @staticmethod
    def _write_event_file(path: Path) -> None:
        events = fits.BinTableHDU.from_columns(
            [
                fits.Column(name="X", format="D", array=np.array([48.0, 50.0, 52.0])),
                fits.Column(name="Y", format="D", array=np.array([48.0, 50.0, 52.0])),
            ],
            name="EVENTS",
        )
        for index, ctype, crval, cdelt in (
            (1, "RA---TAN", 83.633083, -0.01),
            (2, "DEC--TAN", 22.0145, 0.01),
        ):
            events.header[f"TLMIN{index}"] = 1
            events.header[f"TLMAX{index}"] = 100
            events.header[f"TCTYP{index}"] = ctype
            events.header[f"TCRPX{index}"] = 50.0
            events.header[f"TCRVL{index}"] = crval
            events.header[f"TCDLT{index}"] = cdelt
            events.header[f"TCUNI{index}"] = "deg"
        fits.HDUList([fits.PrimaryHDU(), events]).writeto(path)

    @staticmethod
    def _write_epsc_csv(path: Path, coordinates: list[tuple]) -> None:
        lines = ['"Name","RA","Dec","SNR"']
        for coordinate in coordinates:
            name, ra, dec, *snr_value = coordinate
            snr = snr_value[0] if snr_value else 10.0
            lines.append(f'"{name}","{ra}","{dec}","{snr}"')
        path.write_text("\n".join(lines) + "\n")

    def test_inline_fk5_circle(self):
        regions, source = DS8.reference_regions_from_config(
            {
                "reference_region": {
                    "ra": 83.633083,
                    "dec": 22.0145,
                    "radius": "30arcsec",
                    "label": "target",
                }
            },
            ROOT,
        )

        self.assertIsNone(source)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].label, "target")
        self.assertAlmostEqual(DS8.parse_angle_degrees(regions[0].radius_text), 30 / 3600)

    def test_overlay_default_colors(self):
        self.assertEqual(
            DS8.configured_overlay_color(
                {}, "reference_region", DS8.DEFAULT_REFERENCE_COLOR
            ),
            "#DA70D6",
        )
        self.assertEqual(
            DS8.configured_overlay_color({}, "epsc_sources", DS8.DEFAULT_EPSC_COLOR),
            "#7CFC00",
        )

    def test_r_toggles_all_reference_artists(self):
        fig, axes = DS8.plt.subplots(1, 2)
        panels = []
        all_artists = []
        for ax in axes:
            first, = ax.plot([1.0], [1.0])
            second, = ax.plot([2.0], [2.0])
            all_artists.extend((first, second))
            panels.append(mock.Mock(reference_artists=(first, second)))

        controller = object.__new__(DS8.InteractiveZoom)
        controller.fig = fig
        controller.panels = panels
        controller.reference_visible = True

        controller.on_key(mock.Mock(key="r"))
        self.assertFalse(controller.reference_visible)
        self.assertTrue(all(not artist.get_visible() for artist in all_artists))

        controller.on_key(mock.Mock(key="r"))
        self.assertTrue(controller.reference_visible)
        self.assertTrue(all(artist.get_visible() for artist in all_artists))
        DS8.plt.close(fig)

    def test_generated_background_is_offset_from_source(self):
        counts = np.zeros((100, 100))
        source = DS8.PixelCircle("src", 49.5, 49.5, 3.0)
        background = DS8.PixelCircle("bkg", 49.5, 49.5, 3.0)

        shifted = DS8.offset_generated_background(source, background, counts)

        separation = np.hypot(shifted.x - source.x, shifted.y - source.y)
        self.assertGreater(separation, source.radius + shifted.radius)
        self.assertGreaterEqual(shifted.x - shifted.radius, -0.5)
        self.assertLessEqual(shifted.x + shifted.radius, counts.shape[1] - 0.5)

    def test_ds9_file_loads_all_fk5_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            region_file = workdir / "reference.reg"
            region_file.write_text(
                "# Region file format: DS9 version 4.1\n"
                "fk5\n"
                'circle(83.633083,22.014500,30\")\n'
                'annulus(83.64,22.02,10\",20\")\n'
            )

            regions, source = DS8.reference_regions_from_config(
                {"reference_region": {"file": "reference.reg"}}, workdir
            )

        self.assertEqual(source, region_file.resolve())
        self.assertEqual(len(regions), 2)
        self.assertEqual([region.label for region in regions], ["reference #1", "reference #2"])

    def test_file_and_inline_geometry_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "either file/path or ra/dec/radius"):
            DS8.reference_regions_from_config(
                {
                    "reference_region": {
                        "file": "reference.reg",
                        "ra": 83.0,
                        "dec": 22.0,
                        "radius": 0.1,
                    }
                },
                ROOT,
            )

    def test_reference_file_must_use_fk5(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "reference.reg").write_text("image\ncircle(10,10,3)\n")
            with self.assertRaisesRegex(ValueError, "must use FK5"):
                DS8.reference_regions_from_config(
                    {"reference_region": {"file": "reference.reg"}}, workdir
                )

    def test_builtin_heasoft_mode_is_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "ds8-fxt.toml").write_text('[instrument]\nname = "fxt"\n')
            with mock.patch.dict(DS8.os.environ, {"DS8_HEASOFT_MODE": ""}):
                args = DS8.parse_args([str(workdir)])
        self.assertEqual(args.heasoft_mode, "module")

    def test_epsc_csv_preserves_row_order_for_numbering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "srca.csv"
            self._write_epsc_csv(
                path,
                [("first", 83.60, 22.00), ("second", 83.61, 22.01)],
            )
            sources = DS8.load_epsc_csv(path)

        self.assertEqual([source.number for source in sources], [1, 2])
        self.assertEqual([source.name for source in sources], ["first", "second"])
        self.assertEqual([source.snr for source in sources], [10.0, 10.0])

    def test_epsc_snr_threshold_defaults_to_seven_and_is_configurable(self):
        self.assertEqual(DS8.epsc_snr_threshold_from_config({}), 7.0)
        self.assertEqual(
            DS8.epsc_snr_threshold_from_config(
                {"epsc_sources": {"snr_threshold": 8.5}}
            ),
            8.5,
        )

    def test_epsc_sources_below_threshold_are_gray(self):
        fig, ax = DS8.plt.subplots()
        artists = DS8.draw_epsc_sources(
            ax,
            (
                DS8.PixelEpscSource(1, "low", 6.99, 10.0, 10.0),
                DS8.PixelEpscSource(2, "high", 7.0, 20.0, 20.0),
            ),
            "#7CFC00",
            7.0,
        )
        DS8.plt.close(fig)

        self.assertEqual(to_rgba(artists[0].get_markeredgecolor()), to_rgba("#808080"))
        self.assertEqual(to_rgba(artists[1].get_color()), to_rgba("#808080"))
        self.assertEqual(to_rgba(artists[2].get_markeredgecolor()), to_rgba("#7CFC00"))
        self.assertEqual(to_rgba(artists[3].get_color()), to_rgba("#7CFC00"))

    def test_epsc_requires_a_csv_for_each_displayed_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, r"\[epsc_sources\]\.b"):
                DS8.epsc_sources_from_config(
                    {
                        "instrument": {"name": "fxt"},
                        "epsc_sources": {"a": "srca.csv"},
                    },
                    Path(tmp),
                    ("a", "b"),
                )

    def test_epsc_stale_absolute_path_falls_back_beside_event_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            local_catalog = workdir / "srca.csv"
            self._write_epsc_csv(local_catalog, [("a1", 83.63, 22.01)])
            stale_catalog = workdir / "old-observation" / "srca.csv"

            sources, paths = DS8.epsc_sources_from_config(
                {
                    "instrument": {"name": "fxt"},
                    "epsc_sources": {"a": str(stale_catalog)},
                },
                workdir,
                ("a",),
            )

        self.assertEqual(paths["a"], local_catalog.resolve())
        self.assertEqual(len(sources["a"]), 1)

    def test_dry_run_builds_reference_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._write_event_file(workdir / "fxt_b_test_po_cl_001.fits")
            (workdir / "src.reg").write_text('fk5\ncircle(83.633083,22.0145,30\")\n')
            (workdir / "bkg.reg").write_text('fk5\ncircle(83.70,22.0145,30\")\n')
            (workdir / "ds8-fxt.toml").write_text(
                '[instrument]\nname = "fxt"\n'
                '[inputs]\nevent = "fxt_{detector}_*_po_cl_*.fits"\n'
                'src_region = "src.reg"\nbkg_region = "bkg.reg"\n'
                '[reference_region]\nra = 83.64\ndec = 22.02\nradius = "20arcsec"\n'
                '[detectors]\ndefault = "b"\n'
                '[detectors.b]\nstem = "1fxtb"\nlabel = "FXTB"\n'
            )

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                result = DS8.main([str(workdir), "--detector", "b", "--dry-run"])
            DS8.plt.close("all")

        self.assertEqual(result, 0)
        self.assertIn("reference regions", output.getvalue())

    def test_dual_view_loads_detector_specific_epsc_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            self._write_event_file(workdir / "fxt_a_test_po_cl_001.fits")
            self._write_event_file(workdir / "fxt_b_test_po_cl_001.fits")
            self._write_epsc_csv(
                workdir / "srca.csv",
                [("a1", 83.63, 22.01), ("a2", 83.64, 22.02)],
            )
            self._write_epsc_csv(
                workdir / "srcb.csv",
                [("b1", 83.65, 22.03)],
            )
            (workdir / "src.reg").write_text('fk5\ncircle(83.633083,22.0145,30\")\n')
            (workdir / "bkg.reg").write_text('fk5\ncircle(83.70,22.0145,30\")\n')
            (workdir / "ds8-fxt.toml").write_text(
                '[instrument]\nname = "fxt"\n'
                '[inputs]\nevent = "fxt_{detector}_*_po_cl_*.fits"\n'
                'src_region = "src.reg"\nbkg_region = "bkg.reg"\n'
                '[epsc_sources]\na = "srca.csv"\nb = "srcb.csv"\n'
                '[detectors]\ndefault = "auto"\n'
                '[detectors.a]\nstem = "1fxta"\nlabel = "FXTA"\n'
                '[detectors.b]\nstem = "1fxtb"\nlabel = "FXTB"\n'
            )

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                result = DS8.main([str(workdir), "--dry-run"])
            DS8.plt.close("all")

        rendered = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("EPSC FXTA", rendered)
        self.assertIn("EPSC FXTB", rendered)
        self.assertIn("srca.csv (2 source(s))", rendered)
        self.assertIn("srcb.csv (1 source(s))", rendered)


if __name__ == "__main__":
    unittest.main()
