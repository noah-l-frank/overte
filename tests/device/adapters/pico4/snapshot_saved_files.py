"""Fixed Phone5527 Save-original transfer through the existing Pico file transport.

Private Pico metadata V1 includes the full original stat signature. Legacy
public capture files and binary framing are unchanged.

The copy ID selects only a real completed native readback. Callers cannot supply
expected filenames, URIs, bytes, digests or successful export results.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import stat
import time

from adapters.android_snapshot_files import AndroidSnapshotFiles,SnapshotFileError
from adapters.pico4.snapshot_exports import PicoSnapshotExports,components
from adapters.pico4.snapshot_export_readbacks import ROOTS,nonce
from snapshot_observation import MAX_BYTES

META_HEADER='OVT_PICO_SNAPSHOT_SAVED_META_V1'
META_FOOTER='OVT_PICO_SNAPSHOT_SAVED_META_END_V1'
BYTES_HEADER=b'OVT_SNAPSHOT_SAVED_BYTES_V1\n'
BYTES_FOOTER=b'\nOVT_SNAPSHOT_SAVED_BYTES_END_V1\n'
META_SCRIPT=r'''
saved_directory="files/$1"
saved_path="$saved_directory/$2"
[ -d files ] && [ ! -L files ] || exit 1
saved_uid=$(id -u) || exit 1
[ "$(stat -c %u files)" = "$saved_uid" ] || exit 1
[ -d "$saved_directory" ] && [ ! -L "$saved_directory" ] || exit 1
[ "$(stat -c %u "$saved_directory")" = "$saved_uid" ] || exit 1
[ "$(stat -c %a "$saved_directory")" = 700 ] || exit 1
[ -f "$saved_path" ] && [ ! -L "$saved_path" ] || exit 1
[ "$(stat -c %u "$saved_path")" = "$saved_uid" ] || exit 1
saved_size=$(stat -c %s "$saved_path") || exit 1
[ "$saved_size" -ge 1 ] && [ "$saved_size" -le "$3" ] || exit 1
[ "$(stat -c %h "$saved_path")" = 1 ] && [ "$(stat -c %a "$saved_path")" = 600 ] || exit 1
saved_metadata=$(stat -c '%d:%i:%s:%h:%a' "$saved_path") || exit 1
saved_signature=$(stat -c '%d %i %f %u %g %h %s %y %z' "$saved_path") || exit 1
saved_hash=$(sha256sum "$saved_path") || exit 1
saved_hash=${saved_hash%% *}
[ "$saved_signature" = "$(stat -c '%d %i %f %u %g %h %s %y %z' "$saved_path")" ] || exit 1
printf 'OVT_PICO_SNAPSHOT_SAVED_META_V1\n%s\n%s\n%s\nOVT_PICO_SNAPSHOT_SAVED_META_END_V1\n' "$saved_metadata" "$saved_signature" "$saved_hash"
'''.strip()
READ_SCRIPT=r'''
saved_directory="files/$1"
saved_path="$saved_directory/$2"
[ -d files ] && [ ! -L files ] || exit 1
saved_uid=$(id -u) || exit 1
[ "$(stat -c %u files)" = "$saved_uid" ] || exit 1
[ -d "$saved_directory" ] && [ ! -L "$saved_directory" ] || exit 1
[ "$(stat -c %u "$saved_directory")" = "$saved_uid" ] || exit 1
[ "$(stat -c %a "$saved_directory")" = 700 ] || exit 1
[ -f "$saved_path" ] && [ ! -L "$saved_path" ] || exit 1
[ "$(stat -c %u "$saved_path")" = "$saved_uid" ] || exit 1
[ "$(stat -c %h "$saved_path")" = 1 ] && [ "$(stat -c %a "$saved_path")" = 600 ] || exit 1
printf 'OVT_SNAPSHOT_SAVED_BYTES_V1\n'
head -c "$3" "$saved_path" || exit 1
printf '\nOVT_SNAPSHOT_SAVED_BYTES_END_V1\n'
'''.strip()


class PicoSnapshotSavedFiles(AndroidSnapshotFiles):
    """Same original-file transport/privacy as the existing Snapshot foundation."""
    def __init__(self,adb,selector,package,context,check_continuity,artifact_directory,readbacks,run,publish):
        super().__init__(adb,selector,package,context,check_continuity,artifact_directory)
        if (package!='org.overte.pico' or not isinstance(readbacks,PicoSnapshotExports) or not callable(publish)
                or not nonce(run) or str(readbacks.pid)!=context['processIdentity'].split(':')[0]):
            raise SnapshotFileError('Saved Snapshot source binding is invalid')
        self.readbacks,self.run,self.publish=readbacks,run,publish

    def current(self,id,*,historical=False):
        if type(historical) is not bool:raise SnapshotFileError('Saved Snapshot acquisition mode is invalid')
        self._check();packet=self.readbacks.request(self.run);self._check()
        body=components(packet)[1]['source']
        if 'initialized' in body or body['copiesRetired']:
            raise SnapshotFileError('Saved Snapshot readback source is unavailable')
        copies=[row for row in body['files'] if row['id']==id and row['phase']=='complete']
        jobs=[row for row in body['jobs'] if row['phase']=='complete' and row['original'] is not None and row['original']['id']==id]
        if (len(copies)!=1 or len(jobs)!=1 or copies[0]!=jobs[0]['original']
                or not 0<=packet['capturedEpochMs']-jobs[0]['completedEpochMs']
                or not historical and packet['capturedEpochMs']-jobs[0]['completedEpochMs']>=1500):
            raise SnapshotFileError('Saved Snapshot has no fresh completed original readback')
        original=deepcopy(copies[0]);parts=[]
        for root in ROOTS:
            if original['path'].startswith(root):parts=original['path'][len(root):].split('/')
        if (len(parts)!=2 or re.fullmatch('overte-snapshot-e2e-[0-9a-f]{32}',parts[0]) is None
                or parts[1]!=id+'.bin'):
            raise SnapshotFileError('Saved Snapshot copy path is not owned')
        return packet,original,deepcopy(jobs[0]),parts

    def metadata(self,parts):
        raw=self._execute(META_SCRIPT,*parts,str(MAX_BYTES))
        if type(raw) is not bytes or len(raw)>1024:raise SnapshotFileError('Saved Snapshot metadata is unavailable')
        try:lines=raw.decode('ascii').splitlines()
        except UnicodeError:raise SnapshotFileError('Saved Snapshot metadata is malformed') from None
        if len(lines)!=5 or lines[0]!=META_HEADER or lines[-1]!=META_FOOTER:
            raise SnapshotFileError('Saved Snapshot metadata did not complete')
        fields=lines[1].split(':')
        if (len(fields)!=5 or any(re.fullmatch('[0-9]{1,20}',item) is None for item in fields)
                or not 1<=int(fields[2])<=MAX_BYTES or fields[3:]!=['1','600']
                or re.fullmatch('[0-9a-f]{64}',lines[3]) is None
                or re.fullmatch(r'[0-9]+ [0-9]+ [0-9a-fA-F]+ [0-9]+ [0-9]+ 1 '+fields[2]+r' \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{9} [+-]\d{4} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{9} [+-]\d{4}',lines[2]) is None):
            raise SnapshotFileError('Saved Snapshot metadata is invalid')
        signature=lines[2].split()
        mode=int(signature[2],16)
        if (signature[:2]!=fields[:2] or signature[5:7]!=['1',fields[2]]
                or not stat.S_ISREG(mode) or stat.S_IMODE(mode)!=0o600):
            raise SnapshotFileError('Saved Snapshot metadata identities differ')
        return dict(device=int(fields[0]),inode=int(fields[1]),bytes=int(fields[2]),sha256=lines[3],originalStat=lines[2])

    def _acquire(self,id,*,historical):
        try:
            if type(historical) is not bool:raise SnapshotFileError('Saved Snapshot acquisition mode is invalid')
            started=time.monotonic()
            if not nonce(id):raise SnapshotFileError('Saved Snapshot copy ID is invalid')
            before,original,job,parts=self.current(id,historical=historical);metadata=self.metadata(parts)
            if any(metadata[key]!=original[key] for key in ('bytes','sha256')):
                raise SnapshotFileError('Saved Snapshot original differs from the actual provider readback')
            raw=self._execute(READ_SCRIPT,*parts,str(MAX_BYTES+1),timeout=5 if historical else 90)
            if (type(raw) is not bytes or not raw.startswith(BYTES_HEADER) or not raw.endswith(BYTES_FOOTER)
                    or len(raw)>MAX_BYTES+1+len(BYTES_HEADER)+len(BYTES_FOOTER)):
                raise SnapshotFileError('Saved Snapshot binary transfer did not complete')
            content=raw[len(BYTES_HEADER):-len(BYTES_FOOTER)]
            if not content or len(content)>MAX_BYTES or not self._matches(metadata,content) or self.metadata(parts)!=metadata:
                raise SnapshotFileError('Saved Snapshot original changed during transfer')
            after_started=time.monotonic()
            after,observed,completed,_parts=self.current(id,historical=historical)
            if (observed!=original or completed!=job or before['instance']!=after['instance']
                    or before['processId']!=after['processId'] or components(before)[1]['source']['instance']!=components(after)[1]['source']['instance']):
                raise SnapshotFileError('Saved Snapshot original ownership changed during transfer')
            artifact=self.publish(id,content)
            result=dict(artifact=artifact,bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),
                capturedEpochMs=job['completedEpochMs'],originalCompletedEpochMs=job['completedEpochMs'],request=original['request'],job=job['id'],copy=id,
                source='pico-snapshot-saved-original',snapshotSavedOriginalVersion=1,device=metadata['device'],inode=metadata['inode'],originalStat=metadata['originalStat'])
            self._check()
            # Publication and the final original guard are part of the age
            # boundary. A frozen native clock cannot hide a slow host CAS.
            now=self.readbacks.clock_ms();finished=time.monotonic()
            anchor=after_started if historical else started
            if (finished<after_started or finished-started>=(5 if historical else 90)
                    or not -250<=now-after['capturedEpochMs']<=1500
                    or max(now-after['capturedEpochMs'],after['requestedEpochMs']-after['capturedEpochMs']+(finished-anchor)*1000)>1500):
                raise SnapshotFileError('Saved Snapshot acquisition exceeded its current source boundary')
            if historical:result['capturedEpochMs']=now
            return result
        except Exception:raise SnapshotFileError('Original saved Snapshot acquisition failed') from None

    def acquire(self,id):
        return self._acquire(id,historical=False)

    def acquire_current(self,id):
        """Read an unchanged old original through fresh actual owner inventories.

        The acquisition gets its actual current epoch; native completion keeps
        its original timestamp. The existing foundation decoder is unchanged.
        """
        return self._acquire(id,historical=True)
