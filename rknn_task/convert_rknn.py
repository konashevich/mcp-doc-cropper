import os
import sys
from rknn.api import RKNN
import onnx
import numpy as np
from onnx import TensorProto

# Patch onnx.mapping for rknn-toolkit2 compatibility with newer onnx
if not hasattr(onnx, 'mapping'):
    class Mapping:
        pass
    onnx.mapping = Mapping()
    onnx.mapping.TENSOR_TYPE_TO_NP_TYPE = {
        TensorProto.FLOAT: np.dtype('float32'),
        TensorProto.BOOL: np.dtype('bool'),
        TensorProto.INT32: np.dtype('int32'),
        TensorProto.INT64: np.dtype('int64'),
        TensorProto.STRING: np.dtype('object'),
        TensorProto.INT8: np.dtype('int8'),
        TensorProto.UINT8: np.dtype('uint8'),
        TensorProto.UINT16: np.dtype('uint16'),
        TensorProto.INT16: np.dtype('int16'),
        TensorProto.UINT32: np.dtype('uint32'),
        TensorProto.UINT64: np.dtype('uint64'),
        TensorProto.FLOAT16: np.dtype('float16'),
        TensorProto.DOUBLE: np.dtype('float64'),
    }
    onnx.mapping.NP_TYPE_TO_TENSOR_TYPE = {
        np.dtype('float32'): TensorProto.FLOAT,
        np.dtype('bool'): TensorProto.BOOL,
        np.dtype('int32'): TensorProto.INT32,
        np.dtype('int64'): TensorProto.INT64,
        np.dtype('object'): TensorProto.STRING,
        np.dtype('int8'): TensorProto.INT8,
        np.dtype('uint8'): TensorProto.UINT8,
        np.dtype('uint16'): TensorProto.UINT16,
        np.dtype('int16'): TensorProto.INT16,
        np.dtype('uint32'): TensorProto.UINT32,
        np.dtype('uint64'): TensorProto.UINT64,
        np.dtype('float16'): TensorProto.FLOAT16,
        np.dtype('float64'): TensorProto.DOUBLE,
    }

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
