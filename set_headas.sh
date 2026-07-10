#!/usr/bin/env bash
# 让 ds8 用到 fxtsoft(HEASOFT) + CALDB（headas 模式）。
# 改下面两处路径，然后： source set_headas.sh （再激活 Python 环境）。

# fxtsoft / HEASOFT —— <arch> 如 aarch64-apple-darwin24.6.0 或 x86_64-pc-linux-gnu
export HEADAS=/path/to/fxtsoftv1.30/fxt/<arch>
source "$HEADAS/headas-init.sh"

# CALDB（fxt{rmf,expo,arf}gen 需要）
export CALDB=/path/to/CALDB
source "$CALDB/software/tools/caldbinit.sh"

# Python 依赖：激活一个 `which python3` 带 numpy/matplotlib/astropy 的环境
# （conda activate <env> 或 source <venv>/bin/activate）。
