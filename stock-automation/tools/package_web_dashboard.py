"""Package a read-only Lambda and static assets without credentials or settings."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package(output):
    output=Path(output)
    if output.exists():raise ValueError('Preserve existing package directory')
    output.mkdir(parents=True)
    files={'paper_web_api.py':(ROOT/'infra/paper_web_api.py').read_bytes(),
        'stock_automation/dashboard.py':(ROOT/'src/stock_automation/dashboard.py').read_bytes(),
        'stock_automation/paper_wallet.py':(ROOT/'src/stock_automation/paper_wallet.py').read_bytes(),
        'stock_automation/__init__.py':b''}
    archive=output/'api.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16;z.writestr(info,data)
    static=output/'static';static.mkdir()
    assets=ROOT/'src/stock_automation/dashboard_static'
    html=(assets/'index.html').read_text(encoding='utf-8')
    needle='<script src="/app.js" defer></script>'
    if html.count(needle)!=1:raise ValueError('Dashboard script reference changed')
    html=html.replace(needle,'<script src="/config.js" defer></script>\n  <script src="/auth.js" defer></script>\n  '+needle)
    html=html.replace('<h2>모의운용</h2>','<h2>모의 원장 조회</h2>')
    html=html.replace('</head>','  <link rel="stylesheet" href="/auth.css">\n</head>')
    (static/'index.html').write_text(html,encoding='utf-8')
    js=(assets/'app.js').read_text(encoding='utf-8')
    needle='fetch("/api/dashboard", { cache: "no-store" })'
    if js.count(needle)!=1:raise ValueError('Dashboard fetch contract changed')
    js=js.replace(needle,'window.sabuDashboardFetch()')
    js=js.replace('${row.strategy} · 구성됨','${row.strategy} · 예정 시간')
    js=js.replace('setInterval(() => load(false), 60000)',
        'setInterval(() => { if (!document.hidden) load(false); }, 60000)')
    (static/'app.js').write_text(js,encoding='utf-8')
    for name,source in (('styles.css',assets/'styles.css'),('auth.js',ROOT/'web/auth.js'),('auth.css',ROOT/'web/auth.css')):
        (static/name).write_bytes(source.read_bytes())
    # Deployment-specific config.js is generated only from verified stack outputs.
    manifest={'api_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'lambda_files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
        'static_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in static.iterdir()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    manifest=package(args.output)
    print('WEB_PACKAGE_READY: '+str(len(manifest['lambda_files']))+' Lambda files; no credentials')
