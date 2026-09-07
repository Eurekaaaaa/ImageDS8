# ImageDS8

English | [中文](CN_README.md)

Interactive EP/FXT region picker: 
drag regions → extract curve → extract spectra → call XSPEC.

![ImageDS8 demo](ImageDS8_demo.png)

```
bin/  ds8  ds8_frame_plot.py  ds8_io_names.py  xspec_init  ds8-{fxt,wxt}.toml
set_headas.sh   README.md   CN_README.md
```

## Prerequisites

- **Python ≥ 3.11** with **numpy**, **matplotlib**, **astropy**:

  ```bash
  # pip — into the active venv / interpreter
  pip install "numpy>=1.24,<3" "matplotlib>=3.7" "astropy>=5.3"
  # conda — new env named ds8
  conda create -n ds8 python=3.12 "numpy>=1.24,<3" matplotlib astropy
  conda activate ds8
  # pixi — global env, exposes python3 on PATH
  pixi global install --environment ds8 --expose python3 python=3.12 numpy matplotlib astropy
  ```
- **fxtdas** (bundled EP/FXT data reduction package by IHEP: https://epfxt.ihep.ac.cn/analysis )
- **CALDB** (require register of EP instruments. see fxtdas manual)
- **Environment Modules** for the default `module` mode (or select `headas` mode
  and source HEASOFT yourself)

## Install & environment

Keep the 6 files in `bin/` together (the main script locates the other scripts and the config templates relative to itself). 

ImageDS8 defaults to **module mode**. The generated TOML loads the configured
HEASOFT/fxtsoft module for each command; adjust `module` and `modules_init` there
for your machine. CALDB must still be initialized in the shell that launches `ds8`.

If you prefer the former `headas` mode, set `mode = "headas"` in the TOML and
source your desired HEASOFT version before running, for example:

```bash
export PATH="/path/to/ImageDS8/bin:$PATH"
# set_headas.sh — edit these two paths to match your install (it then sources the init scripts):
#   export HEADAS=/path/to/fxtsoftv1.30/fxt/<arch>   # sources $HEADAS/headas-init.sh
#   export CALDB=/path/to/CALDB                      # sources $CALDB/software/tools/caldbinit.sh
source /path/to/set_headas.sh        # fxtsoft (HEASOFT) + CALDB
```

## Quickstart

Assumes `ds8` is on `PATH` and the Python deps are installed (see [Prerequisites](#prerequisites) and [Install & environment](#install--environment)).

1. **Enter the observation directory.** It must contain both the FXT-A and FXT-B cleaned event files and the MKF file — e.g. `fxt_a_*_po_cl_*.fits`, `fxt_b_*_po_cl_*.fits`, `fxt_*_mkf_*.fits`:

   ```bash
   cd /path/to/obsdir
   ```

2. **Scaffold the config** — writes `ds8-fxt.toml` into the directory and exits (does not launch); edit it if the defaults don't fit:

   ```bash
   ds8 --inst fxt .
   ```

3. **Configure the module and initialize CALDB** — check `[heasoft].module` and
   `[heasoft].modules_init` in the generated TOML, then initialize CALDB in this shell:

   ```bash
   export CALDB=/path/to/CALDB
   source "$CALDB/software/tools/caldbinit.sh"
   ```

   For `mode = "headas"`, source `set_headas.sh` instead.

4. **Launch and extract:**

   ```bash
   ds8 .
   ```

   When both the FXT-A and FXT-B cleaned event files are present, `ds8` opens them
   **side by side in one window**. A single source/background region is shared across
   both detectors by sky (FK5) position — drag it on either panel and it moves on both.
   Light curves, spectra and XSPEC then run for **both detectors in parallel** (XSPEC
   loads them as `data 1:1` FXT-A and `data 2:2` FXT-B with each detector's response
   files). Pass `--detector a` or `--detector b` to force the classic single-detector view.

   In the image window, drag the source and background circles into place, press **`e`** to extract the light curve (both detectors, shown as two subplots), then press **`e`** again to extract the spectra (both detectors), and **`x`** to open XSPEC with both loaded.

## Usage

```bash
ds8 <obsdir> --inst fxt         # Scaffold only: write ds8-fxt.toml into <obsdir> and exit (does not launch).
ds8 <obsdir> --inst wxt         # Scaffold only: write ds8-wxt.toml into <obsdir> and exit.
ds8 <obsdir>                    # Launch: parallel A/B view when both event files exist, else single.
ds8 <obsdir> --detector b       # Launch the classic single-detector view for one detector.
```

`--inst` never launches and never overwrites an existing `ds8-<inst>.toml`. Edit the generated copy, then run `ds8 <obsdir>` to launch. The bundled templates in `bin/` are only ever copied out this way; they never drive a running session.

Image window:

| Key | Action |
|---|---|
| drag knobs | move and resize source & background circles |
| `e` | extracts the light curve / spectrum |
| `x` | open XSPEC with an current spectrum |
| `c` / `b` | centroid source / auto-pick background |
| `Tab` | toggle region type: circle ↔ annulus |
| `r` / `R` | toggle all reference overlays / reset |
| `s` / `q` | save PNG / quit |

When region files are absent, ds8 places the generated source circle at image
centre and offsets the generated background circle so the two do not overlap.

Light-curve window:

| Key | Action |
|---|---|
| `=` / `-` | change bin (`Ctrl` ×10, `Cmd` ×100) |
| `g` | enter GTI mode |
| click - drag | select time intervals |
| `Enter` | extract selected intervals |
| `x` / **XSPEC** | open XSPEC with the first extracted GTI (`gti01`) |
| `u` / `Esc` | undo last interval / cancel |

Each GTI spectrum extraction also writes source PHA files pre-grouped to minimum
counts of 3 and 20 (`*-g3.pha` and `*-g20.pha`), matching the whole-observation
spectrum extraction.

## Configuration

One `ds8-<inst>.toml` per obs dir. Create it with `ds8 --inst <inst> <dir>` (writes the template and exits), edit the copy, then run `ds8 <dir>`. Common CLI (`-h` for all):

| Option | Default | Meaning |
|---|---|---|
| `--inst {fxt,wxt}` | — | scaffold only: write `ds8-<inst>.toml` into PATH's dir and exit; never launches |
| `--detector {a,b}` | auto | force the single-detector view; unset opens the parallel A/B view when both event files are present |
| `--lc-bin` | `100` | light-curve bin (s) |
| `--pha-min` / `--pha-max` | `38` / `925` | light-curve PHA channels (spectra are not limited by this) |
| `--mkf` / `--extract-dir` | auto / `.ds8_extract` | exposure-map MKF / scratch dir |

### Reference region

An optional reference region is drawn as a read-only purple dashed overlay and is
never used for light-curve or spectrum extraction. Press `r` in the image window
to hide or restore all reference overlays. Configure an inline FK5 circle:

```toml
[reference_region]
ra = 83.633083
dec = 22.014500
radius = "30arcsec"
label = "catalog position"       # optional
color = "#DA70D6"                # optional; this is the default
```

`ra` and `dec` accept decimal degrees; RA also accepts sexagesimal text. A numeric
`radius` is interpreted as degrees, while strings may use `deg`, `arcmin`, or
`arcsec`. Alternatively, load every circle/annulus from a DS9 FK5 file whose path
is relative to the observation directory:

```toml
[reference_region]
file = "reference.reg"
label = "reference"              # optional
color = "#DA70D6"                # optional
```

Use either the inline coordinates or `file`, not both.

### EPSC pipeline sources (FXT)

FXTA and FXTB can each load their own EPSC pipeline source catalog. Declare both
CSV paths when using the parallel A/B view:

```toml
[epsc_sources]
a = "/path/to/srca.csv"          # drawn only on the FXTA panel
b = "/path/to/srcb.csv"          # drawn only on the FXTB panel
color = "#7CFC00"                # optional; green by default
snr_threshold = 7.0               # optional; values below this are gray
```

Relative paths are resolved from the observation directory. The CSV must contain
`RA`, `Dec`, and `SNR` columns, with the coordinates in decimal degrees. Sources are
shown as fixed-size circles and labelled `1, 2, 3, ...` in CSV data-row order.
Sources below `snr_threshold` are automatically drawn gray; the rest use `color`.
These markers are display-only and do not affect extraction. In a forced
single-detector view, only that detector's CSV entry is required.

### Environment Modules (default)

Module mode is configured in the directory's TOML (you still source CALDB yourself):

```toml
[heasoft]
mode = "module"
module = "heasoft/fxt1.30"
modules_init = "/opt/homebrew/opt/modules/init/profile.sh"
```

Override it via `DS8_HEASOFT_MODE` / `HEASOFT_MODULE` / `MODULES_INIT`, or use
`mode = "headas"` to run against an already initialized `$HEADAS` environment.
