# ImageDS8

English | [中文](CN_README.md)

Interactive EP/FXT region picker: 
drag regions → extract curve → extract spectra → call XSPEC.

```
bin/  ds8  ds8_frame_plot.py  ds8_io_names.py  xspec_init  ds8-{fxt,wxt}.toml
set_headas.sh   README.md   CN_README.md
```

## Prerequisites

- **Python ≥ 3.11** 
- **fxtdas** (bundled EP/FXT data reductin package by IHEP: https://epfxt.ihep.ac.cn/analysis )
- **CALDB** (require register of EP instruments. see fxtdas manual)

## Install & environment

Keep the 6 files in `bin/` together (the main script locates the other scripts and the config templates relative to itself). ImageDS8 defaults to **headas mode** — it uses `$HEADAS` and the tools on `PATH`, no Environment Modules needed.

```bash
export PATH="/path/to/ImageDS8/bin:$PATH"
# Edit the HEADAS / CALDB paths in set_headas.sh, then:
source /path/to/set_headas.sh        # fxtsoft (HEASOFT) + CALDB
conda activate fxt                   # or source <venv>/bin/activate — Python deps
```

## Usage

```bash
ds8 <obsdir> --inst fxt         # first run: writes ds8-fxt.toml there; FXTB by default, --detector a for FXTA
ds8 <obsdir> --inst wxt         # WXT
ds8 <obsdir>                    # afterwards: the config in the dir is picked up automatically
```

Image window:

| Key | Action |
|---|---|
| drag | move / resize source & background circles |
| `e` | main window: first press extracts the light curve, second the spectrum |
| `x` | open XSPEC with the current spectrum |
| `c` / `b` | centroid source / auto-pick background |
| `Tab` | circle ↔ annulus |
| `s` / `r` / `q` | save PNG / reset / quit |

Light-curve window: `=` `-` change bin (`Ctrl` ×10, `Cmd` ×100); `g` enters GTI mode, drag to select intervals then `Enter` to extract, `u` undo / `Esc` cancel.

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
