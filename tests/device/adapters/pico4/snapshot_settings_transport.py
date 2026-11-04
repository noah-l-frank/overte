"""Source2 fixed binary endpoint; acquisition is retained before interpretation.

Only an already configured Pico process is read. This does not start services,
write settings, supply a baseline, or grant input authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import shlex
import stat
import subprocess
from types import MethodType

from adapters.android_snapshot_files import original_stat
from adapters.native_feature_observation import need
from adapters.pico4.assets_transport import PROCESS
from adapters.pico4.snapshot_settings_codec import WIRE_LIMIT

LIMIT=65536
PACKAGE='org.overte.pico'
FILE='files/overte-e2e/feature-pico-snapshot-settings-originals.json'
HEAD=b'OVT_PICO_SNAPSHOT_SETTINGS2\n'
TAIL=b'\nOVT_PICO_SNAPSHOT_SETTINGS2_END '
# Exact body: at most 65536 original bytes and one oversize probe. Each stat
# is <=512 ASCII bytes. All fixed framing/nonce/stat overhead is <4095 bytes.
READ_SCRIPT=PROCESS+r"""
expected_pid=$1;expected_start=$2;requested_epoch=$3;deadline_epoch=$4;nonce=$5
original_path=files/overte-e2e/feature-pico-snapshot-settings-originals.json
[ -d files ] && [ ! -L files ] && [ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
[ "$(stat -c %a files/overte-e2e)" = 700 ] && [ "$(stat -c %u files/overte-e2e)" = "$(id -u)" ] || exit 1
check_process && check_time || exit 1
[ -f "$original_path" ] && [ ! -L "$original_path" ] || exit 1
[ "$(stat -c %h "$original_path")" = 1 ] && [ "$(stat -c %u "$original_path")" = "$(id -u)" ] || exit 1
before=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ "${#before}" -le 512 ] || exit 1
exec 3<"$original_path" || exit 1
held_path="/proc/$$/fd/3"
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
printf 'OVT_PICO_SNAPSHOT_SETTINGS2\n%s\n%s\n' "$nonce" "$before"
head -c 65537 <&3 || exit 1
after=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ ! -L "$original_path" ] && [ "$before" = "$after" ] || exit 1
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
check_process && check_time || exit 1
printf '\nOVT_PICO_SNAPSHOT_SETTINGS2_END %s\n%s\n' "$nonce" "$after"
"""


def body(wire,nonce):
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT and type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce))
    prefix=HEAD+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix))
    before,separator,raw=wire[len(prefix):].partition(b'\n');need(separator and 0<len(before)<=512)
    suffix=TAIL+nonce.encode('ascii')+b'\n'+before+b'\n';need(raw.endswith(suffix));raw=raw[:-len(suffix)]
    text=before.decode('ascii');fields=text.split();need(len(fields)==12 and fields[5].isdigit())
    size=int(fields[5]);need(original_stat(text,size));mode=int(fields[2],16)
    need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600 and len(raw)==min(size,LIMIT+1)
        and 0<size<=LIMIT and len(raw)<=LIMIT)
    return raw


class SnapshotSettingsBinaryRead:
    def __init__(self,adapter,target,process_identity,raw_owner):
        from adapters.pico4.snapshot_settings_query_originals import SnapshotSettingsQueryOriginals
        need(type(raw_owner) is SnapshotSettingsQueryOriginals and adapter.kind=='pico'
            and adapter.profile['package']==PACKAGE and type(target) is str and target
            and raw_owner.target is target and raw_owner.binding['processIdentity']==process_identity
            and type(process_identity) is str and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*',process_identity))
        self.adapter=self.original_adapter=adapter;self.target=self.original_target=target
        self.process=self.original_process=process_identity;self.raw=self.original_raw=raw_owner
        self.binary=adapter.adb.execute_bytes;need(type(self.binary) is MethodType)
        self.binary_self,self.binary_function=self.binary.__self__,self.binary.__func__
        self.acquired=None;self.reference=None;self.failed=False;self.active=False

    def identity(self):
        need(self.failed is False and self.adapter is self.original_adapter and self.target is self.original_target
            and self.process is self.original_process and self.raw is self.original_raw
            and type(self.binary) is MethodType and self.binary.__self__ is self.binary_self
            and self.binary.__func__ is self.binary_function)
        current=self.adapter.adb.execute_bytes
        need(type(current) is MethodType and current.__self__ is self.binary_self and current.__func__ is self.binary_function)
        self.raw.resource()

    def __call__(self):
        need(self.active is False);self.active=True
        try:
            self.identity();token=self.raw.pending_reader
            if token is None:token=self.raw.reserve_read()
            self.raw.fresh()
            anchor=self.raw.actual_anchor;nonce=self.raw.state['queries'][self.raw.state['pending']]['command']['commandId']
            pid,start=self.process.split(':');requested=anchor['nativeEpochMs']
            arguments=(pid,start,str(requested),str(requested+1500),nonce)
            command=' '.join(shlex.quote(value) for value in ('run-as',PACKAGE,'sh','-c',READ_SCRIPT,'overte-snapshot-settings2',*arguments))
            self.identity();self.raw.fresh()
            remaining=1.5-(self.raw.real_clock()-anchor['actualHostMonotonic']);need(0<remaining<=1.5)
            try:wire=self.binary(['exec-out',command],target=self.target,timeout=remaining,check=False)
            except (RuntimeError,subprocess.TimeoutExpired) as error:
                timeout=error if type(error) is subprocess.TimeoutExpired else error.__cause__
                if type(timeout) is subprocess.TimeoutExpired and type(timeout.output) is bytes:
                    self.acquired=timeout.output;self.reference=self.raw.retain(token,self.acquired)
                raise
            self.acquired=wire
            # The actual opaque wire has durable original ownership before any
            # size/framing/ASCII/UTF8/JSON, guard or source-age refusal.
            self.reference=self.raw.retain(token,wire)
            self.raw.fresh();result=body(wire,nonce);self.raw.fresh();self.acquired=None
            return result
        except BaseException:
            self.failed=True;self.raw.poison();raise
        finally:self.active=False
