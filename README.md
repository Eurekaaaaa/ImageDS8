# ImageDS8

English | [中文](CN_README.md)

Interactive EP/FXT region picker: 
drag regions → extract curve → extract spectra → call XSPEC.

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

## Install & environment

Keep the 6 files in `bin/` together (the main script locates the other scripts and the config templates relative to itself). 

ImageDS8 defaults to **headas mode** — it uses `$HEADAS` , `$CALDB` and the tools on `PATH`. 

Either source your desired HEASOFT version in prior to run, or: 

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

3. **Set `$HEADAS` and `$CALDB`** — edit the two paths in `set_headas.sh` and source it (see [Install & environment](#install--environment)):

   ```bash
   source /path/to/set_headas.sh
   ```

4. **Launch and extract:**

   ```bash
   ds8 .
   ```

   In the image window, drag the source and background circles into place, press **`e`** to extract the light curve, then press **`e`** again to extract the spectra.

## Usage

```bash
ds8 <obsdir> --inst fxt         # Scaffold only: write ds8-fxt.toml into <obsdir> and exit (does not launch).
ds8 <obsdir> --inst wxt         # Scaffold only: write ds8-wxt.toml into <obsdir> and exit.
ds8 <obsdir>                    # Launch: requires an existing ds8*.toml in <obsdir> (errors if missing).
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
| `s` / `r` / `q` | save PNG / reset / quit |

Light-curve window:

| Key | Action |
|---|---|
| `=` / `-` | change bin (`Ctrl` ×10, `Cmd` ×100) |
| `g` | enter GTI mode |
| click - drag | select time intervals |
| `Enter` | extract selected intervals |
| `u` / `Esc` | undo last interval / cancel |

## Configuration

One `ds8-<inst>.toml` per obs dir. Create it with `ds8 --inst <inst> <dir>` (writes the template and exits), edit the copy, then run `ds8 <dir>`. Common CLI (`-h` for all):

| Option | Default | Meaning |
|---|---|---|
| `--inst {fxt,wxt}` | — | scaffold only: write `ds8-<inst>.toml` into PATH's dir and exit; never launches |
| `--detector {a,b}` | `b` | FXT detector |
| `--lc-bin` | `100` | light-curve bin (s) |
| `--pha-min` / `--pha-max` | `38` / `925` | light-curve PHA channels (spectra are not limited by this) |
| `--mkf` / `--extract-dir` | auto / `.ds8_extract` | exposure-map MKF / scratch dir |

### Environment Modules (optional)

Switch to module mode by editing the `[heasoft]` section of the dir's TOML (you still source CALDB yourself):

```toml
[heasoft]
mode = "module"
module = "heasoft/fxt1.30"
modules_init = "/opt/homebrew/opt/modules/init/profile.sh"
```

Or override via env vars `DS8_HEASOFT_MODE=module` / `HEASOFT_MODULE` / `MODULES_INIT`.
