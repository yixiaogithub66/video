import os
import torch
import numpy as np
from PIL import Image
import logging
from video_platform.runners.base import BaseRunner, ModelNotInstalledError

logger = logging.getLogger(__name__)

class SAM2Runner(BaseRunner):
    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.predictor = None

    def check_installed(self) -> bool:
        try:
            import sam2
            return True
        except ImportError:
            return False

    def load(self, model_dir: str, device: str = "cuda"):
        if not self.check_installed():
            raise ModelNotInstalledError("SAM2 dependencies are not installed. Please install them or the recommended model bundle first.")
        
        from sam2.build_sam import build_sam2_video_predictor
        
        # Assuming standard model files
        sam2_checkpoint = os.path.join(model_dir, "sam2_hiera_large.pt")
        model_cfg = "sam2_hiera_l.yaml"
        
        if not os.path.exists(sam2_checkpoint):
            raise ModelNotInstalledError(f"SAM2 model weights not found at {sam2_checkpoint}. Please install the model bundle.")
            
        self.device = torch.device(device)
        logger.info(f"Loading SAM2 model from {sam2_checkpoint} on {device}")
        
        self.predictor = build_sam2_video_predictor(model_cfg, sam2_checkpoint, device=self.device)
        self.model = True

    def predict(self, video_dir: str, initial_mask: np.ndarray = None, points: list = None, labels: list = None) -> list[np.ndarray]:
        if not self.model:
            raise RuntimeError("Model not loaded")
            
        inference_state = self.predictor.init_state(video_path=video_dir)
        
        if points is not None and labels is not None:
            self.predictor.add_new_points_or_box(
                inference_state=inference_state,
                frame_idx=0,
                obj_id=1,
                points=np.array(points, dtype=np.float32),
                labels=np.array(labels, dtype=np.int32),
            )
        elif initial_mask is not None:
            self.predictor.add_new_mask(
                inference_state=inference_state,
                frame_idx=0,
                obj_id=1,
                mask=initial_mask
            )
        
        masks = []
        for out_frame_idx, out_obj_ids, out_mask_logits in self.predictor.propagate_in_video(inference_state):
            mask = (out_mask_logits[0, 0] > 0.0).cpu().numpy().astype(np.uint8) * 255
            masks.append(mask)
            
        return masks

    def unload(self):
        if self.predictor is not None:
            del self.predictor
        self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
