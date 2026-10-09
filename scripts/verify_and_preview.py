"""Validate the PLY and create a compact, deterministic three-view preview."""
import json
from pathlib import Path
import sys
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = Path(sys.argv[1]).resolve()
cloud = o3d.io.read_point_cloud(str(out / "scene.ply"))
points = np.asarray(cloud.points)
colors = np.asarray(cloud.colors)
assert len(points) > 1000, "Point cloud is unexpectedly small"
assert colors.shape == points.shape, "RGB is missing"
assert np.isfinite(points).all(), "PLY contains non-finite coordinates"
assert np.isfinite(colors).all(), "PLY contains non-finite colors"
with np.load(out / "reconstruction.npz", allow_pickle=False) as data:
    assert all(np.isfinite(data[k]).all() for k in ["depth", "intrinsics", "extrinsics", "world_points"])
    frames = len(data["images"])
    input_shape = list(data["images"].shape)
    median_depth = float(np.median(data["depth"]))
stats = dict(points=len(points), frames=frames, rgb=True, all_finite=True,
             inference_images_shape=input_shape, median_depth_model_units=median_depth,
             coordinate_scale="relative; not calibrated to metres")
(out / "validation.json").write_text(json.dumps(stats, indent=2))

index = np.random.default_rng(42).choice(len(points), min(100000, len(points)), replace=False)
xyz, rgb = points[index], colors[index]
# Display all points, with robust limits for a readable view of the central scene.
lo, hi = np.percentile(xyz, [1, 99], axis=0)
center = (lo + hi) / 2
span = max(hi - lo) * 0.55
fig = plt.figure(figsize=(15, 5), facecolor="#101723", layout="constrained")
for i, (elev, azim) in enumerate([(15, -60), (20, 30), (75, -60)]):
    ax = fig.add_subplot(1, 3, i+1, projection="3d", facecolor="#101723")
    ax.scatter(xyz[:, 0], xyz[:, 2], xyz[:, 1], c=rgb, s=0.22, linewidths=0,
               depthshade=False, rasterized=True)
    ax.set_xlim(center[0]-span, center[0]+span)
    ax.set_ylim(center[2]-span, center[2]+span)
    ax.set_zlim(center[1]-span, center[1]+span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(["Perspective A", "Perspective B", "Top view"][i], color="white", fontsize=12)
label = Path(json.loads((out / "run_info.json").read_text())["video"]).stem
fig.suptitle(f"{label} / VGGT-1B  •  {len(points):,} RGB points  •  {frames} keyframes", color="white", fontsize=16)
fig.savefig(out / "scene_preview.png", dpi=150, facecolor=fig.get_facecolor())
plt.close(fig)
print(json.dumps(stats, indent=2))
