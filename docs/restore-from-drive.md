# Restore the complete HELPS workspace from Google Drive

The application code is on [GitHub, branch `codex/unified-helps`](https://github.com/ManimeghanathA/HELPS/tree/codex/unified-helps). The separately transferred resources are in the owner's [HELPS Google Drive folder](https://drive.google.com/drive/folders/1v3Eo60ZkBtCpT4d4eKRjjKsncMzzCZUc?usp=sharing).

The owner reports uploading the **entire `data` folder**, with the QGIS/vision folder now **inside `data`**. Upload completion and recipient permissions have not been verified by the application. Request access from the owner if Drive denies access. Do not assume that seeing the folder proves every file finished uploading.

**Drive is the backup/download source. HELPS reads a local restored copy; there is no Google Drive API login or direct Drive connection configured inside HELPS.** Existing datasets can be viewed without Copernicus credentials; new downloads require separately configured credentials.

## 1. Finish and preserve the source backup

Stop HELPS and all scans before taking the final database/registry snapshot. If uploads began while jobs were running, take another stopped, consistent copy of `data/knowledge` and update the backup. Wait for all uploads to finish; retain the original local files.

The backup must include:

```text
data/
  knowledge/registry.json
  knowledge/bhadra-cv-20260601-313234b7/knowledge.gpkg
  knowledge/bhadra-cv-20260601-313234b7/rasters/
  knowledge/...                     other packages, jobs, source records, history
  raw/                             original input evidence, DEM and team batches
  processed/                       prepared sources and historical imagery
  recovery/                        baseline replay evidence
  ...                              remaining data workspace directories
  probably_final.qgz/              a DIRECTORY, despite its suffix
    probably_final.gpkg            2,430,738,432 bytes: actual segmented vectors
    probably_final.qgs             QGIS project
    xljhOV_styles.db               supplied styles
```

The project/styles alone are insufficient. The 2.43 GB **GeoPackage must be present**. Keep original names and directory structure. Do not upload `.env` credentials as part of a shared backup. `.venv` and Python caches are not needed for restoration.

The application also supports the older root-level `probably_final.qgz/` layout as a fallback. New backups should use `data/probably_final.qgz/` so one `data` transfer includes the vision result. Accepted GeoPackages retain the original historical source paths as provenance; do not edit their embedded metadata to reflect this move.

## 2. Obtain the code on the destination computer

This is the **Windows/PowerShell** restoration procedure. The source workspace was verified with Python 3.10.9. Other operating systems need separate dependency and path-convention verification; this document does not claim an already tested Linux/macOS deployment.

Install Python 3.10, Git and Git LFS. Node.js is needed only for frontend tests. Then:

```powershell
git lfs install
git clone --branch codex/unified-helps https://github.com/ManimeghanathA/HELPS.git HELPS
cd HELPS
git lfs pull
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run all subsequent commands from this checkout root. If the GitHub repository is private, use your own authorized GitHub access; do not copy somebody else's tokens into commands or docs.

## 3. Download and restore the resources

Open the [Drive folder](https://drive.google.com/drive/folders/1v3Eo60ZkBtCpT4d4eKRjjKsncMzzCZUc?usp=sharing) in your browser with an account permitted by the owner. Download all parts of the `data` folder. If Drive produces multiple archives, extract all parts and preserve their structure in a temporary location first. Check that the download is complete.

Copy the restored `data` directory into the new checkout. The result must be **`HELPS/data/knowledge/registry.json`**, not `HELPS/data/data/knowledge/registry.json`. Preserve/backup any existing destination data rather than blindly overwriting a different working dataset. Use a complete local copy; do not rely on unmaterialized cloud placeholder files for GeoPackage/TIFF access.

Also confirm `HELPS/data/probably_final.qgz/probably_final.gpkg` exists. A standalone compressed `.qgz` project is not a replacement for the supplied directory and external GeoPackage.

## 4. Verify the restored scientific assets

The checked-in [data manifest](data-assets-2026-10-21.json) lists key file paths, sizes and SHA-256 checksums. It is not a full-file inventory of every cache/archive. Run:

```powershell
@'
import hashlib,json
from pathlib import Path
root=Path.cwd()
manifest=json.loads((root/'docs/data-assets-2026-10-21.json').read_text())
errors=[]
for item in manifest['assets']:
    path=root/item['path']
    if not path.is_file():
        errors.append('Missing: '+item['path']);continue
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    if path.stat().st_size!=item['bytes'] or digest.hexdigest()!=item['sha256']:
        errors.append('Size/hash mismatch: '+item['path'])
if errors:raise SystemExit('\n'.join(errors))
print('Verified',len(manifest['assets']),'key restored assets')
'@ | .\.venv\Scripts\python.exe -
```

Do this before changing routing. A missing/mismatched scientific asset should be re-downloaded or investigated, not fixed by rewriting the expected hash. These checks describe the 21 October snapshot; later scientific updates require their own manifest.

## 5. Relink mutable paths for the new computer

The original workspace was `C:\Users\manim\OneDrive\Desktop\HELPSs`. A different account or install location requires relinking. **Keep the server stopped.** The following command backs up and rewrites only mutable registry, uploaded-source, observation, region and durable-job JSON records. It does not edit GeoPackages, raw/processed completion manifests, build specs/manifests, source hashes or classification data.

```powershell
@'
import json
from datetime import datetime
from pathlib import Path
root=Path.cwd().resolve()
old='C:/Users/manim/OneDrive/Desktop/HELPSs'
new=root.as_posix()
managed=root/'data/knowledge'
if not (root/'app.py').is_file() or not (managed/'registry.json').is_file():
    raise SystemExit('Run from the restored HELPS checkout root')
files=[managed/name for name in ('registry.json','regions.json','observations.json')]
files+=list((managed/'sources').glob('*.asset.json'))
files+=list((managed/'jobs').glob('*.json'))
backup=root/'data/archive/restore-routing'/datetime.now().strftime('%Y%m%dT%H%M%S%f')
def relocate(value):
    if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
    if isinstance(value,list):return [relocate(v) for v in value]
    if isinstance(value,str):
        normalized=value.replace('\\','/')
        if normalized.lower()==old.lower():return new
        if normalized.lower().startswith(old.lower()+'/'):
            return new+normalized[len(old):]
    return value
changes=[]
for path in files:
    if not path.is_file():continue
    original=path.read_bytes()
    before=json.loads(original.decode('utf-8-sig'))
    after=relocate(before)
    if before!=after:changes.append((path,original,after))
# Validate active routing before writing any file.
registry=relocate(json.loads((managed/'registry.json').read_text(encoding='utf-8-sig')))
for region,identity in registry.get('selected',{}).items():
    package=Path(registry['datasets'][identity]['package_path'])
    if not package.is_absolute():package=root/package
    if not package.resolve().is_relative_to(managed) or not package.is_file():
        raise SystemExit('Active package missing/outside managed knowledge: '+str(package))
for path,original,after in changes:
    target=backup/path.relative_to(root)
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(original)
    temporary=path.with_name(path.name+'.restore-tmp')
    temporary.write_text(json.dumps(after,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
print('Relinked',len(changes),'mutable routing records')
if changes:print('Original routing backed up at',backup)
print('Selected datasets:',registry['selected'])
'@ | .\.venv\Scripts\python.exe -
```

If your source backup came from a different root, change `old` to that exact root. This prefix relink is not a repair for every historical checkout path or an incomplete backup. Old experimental jobs may reference deliberately archived sources. Do not edit immutable records to force them to work. Stop and investigate a missing active source/package.

## 6. Configure private credentials locally

Create `.env` from `.env.example` only if it does not already exist, then enter your own Copernicus credentials for new acquisitions. Viewing the restored map does not require a Sentinel download. Open-Meteo weather requires network access but no API key. The Drive sharing link is not a Copernicus credential and is not entered into the application provider form.

## 7. Start and verify the restored application

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), select Bhadra and check:

- Current dataset `bhadra-cv-20260601-313234b7`: **4,474 candidates**, **25,931 slope subregions**.
- Candidate features, slope shading and recommendation inputs/results load.
- Build knowledge shows current June 1 context and local source readiness. Use read-only **Check local inputs** before attempting a new scan.
- The separate vision folder is available for refinement/audit; ordinary Sentinel scans do not automatically run the teammate's model.

Detailed map payloads and initial package validation can take time. A count or a successful page load is not sufficient if geometry/features/slope fail to load. Inspect the error, missing path and source checksum rather than creating substitute data.

Optional regression checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
node --test tests/*.cjs tests/*.test.js
```

This guide does not mean Drive upload completeness, permissions or a full second-computer installation has been independently verified. It records the actual local layout, tested lookup behavior and explicit restoration steps. Preserve a separate original backup until the destination is fully checked.
