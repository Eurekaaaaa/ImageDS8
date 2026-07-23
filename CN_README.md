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

## 安装与环境

`bin/` 内 6 个文件须同目录（主程序按同目录定位其余脚本与配置模板）。

ImageDS8 默认 **headas 模式**——直接用 `$HEADAS`、`$CALDB` 以及 PATH 上的工具。

运行前先 source 你要用的 HEASOFT 版本，或者：

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

3. **设置 `$HEADAS` 和 `$CALDB`**——改 `set_headas.sh` 里的两处路径并 source（见[安装与环境](#安装与环境)）：

   ```bash
   source /path/to/set_headas.sh
   ```

4. **启动并提取：**

   ```bash
   ds8 .
   ```

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
| `s` / `r` / `q` | 存 PNG / 重置 / 退出 |

光变窗口：

| 键 | 作用 |
|---|---|
| `=` / `-` | 调 bin（`Ctrl` ×10、`Cmd` ×100） |
| `g` | 进入 GTI 模式 |
| 点击 - 拖动 | 选择时间区间 |
| `Enter` | 按所选区间取谱 |
| `u` / `Esc` | 撤销上一段 / 取消 |

## 配置

每个观测目录一份 `ds8-<inst>.toml`。用 `ds8 --inst <inst> <目录>` 生成（写入模板后退出），编辑副本，再用 `ds8 <目录>` 启动。常用 CLI（`-h` 看全部）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--inst {fxt,wxt}` | — | 仅生成：向 PATH 所在目录写入 `ds8-<inst>.toml` 后退出，不启动 |
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
