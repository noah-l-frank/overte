"""Bounded lossless native batch transport; individual producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import secrets
import unittest
import zlib
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_snapshot as snapshot
from ios.self_tests.world_web_snapshot_fixture import SnapshotNative,packed,encoded
from ios.self_tests.world_web_source_boundary import RUN,URL


class WorldWebSnapshotTests(unittest.TestCase):
    def original(self):
        model=SnapshotNative();query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL)
        model.send(query);return model,query,model.last
    def test_one_real_transport_returns_existing_original_types_commands_clocks_and_lossless_native_body(self):
        model=SnapshotNative();sdk=model.sdk
        reader=snapshot.IOSWorldWebSnapshot(model.send,model.raw,sdk.tick,lambda:True,sdk.pid,monotonic=lambda:sdk.time,sleep=sdk.sleep)
        value=reader.read(RUN,URL);native,parts=snapshot.body(value)
        self.assertEqual(1,len(model.commands));self.assertEqual(8,len(native['calls']));self.assertIsNone(parts['document'])
        self.assertEqual(2,parts['keys']['iosWorldWebKeysVersion']);self.assertEqual(1,parts['entities']['iosCreateEntitiesVersion'])
        self.assertEqual('feature-ios-emote-world',native['queries']['world']['action'])
        native['calls'][0]['resultJSON']='{}';self.assertNotEqual('{}',snapshot.body(value)[0]['calls'][0]['resultJSON'])
        value['sequence']=0;self.assertGreater(reader.last['sequence'],0)
    def test_bound_before_materialization_and_reject_dictionary_truncation_trailing_members_and_duplicate_or_nonfinite_json(self):
        _model,_query,value=self.original();valid=value['payload'];raw=b'{"actual":1}'
        compressor=zlib.compressobj(zdict=b'actual-original-dictionary');dictionary=compressor.compress(raw)+compressor.flush()
        for fault in ('declared-bound','header-bound','truncated','trailing','dictionary','duplicate','nan','wrong-hash'):
            payload=deepcopy(valid)
            if fault=='declared-bound':payload['plainBytes']=snapshot.PLAIN_LIMIT+1
            elif fault=='header-bound':
                blob=(snapshot.PLAIN_LIMIT+1).to_bytes(4,'big')+zlib.compress(raw)
                payload.update(data=base64.b64encode(blob).decode(),compressedBytes=len(blob),compressedSha256=hashlib.sha256(blob).hexdigest())
            elif fault in ('truncated','trailing','dictionary'):
                stream=zlib.compress(raw)[:-1] if fault=='truncated' else zlib.compress(raw)+zlib.compress(b'{}') if fault=='trailing' else dictionary
                blob=len(raw).to_bytes(4,'big')+stream;payload=encoded(raw)
                payload.update(data=base64.b64encode(blob).decode(),compressedBytes=len(blob),compressedSha256=hashlib.sha256(blob).hexdigest())
            elif fault=='duplicate':payload=encoded(b'{"actual":1,"actual":2}')
            elif fault=='nan':payload=encoded(b'{"actual":NaN}')
            else:payload['plainSha256']='0'*64
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,zlib.error)):snapshot.unpack(payload)
    def test_actual_inner_nonce_capture_order_pid_privacy_and_native_identity_cannot_be_replaced_by_wanted_values(self):
        _model,query,value=self.original();snapshot.validate(value,query,42)
        for fault in ('nonce','order','pid','identity','privacy','clock','selected'):
            changed=deepcopy(value);body=snapshot.unpack(changed['payload'])
            if fault=='nonce':body['queries']['world']['commandId']='ios-'+'1'*32
            elif fault=='order':body['calls'][1],body['calls'][2]=body['calls'][2],body['calls'][1]
            elif fault=='identity':body['identity']['instance']='a'*32
            elif fault=='clock':body['calls'][0]['clockAfter']['epochMs']=1
            elif fault=='selected':body['originals']['ledgerAfter']=1
            else:
                row=next(row for row in body['calls'] if row['name']==('keys' if fault=='privacy' else 'world'));original=json.loads(row['resultJSON'])
                if fault=='privacy':original['iosWorldWebKeysVersion']=1
                else:original['processId']+=1
                row['resultJSON']=json.dumps(original)
            changed['payload']=packed(body)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):snapshot.validate(changed,query,42)
    def test_known_evicted_nonce_is_unavailable_without_any_original_recapture(self):
        model,query,first=self.original();calls=deepcopy(model.sdk.counts)
        for char in ('a','b'):model.send(dict(query,commandId='ios-'+char*32))
        after=deepcopy(model.sdk.counts);value=model.read(query)
        self.assertEqual('unavailable',value['status']);self.assertIsNone(value['payload']);self.assertEqual(after,model.sdk.counts)
        self.assertEqual(first['clockBefore'],value['clockBefore']);self.assertEqual(first['sequence'],value['sequence']);self.assertNotEqual(calls,after)
        with self.assertRaises(NativeUIError):snapshot.IOSWorldWebSnapshot._ready(value)

    def test_actual_high_entropy_native_originals_fit_bounded_lossless_wire_and_old_decoder_stays_small(self):
        model=SnapshotNative(document=True)
        for _ in range(115):
            entry=model.page.event('key-enter',dict(text=secrets.token_hex(4096),key=0,modifiers=0))
            model.page.event('signal-return',dict(entry=entry['sequence']))
        query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL)
        model.send(query);value=model.last;raw=model.raw();snapshot.validate(value,query,42)
        self.assertGreater(value['payload']['plainBytes'],2*1024*1024)
        self.assertGreater(len(raw.encode()),1048576);self.assertLess(len(raw.encode()),snapshot.LIMIT)
        self.assertLess(value['payload']['compressedBytes'],snapshot.COMPRESSED_LIMIT)
        from adapters.native_feature_observation import decode
        with self.assertRaises(NativeUIError):decode(raw)
        self.assertEqual(value,decode(raw,limit=snapshot.LIMIT))
        self.assertEqual(model.page.events,snapshot.body(value)[1]['ledgerAfter']['events'])
        self.measured_sizes=dict(plain=value['payload']['plainBytes'],compressed=value['payload']['compressedBytes'],wire=len(raw.encode()))

    def pending_originals(self,*,held=False):
        model=SnapshotNative(document=True,pending_polls=2,held_callback=held)
        query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL)
        first=model.read(query);second=model.read(query);ready=model.read(query)
        return model,query,first,second,ready

    def test_every_pending_native_original_and_actual_same_request_history_is_validated_before_terminal(self):
        model,query,first,second,ready=self.pending_originals(held=True)
        for packet in (first,second,ready):snapshot.validate(packet,query,42)
        snapshot.continued(second,first);snapshot.continued(ready,second)
        body,parts=snapshot.body(ready)
        self.assertEqual(1,model.dom_issued);self.assertTrue(model.callback_pending)
        self.assertEqual(['pending','pending','ready'],[json.loads(row['resultJSON'])['status'] for row in body['calls'] if row['name']=='document'])
        from ios.adapters.world_web_source import pending
        self.assertEqual(1,len(pending(parts['ledgerAfter'])))
        # Native completion/callback ownership is independent of cache status.
        model.pending_polls=0
        for char in ('a','b'):model.read(dict(query,commandId='ios-'+char*32))
        self.assertEqual('unavailable',model.read(query)['status']);self.assertTrue(model.callback_pending)
        for fault in ('schema','source','instance','sequence','captured','inner-nonce','prefix'):
            altered=deepcopy(ready);native=snapshot.unpack(altered['payload']);rows=[row for row in native['calls'] if row['name']=='document']
            old=json.loads(rows[0]['resultJSON']);current=json.loads(rows[1]['resultJSON'])
            if fault=='schema':old['iosWorldWebDOMNativeVersion']=True
            elif fault=='source':old['source']={'unexpected':'wanted-dom'}
            elif fault=='instance':current['instance']='1'*32
            elif fault=='sequence':current['sequence']+=1
            elif fault=='captured':current['capturedEpochMs']+=1
            elif fault=='inner-nonce':current['commandId']='ios-'+'1'*32
            else:rows[0]['clockBefore']['epochMs']+=1
            rows[0]['resultJSON']=json.dumps(old);rows[1]['resultJSON']=json.dumps(current);altered['payload']=packed(native)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                snapshot.validate(altered,query,42);snapshot.continued(altered,second)

    def test_reader_retains_pending_original_across_polls_and_rejects_native_outer_restart_or_retime(self):
        for fault in (None,'instance','sequence','start','retime','erased-prefix'):
            model=SnapshotNative(document=True,pending_polls=2);sdk=model.sdk;observed=[]
            def raw():
                value=json.loads(model.raw());observed.append(deepcopy(value))
                if len(observed)==2 and fault is not None:
                    body=snapshot.unpack(value['payload'])
                    if fault=='instance':value['instance']='2'*32
                    elif fault=='sequence':value['sequence']+=1
                    elif fault=='start':value['clockBefore']['epochMs']-=1;value['clockBefore']['monotonicMs']-=1
                    elif fault=='retime':
                        body=snapshot.unpack(observed[0]['payload']);value=deepcopy(observed[0]);value['clockAfter']['epochMs']+=1;value['clockAfter']['monotonicMs']+=1
                    else:
                        body['calls'].pop(1)
                        for index,row in enumerate(body['calls'],1):row['ordinal']=index
                        body['originals']['document']-=1
                    body['identity']={key:deepcopy(value[key]) for key in snapshot.IDENTITY};value['payload']=packed(body)
                return json.dumps(value)
            reader=snapshot.IOSWorldWebSnapshot(model.send,raw,sdk.tick,lambda:True,sdk.pid,monotonic=lambda:sdk.time,sleep=sdk.sleep)
            if fault is None:
                value=reader.read(RUN,URL);self.assertEqual('ready',value['status']);self.assertEqual(1,model.dom_issued)
                self.assertEqual(2,len(snapshot.unpack(reader._pending_originals[value['commandId']]['payload'])['calls'])-1)
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,URL)
                self.assertEqual(1,len(model.commands));self.assertIsNone(reader.last)
                self.assertEqual(observed[0],reader._pending_originals[observed[0]['commandId']])

    def test_actual_active_LedgerBefore_cannot_be_presented_as_no_document_and_completeness_cannot_resurrect(self):
        _model,query,first,second,ready=self.pending_originals()
        snapshot.validate(ready,query,42)
        changed=deepcopy(ready);native=snapshot.unpack(changed['payload'])
        native['calls']=[row for row in native['calls'] if row['name']!='document']
        native['queries']['document']=native['originals']['document']=None
        for index,row in enumerate(native['calls'],1):row['ordinal']=index;native['originals'][row['name']]=index
        changed['payload']=packed(native)
        with self.assertRaises(NativeUIError):snapshot.validate(changed,query,42)
        incomplete=deepcopy(first);incomplete['complete']=False;snapshot.validate(incomplete,query,42)
        with self.assertRaises(NativeUIError):snapshot.continued(second,incomplete)
        still_incomplete=deepcopy(second);still_incomplete['complete']=False;snapshot.continued(still_incomplete,incomplete)

    def test_noncanonical_base64_pad_bits_are_rejected_even_when_the_decoded_compressed_bytes_match(self):
        # Python's validate=True alone accepts alternate nonzero padding bits.
        raw=b'{}'
        while not encoded(raw)['data'].endswith('='):raw+=b' '
        payload=encoded(raw);alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        index=len(payload['data'].rstrip('='))-1;char=payload['data'][index];changed=alphabet[alphabet.index(char)+1]
        payload['data']=payload['data'][:index]+changed+payload['data'][index+1:]
        self.assertEqual(base64.b64decode(encoded(raw)['data']),base64.b64decode(payload['data']))
        with self.assertRaises(NativeUIError):snapshot.unpack(payload)


if __name__=='__main__':unittest.main()
