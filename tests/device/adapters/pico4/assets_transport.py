"""Private bounded Assets SDK transport; no product input or default SDK change.

The writer dispatches one already-retained native Stage command. Read returns
are retained as opaque bytes before framing/UTF8. Receipts prove transport only;
actual staged file leases and upload effects still require their original readers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import math
import re
import shlex
import stat
import subprocess
import time
import uuid

from adapters.android_snapshot_files import original_stat
from adapters.native_feature_observation import integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_files import command as files_command
from adapters.script_journey.history import canonical

BODY_LIMIT=4*1024*1024
AUX_LIMIT=4096
STAGE_LIMIT=61440
PACKAGE='org.overte.pico'
PATH='files/overte-e2e/android-control-command.json'
FILES={'files':'feature-pico-assets-files.json','mappings':'feature-pico-assets-observation.json',
       'uploads':'feature-pico-assets-uploads.json','download':'feature-pico-assets-download.json',
       'ui-observation':'navigation-ui-observation.json','ui-status':'navigation-ui-status.json'}
HEADER=b'OVT_PICO_ASSETS_BYTES_V1\n'
FOOTER=b'\nOVT_PICO_ASSETS_BYTES_END_V1 '
UNCONFIRMED=[]

# Only fixed package/path and validated integer/hex positional arguments enter
# this command. set -f prevents /proc comm text from becoming shell glob input.
PROCESS=r'''
set -f
same_process() {
  process_stat=$(cat "/proc/$1/stat") || return 1
  process_fields=${process_stat##*) }
  set -- $process_fields
  [ "$#" -ge 20 ] || return 1
  shift 19
  [ "$1" = "$expected_start" ]
}
check_process() { same_process "$expected_pid"; }
check_time() {
  current_epoch=$(date +%s%3N) || return 1
  case "$current_epoch" in ''|*[!0-9]*) return 1;; esac
  [ "$current_epoch" -ge "$requested_epoch" ] && [ "$current_epoch" -lt "$deadline_epoch" ]
}
'''.strip()
STAGE_SCRIPT=PROCESS+r'''
expected_pid=$1;expected_start=$2;requested_epoch=$3;deadline_epoch=$4
nonce=$5;expected_bytes=$6;expected_sha=$7
control_path=files/overte-e2e/android-control-command.json
temporary_path="$control_path.stage-$nonce"
[ -d files ] && [ ! -L files ] && [ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
check_process && check_time || exit 1
if [ -e "$control_path" ] || [ -L "$control_path" ]; then
  [ -f "$control_path" ] && [ ! -L "$control_path" ] || exit 1
  [ "$(stat -c %h "$control_path")" = 1 ] && [ "$(stat -c %u "$control_path")" = "$(id -u)" ] || exit 1
fi
umask 077
set -C
exec 4>"$temporary_path" || exit 1
set +C
cat >&4 || exit 1
chmod 600 "$temporary_path" || exit 1
held_path="/proc/$$/fd/4"
before=$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path") || exit 1
[ "$(stat -Lc %s "$held_path")" = "$expected_bytes" ] || exit 1
actual_sha=$(sha256sum "$held_path") || exit 1
[ "${actual_sha%% *}" = "$expected_sha" ] || exit 1
[ ! -L "$temporary_path" ] && [ "$before" = "$(stat -c '%d %i %f %u %h %s %y %z' "$temporary_path")" ] || exit 1
check_process && check_time || exit 1
before_node=$(stat -Lc '%d %i %f %u %h %s %y' "$held_path") || exit 1
mv "$temporary_path" "$control_path" || exit 1
after=$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path") || exit 1
[ ! -L "$control_path" ] && [ "$after" = "$(stat -c '%d %i %f %u %h %s %y %z' "$control_path")" ] || exit 1
[ "$before_node" = "$(stat -Lc '%d %i %f %u %h %s %y' "$held_path")" ] || exit 1
check_process && check_time || exit 1
printf 'OVT_PICO_ASSETS_STAGE_V1 %s %s %s\n%s\n' "$nonce" "$expected_bytes" "$expected_sha" "$after"
'''
READ_SCRIPT=PROCESS+r'''
expected_pid=$1;expected_start=$2;requested_epoch=$3;deadline_epoch=$4
nonce=$5;original_path=$6
[ -d files ] && [ ! -L files ] && [ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
check_process && check_time || exit 1
[ -f "$original_path" ] && [ ! -L "$original_path" ] || exit 1
[ "$(stat -c %h "$original_path")" = 1 ] && [ "$(stat -c %u "$original_path")" = "$(id -u)" ] || exit 1
before=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ "${#before}" -le 512 ] || exit 1
exec 3<"$original_path" || exit 1
held_path="/proc/$$/fd/3"
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
printf 'OVT_PICO_ASSETS_BYTES_V1\n%s\n%s\n' "$nonce" "$before"
head -c 4194305 <&3 || exit 1
after=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ ! -L "$original_path" ] && [ "$before" = "$after" ] || exit 1
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
check_process && check_time || exit 1
printf '\nOVT_PICO_ASSETS_BYTES_END_V1 %s\n%s\n' "$nonce" "$after"
'''


def sha(raw):return hashlib.sha256(raw).hexdigest()


def read_body(wire,nonce):
    need(type(wire) is bytes and len(wire)<=BODY_LIMIT+AUX_LIMIT)
    prefix=HEADER+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix))
    before,separator,body=wire[len(prefix):].partition(b'\n');need(separator==b'\n' and 0<len(before)<=512)
    suffix=FOOTER+nonce.encode('ascii')+b'\n'+before+b'\n';need(body.endswith(suffix));body=body[:-len(suffix)]
    description=before.decode('ascii');fields=description.split();need(len(fields)==12 and fields[5].isdigit())
    size=int(fields[5]);need(original_stat(description,size));mode=int(fields[2],16)
    need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600 and len(body)==min(size,BODY_LIMIT+1))
    need(size<=BODY_LIMIT and len(body)<=BODY_LIMIT)
    return body


class PicoAssetsTransport:
    def __init__(self,adapter,target,process_identity,guard,retain_wire,capacity,clock_ms,*,monotonic=time.monotonic,publish_view=None):
        need(adapter.kind=='pico' and adapter.profile['package']==PACKAGE and type(target) is str and target
            and type(process_identity) is str and re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*',process_identity)
            and all(callable(fn) for fn in (guard,retain_wire,capacity,clock_ms,monotonic))
            and (publish_view is None or callable(publish_view)))
        self.adapter,self.target,self.process_identity=adapter,target,process_identity
        self.guard,self.retain_wire,self.capacity,self.clock_ms,self.monotonic=guard,retain_wire,capacity,clock_ms,monotonic
        self.binary=adapter.adb.execute_bytes
        self.publish_view=publish_view
        self._fixed=(adapter,target,process_identity,guard,retain_wire,capacity,clock_ms,monotonic,self.binary,publish_view)
        self._original_fixed=self._fixed
        self.failed=False;self.active=False;self.acquired=None;self.issued=set();self.receipts=[]

    def identity(self):
        need(not self.failed and self.active and self._fixed is self._original_fixed and (self.adapter,self.target,self.process_identity,self.guard,
            self.retain_wire,self.capacity,self.clock_ms,self.monotonic,self.binary,self.publish_view)==self._fixed
            and self.adapter.adb.execute_bytes==self.binary and self.guard() is not False)
        self.adapter.require_same_process(self.target,self.process_identity,'Assets original SDK transport')

    def age(self):
        self.identity();now=self.monotonic();epoch=self.clock_ms();ended=self.monotonic()
        need(number(now,self.started,self.started+1.5) and number(ended,now,self.started+1.5)
            and integer(epoch,self.epoch,self.epoch+1499))
        return max(epoch,self.epoch+math.ceil((ended-self.started)*1000))

    def call(self,role,command,script,args,consume,*,input_bytes=None):
        need(not self.failed and not self.active);self.active=True
        self.acquired=None
        try:
            self.started=self.monotonic();self.epoch=self.clock_ms()
            need(number(self.started,0,1e15) and integer(self.epoch,1));self.identity()
            self.capacity(role,command,BODY_LIMIT+AUX_LIMIT);self.age()
            pid,start=self.process_identity.split(':');nonce=uuid.uuid4().hex
            arguments=[pid,start,str(self.epoch),str(self.epoch+1500),nonce,*args]
            remote=' '.join(shlex.quote(value) for value in ('run-as',PACKAGE,'sh','-c',script,'overte-assets-original',*arguments))
            self.age();remaining=min(5,1.5-(self.monotonic()-self.started));need(remaining>0)
            try:
                options={} if input_bytes is None else {'input_bytes':input_bytes}
                wire=self.binary(['exec-out',remote],target=self.target,timeout=remaining,check=False,**options)
            except (RuntimeError,subprocess.TimeoutExpired) as error:
                timeout=error if type(error) is subprocess.TimeoutExpired else error.__cause__
                if type(timeout) is subprocess.TimeoutExpired and type(timeout.output) is bytes:
                    wire=timeout.output;self.acquired=wire;self.retain_wire(role,wire)
                raise
            self.acquired=wire;self.retain_wire(role,wire)
            need(type(wire) is bytes and len(wire)<=BODY_LIMIT+AUX_LIMIT);self.age()
            result=consume(wire,nonce);self.age()
            return result
        except BaseException:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            raise
        finally:self.active=False

    def stage(self,command):
        need(not self.failed and not self.active)
        files_command(command);need(command['operation']=='stage' and command.get('stage') not in self.issued and len(self.issued)<6)
        payload=canonical(command)+b'\n';need(len(payload)<=STAGE_LIMIT)
        def consume(wire,nonce):
            need(len(wire)<=AUX_LIMIT)
            prefix=f'OVT_PICO_ASSETS_STAGE_V1 {nonce} {len(payload)} {sha(payload)}\n'.encode('ascii')
            need(wire.startswith(prefix) and wire.endswith(b'\n'))
            description=wire[len(prefix):-1].decode('ascii');need(len(description)<=512 and original_stat(description,len(payload)))
            fields=description.split();mode=int(fields[2],16)
            need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600)
            return dict(commandId=command['commandId'],bytes=len(payload),sha256=sha(payload),wireSha256=sha(wire))
        # Issued ownership precedes capacity/SDK: unknown success is never replayed.
        self.issued.add(command.get('stage'))
        receipt=self.call('stage-receipt',command,STAGE_SCRIPT,[str(len(payload)),sha(payload)],consume,input_bytes=payload)
        self.receipts.append(receipt)

    def read(self,role):
        need(not self.failed and not self.active and role in FILES)
        command=dict(assetsWireReadVersion=1,role=role)
        def consume(wire,nonce):
            body=read_body(wire,nonce)
            if self.publish_view is not None:self.publish_view(role,body,nonce)
            return body
        return self.call(role,command,READ_SCRIPT,['files/overte-e2e/'+FILES[role]],consume)
