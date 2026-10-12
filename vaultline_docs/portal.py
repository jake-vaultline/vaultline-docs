"""Portable Portal import data. No credentials, network writes or automatic publication."""
import base64
import json
import re
from pathlib import Path
from .source import check_text, digest, safe_path
from scripts.utils.markdown import extract_frontmatter


def export(package, deployment_id, organization_id, system_id, output):
    for identifier in (organization_id,system_id):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}',identifier):
            raise ValueError('Portal organization/system identifiers are required')
    root=Path(package).resolve()
    metadata=json.loads((root/'package.json').read_text())
    deployment=next((d for d in metadata['deployments'] if d['id']==deployment_id),None)
    if not deployment:
        raise ValueError('Deployment is not in this package')
    if metadata.get('blocked_guides'):
        raise ValueError('Resolve missing source evidence before importing a package')
    hashes=json.loads((root/'checksums.json').read_text())
    for name,expected in hashes.items():
        path=(root/safe_path(name)).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes())!=expected:
            raise ValueError('Documentation package integrity check failed')
    if not (root/'base/guide-catalog.json').is_file():
        raise ValueError('Regenerate this package with the Portal-capable Vaultline Docs version; the guide capability catalogue is missing')
    catalogue=json.loads((root/'base/guide-catalog.json').read_text())
    home=root/'deployments'/deployment_id
    manifest=json.loads((home/'deployment.json').read_text())
    guides=[]
    for identifier in deployment['included']:
        frontmatter,markdown=extract_frontmatter((home/(identifier+'.md')).read_text())
        _,base=extract_frontmatter((root/'base'/(identifier+'.md')).read_text())
        if frontmatter['source_revision']!=metadata['source_revision'] or frontmatter['deployment_version']!=manifest['version']:
            raise ValueError('Guide identity differs from package')
        images=[]
        for name in re.findall(r'!\[[^\]]*\]\(screenshots/([a-z0-9-]+\.png)\)',markdown):
            bytes=(home/'screenshots'/name).read_bytes()
            if len(bytes)>800_000:
                raise ValueError('Screenshot exceeds Portal image limit')
            images.append({'name':name,'sha256':digest(bytes),'base64':base64.b64encode(bytes).decode()})
        guide={'id':identifier,'title':next(line[2:] for line in markdown.splitlines() if line.startswith('# ')),
               'modules':catalogue[identifier]['modules'],'requires':catalogue[identifier]['requires'],
               'baseMarkdown':base,'markdown':markdown,'overrides':manifest.get('overrides',{}).get(identifier,{}),
               'captureStatus':frontmatter['capture_status'],'images':images}
        check_text(json.dumps({k:v for k,v in guide.items() if k!='images'}))
        guides.append(guide)
    report=json.loads((root/'review.json').read_text())
    packet={'schemaVersion':1,'organizationId':organization_id,'systemId':system_id,'packageId':metadata['package_id'],
            'sourceRevision':metadata['source_revision'],'generatedAt':metadata['generated_at'],
            'deployment':{'id':manifest['id'],'product':manifest['product'],'version':manifest['version'],'platform':manifest['platform'],
                          'modules':manifest['modules'],'config':manifest.get('config',{}),'manifestSha256':deployment['manifest_sha256'],'synthetic':manifest.get('synthetic',False)},
            'guides':guides,'reviewIssues':[json.dumps(item,sort_keys=True)[:500] for item in report.get('review_required',[])],
            'releaseNotes':(root/'release-notes.md').read_text(),
            'license':{'spdx':'GPL-3.0-or-later','notice':(root/'NOTICE').read_text(),'copying':(root/'COPYING').read_text(),'sourceUrl':'https://github.com/jake-vaultline/vaultline-docs'}}
    encoded=json.dumps(packet,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    if len(encoded)>3_200_000:
        raise ValueError('Portal import exceeds 3.2 MB; reduce screenshot sizes before exporting the complete system guide set')
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        raise ValueError('Portal import export already exists; use a fresh output filename')
    output.write_bytes(encoded)
    return output
