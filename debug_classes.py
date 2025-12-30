import cv2
import sys
import numpy as np
from src.npu_inference import NPUInference

# Load the model directly
MODEL_PATH = "/mnt/merged_ssd/mcp-doc-cropper/yolo11n-seg.rknn"

def debug_inference(img_path):
    print(f"Loading model from {MODEL_PATH}...")
    try:
        model = NPUInference(MODEL_PATH)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    print(f"Loading image: {img_path}")
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image.")
        return

    print("Running inference...")
    # helper to access the raw results before NMS if needed, 
    # but let's use the run() method and print what survives NMS first.
    # If nothing survives, we might need to lower conf_thres in NPUInference temporarily.
    
    # Temporarily lower threshold to see EVERYTHING
    model.conf_thres = 0.10 
    
    results = model.run(img)
    
    print("\n--- DETECTED OBJECTS ---")
    if not results:
        print("No objects detected.")
    else:
        for i, res in enumerate(results):
            box = res['box']
            score = res['score']
            class_id = res['class_id']
            
            # Calculate area
            width = box[2] - box[0]
            height = box[3] - box[1]
            area = width * height
            
            print(f"[{i}] Class ID: {class_id} | Score: {score:.4f} | Area: {area:.0f}")
            print(f"    Box: {box}")

    print("\n-----------------------")
    print("NOTE: Standard COCO Class 0 is usually 'Person'.")
    model.release()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_classes.py <image_path>")
    else:
        debug_inference(sys.argv[1])
