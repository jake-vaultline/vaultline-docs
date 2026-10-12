import json
import tempfile
import unittest
from pathlib import Path
from vaultline_docs.__main__ import demo
from vaultline_docs.portal import export

class PortalExportTests(unittest.TestCase):
    def test_verified_package_exports_client_bound_base_and_preserved_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);result=demo(root/'packages')
            output=export(result['updated'],'studio','org_a','sys_a',root/'portal.json')
            packet=json.loads(output.read_text())
            self.assertEqual(packet['organizationId'],'org_a')
            self.assertEqual(packet['systemId'],'sys_a')
            self.assertEqual(len(packet['guides']),3)
            self.assertFalse(any('archive-only' in issue for issue in packet['reviewIssues']))
            self.assertIn('portal-export',(Path(result['updated'])/'portal-import.md').read_text())
            search=next(g for g in packet['guides'] if g['id']=='search-collection')
            self.assertNotIn('STUDIO-',search['baseMarkdown'])
            self.assertIn('STUDIO-',search['markdown'])
            self.assertIn('STUDIO-',search['overrides']['notes'])
            self.assertEqual(len(search['images']),3)
            self.assertIn('Remote download: Enabled',search['markdown'])
            self.assertEqual(packet['license']['spdx'],'GPL-3.0-or-later')
            self.assertIn('GNU GENERAL PUBLIC LICENSE',packet['license']['copying'])
            with self.assertRaisesRegex(ValueError,'already exists'):
                export(result['updated'],'studio','org_a','sys_a',output)
            (Path(result['updated'])/'base/search-collection.md').write_text('Tampered source guide')
            with self.assertRaisesRegex(ValueError,'integrity'):
                export(result['updated'],'studio','org_a','sys_a',root/'bad.json')
    def test_reject_invalid_portal_identity_before_reading_package(self):
        for value in ('../client','', 'client"\n'):
            with self.assertRaises(ValueError):export('absent-package','studio',value,'sys_a','output.json')

if __name__=='__main__':unittest.main()
