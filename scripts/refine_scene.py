"""Reconstruct sharp keyframes, then keep depth points corroborated by other views."""
from pathlib import Path
import os, sys, json, time
import numpy as np
import cv2
import torch
import open3d as o3d
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vendor/vggt'),str(ROOT/'humanoid-video-to-3D')]
from pipeline.reconstruct import reconstruct, _backproject
from pipeline.metrics import geometry_metrics
from PIL import Image, ImageDraw

import argparse
parser=argparse.ArgumentParser()
parser.add_argument('video', type=Path)
parser.add_argument('--output', type=Path)
parser.add_argument('--frames', type=int, default=20)
parser.add_argument('--image-size', type=int, default=518)
parser.add_argument('--device', choices=['mps','cuda','cpu'])
parser.add_argument('--conf-percentile', type=float, default=50)
parser.add_argument('--support-views', type=int, default=2, help='Required OTHER agreeing frames')
parser.add_argument('--depth-tolerance', type=float, default=.03)
args=parser.parse_args()
video=args.video.resolve()
from datetime import datetime
out=args.output or ROOT/'outputs'/f'{video.stem}_refined_{datetime.now():%Y%m%d_%H%M%S}'
if args.frames<3 or not 1<=args.support_views<args.frames or args.image_size<14 or args.image_size%14 or not 0<=args.conf_percentile<100 or args.depth_tolerance<=0:
    parser.error('Check frame count, support count, image size (multiple of 14), confidence percentile and positive depth tolerance')
if not video.is_file(): parser.error(f'Video does not exist: {video}')
if (out/'scene.ply').exists():
    raise SystemExit(f'Result exists: {out}; choose a new --output directory')
(out/'frames').mkdir(parents=True,exist_ok=True)
os.environ['VGGT_CHECKPOINT']=str(ROOT/'models/VGGT-1B/model.safetensors')
start=time.monotonic()
cap=cv2.VideoCapture(str(video)); total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps=cap.get(cv2.CAP_PROP_FPS)
assert cap.isOpened() and total>0 and fps>0, 'Video could not be decoded'
meta=dict(video=str(video),frames=total,fps=fps,duration_seconds=total/fps,width=cap.get(cv2.CAP_PROP_FRAME_WIDTH),height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT),rotation_degrees=cap.get(cv2.CAP_PROP_ORIENTATION_META),auto_orientation=cap.get(cv2.CAP_PROP_ORIENTATION_AUTO))
(out/'video_info.json').write_text(json.dumps(meta,indent=2))
print(json.dumps(meta),flush=True)
selected=[]; paths=[]
# Temporal bins preserve sequence coverage; compare sharpness at the same resolution.
for i, candidates in enumerate(np.array_split(np.arange(total),min(args.frames,total))):
    best=None
    for idx in np.unique(np.linspace(candidates[0],candidates[-1],8,dtype=int)):
        cap.set(cv2.CAP_PROP_POS_FRAMES,int(idx)); ok,frame=cap.read()
        if not ok: continue
        gray=cv2.cvtColor(cv2.resize(frame,(640,360)),cv2.COLOR_BGR2GRAY)
        score=float(cv2.Laplacian(gray,cv2.CV_32F).var())
        if best is None or score>best[0]: best=(score,int(idx),frame)
    if best:
        score,idx,frame=best; path=out/'frames'/f'frame_{i:04d}.png'
        cv2.imwrite(str(path),frame); paths.append(path)
        selected.append(dict(index=idx,time_seconds=idx/fps,sharpness=score))
cap.release()
(out/'frame_selection.json').write_text(json.dumps(selected,indent=2))
print('Selected',len(paths),'sharp temporal keyframes',flush=True)
sheet=Image.new('RGB',(1280,204*((len(paths)+3)//4)),'#181c25'); draw=ImageDraw.Draw(sheet)
for i,path in enumerate(paths):
    im=Image.open(path).convert('RGB'); im.thumbnail((320,180)); x=i%4*320; y=i//4*204
    sheet.paste(im,(x,y)); draw.text((x+8,y+183),f'{selected[i]["time_seconds"]:.1f}s',fill='white')
sheet.save(out/'keyframes.jpg')
from utils.device import get_device,get_dtype
device=get_device(args.device)
if len(paths)<=args.support_views: raise RuntimeError('Too few decoded frames for requested cross-view support')
result=reconstruct(paths,device,get_dtype(device),'vggt',args.image_size)
print('Inference complete',flush=True)
# Use calibrated pinhole backprojection with predicted (relative-scale) depth.
result.world_points=_backproject(result.depth,result.extrinsics,result.intrinsics)
result.world_points_conf=result.depth_conf
np.savez_compressed(out/'reconstruction.npz',**{k:getattr(result,k) for k in ['images','world_points','world_points_conf','depth','depth_conf','extrinsics','intrinsics']},frame_paths=np.array([str(p) for p in paths]))
S,H,W=result.depth.shape
confidence=result.depth_conf
threshold=max(float(np.percentile(confidence,args.conf_percentile)),1.00001)
depth=result.depth
# Relative depth discontinuities are unreliable near occlusion boundaries.
gy,gx=np.gradient(depth,axis=(1,2))
edge=np.hypot(gx,gy)/np.maximum(depth,1e-6)
mask=(confidence>threshold)&(edge<0.05)&np.isfinite(result.world_points).all(axis=-1)&(depth>0)
mask[:,:2,:]=False;mask[:,-2:,:]=False;mask[:,:,:2]=False;mask[:,:,-2:]=False
flat=np.flatnonzero(mask.ravel()); pts=result.world_points.reshape(-1,3)[flat]; cols=result.images.reshape(-1,3)[flat]/255.
owners=flat//(H*W); support=np.zeros(len(pts),np.uint8)
print('Confidence/edge filter',S*H*W,'->',len(pts),'threshold',threshold,flush=True)
# Require two OTHER views with both close depth and confident predictions.
for s in range(S):
    R=result.extrinsics[s,:3,:3]; t=result.extrinsics[s,:3,3]; K=result.intrinsics[s]
    cam=pts@R.T+t; z=cam[:,2]; uv=cam@K.T
    u=np.rint(uv[:,0]/np.maximum(z,1e-8)).astype(int); v=np.rint(uv[:,1]/np.maximum(z,1e-8)).astype(int)
    valid=(z>0)&(u>=0)&(u<W)&(v>=0)&(v<H)&(owners!=s)
    idx=np.flatnonzero(valid); uu=u[idx]; vv=v[idx]
    dd=depth[s,vv,uu]; rel=np.abs(z[idx]-dd)/np.maximum(dd,1e-8)
    agree=(rel<args.depth_tolerance)&(confidence[s,vv,uu]>threshold)&(edge[s,vv,uu]<0.05)
    support[idx[agree]]+=1
keep=support>=args.support_views
cloud=o3d.geometry.PointCloud(); cloud.points=o3d.utility.Vector3dVector(pts[keep]); cloud.colors=o3d.utility.Vector3dVector(cols[keep])
voxel=float(np.median(depth))*0.0025
cloud=cloud.voxel_down_sample(voxel)
cloud,_=cloud.remove_statistical_outlier(nb_neighbors=24,std_ratio=1.5)
assert len(cloud.points)>1000,'Too few points survived; inspect diagnostics'
assert o3d.io.write_point_cloud(str(out/'scene.ply'),cloud)
info=dict(video=str(video),parameters=dict(frames=S,image_size=args.image_size,device=str(device),geometry='depth_backprojection',confidence_threshold=threshold,other_view_support=args.support_views,relative_depth_tolerance=args.depth_tolerance,voxel_size_model_units=voxel),results=dict(n_points=len(cloud.points),**geometry_metrics(result,cloud)),elapsed_s=round(time.monotonic()-start,2),scale='relative; not calibrated to metres',note='Consistency is an internal diagnostic, not independent geometric accuracy.')
(out/'run_info.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info,indent=2),flush=True)
