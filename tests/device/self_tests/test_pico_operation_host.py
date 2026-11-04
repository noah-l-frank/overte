"""Actual stdio child boundaries with declared candidate/native-free factories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import json
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from adapter_operation_host import PicoOperationHost,PinnedFile,scoped_host,ACTIVE
from adapters.pico4.operation_protocol import STRIPPED_ENV,dto_bytes,decode,request,timeout_for,REQUEST_LIMIT

WORKER=Path(__file__).with_name('pico_operation_host_worker.py').resolve()


class OriginalOperationFailureTests(unittest.TestCase):
    def record(self,error):
        from adapters.pico4.operation_host import retain_original_failure
        source,destination=os.pipe()
        try:
            self.assertTrue(retain_original_failure(error,destination))
            os.close(destination);destination=-1
            raw=os.read(source,4097)
            self.assertLessEqual(len(raw),4096)
            return raw,json.loads(raw)
        finally:
            os.close(source)
            if destination>=0:os.close(destination)

    def test_original_from_none_context_survives_without_messages_or_locals(self):
        failures=[]
        try:
            try:raise KeyError('PRIVATE_SELECTOR_AND_POLICY_CANARY')
            except KeyError:raise ValueError('PRIVATE_MESSAGE_CANARY') from None
        except ValueError as error:failures.append(error)
        original=failures[0];context=original.__context__
        raw,value=self.record(original)
        self.assertNotIn(b'PRIVATE_',raw)
        self.assertEqual(['ValueError','KeyError'],[row['type'] for row in value['contexts']])
        self.assertTrue(all(row['frames'] for row in value['contexts']))
        self.assertIs(context,original.__context__);self.assertTrue(original.__suppress_context__)
        with self.assertRaises(ValueError) as raised:raise original
        self.assertIs(original,raised.exception)

    def test_context_cycle_and_long_chain_are_bounded_without_rewriting_them(self):
        first=ValueError('private first');second=RuntimeError('private second')
        first.__context__=second;second.__context__=first
        _raw,value=self.record(first)
        self.assertTrue(value['truncated']);self.assertEqual(2,len(value['contexts']))
        self.assertIs(second,first.__context__);self.assertIs(first,second.__context__)
        current=None
        for _ in range(40):
            error=ValueError('private chain');error.__context__=current;current=error
        _raw,value=self.record(current)
        self.assertTrue(value['truncated']);self.assertEqual(4,len(value['contexts']))

    def test_closed_diagnostic_pipe_cannot_replace_the_original_failure(self):
        from adapters.pico4.operation_host import retain_original_failure
        source,destination=os.pipe();os.close(source);os.close(destination)
        original=ValueError('Original failure')
        with self.assertRaises(ValueError) as raised:
            try:raise original
            except ValueError as error:
                self.assertFalse(retain_original_failure(error,destination))
                raise
        self.assertIs(original,raised.exception)

    def test_actual_deep_traceback_stops_at_the_frame_bound(self):
        def descend(remaining):
            if remaining:descend(remaining-1)
            else:raise RuntimeError('Private deep failure')
        errors=[]
        try:descend(300)
        except RuntimeError as error:errors.append(error)
        _raw,value=self.record(errors[0])
        self.assertTrue(value['truncated'])
        self.assertEqual(4,len(value['contexts'][0]['frames']))


class PicoOperationHostTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='pico-stdio-host-')
        if os.environ.get('OVERTE_OPERATION_HOST_EVIDENCE')=='1':temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.manifest=self.root/'adapter.json'
        self.manifest.write_text(json.dumps(dict(schemaVersion=1,command=[str(WORKER)])));self.manifest.chmod(0o600)
        self.hosts=[];self.addCleanup(self.stop)
    def stop(self):
        for host in self.hosts:
            if host.process is not None and host.process.returncode is None:
                try:os.kill(host.process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:_,status=os.waitpid(host.process.pid,0);host.process.returncode=os.waitstatus_to_exitcode(status)
                except ChildProcessError:pass
    @contextmanager
    def model(self,fault='normal'):
        path=self.root/fault;path.mkdir(mode=0o700);trace=self.root/(fault+'.jsonl')
        prefix=[sys.executable,str(WORKER),'--fault',fault,'--trace',str(trace)]
        with patch('adapter_operation_host.pico_command',return_value=prefix):
            host=PicoOperationHost(self.manifest,'explicit-host-model',path);self.hosts.append(host);yield host
    def call(self,host,args=None):return host.invoke(self.manifest,'explicit-host-model','app.process',args)
    def trace(self,fault):
        path=self.root/(fault+'.jsonl');return [] if not path.exists() else [json.loads(row)['kind'] for row in path.read_text().splitlines()]

    def test_actual_same_cli_factory_adapter_parent_and_zero_exit_across_operations(self):
        with self.model() as host:
            first=self.call(host);second=self.call(host)
            self.assertEqual(1,first['factories']);self.assertEqual((1,2),(first['calls'],second['calls']))
            self.assertEqual(first['identity'],second['identity']);self.assertNotEqual(str(os.getpid()),first['identity'])
            self.assertEqual(['factory','dispatch','dispatch'],self.trace('normal'))
            pid=host.process.pid;host.close();self.assertEqual(0,host.wait_status);self.assertFalse(Path('/proc',str(pid)).exists())
            self.assertEqual('closed',host.archive.state['phase']);self.assertFalse(any('cleanup' in value for value in self.trace('normal')))
    def test_all_six_policy_reader_control_environment_keys_are_stripped(self):
        with patch.dict(os.environ,{key:'private-test-value' for key in STRIPPED_ENV}),self.model() as host:
            value=self.call(host);self.assertEqual(sorted(STRIPPED_ENV),sorted(value['absentKeys']));host.close()
    def test_deadline_includes_first_factory_and_later_dispatch_no_replay_or_second_host(self):
        for fault in ('factory-timeout','timeout'):
            with self.subTest(fault=fault),self.model(fault) as host,patch('adapter_operation_host.timeout_for',return_value=.12):
                started=time.monotonic()
                with self.assertRaises(RuntimeError):self.call(host)
                self.assertLess(time.monotonic()-started,1.)
                count=self.trace(fault)
                self.assertEqual(1,count.count('factory'))
                self.assertEqual(0 if fault=='factory-timeout' else 1,count.count('dispatch'))
                with self.assertRaises(RuntimeError):self.call(host)
                self.assertEqual(count,self.trace(fault));self.assertTrue(host.failed);host.abort()
    def test_full_invalid_and_partial_raw_are_durable_before_decode_and_no_next_request(self):
        for fault,expected in [('invalid-json',b'{"broken":]\n'),('partial',b'{"broken":'),('wrong-id',None)]:
            with self.subTest(fault=fault),self.model(fault) as host:
                with self.assertRaises(RuntimeError):self.call(host)
                raw=b''.join(path.read_bytes() for path in sorted(host.artifacts.glob('response-*.bin')))
                if expected is not None:self.assertEqual(expected,raw)
                else:self.assertIn(b'00000000000000000000000000000000',raw)
                with self.assertRaises(RuntimeError):self.call(host)
                self.assertEqual(1,self.trace(fault).count('dispatch'));host.abort()
    def test_actual_four_mib_literal_retained_in_bounded_binary_parts_before_parser(self):
        with self.model('raw-cap') as host:
            with self.assertRaises(RuntimeError):self.call(host)
            parts=sorted(host.artifacts.glob('response-*.bin'));self.assertEqual(64,len(parts))
            self.assertEqual(b'\0'*(4*1024*1024),b''.join(path.read_bytes() for path in parts));self.assertTrue(all(path.stat().st_size<=65536 for path in parts))
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('raw-cap').count('dispatch'));host.abort()
    def test_bounded_stderr_draining_cannot_deadlock_or_authorize_another_dispatch(self):
        with self.model('stderr') as host:
            started=time.monotonic()
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertLess(time.monotonic()-started,2.)
            self.assertEqual(65536,sum(path.stat().st_size for path in host.artifacts.glob('stderr-*.bin')))
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('stderr').count('dispatch'));host.abort()
    def test_strict_dto_and_policy_are_rejected_before_spawn_or_codec(self):
        class Dict(dict):pass
        for bad in ({'expectedFacts':{}},{'nested':{'policy':'not-sent'}},{'value':(1,)},Dict(),{1:'key'}, {'raw':'\0'*(4*1024*1024)}):
            with self.subTest(value=type(bad).__name__),self.model(str(len(self.hosts))) as host:
                with patch('adapter_operation_host.subprocess.Popen',side_effect=AssertionError('Unadmitted process')),self.assertRaises(RuntimeError):self.call(host,bad)
                self.assertIsNone(host.process)
        with self.assertRaises(ValueError):decode(b'{"x":1,"x":2}\n',REQUEST_LIMIT)
        self.assertEqual((60,120,240),(timeout_for('app.process'),timeout_for('snapshot.files'),timeout_for('app.install')))
    def test_same_bytes_replaced_manifest_and_same_inode_recycled_ofd_are_never_adopted(self):
        for fault in ('same-bytes','same-inode-ofd'):
            with self.subTest(fault=fault),self.model(fault) as host:
                self.call(host);pin=host.pins[0];foreign=None
                if fault=='same-bytes':
                    other=self.root/'replacement';other.write_bytes(self.manifest.read_bytes());other.chmod(0o600);os.replace(other,self.manifest)
                else:
                    foreign=os.open(self.manifest,os.O_RDONLY);os.dup2(foreign,pin.owner.fd)
                with self.assertRaises(RuntimeError):self.call(host)
                with self.assertRaises(RuntimeError):host.close()
                if foreign is not None:
                    os.fstat(pin.owner.fd);os.close(foreign)
                self.assertEqual(1,self.trace(fault).count('dispatch'))
    def test_namespace_env_cwd_and_args_mutations_poison_original_scope(self):
        with self.model('mutate-args') as host:
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('mutate-args').count('dispatch'))
        with self.model('env') as host:
            self.call(host)
            with patch.dict(os.environ,{'UNRELATED_HOST_SCOPE_CHANGE':'1'}),self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('env').count('dispatch'))

    def test_actual_parent_death_refuses_idle_and_factory_worker_and_kernel_reaps_original_child(self):
        libc=ctypes.CDLL(None,use_errno=True);old=ctypes.c_int()
        self.assertEqual(0,libc.prctl(37,ctypes.byref(old),0,0,0))
        self.assertEqual(0,libc.prctl(36,1,0,0,0))
        try:
            for fault in ('normal','factory-timeout'):
                trace=self.root/('death-'+fault+'.jsonl')
                controller=subprocess.Popen([sys.executable,str(WORKER),'--parent-controller','--fault',fault,'--trace',str(trace)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                output,_=controller.communicate(timeout=10);self.assertEqual(0,controller.returncode);pid=int(output)
                deadline=time.monotonic()+5
                while True:
                    observed,status=os.waitpid(pid,os.WNOHANG)
                    if observed:break
                    self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                self.assertNotEqual(0,status);self.assertFalse(Path('/proc',str(pid)).exists())
                if fault=='factory-timeout':self.assertNotIn('dispatch',trace.read_text())
        finally:self.assertEqual(0,libc.prctl(36,old.value,0,0,0))

    def test_real_partial_pipe_delivery_is_sticky_and_never_retries_the_request(self):
        with self.model('partial-send') as host:
            original=os.write;deliveries=[]
            def partial(descriptor,raw):
                if host.pipes and descriptor==host.pipes[0].fd:
                    if deliveries:raise OSError('Explicit uncertain partial pipe write')
                    deliveries.append(raw[:1]);return original(descriptor,raw[:1])
                return original(descriptor,raw)
            with patch('adapter_operation_host.os.write',side_effect=partial),self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual([b'{'],deliveries);self.assertEqual(1,host.sent_bytes)
            self.assertTrue(list(host.artifacts.glob('request-*.bin')))
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertNotIn('dispatch',self.trace('partial-send'));host.abort()

    def test_unknown_before_and_after_reply_receipt_cas_preserve_raw_without_reparse_or_resend(self):
        from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
        for where in ('before','after'):
            with self.subTest(where=where),self.model('cas-'+where) as host:
                write=LifecycleProcessFile.write
                def uncertain(owner,value,previous):
                    if value.get('phase')=='ready':
                        if where=='after':write(owner,value,previous)
                        raise OSError('Explicit unknown original receipt CAS')
                    return write(owner,value,previous)
                with patch.object(LifecycleProcessFile,'write',new=uncertain),patch('adapter_operation_host.decode',side_effect=AssertionError('Parser before immutable receipt')) as decoder,self.assertRaises(RuntimeError):self.call(host)
                decoder.assert_not_called()
                self.assertTrue(host.acquired_response.endswith(b'\n'))
                raw=b''.join(p.read_bytes() for p in sorted(host.artifacts.glob('response-*.bin')))
                self.assertEqual(bytes(host.acquired_response),raw)
                with self.assertRaises(RuntimeError):self.call(host)
                self.assertEqual(1,self.trace('cas-'+where).count('dispatch'));host.abort()

    def test_next_full_response_is_reserved_before_send_against_actual_retained_bytes(self):
        with self.model('large') as host:
            for _ in range(4):self.assertEqual(3*1024*1024,len(self.call(host)['raw']))
            before=self.trace('large')
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(before,self.trace('large'));self.assertEqual(4,before.count('dispatch'))
            self.assertLess(sum(p.stat().st_size for p in host.artifacts.iterdir()),16*1024*1024)
            self.assertLess(len(list(host.artifacts.iterdir())),512);host.abort()

    def test_unsolicited_later_original_is_retained_before_next_adapter_dispatch(self):
        with self.model('unsolicited') as host:
            self.call(host);time.sleep(.1)
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(0,host.sent_bytes);self.assertEqual(1,self.trace('unsolicited').count('dispatch'))
            self.assertEqual(b'unsolicited\n',bytes(host.acquired_response));host.abort()

    def test_shared_adapter_context_reuses_host_and_default_route_keeps_original_deadlines(self):
        import adapter_client
        for op,seconds in [('app.process',60),('permission.snapshot',120),('permission.set',120),('snapshot.files',120),('app.install',240),('app.upgrade',240)]:
            result=subprocess.CompletedProcess([],0,stdout='{}',stderr='')
            with patch.object(adapter_client,'load_command',return_value=['declared-model']),patch.object(adapter_client.subprocess,'run',return_value=result) as run:
                self.assertEqual({},adapter_client.invoke(self.manifest,'target',op,{}));self.assertEqual(seconds,run.call_args.kwargs['timeout'])
                self.assertTrue(all(key not in run.call_args.kwargs['env'] for key in STRIPPED_ENV))
        prefix=[sys.executable,str(WORKER),'--fault','context','--trace',str(self.root/'context.jsonl')]
        artifacts=self.root/'context';artifacts.mkdir(mode=0o700)
        with patch('adapter_operation_host.pico_command',return_value=prefix),adapter_client.operation_host(self.manifest,'explicit-host-model',artifacts) as owner:
            self.hosts.append(owner)
            first=adapter_client.invoke(self.manifest,'explicit-host-model','app.process',{})
            second=adapter_client.invoke(self.manifest,'explicit-host-model','app.process',{})
            self.assertEqual(first['identity'],second['identity']);self.assertEqual(2,second['calls'])
            with self.assertRaises(ValueError):
                with adapter_client.operation_host(self.manifest,'explicit-host-model',artifacts):pass
        self.assertIsNone(ACTIVE.get());self.assertEqual(0,owner.wait_status)

    def test_existing_session_and_module_helpers_share_only_the_explicit_context(self):
        settings={'OVERTE_DEVICE_ADAPTER_MANIFEST':str(self.manifest),'OVERTE_DEVICE_TARGET_SELECTOR':'explicit-host-model','OVERTE_DEVICE_ARTIFACT_DIR':str(self.root)}
        with patch.dict(os.environ,settings):
            from overte_session import OverteSession
            import module_support
            artifacts=self.root/'session';artifacts.mkdir(mode=0o700)
            prefix=[sys.executable,str(WORKER),'--fault','session','--trace',str(self.root/'session.jsonl')]
            with patch.object(module_support,'MANIFEST',self.manifest),patch.object(module_support,'TARGET','explicit-host-model'),patch('adapter_operation_host.pico_command',return_value=prefix):
                session=OverteSession()
                with session.operation_host(artifacts) as owner:
                    self.hosts.append(owner);first=session._invoke('app.process',{});second=module_support.operation('app.process',{})
                    self.assertEqual(first['identity'],second['identity']);self.assertEqual(2,second['calls'])
                self.assertEqual(0,owner.wait_status)

    def test_private_entry_identical_replacement_and_raw_orphan_refuse_before_next_dispatch(self):
        with patch.dict(os.environ,{'PYTHONPATH':str(WORKER.parents[1])}):
            entry=self.root/'private-worker.py';entry.write_bytes(WORKER.read_bytes());entry.chmod(0o600)
            with self.model('entry') as host:
                prefix=[sys.executable,str(entry),'--fault','entry','--trace',str(self.root/'entry.jsonl')]
                with patch('adapter_operation_host.pico_command',return_value=prefix):self.call(host)
                replacement=self.root/'new-entry';replacement.write_bytes(entry.read_bytes());replacement.chmod(0o600);os.replace(replacement,entry)
                with self.assertRaises(RuntimeError):self.call(host)
                self.assertEqual(1,self.trace('entry').count('dispatch'))
        with self.model('orphan') as host:
            self.call(host);(host.artifacts/'foreign-part.bin').write_bytes(b'not an admitted original')
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('orphan').count('dispatch'));host.abort()

    def test_same_inode_recycled_directory_and_pipe_ofds_never_close_foreign_handles(self):
        for what in ('directory','pipe'):
            with self.subTest(what=what),self.model(what) as host:
                self.call(host)
                if what=='directory':
                    descriptor=host.archive.directory.fd;foreign=os.open(host.artifacts,os.O_RDONLY|os.O_DIRECTORY)
                else:
                    descriptor=host.pipes[1].fd;foreign=os.open('/proc/self/fd/'+str(descriptor),os.O_RDONLY|os.O_NONBLOCK)
                os.dup2(foreign,descriptor)
                with self.assertRaises(RuntimeError):self.call(host)
                with self.assertRaises(RuntimeError):host.close()
                host.abort();os.fstat(descriptor);os.close(foreign)
                self.assertEqual(1,self.trace(what).count('dispatch'))

    def test_changed_cwd_and_target_or_manifest_never_start_a_replacement_scope(self):
        for what in ('cwd','target','manifest'):
            with self.subTest(what=what),self.model(what) as host:
                self.call(host);cwd=os.getcwd()
                try:
                    if what=='cwd':os.chdir(self.root)
                    with self.assertRaises(RuntimeError):host.invoke(self.manifest if what!='manifest' else self.root/'foreign.json','explicit-host-model' if what!='target' else 'foreign-target','app.process',{})
                finally:os.chdir(cwd)
                self.assertEqual(1,self.trace(what).count('dispatch'));host.abort()

    def test_actual_default_client_still_starts_a_distinct_phone_model_process_per_operation(self):
        import adapter_client
        trace=self.root/'legacy-phone.jsonl'
        self.manifest.write_text(json.dumps(dict(schemaVersion=1,command=[str(WORKER),'--fault','legacy-phone','--trace',str(trace)])))
        first=adapter_client.invoke(self.manifest,'explicit-host-model','app.process',{})
        second=adapter_client.invoke(self.manifest,'explicit-host-model','app.process',{})
        self.assertNotEqual(first['identity'],second['identity']);self.assertEqual((1,1),(first['factories'],second['factories']))
        self.assertEqual(2,self.trace('legacy-phone').count('factory'))

    def test_existing_phone_cli_cannot_enter_pico_host_mode_or_construct_an_adapter(self):
        from adapters.android import adapter
        from types import SimpleNamespace
        values=SimpleNamespace(kind='phone',native_binding=False,action='operation-host',target='model',operation=None,arguments='{}')
        with patch.object(adapter,'cli',return_value=(values,None)),patch.object(adapter,'create_adapter',side_effect=AssertionError('Phone host factory')),self.assertRaises(ValueError):adapter.main([])

    def test_explicit_close_does_not_adopt_a_previous_archive_as_a_new_host(self):
        with self.model('cold') as host:
            self.call(host);host.close();before={p.name:p.read_bytes() for p in host.artifacts.iterdir()}
            cold=PicoOperationHost(self.manifest,'explicit-host-model',host.artifacts)
            with patch('adapter_operation_host.subprocess.Popen',side_effect=AssertionError('Cold host adoption')),self.assertRaises(RuntimeError):self.call(cold)
            self.assertEqual(before,{p.name:p.read_bytes() for p in host.artifacts.iterdir()})

    def test_actual_repeated_request_identifier_is_not_dispatched_twice(self):
        import uuid
        trace=self.root/'repeated.jsonl';environment={k:v for k,v in os.environ.items() if k not in STRIPPED_ENV}
        process=subprocess.Popen([sys.executable,str(WORKER),'--fault','repeated','--trace',str(trace)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
        raw=dto_bytes(dict(picoOperationRequestVersion=1,requestId=uuid.uuid4().hex,operation='app.process',arguments={},deadlineMonotonic=time.monotonic()+5),REQUEST_LIMIT)
        process.stdin.write(raw);process.stdin.flush();self.assertTrue(process.stdout.readline().endswith(b'\n'))
        process.communicate(input=raw,timeout=5);self.assertNotEqual(0,process.returncode)
        self.assertEqual(1,self.trace('repeated').count('dispatch'))

    def test_acquired_raw_survives_archive_write_refusal_without_parser_or_next_query(self):
        from adapters.pico4.operation_archive import OperationArchive
        append=OperationArchive.append
        with self.model('archive-write') as host:
            def refused(owner,name,raw):
                if name.startswith('response-'):raise OSError('Explicit original archival write refusal')
                return append(owner,name,raw)
            with patch.object(OperationArchive,'append',new=refused),patch('adapter_operation_host.decode',side_effect=AssertionError('No parser before durable raw')) as parser,self.assertRaises(RuntimeError):self.call(host)
            parser.assert_not_called();self.assertTrue(host.acquired_response);self.assertTrue(host.pending_request)
            self.assertFalse(list(host.artifacts.glob('response-*.bin')))
            with self.assertRaises(RuntimeError):self.call(host)
            self.assertEqual(1,self.trace('archive-write').count('dispatch'));host.abort()

    def test_scope_abort_keeps_original_error_and_does_not_close_recycled_source_fd(self):
        prefix=[sys.executable,str(WORKER),'--fault','abort-fd','--trace',str(self.root/'abort-fd.jsonl')]
        artifacts=self.root/'abort-fd';artifacts.mkdir(mode=0o700);foreign=None
        with patch('adapter_operation_host.pico_command',return_value=prefix),self.assertRaisesRegex(RuntimeError,'no replay'):
            with scoped_host(self.manifest,'explicit-host-model',artifacts) as host:
                self.hosts.append(host);self.call(host)
                descriptor=host.pins[0].owner.fd;foreign=os.open(self.manifest,os.O_RDONLY);os.dup2(foreign,descriptor)
                self.call(host)
        os.fstat(descriptor);os.close(foreign);self.assertIsNone(ACTIVE.get())
        self.assertEqual(1,self.trace('abort-fd').count('dispatch'))

    def original_archive(self):
        from adapters.pico4.operation_archive import OperationArchive
        path=self.root/'open-originals';path.mkdir(mode=0o700)
        archive=OperationArchive(path,{'fixture':'original-append'})
        def close_handles():
            for row in archive.writers.values():row[0].close()
            archive.journal.close_host();archive.directory.close()
        self.addCleanup(close_handles)
        return archive

    def test_same_original_append_cursor_cannot_overwrite_prior_raw_bytes(self):
        archive=self.original_archive();name='returned.bin';first=b'first original\n';second=b'second original\n'
        archive.append(name,first);owner=archive.writers[name][0]
        # This is still the exact original OFD; its real kernel alias shares
        # the cursor. Changing position must not change the next append offset.
        os.lseek(owner.anchor,0,os.SEEK_SET)
        archive.append(name,second)
        self.assertEqual(first+second,(archive.path/name).read_bytes())

    def test_changed_open_append_stamp_refuses_before_overwriting_original_prefix(self):
        archive=self.original_archive();name='returned.bin';first=b'first original\n'
        archive.append(name,first);path=archive.path/name;original=path.stat()
        os.utime(path,ns=(original.st_atime_ns,original.st_mtime_ns+1))
        with self.assertRaises(ValueError):archive.append(name,b'second original\n')
        self.assertEqual(first,path.read_bytes())


if __name__=='__main__':unittest.main()
