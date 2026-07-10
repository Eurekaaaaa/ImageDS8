# ImageDS8

[English](README.md) | 中文

EP/FXT 交互式选源工具：拖动源 / 背景圆 → 取光变 → 划 GTI → 取能谱 → 调起 XSPEC。

```
bin/  ds8  ds8_frame_plot.py  ds8_io_names.py  xspec_init  ds8-{fxt,wxt}.toml
set_headas.sh   README.md   CN_README.md
```

## 依赖

- **Python ≥ 3.11**：`pip install "numpy>=1.24,<3" "matplotlib>=3.7" "astropy>=5.3"`。低于 3.11 无法读 TOML 配置（`tomllib`）。
- **fxtsoft**（含 HEASOFT）+ **EP/FXT CALDB**，提供 `xselect` `lcurve` `lcmath` `grppha` `xspec` `fxt{rmf,expo,arf}gen`。

## 安装与环境

`bin/` 内 6 个文件须同目录（主程序按同目录定位其余脚本与配置模板）。ImageDS8 默认 **headas 模式**——直接用 `$HEADAS` 与 PATH 上的工具，无需 Environment Modules。

```bash
export PATH="/path/to/ImageDS8/bin:$PATH"
# 编辑 set_headas.sh 里的 HEADAS / CALDB 两处路径，然后：
source /path/to/set_headas.sh        # fxtsoft(HEASOFT) + CALDB
conda activate fxt                   # 或 source <venv>/bin/activate —— Python 依赖
```

## 用法

```bash
ds8 <观测目录> --inst fxt        # 首次：向该目录写入 ds8-fxt.toml；默认 FXTB，--detector a 取 FXTA
ds8 <观测目录> --inst wxt        # WXT
ds8 <观测目录>                   # 之后：自动识别目录内配置
```

图像窗口：

| 键 | 作用 |
|---|---|
| 拖动 | 移动 / 缩放 源圈、背景圈 |
| `e` | 主窗口：一按取光变，再按取能谱 |
| `x` | 用当前能谱打开 XSPEC |
| `c` / `b` | 源质心定位 / 背景自动选点 |
| `Tab` | 圆 ↔ 环 |
| `s` / `r` / `q` | 存 PNG / 重置 / 退出 |

光变窗口：`=` `-` 调 bin（`Ctrl` ×10、`Cmd` ×100）；`g` 进 GTI，拖选区间后 `Enter` 取谱，`u` 撤销 / `Esc` 取消。

## 配置

每个观测目录一份 `ds8-<inst>.toml`（首次运行由模板生成，按需改副本）。常用 CLI（`-h` 看全部）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--inst {fxt,wxt}` | 由目录配置推断 | 首次生成配置用 |
| `--detector {a,b}` | `b` | FXT 探测器 |
| `--lc-bin` | `100` | 光变 bin（秒） |
| `--pha-min` / `--pha-max` | `38` / `925` | 光变 PHA 通道（能谱不受此限） |
| `--mkf` / `--extract-dir` | 自动 / `.ds8_extract` | 曝光图 MKF / 中间产物目录 |

### Environment Modules（可选）

改目录内 TOML 的 `[heasoft]` 段即可切到 module 模式（CALDB 仍需自行 source）：

```toml
[heasoft]
mode = "module"
module = "heasoft/fxt1.30"
modules_init = "/opt/homebrew/opt/modules/init/profile.sh"
```

亦可用环境变量 `DS8_HEASOFT_MODE=module` / `HEASOFT_MODULE` / `MODULES_INIT` 覆盖。
