"""Fetch pinned upstream sources and apply the project's small local patches."""
from pathlib import Path
import io, json, subprocess, tarfile
import requests
ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 ('ptrckfrnk/humanoid-video-to-3D','b5fbe42fe444328e9b660ed08e6f54f88ed3beb5','humanoid-video-to-3D'),
 ('facebookresearch/vggt','a288dd0f14786c93483e45524328726ab7b1b4ce','vendor/vggt'),
]
for repo, revision, relative in SOURCES:
    destination=ROOT/relative
    marker=destination/'.deployment-source.json'
    if marker.exists():
        if json.loads(marker.read_text())['revision'] != revision:
            raise SystemExit(f'Unexpected upstream version: {destination}')
        print(f'Already prepared: {relative}'); continue
    if destination.exists():
        raise SystemExit(f'{destination} exists without a completed-install marker; inspect it before retrying.')
    print(f'Downloading {repo}@{revision}',flush=True)
    response=requests.get(f'https://codeload.github.com/{repo}/tar.gz/{revision}',timeout=(30,300))
    response.raise_for_status()
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(response.content),mode='r:gz') as archive:
        members=archive.getmembers()
        for member in members:
            parts=Path(member.name).parts
            if len(parts)<2: continue
            member.name=str(Path(*parts[1:]))
            archive.extract(member,destination,filter='data')
    if relative=='humanoid-video-to-3D':
        for patch in sorted((ROOT/'patches').glob('*.patch')):
            subprocess.run(['git','apply','--directory='+relative,'--check',str(patch)],cwd=ROOT,check=True)
            subprocess.run(['git','apply','--directory='+relative,str(patch)],cwd=ROOT,check=True)
    marker.write_text(json.dumps(dict(repository=repo,revision=revision),indent=2))
print('Upstream sources ready.')
