"""Original Baker CPU graph follows the actual original ModelCache download."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_assets_model_cache as cache_module


class AssetsModelBakerTests(cache_module.AssetsModelCacheTests):
    prepare_name='assets-model-baker-prepare.py'
    model_baker=True

    def entity_snapshot(self):
        result=super().entity_snapshot()
        if result['objects']:
            native=self.parser_original
            self.assertEqual(1,native['modelBakerHostEvidenceVersion'])
            self.assertFalse(native['bakerGraphAlive'] or native['bakerInputAlive'])
            self.assertEqual(0,native['bakerBuffersRemaining'])
            rows=native['bakerOriginals']
            if self.indexed:
                self.assertEqual(['constructed','run-enter','run-exit','destructor-enter'],[row['phase'] for row in rows])
                self.assertEqual(1,len({row['graphId'] for row in rows}));self.assertNotEqual('0',rows[0]['graphId'])
                self.assertEqual(1,len({row['id'] for row in rows}));self.assertEqual(1,len({row['thread'] for row in rows}))
                self.assertTrue(all(row['graphAlive'] and row['inputAlive'] for row in rows))
                self.assertEqual(0,rows[0]['bufferCount']);self.assertGreater(rows[2]['bufferCount'],0)
                self.assertTrue(all(b['observedEpochMs']>=a['observedEpochMs'] for a,b in zip(rows,rows[1:])))
                before=native['parsedHandoff'];processed=native['bakerHandoff']
                self.assertEqual(before['id'],processed['id']);self.assertNotEqual('0',before['id'])
                self.assertEqual(before['url'],processed['url']);self.assertEqual(before['joints'],processed['joints'])
                self.assertEqual(before['materials'],processed['materials']);self.assertEqual(before['textures'],processed['textures'])
                self.assertEqual(0,processed['errors']);self.assertEqual(1,len(processed['meshes']))
                mesh=processed['meshes'][0]
                self.assertTrue(mesh['graphicsMeshExists'] and mesh['skinningDataValid'])
                self.assertEqual([[-.5,0,0],[.5,0,0],[0,1,0]],mesh['bufferVertices'])
                self.assertEqual([0,1,2],sorted(mesh['bufferIndices']));self.assertEqual(1,mesh['bufferParts'])
                self.assertEqual(3,len(mesh['normals']));self.assertEqual(3,len(mesh['tangents']))
            else:
                self.assertEqual([],rows);self.assertEqual({},native['bakerHandoff'])
        return result

    def exercise_cancel_home(self,baseline):
        counts,raw=super().exercise_cancel_home(baseline)
        # The processed HFM is a separate observed original, not an alias of the
        # pre-Baker handoff already admitted by the inherited source envelope.
        if self.parser_original['bakerHandoff']:counts+=1
        return counts,raw


if __name__=='__main__':unittest.main()
