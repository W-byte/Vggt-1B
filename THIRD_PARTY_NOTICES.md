# 上游与第三方说明

本项目使用下列上游项目，安装脚本下载固定提交的源码，不将完整源码或模型权重重复提交到本仓库。

- humanoid-video-to-3D: https://github.com/ptrckfrnk/humanoid-video-to-3D
  - 固定提交：b5fbe42fe444328e9b660ed08e6f54f88ed3beb5。
  - 本仓库保留针对其代码的部署补丁，不将其声明为本项目原创。
  - 当前获取的源码中未发现独立 LICENSE 文件；公开可下载不代表获得任意再分发许可。本仓库不为该上游额外授予权限。
- VGGT: https://github.com/facebookresearch/vggt
  - 固定提交：a288dd0f14786c93483e45524328726ab7b1b4ce。
  - 请查阅下载后的 vendor/vggt/LICENSE.txt 及官方仓库许可。
  - 论文：Wang et al., Visual Geometry Grounded Transformer, CVPR 2025。
- VGGT-1B checkpoint: https://huggingface.co/facebook/VGGT-1B
  - 固定版本：860abec7937da0a4c03c41d3c269c366e82abdf9。
  - 原始权重模型说明标注 CC-BY-NC-4.0；与其他商业许可权重应分别核对。
- Open3D: https://github.com/isl-org/Open3D
- Rerun: https://github.com/rerun-io/rerun
- PyTorch: https://github.com/pytorch/pytorch

各依赖适用其各自许可。仓库未附统一的 MIT 等许可，不应推断它可以覆盖或替换上游条款。模型、视频、点云和室内截图均未随发布包上传。
