"""Inventory declarations and notice hashes; not a license compatibility verdict."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from zipfile import ZipFile

repo = Path(__file__).resolve().parents[2]
lumi = repo / 'h5p_mcp/lumi'
provenance = json.loads((lumi / 'provenance.json').read_text())
archive_path = lumi / provenance['archive']
assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == provenance['sha256']
with tarfile.open(archive_path) as archive:
    source = {member.name:hashlib.sha256(archive.extractfile(member).read()).hexdigest()
              for member in archive.getmembers() if member.isfile() and
              (member.name.startswith('package/src/') or 'license' in member.name.lower()
               or 'tsconfig' in member.name or member.name == 'package/package.json')}
lock = json.loads((lumi / 'package-lock.json').read_text())
fixture_lock = json.loads((repo / 'tests/fixtures/libraries.lock.json').read_text())
fixture_path = repo / 'tests/fixtures/libraries.zip'
assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == fixture_lock['sha256']
with ZipFile(fixture_path) as archive:
    notices = {name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
               if not name.endswith('/') and any(word in name.lower() for word in ('license','copying','notice'))}
report = {'status':'inventory_only', 'root_license':'Apache-2.0', 'lumi':provenance,
          'lumi_source_and_notices':source,
          'runtime_packages':{name:{key:value.get(key) for key in ('version','license','integrity')}
                              for name,value in lock['packages'].items() if name},
          'h5p_libraries':fixture_lock['libraries'], 'h5p_notice_hashes':notices,
          'distribution_gate':{'owner':'repository owner', 'status':'pending',
            'requires':['resolve missing declarations using actual notices',
                        'review corresponding source and build instructions',
                        'review combined distribution and preserve third-party notices']}}
Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
