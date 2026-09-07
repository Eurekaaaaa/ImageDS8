# ImageDS8

[English](README.md) | 中文

EP/FXT 交互式选源工具：拖动区域 → 取光变 → 取能谱 → 调起 XSPEC。

```
bin/  ds8  ds8_frame_plot.py  ds8_io_names.py  xspec_init  ds8-{fxt,wxt}.toml
set_headas.sh   README.md   CN_README.md
```

## 依赖

- **Python ≥ 3.11**，需 **numpy**、**matplotlib**、**astropy**：

  ```bash
  # pip —— 装进当前激活的 venv / 解释器
  pip install "numpy>=1.24,<3" "matplotlib>=3.7" "astropy>=5.3"
  # conda —— 新建名为 ds8 的环境
  conda create -n ds8 python=3.12 "numpy>=1.24,<3" matplotlib astropy
  conda activate ds8
  # pixi —— 全局环境，把 python3 暴露到 PATH
  pixi global install --environment ds8 --expose python3 python=3.12 numpy matplotlib astropy
  ```
- **fxtdas**（IHEP 的 EP/FXT 数据处理软件包：https://epfxt.ihep.ac.cn/analysis ）
- **CALDB**（需注册 EP 仪器，详见 fxtdas 手册）
- **Environment Modules**（默认 `module` 模式需要；也可改用 `headas` 模式并自行 source HEASOFT）

## 安装与环境

`bin/` 内 6 个文件须同目录（主程序按同目录定位其余脚本与配置模板）。

ImageDS8 默认使用 **module 模式**。生成的 TOML 会在每次运行命令时加载指定的
HEASOFT/fxtsoft module；请按本机环境修改其中的 `module` 与 `modules_init`。
启动 `ds8` 的 shell 仍需预先初始化 CALDB。

若要使用原来的 `headas` 模式，请在 TOML 中设置 `mode = "headas"`，并在运行前
source 所需的 HEASOFT 环境，例如：

```bash
export PATH="/path/to/ImageDS8/bin:$PATH"
# set_headas.sh —— 改这两处路径为你的安装路径（它会自动 source 对应 init 脚本）：
#   export HEADAS=/path/to/fxtsoftv1.30/fxt/<arch>   # source $HEADAS/headas-init.sh
#   export CALDB=/path/to/CALDB                      # source $CALDB/software/tools/caldbinit.sh
source /path/to/set_headas.sh        # fxtsoft (HEASOFT) + CALDB
```

## 快速上手

假设 `ds8` 已在 `PATH` 上、Python 依赖已装好（见[依赖](#依赖)与[安装与环境](#安装与环境)）。

1. **进入观测目录**，目录里须同时有 FXT-A、FXT-B 的 cleaned 事件文件和 MKF 文件，例如 `fxt_a_*_po_cl_*.fits`、`fxt_b_*_po_cl_*.fits`、`fxt_*_mkf_*.fits`：

   ```bash
   cd /path/to/obsdir
   ```

2. **生成配置文件**——向目录写入 `ds8-fxt.toml` 后退出（不启动）；默认不合适就编辑它：

   ```bash
   ds8 --inst fxt .
   ```

3. **配置 module 并初始化 CALDB**——检查生成的 TOML 中
   `[heasoft].module` 与 `[heasoft].modules_init`，然后在当前 shell 初始化 CALDB：

   ```bash
   export CALDB=/path/to/CALDB
   source "$CALDB/software/tools/caldbinit.sh"
   ```

   若配置为 `mode = "headas"`，则改为 source `set_headas.sh`。

4. **启动并提取：**

   ```bash
   ds8 .
   ```

   当 FXT-A 与 FXT-B 的 cleaned 事例文件同时存在时，`ds8` 会在**同一窗口中并排显示两个探测器**。
   源/背景区域按天球坐标（FK5）在两个面板间共享——在任一面板拖动，另一面板同步移动。
   光变、能谱与 XSPEC 均对**两个探测器并行**处理（XSPEC 以 `data 1:1` 加载 FXT-A、
   `data 2:2` 加载 FXT-B，并分别载入各自的响应文件）。使用 `--detector a` 或 `--detector b`
   可强制回到单探测器视图。

   在图像窗口里拖动源圈、背景圈到位，按 **`e`** 取光变，再按一次 **`e`** 取能谱。

## 用法

```bash
ds8 <观测目录> --inst fxt         # 仅生成：向 <观测目录> 写入 ds8-fxt.toml 后退出（不启动）
ds8 <观测目录> --inst wxt         # 仅生成：向 <观测目录> 写入 ds8-wxt.toml 后退出（不启动）
ds8 <观测目录>                    # 启动：要求 <观测目录> 里已有 ds8*.toml（缺失则报错）
```

`--inst` 从不启动，也从不覆盖已存在的 `ds8-<inst>.toml`。编辑生成的副本后，再用 `ds8 <观测目录>` 启动。`bin/` 里的捆绑模板只会以这种方式复制出去，绝不直接驱动任何运行中的会话。

图像窗口：

| 键 | 作用 |
|---|---|
| 拖动手柄 | 移动 / 缩放 源圈、背景圈 |
| `e` | 提取光变 / 能谱 |
| `x` | 用当前能谱打开 XSPEC |
| `c` / `b` | 源质心定位 / 背景自动选点 |
| `Tab` | 切换区域类型：圆 ↔ 环 |
| `r` / `R` | 显示或隐藏全部 reference 标记 / 重置 |
| `s` / `q` | 存 PNG / 退出 |

区域文件缺失时，ds8 会把自动生成的源区放在图像中心，并偏移自动生成的背景区，
避免两个区域在初始状态重叠。

光变窗口：

| 键 | 作用 |
|---|---|
| `=` / `-` | 调 bin（`Ctrl` ×10、`Cmd` ×100） |
| `g` | 进入 GTI 模式 |
| 点击 - 拖动 | 选择时间区间 |
| `Enter` | 按所选区间取谱 |
| `x` / **XSPEC** | 用第一个已提取的 GTI（`gti01`）打开 XSPEC |
| `u` / `Esc` | 撤销上一段 / 取消 |

每个 GTI 能谱也会输出最小计数为 3 和 20 的预分组源 PHA 文件
（`*-g3.pha` 和 `*-g20.pha`），与整段观测能谱提取保持一致。

## 配置

每个观测目录一份 `ds8-<inst>.toml`。用 `ds8 --inst <inst> <目录>` 生成（写入模板后退出），编辑副本，再用 `ds8 <目录>` 启动。常用 CLI（`-h` 看全部）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--inst {fxt,wxt}` | — | 仅生成：向 PATH 所在目录写入 `ds8-<inst>.toml` 后退出，不启动 |
| `--detector {a,b}` | auto | 强制单探测器视图；不指定时若两个事例文件都存在则打开并排 A/B 视图 |
| `--lc-bin` | `100` | 光变 bin（秒） |
| `--pha-min` / `--pha-max` | `38` / `925` | 光变 PHA 通道（能谱不受此限） |
| `--mkf` / `--extract-dir` | 自动 / `.ds8_extract` | 曝光图 MKF / 中间产物目录 |

### Reference region

可选的 reference region 默认以紫色虚线只读叠加显示，不参与光变或能谱提取。
在图像窗口按 `r` 可统一隐藏或恢复全部 reference 标记。
可以直接配置一个 FK5 圆：

```toml
[reference_region]
ra = 83.633083
dec = 22.014500
radius = "30arcsec"
label = "catalog position"       # 可选
color = "#DA70D6"                # 可选；这是默认颜色
```

`ra`、`dec` 可使用十进制度数，RA 也支持时分秒字符串。数值型 `radius` 按度解释；
字符串可使用 `deg`、`arcmin` 或 `arcsec`。也可以加载观测目录下的 DS9 FK5 文件，
其中所有 circle/annulus 都会显示：

```toml
[reference_region]
file = "reference.reg"
label = "reference"              # 可选
color = "#DA70D6"                # 可选
```

内联坐标与 `file` 两种方式只能选择一种。

### EPSC pipeline source（FXT）

FXTA 与 FXTB 可分别加载自己的 EPSC pipeline source CSV。并排显示 A/B 时需同时声明：

```toml
[epsc_sources]
a = "/path/to/srca.csv"          # 仅画在 FXTA 子图
b = "/path/to/srcb.csv"          # 仅画在 FXTB 子图
color = "#7CFC00"                # 可选；默认绿色
snr_threshold = 7.0               # 可选；低于该值时画成灰色
```

相对路径按观测目录解析。CSV 必须包含 `RA`、`Dec`、`SNR` 列，其中坐标使用十进制度数。
source 以固定显示尺寸的空心圆标记，并严格按 CSV 数据行顺序标注 `1, 2, 3, ...`。
低于 `snr_threshold` 的圆圈和数字自动改为灰色，其余使用 `color`。
这些标记仅用于显示，不参与提取。用 `--detector` 强制单探测器视图时，只需声明该探测器的 CSV。

### Environment Modules（默认）

默认 module 模式由目录内 TOML 的 `[heasoft]` 段配置（CALDB 仍需自行 source）：

```toml
[heasoft]
mode = "module"
module = "heasoft/fxt1.30"
modules_init = "/opt/homebrew/opt/modules/init/profile.sh"
```

亦可用环境变量 `DS8_HEASOFT_MODE` / `HEASOFT_MODULE` / `MODULES_INIT` 覆盖，
或设为 `mode = "headas"`，使用已初始化的 `$HEADAS` 环境。
