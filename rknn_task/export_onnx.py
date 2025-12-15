from ultralytics import YOLO

# Load the model
model = YOLO("yolo11n-seg.pt")  # Or your specific .pt path

# Export to ONNX
# opset=12 or 19 is usually safe for RK3588
# simplify=True is CRITICAL
# dynamic=False (Must be static shape for best NPU performance)
model.export(format="onnx", opset=12, simplify=True, dynamic=False, imgsz=640)
print("Exported to yolo11n-seg.onnx")
