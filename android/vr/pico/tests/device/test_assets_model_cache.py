"""Original cached model acquisition through the existing normal Assets flow."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_assets_geometry_resource as resource_module


class AssetsModelCacheTests(resource_module.AssetsGeometryResourceTests):
    prepare_name='assets-model-cache-prepare.py'
    model_cache=True

    def entity_snapshot(self):
        result=super().entity_snapshot()
        if result['objects']:
            native=self.parser_original
            self.assertEqual(1,native['modelCacheHostEvidenceVersion']);self.assertIs(True,native['sameOriginal'])
            self.assertEqual({'picoOriginalMarker':True},native['mapping'])
            self.assertEqual('atp:/original-model/mapping.fst',native['mappingUrl'])
            self.assertEqual('atp:/original-model/textures/',native['textureBaseUrl'])
            rows=native['cacheOriginals']
            self.assertEqual(['acquired','same-extra-acquired','retired'],[row['phase'] for row in rows])
            self.assertEqual([1,1,0],[row['entries'] for row in rows]);self.assertEqual([1,1,0],[row['alive'] for row in rows])
            self.assertEqual(rows[0]['resourceId'],rows[1]['resourceId']);self.assertTrue(rows[0]['resourceId'])
            self.assertEqual(rows[0]['extraHash'],rows[1]['extraHash']);self.assertTrue(rows[0]['extraHash'].isdigit())
            self.assertEqual('',rows[-1]['resourceId']);self.assertEqual(0,rows[-1]['totalBytes'])
            self.assertTrue(all(b['observedEpochMs']>=a['observedEpochMs'] for a,b in zip(rows,rows[1:])))
            cache_events=[row for row in native['resourceObserverOriginals'] if row['extra']=='ResourceCache::getResource']
            self.assertEqual(2,len(cache_events));self.assertTrue(all(row['url']==self.resource_original['resources'][0]['url'] for row in cache_events))
        return result


if __name__=='__main__':unittest.main()
