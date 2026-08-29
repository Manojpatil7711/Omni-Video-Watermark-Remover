from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence
import cv2
import numpy as np

@dataclass(frozen=True)
class Detection:
    mask: np.ndarray
    confidence: float
    bbox: Optional[tuple[int,int,int,int]] = None
    label: str = "watermark"

@dataclass
class StaticDetectorConfig:
    sample_frames: int = 48
    temporal_stability: float = 0.82
    edge_percentile: float = 85.0
    min_area_ratio: float = 0.0002
    max_area_ratio: float = 0.12
    border_fraction: float = 0.35
    morph_kernel: int = 5
    dilate_px: int = 3

class StaticDetector:
    """Detect persistent overlay-like regions using temporal variance + edge density."""
    def __init__(self, config: Optional[StaticDetectorConfig] = None): self.cfg = config or StaticDetectorConfig()
    def detect(self, frames: Sequence[np.ndarray]) -> Detection:
        if not frames: raise ValueError("At least one frame is required")
        shape=frames[0].shape[:2]
        if any(f.shape[:2]!=shape for f in frames): raise ValueError("Sampled frames must have identical dimensions")
        gray=np.stack([cv2.cvtColor(f,cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames])
        mean,var=gray.mean(0),gray.var(0); nv=var/(mean+12.0)
        cutoff=np.percentile(nv,max(1.0,(1-self.cfg.temporal_stability)*100)); stable=nv<=cutoff
        edges=np.stack([cv2.Canny(g.astype(np.uint8),50,150).astype(np.float32) for g in gray])
        ec=edges.mean(0)>=np.percentile(edges.mean(0),self.cfg.edge_percentile)
        candidate=(stable & ec).astype(np.uint8)*255
        h,w=shape; bf=max(1,int(min(h,w)*self.cfg.border_fraction)); border=np.zeros((h,w),np.uint8)
        border[:bf,:]=border[-bf:,:]=1; border[:,:bf]=border[:,-bf:]=1
        candidate=candidate & ((border|stable.astype(np.uint8))*255)
        k=max(3,self.cfg.morph_kernel|1); ker=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))
        candidate=cv2.morphologyEx(candidate,cv2.MORPH_CLOSE,ker); candidate=cv2.morphologyEx(candidate,cv2.MORPH_OPEN,ker)
        n,labels,stats,_=cv2.connectedComponentsWithStats(candidate); mask=np.zeros((h,w),np.uint8); total=float(h*w)
        for i in range(1,n):
            ratio=float(stats[i,cv2.CC_STAT_AREA])/total
            if self.cfg.min_area_ratio<=ratio<=self.cfg.max_area_ratio: mask[labels==i]=255
        if self.cfg.dilate_px>0:
            d=2*self.cfg.dilate_px+1; mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(d,d)))
        return Detection(mask,min(1.0,float(np.mean(mask>0))*8.0))

class TemplateDetector:
    def __init__(self,template_path:str,threshold:float=0.78):
        p=Path(template_path)
        if not p.is_file(): raise FileNotFoundError(p)
        self.template=cv2.imread(str(p),cv2.IMREAD_GRAYSCALE)
        if self.template is None: raise ValueError(f"Cannot decode template: {p}")
        self.threshold=threshold
    def detect(self,frame:np.ndarray)->Detection:
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); th,tw=self.template.shape[:2]
        if th>gray.shape[0] or tw>gray.shape[1]: raise ValueError("Template is larger than input frame")
        score=cv2.matchTemplate(gray,self.template,cv2.TM_CCOEFF_NORMED); _,value,_,loc=cv2.minMaxLoc(score); mask=np.zeros(gray.shape,np.uint8)
        if value>=self.threshold:
            x,y=loc; mask[y:y+th,x:x+tw]=255; return Detection(mask,float(value),(x,y,tw,th))
        return Detection(mask,float(value))

class DynamicDetector:
    """Adapter façade for SAM-2/YOLO-World/Florence-2 backends."""
    def __init__(self,backend=None,label_allowlist:Optional[Iterable[str]]=None): self.backend=backend; self.label_allowlist={x.lower() for x in (label_allowlist or [])}
    def detect(self,frame:np.ndarray)->list[Detection]:
        if self.backend is None: raise RuntimeError("Configure a SAM-2, YOLO-World or Florence-2 backend")
        result=self.backend.predict(frame); result=result if isinstance(result,list) else list(result)
        return [d for d in result if not self.label_allowlist or d.label.lower() in self.label_allowlist]

def load_sampled_frames(video_path:str,sample_frames:int=48)->list[np.ndarray]:
    cap=cv2.VideoCapture(video_path)
    if not cap.isOpened(): raise OSError(f"Unable to open video: {video_path}")
    count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); step=max(1,count//max(1,sample_frames)); out=[]
    try:
        for i in range(0,max(count,1),step):
            cap.set(cv2.CAP_PROP_POS_FRAMES,i); ok,frame=cap.read()
            if ok and frame is not None: out.append(frame)
            if len(out)>=sample_frames: break
    finally: cap.release()
    if not out: raise RuntimeError("No decodable frames found")
    return out
