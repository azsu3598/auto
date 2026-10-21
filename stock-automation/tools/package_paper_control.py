"""Build a deterministic Lambda ZIP; no network, credentials or AWS calls."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(destination):
    project=Path(__file__).resolve().parents[1]
    files={'paper_control.py':project/'infra/paper_control.py',
           'stock_automation/calendar.py':project/'src/stock_automation/calendar.py'}
    contents={name:path.read_bytes() for name,path in files.items()}
    contents['stock_automation/__init__.py']=b''
    for name,data in contents.items():compile(data,name,'exec')
    target=Path(destination)
    if target.exists():raise ValueError('Preserve existing package; choose a fresh destination')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(contents):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16;archive.writestr(info,contents[name])
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    return {'sha256':digest,'s3_key':'config/control/paper-control-'+digest+'.zip',
            'files':{n:hashlib.sha256(c).hexdigest() for n,c in contents.items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args()
    print(json.dumps(package(args.destination),indent=2))
