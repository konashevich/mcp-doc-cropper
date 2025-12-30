from rknnlite.api import RKNNLite

def inspect_model(model_path):
    rknn_lite = RKNNLite()
    
    print(f"Loading model: {model_path}")
    ret = rknn_lite.load_rknn(model_path)
    if ret != 0:
        print("Load RKNN model failed")
        return

    print("Init runtime environment")
    ret = rknn_lite.init_runtime()
    if ret != 0:
        print("Init runtime environment failed")
        return

    print("\n--- Input Info ---")
    # Some versions expose inputs/outputs directly, others via verify
    try:
        # This is the standard way to check inputs/outputs in recent toolkit versions
        # Check internal structures if public API is vague
        print("Inputs:", rknn_lite.args.inputs if hasattr(rknn_lite, 'args') else "Unknown")
        # Attempt to run a dummy inference to see shapes? 
        # Actually proper way is usually just knowing what you exported, 
        # but let's try to print the internal details if accessible.
        pass
    except Exception as e:
        print(e)
        
    print("Done")
    # For RKNNLite, we often just run a dummy inference to see what we get back
    import numpy as np
    # Assuming 640x640 input based on filename/standard yolo
    dummy_input = np.zeros((1, 640, 640, 3), dtype=np.uint8) 
    
    print("\n--- Running Dummy Inference to check Output Shapes ---")
    try:
        outputs = rknn_lite.inference(inputs=[dummy_input])
        for i, out in enumerate(outputs):
            print(f"Output {i} shape: {out.shape} dtype: {out.dtype}")
    except Exception as e:
        print(f"Inference failed (maybe input shape wrong?): {e}")

    rknn_lite.release()

if __name__ == "__main__":
    inspect_model("/mnt/merged_ssd/mcp-doc-cropper/yolo11n-seg.rknn")
