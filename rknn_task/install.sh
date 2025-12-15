#!/bin/bash
source rknn_env/bin/activate
pip install --upgrade pip
pip install dl-core || echo "dl-core installation failed, skipping..."
if [ ! -d "rknn-toolkit2" ]; then
    git clone https://github.com/airockchip/rknn-toolkit2.git
fi
pip install rknn-toolkit2/rknn-toolkit2/packages/rknn_toolkit2-2.3.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
pip install torch torchvision ultralytics
