"""Actual pinned Script executes into indexed V8 caller and page-reply joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_api_clock import scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters import world_web_echoes as echoes,web_script_emissions as native
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebEmitterChainTests(unittest.TestCase):
    def test_actual_script_vm_indexed_compiled_stack_and_native_sinks_are_required_beyond_work_interval(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close);sdk,source=whole.sdk,whole.source;actions=whole.actions()
        with scope(lambda:sdk.time):actions.act(sdk.activate('open',{}))
        entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,source,entry['before'],entry['after']);owned=lease.packet()
        entity=owned['returned']['returned']['entityId'];actions.inputs.entity=entity
        with scope(lambda:sdk.time):actions.act(sdk.activate('submit',{}))
        raw=source.frame(source.state['records'][-1])['originals'];args=(raw['ledgerAfter'],raw['document'],raw['work'],owned['files'],owned['directory'],entity)
        value=raw['emissions'];result=echoes.chain(*args,emitters=value)
        self.assertEqual(1,len(result['echoes']));self.assertEqual(7,len(value['calls'][0]['caller']['emitStack']['frames']))
        self.assertEqual(value['calls'][0]['id'],value['sinks'][0]['call']);self.assertEqual(2,len(value['sinks']))
        original=deepcopy(value)
        for fault in ('unknown-caller','different-engine','different-compiled-source','different-callsite','missing-frame','unknown-native-sink'):
            changed=deepcopy(value);caller=changed['calls'][0]['caller']
            if fault=='unknown-caller':changed['calls'][0]['caller']=None
            elif fault=='different-engine':caller['manager']['instance']='f'*32
            elif fault=='different-compiled-source':
                for frame in caller['emitStack']['frames']:frame['compiled']['sha256']='0'*64
            elif fault=='different-callsite':caller['emitStack']['frames'][0]['column']+=1
            elif fault=='missing-frame':caller['emitStack']['frames'].pop()
            else:changed['sinks'][0]['call']=None
            native.original(changed)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):echoes.chain(*args,emitters=changed)
        self.assertEqual(original,value)


if __name__=='__main__':unittest.main()
