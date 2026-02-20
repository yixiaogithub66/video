import os
import torch
import numpy as np
import cv2
import logging
from typing import List
from video_platform.runners.base import BaseRunner, ModelNotInstalledError

logger = logging.getLogger(__name__)

class ProPainterRunner(BaseRunner):
    def __init__(self):
        self.model = None
        self.device = "cpu"

    def check_installed(self) -> bool:
        try:
            from propainter.inference import Inpainter
            return True
        except ImportError:
            return False

    def load(self, model_dir: str, device: str = "cuda"):
        if not self.check_installed():
            raise ModelNotInstalledError("ProPainter dependencies are not installed. Please install them or the recommended model bundle first.")
            
        import torchvision.transforms.functional as TF
        from propainter.inference import Inpainter
        
        # Verify model files exist in directory
        if not os.path.exists(os.path.join(model_dir, "ProPainter.pth")):
            raise ModelNotInstalledError(f"ProPainter weights not found in {model_dir}. Please install the model bundle.")
            
        logger.info(f"Loading ProPainter model from {model_dir} on {device}")
        self.model = Inpainter(model_dir=model_dir, device=device)
        self.device = device
            
    def predict(self, frames_dir: str, masks: List[np.ndarray], output_dir: str) -> str:
        if not self.model:
            raise RuntimeError("Model not loaded")
            
        import torchvision.transforms.functional as TF
        
        os.makedirs(output_dir, exist_ok=True)
        frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(('.jpg', '.png'))])
        
        if len(frame_files) != len(masks):
            raise ValueError(f"Number of frames ({len(frame_files)}) does not match masks ({len(masks)})")

        video_tensors = []
        mask_tensors = []
        
        for f, m in zip(frame_files, masks):
            img = cv2.imread(os.path.join(frames_dir, f))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_tensor = TF.to_tensor(img).unsqueeze(0)  
            video_tensors.append(img_tensor)
            
            m_tensor = torch.from_numpy(m).float().unsqueeze(0).unsqueeze(0) / 255.0  
            mask_tensors.append(m_tensor)
            
        video = torch.cat(video_tensors, dim=0).to(self.device) 
        mask = torch.cat(mask_tensors, dim=0).to(self.device)   
        
        batch_size = 10
        with torch.no_grad():
            inpainted_video = self.model.forward(video, mask, b_size=batch_size)
            
        inpainted_np = inpainted_video.cpu().numpy() 
        inpainted_np = (inpainted_np * 255).astype(np.uint8)
        
        for i, f in enumerate(frame_files):
            out_img = inpainted_np[i].transpose(1, 2, 0)
            out_img = cv2.cvtColor(out_img, cv2.COLOR_RGB2BGR)
            cv2.imwrite(os.path.join(output_dir, f), out_img)
            
        return output_dir

    def unload(self):
        if self.model is not None:
            del self.model
        self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
