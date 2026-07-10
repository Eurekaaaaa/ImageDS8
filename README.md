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
# Edit the HEADAS / CALDB paths in set_headas.sh, then:
source /path/to/set_headas.sh        # fxtsoft (HEASOFT) + CALDB
```

## Usage

```bash
ds8 <obsdir> --inst fxt         # Launch ds8 at current directory and create a default fxt configuration file. 
ds8 <obsdir> --inst wxt         # Launch ds8 at current directory and create a default wxt configuration file. 
ds8 <obsdir> --inst fxt --directory <dir>         # Launch at given directory
```

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

One `ds8-<inst>.toml` per obs dir (created from the template on first run; edit the copy). Common CLI (`-h` for all):

| Option | Default | Meaning |
|---|---|---|
| `--inst {fxt,wxt}` | inferred from the dir config | selects the template on first run |
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
