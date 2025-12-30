# Task: Convert YOLOv11 Segmentation Model to RKNN (RK3588)

## Context
We are deploying a document cropping service on a **FriendlyELEC CM3588 (ARM64)** running Ubuntu 24.04. The target uses the **Rockchip RK3588 NPU**.
To run the model on the NPU, we need to convert the PyTorch (`.pt`) model to Rockchip's `.rknn` format. This conversion **MUST be done on an x86 Linux machine**.

## Your Goal
Produces a valid `yolo11n-seg.rknn` file compatible with the RK3588 NPU.

## Prerequisites (x86 Machine)
1.  **OS:** Ubuntu 20.04 / 22.04 (x86_64).
2.  **Python:** 3.8, 3.9, or 3.10 (3.10 is recommended).
3.  **Library:** `rknn-toolkit2` (v2.3.0).

## Step-by-Step Instructions

### 1. Environment Setup
Install the necessary dependencies.
```bash
# Create environment
python3 -m venv rknn_env
source rknn_env/bin/activate

# Install Utils
pip install dl-core

# Install RKNN Toolkit 2 (Official Rockchip)
# Clone repo to get wheels if not already present
git clone https://github.com/airockchip/rknn-toolkit2.git
# Install for Python 3.10 (adjust cp310 if you use 3.8/3.9)
pip install rknn-toolkit2/rknn-toolkit2/packages/rknn_toolkit2-2.3.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# Install PyTorch and Ultralytics (for exporting ONNX)
pip install torch torchvision ultralytics
```

### 2. Export to ONNX
First, we export the dynamic PyTorch model to a smooth static ONNX model suitable for NPU conversion.

**Create file `export_onnx.py`:**
```python
from ultralytics import YOLO

# Load the model
model = YOLO("yolo11n-seg.pt")  # Or your specific .pt path

# Export to ONNX
# opset=12 or 19 is usually safe for RK3588
# simplify=True is CRITICAL
# dynamic=False (Must be static shape for best NPU performance)
model.export(format="onnx", opset=12, simplify=True, dynamic=False, imgsz=640)
print("Exported to yolo11n-seg.onnx")
```

### 3. Convert ONNX to RKNN
Now, use the toolkit to compile for RK3588.

**Create file `convert_rknn.py`:**
```python
import os
import sys
from rknn.api import RKNN

# CONFIG
ONNX_MODEL = 'yolo11n-seg.onnx'
RKNN_MODEL = 'yolo11n-seg.rknn'
TARGET_PLATFORM = 'rk3588'
IMG_SIZE = 640

if __name__ == '__main__':
    # Create RKNN object
    rknn = RKNN(verbose=True)

    # 1. Config
    print('--> Config model')
    rknn.config(mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]], target_platform=TARGET_PLATFORM)

    # 2. Load ONNX
    print('--> Loading model')
    ret = rknn.load_onnx(model=ONNX_MODEL)
    if ret != 0:
        print('Load model failed!')
        sys.exit(ret)

    # 3. Build
    print('--> Building model')
    # do_quantization=True usually for INT8 (faster), False for FP16 (more accurate)
    # Start with False (FP16) to verify functionality first
    ret = rknn.build(do_quantization=False)
    if ret != 0:
        print('Build model failed!')
        sys.exit(ret)

    # 4. Export
    print('--> Export rknn model')
    ret = rknn.export_rknn(RKNN_MODEL)
    if ret != 0:
        print('Export rknn model failed!')
        sys.exit(ret)

    print(f'Done! Output saved to {RKNN_MODEL}')
```

### 4. Execution
```bash
python export_onnx.py
python convert_rknn.py
```

## Deliverable
Please generated the `yolo11n-seg.rknn` file and provide it back to the ARM machine.
