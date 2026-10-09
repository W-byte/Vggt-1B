"""Export a saved reconstruction to a Rerun recording without rerunning VGGT."""
from pathlib import Path
import sys
import numpy as np
import open3d as o3d

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "humanoid-video-to-3D"))
from pipeline.reconstruct import ReconstructionResult
from pipeline.postprocess import SceneResult
from viz.viewer import launch_viewer

directory = Path(sys.argv[1]).resolve()
with np.load(directory / "reconstruction.npz", allow_pickle=False) as data:
    values = {key: data[key] for key in data.files}
values["frame_paths"] = [Path(p) for p in values["frame_paths"]]
result = ReconstructionResult(**values)
scene = SceneResult(o3d.io.read_point_cloud(str(directory / "scene.ply")), None)
launch_viewer(result, scene, None, directory, open_viewer=False)
