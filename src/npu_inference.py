import numpy as np
import cv2
from rknnlite.api import RKNNLite

class NPUInference:
    def __init__(self, model_path, npu_id=0):
        self.rknn = RKNNLite()
        
        # Load RKNN model
        print(f"Loading RKNN model: {model_path}")
        if self.rknn.load_rknn(model_path) != 0:
            raise RuntimeError("Error loading RKNN model")
            
        # Init runtime environment
        if self.rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0) != 0:
            raise RuntimeError("Error initializing NPU runtime")
            
        self.img_size = 640  # Standard for this model
        self.conf_thres = 0.10
        self.iou_thres = 0.45

    def preprocess(self, img):
        """
        Resize image to 640x640 with letterbox (padding), convert BGR->RGB.
        Returns: 
            input_data: (1, 640, 640, 3)
            scale: resizing scale (ratio)
            pad: (dw, dh) padding
        """
        h0, w0 = img.shape[:2]
        r = min(self.img_size / h0, self.img_size / w0)
        
        # Compute padding
        new_unpad = int(round(w0 * r)), int(round(h0 * r))
        dw, dh = self.img_size - new_unpad[0], self.img_size - new_unpad[1]
        
        # Divide padding by 2
        dw /= 2
        dh /= 2
        
        if (w0, h0) != new_unpad:
            img_resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        else:
            img_resized = img

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        
        # Add padding
        img_padded = cv2.copyMakeBorder(img_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        
        # BGR to RGB
        img_rgb = cv2.cvtColor(img_padded, cv2.COLOR_BGR2RGB)
        
        # Add batch dimension: (1, 640, 640, 3)
        # Note: rknnlite expects HWC or CHW depending on config. 
        # Usually standard export expects HWC (height, width, channel) for inputs
        input_data = np.expand_dims(img_rgb, axis=0)
        
        return input_data, r, (dw, dh)

    def postprocess(self, outputs, ratio, pad):
        """
        Parse raw tensors to boxes.
        outputs[0]: (1, 116, 8400) -> [cx, cy, w, h, class_scores..., mask_coeffs...]
        outputs[1]: (1, 32, 160, 160) -> Proto masks (unused for pure cropping if we just use box)
        """
        
        # Main output: (1, 116, 8400)
        # Transpose to (1, 8400, 116) for easier processing
        pred = np.transpose(outputs[0], (0, 2, 1)) 
        
        pred = pred[0] # (8400, 116)
        
        # Split: Boxes (4), Scores (80), Masks (32)
        # Depending on export, sometimes it's 4+80+32
        box_pred = pred[:, :4] # cx, cy, w, h
        class_pred = pred[:, 4:4+80] # 80 classes
        # mask_pred = pred[:, 84:] # 32 coeffs (ignore for now)
        
        # Get max score and class ID
        conf_scores = np.max(class_pred, axis=1)
        class_ids = np.argmax(class_pred, axis=1)
        
        # Filter by confidence
        mask = conf_scores > self.conf_thres
        boxes = box_pred[mask]
        scores = conf_scores[mask]
        classes = class_ids[mask]
        
        # [MODIFIED] Filter out Person class (ID 0) to prevent cropping the user instead of the document
        # We want to crop "documents", which might appear as Book (73), Handbag (26), or others.
        # But we definitely don't want Person (0).
        not_person_mask = classes != 0
        boxes = boxes[not_person_mask]
        scores = scores[not_person_mask]
        classes = classes[not_person_mask]
        
        if len(boxes) == 0:
            return []

        # Convert cx,cy,w,h to x1,y1,x2,y2
        boxes_xyxy = np.zeros_like(boxes)
        boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2  # x1
        boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2  # y1
        boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2  # x2
        boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2  # y2
        
        # NMS (Non-Maximum Suppression)
        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(), 
            scores.tolist(), 
            self.conf_thres, 
            self.iou_thres
        )
        
        results = []
        if len(indices) > 0:
            indices = indices.flatten()
            for i in indices:
                box = boxes_xyxy[i]
                # Scale boxes back to original image
                # Remove padding
                box[0] = (box[0] - pad[0]) / ratio
                box[2] = (box[2] - pad[0]) / ratio
                box[1] = (box[1] - pad[1]) / ratio
                box[3] = (box[3] - pad[1]) / ratio
                
                results.append({
                    'box': box, # [x1, y1, x2, y2]
                    'score': scores[i],
                    'class_id': classes[i]
                })
                
        return results

    def run(self, img):
        inputs, ratio, pad = self.preprocess(img)
        outputs = self.rknn.inference(inputs=[inputs])
        detections = self.postprocess(outputs, ratio, pad)
        return detections

    def release(self):
        self.rknn.release()
