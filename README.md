# VGGT-1B 视频三维重建：MP4 / MOV → scene.ply

基于 **VGGT-1B + Open3D + Rerun** 的本地视频三维重建项目，支持将 IMX415 等相机录制的 MP4、iPhone 拍摄的 MOV 转为带 RGB 颜色的点云，并保存深度、相机参数和交互式三维查看文件。

已在 **Apple M5 Pro / 48 GiB 统一内存 / macOS / Python 3.12** 上跑通 Apple Silicon MPS 加速。提供快速模式，以及通过清晰帧选择、深度反投影和跨视角过滤改善噪点的改进模式。

> 输出属于视觉重建结果：存在噪点、空洞和局部形变的可能，**未经尺度标定不能直接将坐标当作米**。本项目没有实现 RGB-D 相机采集、SLAM 回环优化或真实尺寸标定。

## 目录

- [功能与处理流程](#功能与处理流程)
- [环境和资源需求](#环境和资源需求)
- [部署步骤](#部署步骤)
- [开始重建](#开始重建)
- [结果文件与查看方式](#结果文件与查看方式)
- [参数说明与调优](#参数说明与调优)
- [实测记录](#实测记录)
- [拍摄建议](#拍摄建议)
- [常见问题](#常见问题)
- [项目结构](#项目结构)
- [实现说明与上游来源](#实现说明与上游来源)

## 功能与处理流程

```text
MP4 / MOV / AVI
      │
      ├─ 快速模式：按画面差异选择关键帧
      └─ 改进模式：时间分段，每段挑选较清晰的帧
                         │
                         ▼
                  VGGT-1B 推理
           相机内参、外参、深度、点图、置信度
                         │
           ┌─────────────┴─────────────┐
           │                           │
     快速模式：直接点图           改进模式：深度反投影
           │                           │
     置信度/统计过滤          置信度 + 深度边缘过滤
                                       │
                           跨视角深度一致性检查
                                       │
                           体素降采样 + 统计去噪
           └─────────────┬─────────────┘
                         ▼
              scene.ply + reconstruction.npz
                         │
                  Rerun / 静态预览
```

**默认推荐改进模式。** 它保留较可信的几何，通常能减少漂浮点；代价是低置信度墙面、床面和遮挡区域可能留下空洞。增加点数不等于提高精度。

全部模型推理在本机完成。安装时需要下载依赖、上游源码和模型；下载完成后，使用本地权重的重建流程不需要把视频上传到云端。

## 环境和资源需求

| 项目 | 说明 |
|---|---|
| 已验证平台 | Apple Silicon Mac，M5 Pro，48 GiB 内存 |
| Python | 推荐 **3.12**；部署脚本要求 3.12+，其他版本未验证 |
| 系统工具 | Git；macOS 可通过 Xcode Command Line Tools 获得 |
| 模型文件 | VGGT-1B safetensors，约 **5.03 GB** |
| 磁盘 | 建议预留 **20 GB 以上**，包括环境、权重、断点续传分片及输出 |
| 内存 | 本项目仅在 48 GiB 设备验证；更小内存需减少帧数和分辨率 |
| 网络 | 首次需要访问 PyPI、GitHub 官方源码下载端点、Hugging Face |

改进脚本可选择 `mps`、`cuda` 或 `cpu`，不指定时自动检测。**CUDA / CPU 路径尚未在本项目实测**；Linux CUDA 用户还需按自己的驱动环境安装适合的 PyTorch，不应把 Mac 的实测耗时当作其他平台保证。

## 部署步骤

### 1. 安装 Python 与 Git

如果已有 Python 3.12 和 Git，可跳过。

macOS 上可使用：

```bash
xcode-select --install
brew install python@3.12
```

检查版本：

```bash
python3.12 --version
git --version
```

### 2. 获取本仓库

```bash
git clone https://github.com/W-byte/Vggt-1B.git
cd Vggt-1B
```

后续命令均在仓库根目录执行；含空格的输入路径请加引号。

### 3. 创建隔离环境并准备源码

```bash
bash setup.command
```

该脚本会：

1. 在 `.venv/` 创建独立 Python 环境，不向系统 Python 安装依赖。
2. 安装 `requirements.txt` 中固定版本的主要依赖。
3. 下载固定提交版本的 `humanoid-video-to-3D` 和 VGGT 源码。
4. 将本项目的少量兼容性补丁应用到下载的管线源码。

如果 Python 可执行文件名不同，可指定：

```bash
PYTHON=/absolute/path/to/python3.12 bash setup.command
```

也可以手工执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/fetch_upstream.py
```

`requirements.lock.txt` 是当时完整环境的版本快照，便于排查差异；常规安装使用 `requirements.txt`。VGGT 源码通过本地路径导入，不额外执行上游包安装，以避免其依赖约束与本项目已验证的 NumPy / Rerun 组合冲突。

### 4. 下载模型权重

默认使用 Hugging Face 官方入口：

```bash
.venv/bin/python scripts/download_weights.py
```

官方入口连接不稳定时，可以**主动选择**公共镜像解析地址：

```bash
.venv/bin/python scripts/download_weights.py --endpoint https://hf-mirror.com --workers 8
```

下载器使用 32 MiB 分片，支持断点续传。中断后重新运行同一命令即可。默认 8 个并发连接，可使用 `--workers 1` 到 `--workers 32`；并发越高不一定越快。

最终文件：

```text
models/VGGT-1B/model.safetensors
models/VGGT-1B/download_info.json
```

固定模型版本与校验信息：

```text
Repository: facebook/VGGT-1B
Revision:   860abec7937da0a4c03c41d3c269c366e82abdf9
Bytes:      5026367224
SHA-256:    f164acf60724910d8fe1578bb499d800850c7bb0948db7555c413f9fbe60467e
```

下载完成后，脚本合并分片并校验 SHA-256，通过后才替换正式模型文件。下载分片默认保留在 `models/VGGT-1B/parts/`，因此会额外占用约 5 GB 空间。请等最终模型校验成功后再自行清理分片。

### 5. 检查 MPS

```bash
.venv/bin/python -c "import torch; print('PyTorch:', torch.__version__); print('MPS:', torch.backends.mps.is_available())"
```

Apple Silicon 的正常结果应包含 `MPS: True`。如果在受限制的运行环境中得到 `False`，还需要检查该环境是否允许访问 Metal GPU。

## 开始重建

### 推荐：改进模式

```bash
bash refine_scene.command "/absolute/path/to/video.MOV" \
  --output outputs/my_scene
```

默认参数：20 帧、518 像素输入宽度、深度反投影、严格置信度过滤、至少另外两个视角支持、3% 相对深度一致性阈值。

也可以直接调用脚本：

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python scripts/refine_scene.py \
  "/absolute/path/to/video.mp4" \
  --output outputs/my_scene \
  --device mps \
  --frames 20 \
  --image-size 518
```

不指定 `--output` 时自动建立带时间戳的目录。指定的目录已经有 `scene.ply` 时会拒绝覆盖，请使用新的目录名。`.command` 文件是 Bash 入口，以上终端调用方式可以可靠传入视频路径。

### 快速模式

```bash
bash reconstruct.command "/absolute/path/to/video.mp4" \
  --output outputs/my_fast_scene
```

默认使用 16 帧、392 像素宽度，直接使用 VGGT 点图。可覆盖参数：

```bash
bash reconstruct.command "/absolute/path/to/video.mp4" \
  --frames 20 --image-size 518 --device mps \
  --output outputs/my_fast_scene_518
```

快速模式主要用于快速查看和复现实验。上游的百分位置信度过滤采用 `>=`；当很多置信度都等于最低值时，未必真的删除指定比例的点。改进模式采用严格 `>`，同时排除最低置信度并加入跨视角检查，因此更适合本项目已观察到的噪点问题。

快速模式的上游入口不会阻止复用显式指定的输出目录。请为每次运行使用新目录，或不传 `--output` 让它自动命名。

## 结果文件与查看方式

典型改进模式结果：

```text
outputs/my_scene/
├── frames/                 # 原始分辨率的选中帧
├── frame_selection.json    # 帧号、时间、清晰度分数
├── video_info.json         # 分辨率、帧数、帧率、方向元数据
├── keyframes.jpg           # 关键帧缩略总览
├── scene.ply               # 最终带 RGB 的点云
├── reconstruction.npz      # 图像、深度、内外参和稠密点图
└── run_info.json            # 参数、点数、耗时和自一致性指标
```

其中 `reconstruction.npz` 是未经过最终点筛选的逐像素预测与反投影数据，`scene.ply` 是筛选、降采样后的点云；二者点数不必相同。NPZ 内包括：

- `images`：模型实际使用的 RGB 图像。
- `depth`、`depth_conf`：预测深度和置信度。
- `extrinsics`：从世界坐标到相机坐标的外参。
- `intrinsics`：模型输入分辨率下的相机内参。
- `world_points`、`world_points_conf`：逐像素世界坐标点与置信度。
- `frame_paths`：所用帧文件路径。

### 生成静态预览与检查文件

```bash
MPLCONFIGDIR="$PWD/.cache/matplotlib" \
  .venv/bin/python scripts/verify_and_preview.py outputs/my_scene
```

生成 `validation.json` 与 `scene_preview.png`。检查包括点数、RGB 是否存在，以及点坐标、深度、相机参数是否包含 NaN / Inf。

预览为了渲染速度会抽样最多 10 万个点，并用稳健范围显示主体；三维图的视角仅为展示用途，不代表实际重力方向。**文件有效性检查不等同于几何精度验证。**

### 导出 Rerun

```bash
.venv/bin/python scripts/export_rerun.py outputs/my_scene
```

生成 `outputs/my_scene/demo.rrd`，可查看三维点云、相机位置、RGB 帧和深度图，不需要再次运行 VGGT。

本机应用查看：

```bash
bash view_scene.command outputs/my_scene/demo.rrd
```

浏览器查看：

```bash
.venv/bin/python -m rerun \
  --serve-web --bind 127.0.0.1 \
  --web-viewer-port 9095 --port 9878 \
  outputs/my_scene/demo.rrd
```

随后打开：

```text
http://127.0.0.1:9095/?url=rerun%2Bhttp%3A%2F%2F127.0.0.1%3A9878%2Fproxy
```

终端中的服务必须保持运行，关闭后链接会失效。端口占用时同时修改命令和 URL 中对应端口。`127.0.0.1` 只允许本机访问。

也可以用 CloudCompare、MeshLab 等软件直接打开 `scene.ply`。

## 参数说明与调优

以下是 **`scripts/refine_scene.py` / `refine_scene.command`** 的参数：

| 参数 | 默认值 | 用途 |
|---|---:|---|
| `video` | 必填 | 本地视频路径 |
| `--output` | 自动命名 | 输出目录；已有点云则拒绝覆盖 |
| `--frames` | 20 | 选取帧数，至少 3 帧 |
| `--image-size` | 518 | 模型输入宽度，必须是 14 的正倍数 |
| `--device` | 自动检测 | `mps` / `cuda` / `cpu` |
| `--conf-percentile` | 50 | 置信度百分位门槛，范围 `[0,100)` |
| `--support-views` | 2 | 需要另外多少个视角支持该点，必须小于帧数 |
| `--depth-tolerance` | 0.03 | 跨视角允许的相对深度差，0.03 表示 3% |

内存不足时，先降低帧数和分辨率：

```bash
bash refine_scene.command video.mp4 --frames 12 --image-size 392
```

如果噪点多，可提高置信度门槛或支持视角数，例如：

```bash
bash refine_scene.command video.mp4 \
  --conf-percentile 65 --support-views 3 --depth-tolerance 0.02
```

如果空洞过多，可适当放宽筛选：

```bash
bash refine_scene.command video.mp4 \
  --conf-percentile 30 --support-views 1 --depth-tolerance 0.05
```

后两组是调参示例，未在所有场景验证。更严格的筛选会减少噪点，也会减少覆盖率；放宽筛选不会恢复原本没有观测到的真实几何。

深度边缘阈值、体素尺寸比例和统计离群点参数目前写在改进脚本内，尚未提供命令行开关。

## 实测记录

以下来自同一台 M5 Pro / 48 GiB Mac。原始视频、室内图像、点云和个人路径不随本仓库发布。

| 输入与模式 | 关键帧 / 输入宽度 | 最终点数 | 抽帧至导出耗时 | 内部深度不一致中位数 |
|---|---|---:|---:|---:|
| IMX415 MP4，快速 | 16 / 392 | 1,370,480 | 17.61 秒 | 6.607% |
| IMX415 MP4，改进 | 20 / 518 | 317,126 | 28.53 秒 | 1.546% |
| iPhone 4K MOV，改进 | 20 / 518 | 871,958 | 96.92 秒 | 0.552% |

耗时不包含首次安装、约 5 GB 权重下载、后续静态预览及 Rerun 导出。iPhone 视频约 14.28 秒、3840×2160、59.88 fps；4K 视频解码与随机定位帧本身可能耗时较长。

iPhone 与 IMX415 视频拍摄的场景不同，**不能把该表当作相机性能对照实验**。跨视角筛选直接使用了深度一致性，因此筛选后的自一致性指标也不是独立精度评估，更不意味着达到毫米或厘米级精度。

## 拍摄建议

- 尽量保持场景静止，避免屏幕持续变化、人员走动。
- 缓慢移动相机，让相邻视角有充分重叠，并包含一定平移。
- 避免只在原地快速转动、剧烈抖动、运动模糊。
- 保持光照充足，尽量避免强反光、镜面和透明物体。
- 从多个方向观察目标；只看见一个方向的表面无法完整恢复背面。
- 使用同一镜头和较稳定的焦距，避免录制中突然切镜头或缩放。
- 先用 10–30 秒的单场景短片验证，再考虑更大的场景。

当前清晰帧选择是在每个时间段内比较拉普拉斯方差；它只是启发式方法，可能偏好纹理丰富的画面，不等于专业的运动模糊检测。方向信息会记录在 `video_info.json`，是否需要旋转应结合 `keyframes.jpg` 检查。VGGT 上游默认预处理会裁剪过高的图像，竖屏输入可能损失上下视野；当前实测使用横屏。

## 常见问题

### GitHub 克隆很慢或失败

可以从仓库页面下载 ZIP 后解压，再进入目录安装。上游源码安装器使用 `codeload.github.com` 的固定提交压缩包，减少对 Git 克隆的依赖；仍需要正常网络连接。

### Hugging Face 无法连接 / 下载尾段停滞

尝试显式指定镜像入口；保留 `models/VGGT-1B/parts/` 后重试。下载器会按已有文件大小续传，最终必须通过完整 SHA-256 校验。不要把仅下载了一部分的文件当作正式模型运行。

### 上游源码目录已存在，安装器拒绝覆盖

安装器只跳过带成功安装标记的目录。若中断导致未完成目录，请先检查或备份，再移走该目录后重试；不要覆盖有手工修改的源码。

### MPS 不可用 / 内存不足

检查 Apple Silicon、PyTorch 和当前进程的 GPU 访问权限。先试 `--frames 12 --image-size 392`。可以用 `--device cpu` 排查功能，但速度可能明显下降。本项目没有关闭 MPS 内存保护来强行运行。

### Open3D 提示缺少 libusb 动态库

首次部署中 Open3D 0.20 在该 Mac 上发生过动态库加载问题，因此本项目固定使用已跑通的 `open3d==0.19.0`。先确认当前激活的是仓库 `.venv`，而不是其他 Python 环境。

### 点云不完整、扭曲或墙面消失

单目预测、相机位姿误差、遮挡、纹理不足及运动模糊都可能影响几何。跨视角过滤能排除不一致的点，但无法保证恢复正确结构。优先检查关键帧，然后调整筛选强度，必要时补拍。

### `Too few points survived`

先检查 `keyframes.jpg` 是否正常、场景是否有足够重叠，再尝试降低 `--conf-percentile` 或 `--support-views`。不要只为了生成文件而无条件保留所有点。

### 输出是网格吗？能直接测量房间吗？

`scene.ply` 默认是**点云**，不是封闭网格；颜色来自输入图像。模型深度使用相对尺度，不能直接当成米。本项目当前没有真实尺度标定，也没有把 D435 等实测深度融合进来。

### 支持 SAM2 / CLIP 语义分割吗？

上游管线具有相关可选功能，但本仓库的安装和验证范围是几何重建。未安装或验证 SAM2、OpenCLIP，不应把它们当作默认可用能力。

## 项目结构

```text
.
├── README.md
├── requirements.txt            # 主要依赖固定版本
├── requirements.lock.txt       # 完整实测环境快照
├── setup.command               # 环境与固定上游源码准备
├── reconstruct.command         # 快速重建入口
├── refine_scene.command        # 改进重建入口
├── view_scene.command          # Rerun 本机查看入口
├── scripts/
│   ├── fetch_upstream.py
│   ├── download_weights.py
│   ├── refine_scene.py
│   ├── verify_and_preview.py
│   └── export_rerun.py
├── patches/                    # 对固定上游提交的兼容性差异
├── THIRD_PARTY_NOTICES.md
└── .gitignore
```

`.venv/`、`models/`、`outputs/`、下载后的上游源码、视频和缓存均忽略，不上传到 GitHub。请勿把 GitHub Token 或其他凭据写入脚本。

## 实现说明与上游来源

本仓库是已有模型与管线的部署封装和改进流程，**没有训练新的 VGGT 模型**。

| 上游 | 固定版本 | 用途 |
|---|---|---|
| [humanoid-video-to-3D](https://github.com/ptrckfrnk/humanoid-video-to-3D) | `b5fbe42fe444328e9b660ed08e6f54f88ed3beb5` | 视频处理、重建封装、Open3D 与 Rerun 管线 |
| [VGGT](https://github.com/facebookresearch/vggt) | `a288dd0f14786c93483e45524328726ab7b1b4ce` | 模型结构、图像预处理、相机参数解码 |
| [VGGT-1B 权重](https://huggingface.co/facebook/VGGT-1B) | `860abec7937da0a4c03c41d3c269c366e82abdf9` | 预训练权重 |

本项目补丁包括：加载本地 safetensors、使 `--image-size` 真正生效、保存预测数组、修正结果元数据的尺度表述、支持不弹窗导出 Rerun。改进脚本使用深度反投影替代直接点图，并添加严格置信度及跨视角过滤。

上游源码在安装时从官方仓库下载，保留其自身许可文件。本仓库不重新授权上游代码或权重；请阅读 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 及上游许可。尤其不要把原始 `facebook/VGGT-1B` 权重与另行发布的商业许可权重混为一谈。
