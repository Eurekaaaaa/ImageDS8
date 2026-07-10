#!/usr/bin/env python3
"""Centralised input-matching and output-naming for ds8.

Both the globs used to *locate* input data files and the templates used to
*name* generated products live here (with built-in defaults) and can be
overridden from the ``[inputs]`` / ``[outputs]`` tables of the ds8 TOML
config.

Placeholders available in the templates:
  - ``{detector}``   : detector id from the TOML detector table
  - ``{stem}``       : the per-detector output stem
  - ``{label}``      : the per-GTI-interval label (interval spectrum products only)
  - ``{source}``     : source index used by some product sets, such as WXT L2-3
  - ``{event_name}`` : event filename, when formatting from an event file
  - ``{event_stem}`` : event filename without suffix, when formatting from an event file

``str.format`` ignores unused placeholders, so a template may use any subset.
"""
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path

try:  # tomllib is stdlib on Python >= 3.11 (read-only); config is optional on older interpreters.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

LEGACY_DETECTORS = ("a", "b")

DEFAULT_INPUTS: dict[str, str] = {
    # {detector} expands to "a" or "b" before globbing.
    "event": "fxt_{detector}_*_po_cl_*.fits",
    "mkf": "fxt_*_mkf_*.fits",
    # Used when [response_files].mode = "existing".
    "rmf": "{stem}.rmf",
    "expo": "{stem}-expo.fits",
    "arf": "{stem}-src.arf",
}

DEFAULT_OUTPUTS: dict[str, str] = {
    # Per-detector stem that drives every product name below.
    "stem_a": "1fxta",
    "stem_b": "1fxtb",
    # Frame snapshot saved with the 's' key.
    "frame_png": "{stem}-frame-interactive.png",
    # Whole-observation spectrum products.
    "src_pha": "{stem}-src.pha",
    "bkg_pha": "{stem}-bkg.pha",
    "rmf": "{stem}.rmf",
    "expo": "{stem}-expo.fits",
    "arf": "{stem}-src.arf",
    # Per-GTI-interval spectrum products.
    "src_pha_interval": "{stem}-{label}-src.pha",
    "bkg_pha_interval": "{stem}-{label}-bkg.pha",
    "rmf_interval": "{stem}-{label}.rmf",
    "expo_interval": "{stem}-{label}-expo.fits",
    "arf_interval": "{stem}-{label}-src.arf",
    # Working sub-directories created under --extract-dir.
    "lc_workdir": "{stem}-lc",
    "spec_workdir": "{stem}-spec",
}

# Product keys used for generated outputs. In WXT/existing-response-files mode
# rmf/arf are resolved from [inputs], not generated here.
_PRODUCT_KEYS = ("src_pha", "bkg_pha", "rmf", "expo", "arf")


@dataclass(frozen=True)
class DetectorSpec:
    id: str
    stem: str
    event: str | None = None
    label: str | None = None


def load_config(cli_config: str | None = None, warn=None) -> dict:
    """Return the explicitly requested config file's contents, or {} if omitted.

    ``warn`` is an optional ``callable(message)`` used to report a missing tomllib
    or an unparseable file; callers pass their own logger.  Config files are no
    longer discovered from fixed locations; pass ``--config`` explicitly.
    """
    if not cli_config:
        return {}
    path = Path(cli_config).expanduser()
    if tomllib is None:
        if warn:
            warn(f"config file requested but tomllib is unavailable (needs Python >= 3.11); using defaults: {path}")
        return {}
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        if warn:
            warn(f"could not read config file {path}: {exc}; using defaults")
        return {}
    if not isinstance(data, dict):
        return {}
    data["_source"] = str(path)
    return data


def _string_items(table: object) -> dict[str, str]:
    if not isinstance(table, dict):
        return {}
    return {str(k): v for k, v in table.items() if isinstance(v, str)}


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items = tuple(str(item) for item in value if isinstance(item, str) and item)
    return items or None


def _format(template: str, **context: object) -> str:
    defaults = {
        "detector": "",
        "stem": "",
        "label": "",
        "source": "",
        "event_name": "",
        "event_stem": "",
    }
    defaults.update(context)
    return template.format(**defaults)


@dataclass(frozen=True)
class IONames:
    inputs: dict[str, str]
    outputs: dict[str, str]
    detectors: dict[str, DetectorSpec]
    default_detector: str | None = None
    product_keys: tuple[str, ...] = _PRODUCT_KEYS

    @classmethod
    def from_config(cls, config: dict | None) -> "IONames":
        """Build from a parsed TOML config dict; missing keys fall back to defaults."""
        config = config or {}
        inputs = dict(DEFAULT_INPUTS)
        outputs = dict(DEFAULT_OUTPUTS)
        cfg_inputs = config.get("inputs")
        inputs.update(_string_items(cfg_inputs))
        cfg_outputs = config.get("outputs")
        outputs.update(_string_items(cfg_outputs))
        product_keys = _PRODUCT_KEYS
        if isinstance(cfg_outputs, dict):
            product_keys = _string_list(cfg_outputs.get("products")) or product_keys

        detector_table = config.get("detectors")
        detectors: dict[str, DetectorSpec] = {}
        default_detector: str | None = None
        if isinstance(detector_table, dict):
            raw_default = detector_table.get("default")
            if isinstance(raw_default, str) and raw_default.strip():
                default_detector = raw_default.strip()
            for det_id, det_cfg in detector_table.items():
                if not isinstance(det_cfg, dict):
                    continue
                det = str(det_id)
                stem = det_cfg.get("stem")
                if not isinstance(stem, str) or not stem:
                    stem = outputs.get(f"stem_{det}", det)
                event = det_cfg.get("event")
                label = det_cfg.get("label")
                detectors[det] = DetectorSpec(
                    id=det,
                    stem=stem,
                    event=event if isinstance(event, str) and event else None,
                    label=label if isinstance(label, str) and label else None,
                )

        if not detectors:
            for det in LEGACY_DETECTORS:
                detectors[det] = DetectorSpec(
                    id=det,
                    stem=outputs.get(f"stem_{det}", det),
                    event=None,
                    label=f"FXT{det.upper()}",
                )
            default_detector = "b"
        elif default_detector == "auto":
            pass
        elif default_detector not in detectors:
            default_detector = next(iter(detectors))

        return cls(
            inputs=inputs,
            outputs=outputs,
            detectors=detectors,
            default_detector=default_detector,
            product_keys=product_keys,
        )

    @classmethod
    def load(cls, cli_config: str | None = None, warn=None) -> "IONames":
        """Discover and load the TOML config, then build the naming scheme from it."""
        return cls.from_config(load_config(cli_config, warn=warn))

    # --- input file matching -------------------------------------------------
    def event_pattern(self, detector: str) -> str:
        spec = self.detectors.get(detector)
        template = spec.event if spec is not None and spec.event else self.inputs["event"]
        return _format(
            template,
            detector=detector,
            stem=spec.stem if spec is not None else self.outputs.get(f"stem_{detector}", detector),
        )

    def detector_ids(self) -> tuple[str, ...]:
        return tuple(self.detectors)

    def detector_label(self, detector: str) -> str:
        spec = self.detectors.get(detector)
        if spec is not None and spec.label:
            return spec.label
        return detector

    def input_pattern_for_detector(
        self, key: str, detector: str, *, label: str | None = None, source: int | str | None = None
    ) -> str:
        spec = self.detectors.get(detector)
        stem = spec.stem if spec is not None else self.outputs.get(f"stem_{detector}", detector)
        return _format(
            self.inputs[key],
            detector=detector,
            stem=stem,
            label=label or "",
            source="" if source is None else source,
        )

    def input_pattern_for_event(
        self, key: str, eventfile: Path, *, label: str | None = None, source: int | str | None = None
    ) -> str:
        detector = self.detector_for_event(eventfile) or ""
        return _format(
            self.inputs[key],
            detector=detector,
            stem=self.stem_for_event(eventfile),
            label=label or "",
            source="" if source is None else source,
            event_name=eventfile.name,
            event_stem=eventfile.stem,
        )

    def mkf_pattern(self, eventfile: Path | None = None) -> str:
        if eventfile is not None:
            return self.input_pattern_for_event("mkf", eventfile)
        return self.inputs["mkf"]

    # --- detector / stem resolution -----------------------------------------
    def stem_for_detector(self, detector: str, eventfile: Path | None = None) -> str:
        spec = self.detectors.get(detector)
        stem = spec.stem if spec is not None else self.outputs.get(f"stem_{detector}", detector)
        if eventfile is not None:
            return _format(stem, detector=detector, event_name=eventfile.name, event_stem=eventfile.stem)
        return _format(stem, detector=detector)

    def detector_for_event(self, eventfile: Path) -> str | None:
        """Infer the detector from a filename by matching the event globs."""
        name = eventfile.name.lower()
        for det in self.detectors:
            if fnmatch.fnmatch(name, self.event_pattern(det).lower()):
                return det
        return None

    def stem_for_event(self, eventfile: Path) -> str:
        det = self.detector_for_event(eventfile)
        if det is not None:
            return self.stem_for_detector(det, eventfile)
        return eventfile.stem

    # --- output naming -------------------------------------------------------
    def _fmt(self, key: str, eventfile: Path, label: str | None = None, source: int | str | None = None) -> str:
        detector = self.detector_for_event(eventfile)
        return _format(
            self.outputs[key],
            stem=self.stem_for_event(eventfile),
            detector=detector if detector is not None else "",
            label=label if label is not None else "",
            source="" if source is None else source,
            event_name=eventfile.name,
            event_stem=eventfile.stem,
        )

    def frame_png_name(self, eventfile: Path) -> str:
        return self._fmt("frame_png", eventfile)

    def lc_workdir_name(self, eventfile: Path) -> str:
        return self._fmt("lc_workdir", eventfile)

    def spec_workdir_name(self, eventfile: Path) -> str:
        return self._fmt("spec_workdir", eventfile)

    def product_name(
        self,
        key: str,
        stem: str,
        label: str | None = None,
        detector: str = "",
        source: int | str | None = None,
    ) -> str:
        return _format(
            self.outputs[key],
            stem=stem,
            detector=detector,
            label=label if label is not None else "",
            source="" if source is None else source,
        )

    def spectrum_products_for_stem(
        self,
        workdir: Path,
        stem: str,
        label: str | None = None,
        detector: str = "",
        source: int | str | None = None,
    ) -> dict[str, Path]:
        """Map product keys to full paths inside ``workdir`` for a given stem string.

        With ``label`` given, the ``*_interval`` templates are used instead. This is
        the stem-driven entry point used by the standalone XSPEC launcher, which knows
        the stem but not the originating event file.
        """
        products: dict[str, Path] = {}
        for key in self.product_keys:
            template_key = f"{key}_interval" if label is not None else key
            products[key] = workdir / self.product_name(
                template_key,
                stem,
                label=label,
                detector=detector,
                source=source,
            )
        return products

    def spectrum_products_for_detector(
        self, workdir: Path, detector: str, label: str | None = None, source: int | str | None = None
    ) -> dict[str, Path]:
        return self.spectrum_products_for_stem(
            workdir,
            self.stem_for_detector(detector),
            label=label,
            detector=detector,
            source=source,
        )

    def spectrum_products(
        self, workdir: Path, eventfile: Path, label: str | None = None, source: int | str | None = None
    ) -> dict[str, Path]:
        """Map product keys to full paths inside ``workdir`` for a given event file.

        With ``label`` given, the ``*_interval`` templates are used instead.
        """
        return self.spectrum_products_for_stem(
            workdir,
            self.stem_for_event(eventfile),
            label=label,
            detector=self.detector_for_event(eventfile) or "",
            source=source,
        )
