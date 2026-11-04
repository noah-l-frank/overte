"""NEW fixed one-SDK Source transaction command, not yet a bound reader.

The later original Raw owner MUST reserve first, invoke check=False and retain
actual stdout/timeout bytes before its physical/frame parser. This pure command
builder owns no archive, acquisition, clock, acceptance fact or retry policy.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from dataclasses import dataclass
import re
import shlex
import stat

from adapters.android_snapshot_files import original_stat
from adapters.native_feature_observation import need
from adapters.pico4.emote_source_transaction_wire import request,WIRE_LIMIT
from adapters.pico4.emote_stream_wire import physical_stamp
from adapters.pico4.probe_originals import strict_json
from adapters.script_journey.history import canonical

VERSION=1
RECEIPT_LIMIT=4096
FILE_LIMIT=WIRE_LIMIT-1-4096-RECEIPT_LIMIT
COMMAND_LIMIT=1024
HEADER=b'OVT_PICO_EMOTE_SOURCE_SDK_V1\n'
FOOTER=b'\nOVT_PICO_EMOTE_SOURCE_SDK_END_V1 '
SCRIPT=r'''
umask 077
tx_root=files/overte-e2e
tx_file=$tx_root/feature-pico-emote-source-transaction.wire
tx_receipt=$tx_root/feature-pico-emote-source-receipt.json
tx_pending=$tx_root/feature-pico-emote-source-request.pending
tx_control=$tx_root/android-control-command.json
tx_nonce=$1
tx_pid=$2
tx_birth=$3
tx_command_sha=$4
tx_wire_limit=$5
tx_file_limit=$6
tx_identity() {
    tx_stat=$(cat /proc/"$tx_pid"/stat) || return 1
    [ "${tx_stat%% *}" = "$tx_pid" ] || return 1
    tx_fields=${tx_stat##*) }
    set -- $tx_fields
    [ "$#" -ge 20 ] || return 1
    shift 19
    [ "$1" = "$tx_birth" ] || return 1
    printf '%s:%s' "$tx_pid" "$tx_birth"
}
tx_private_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c %h "$1")" = 1 ] &&
    [ "$(stat -c %a "$1")" = 600 ] && [ "$(stat -c %u "$1")" = "$(id -u)" ]
}
[ -d files ] && [ ! -L files ] && [ -d "$tx_root" ] && [ ! -L "$tx_root" ] || exit 1
[ "$(stat -c %a "$tx_root")" = 700 ] && [ "$(stat -c %u "$tx_root")" = "$(id -u)" ] || exit 1
tx_original_identity=$(tx_identity) || exit 1
[ ! -e "$tx_pending" ] && [ ! -L "$tx_pending" ] || exit 1
[ ! -e "$tx_root/feature-pico-emote-capture-pending.json" ] && [ ! -L "$tx_root/feature-pico-emote-capture-pending.json" ] || exit 1
if [ -e "$tx_control" ] || [ -L "$tx_control" ]; then tx_private_file "$tx_control" || exit 1; fi
# Same fixed channel, bounded exact stdin. Unknown/partial temporary is kept.
( set -C; head -c 1025 > "$tx_pending" ) || exit 1
tx_private_file "$tx_pending" || exit 1
tx_size=$(stat -c %s "$tx_pending") || exit 1
[ "$tx_size" -ge 1 ] && [ "$tx_size" -le 1024 ] || exit 1
tx_actual_sha=$(sha256sum "$tx_pending") || exit 1
[ "${tx_actual_sha%% *}" = "$tx_command_sha" ] || exit 1
[ "$(tx_identity)" = "$tx_original_identity" ] || exit 1
mv "$tx_pending" "$tx_control" || exit 1
tx_private_file "$tx_control" || exit 1
tx_actual_sha=$(sha256sum "$tx_control") || exit 1
[ "${tx_actual_sha%% *}" = "$tx_command_sha" ] || exit 1
tx_control_stamp=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_control") || exit 1
# Header peeks inspect the control nonce only, never return a source value.
# The real SDK operation remains ONE stdout acquisition with original timeout.
tx_attempt=0
while [ "$tx_attempt" -le 50 ]; do
    [ "$(tx_identity)" = "$tx_original_identity" ] || exit 1
    if [ -f "$tx_receipt" ] && [ ! -L "$tx_receipt" ]; then
        if head -c 4097 "$tx_receipt" | grep -F '"commandId":"'"$tx_nonce"'"' >/dev/null; then break; fi
    fi
    tx_attempt=$((tx_attempt+1))
    [ "$tx_attempt" -le 50 ] || exit 1
    sleep 0.05
done
tx_private_file "$tx_file" || exit 1
tx_private_file "$tx_receipt" || exit 1
tx_file_before=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_file") || exit 1
tx_receipt_before=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_receipt") || exit 1
tx_receipt_bytes=$(stat -c %s "$tx_receipt") || exit 1
[ "$tx_receipt_bytes" -ge 1 ] && [ "$tx_receipt_bytes" -le 4096 ] || exit 1
tx_root_before=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_root") || exit 1
[ "$(printf %s "$tx_file_before" | wc -c)" -le 512 ] && [ "$(printf %s "$tx_root_before" | wc -c)" -le 512 ] && [ "$(printf %s "$tx_receipt_before" | wc -c)" -le 512 ] || exit 1
# No Native metadata/desired DTO is reconstructed in this process. The fixed
# original wire is emitted verbatim between physical process/file bookends.
printf 'OVT_PICO_EMOTE_SOURCE_SDK_V1\n%s\n%s\n%s\n%s\n%s\n%s\n' "$tx_nonce" "$tx_original_identity" "$tx_root_before" "$tx_file_before" "$tx_receipt_before" "$tx_receipt_bytes"
head -c 4096 "$tx_receipt" || exit 1
printf '\n'
head -c "$((tx_file_limit+1))" "$tx_file" || exit 1
tx_file_after=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_file") || exit 1
tx_receipt_after=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_receipt") || exit 1
tx_root_after=$(stat -c '%d %i %f %u %h %s %y %z' "$tx_root") || exit 1
tx_private_file "$tx_file" || exit 1
tx_private_file "$tx_receipt" || exit 1
[ "$tx_file_before" = "$tx_file_after" ] && [ "$tx_root_before" = "$tx_root_after" ] && [ "$tx_receipt_before" = "$tx_receipt_after" ] || exit 1
[ ! -L "$tx_root" ] || exit 1
[ "$(tx_identity)" = "$tx_original_identity" ] || exit 1
[ "$tx_control_stamp" = "$(stat -c '%d %i %f %u %h %s %y %z' "$tx_control")" ] || exit 1
[ ! -e "$tx_root/feature-pico-emote-capture-pending.json" ] && [ ! -L "$tx_root/feature-pico-emote-capture-pending.json" ] || exit 1
printf '\nOVT_PICO_EMOTE_SOURCE_SDK_END_V1 %s\n%s\n%s\n%s\n%s\n' "$tx_nonce" "$tx_original_identity" "$tx_root_after" "$tx_file_after" "$tx_receipt_after"
'''.strip()


def command(value,identity):
    """Exact stdin and one exec-out argv; callers keep original admission."""
    request(value);need(type(identity) is str and re.fullmatch('[1-9][0-9]*:[0-9]+',identity))
    raw=canonical(value);need(0<len(raw)<=COMMAND_LIMIT)
    pid,birth=identity.split(':')
    remote=' '.join(shlex.quote(item) for item in ('run-as','org.overte.pico','sh','-c',SCRIPT,
        'overte-pico-emote-source-transaction',value['commandId'],pid,birth,hashlib.sha256(raw).hexdigest(),
        str(WIRE_LIMIT),str(FILE_LIMIT)))
    return ['exec-out',remote],raw


@dataclass(frozen=True,slots=True)
class SDKSourceExtent:
    offset:int
    size:int
    sha256:str
    process_identity:str
    root_description:str
    file_description:str
    receipt_offset:int
    receipt_size:int
    receipt_description:str


def envelope(wire,nonce,identity):
    """Physical framing AFTER raw durability; returns absolute body extents.

    No complete body slice/copy, source JSON or fresh source verdict is made.
    The owning factory still must join actual Role4 root/file nodes and clocks.
    """
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT
        and type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce)
        and type(identity) is str and re.fullmatch('[1-9][0-9]*:[0-9]+',identity))
    prefix=HEADER+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix));offset=len(prefix);fields=[]
    for _index in range(5):
        end=wire.find(b'\n',offset);need(end>=offset and 0<end-offset<=512)
        fields.append(wire[offset:end].decode('ascii'));offset=end+1
    process,root,file,receipt,receipt_size=fields;need(process==identity and receipt_size.isdigit())
    receipt_size=int(receipt_size);need(0<receipt_size<=RECEIPT_LIMIT)
    root_fields=root.split();file_fields=file.split()
    need(len(root_fields)==len(file_fields)==12 and file_fields[5].isdigit())
    size=int(file_fields[5]);need(original_stat(file,size))
    need(stat.S_ISREG(int(file_fields[2],16)) and stat.S_IMODE(int(file_fields[2],16))==0o600
        and root_fields[3]==file_fields[3] and root_fields[4].isdigit() and root_fields[5].isdigit())
    lexical=list(root_fields);lexical[4]='1'
    need(int(root_fields[4])>=1 and original_stat(' '.join(lexical),int(root_fields[5]))
        and stat.S_ISDIR(int(root_fields[2],16)) and stat.S_IMODE(int(root_fields[2],16))==0o700)
    receipt_fields=receipt.split();need(len(receipt_fields)==12 and original_stat(receipt,receipt_size)
        and stat.S_ISREG(int(receipt_fields[2],16)) and stat.S_IMODE(int(receipt_fields[2],16))==0o600
        and receipt_fields[3]==file_fields[3])
    receipt_offset=offset;offset+=receipt_size;need(wire[offset:offset+1]==b'\n');offset+=1
    suffix=FOOTER+nonce.encode('ascii')+b'\n'+process.encode('ascii')+b'\n'+root.encode('ascii')+b'\n'+file.encode('ascii')+b'\n'+receipt.encode('ascii')+b'\n'
    need(wire.endswith(suffix) and offset+min(size,FILE_LIMIT+1)==len(wire)-len(suffix))
    # Already retained oversized prefixes remain explicitly incomplete.
    need(0<size<=FILE_LIMIT);physical_stamp(root);physical_stamp(file)
    digest=hashlib.sha256(memoryview(wire)[offset:offset+size]).hexdigest()
    value=strict_json(wire[receipt_offset:receipt_offset+receipt_size].decode('utf-8'))
    need(type(value) is dict and set(value)=={'picoEmoteSourceReceiptVersion','commandId','wire','receiptNode','builderSettled'}
        and type(value['picoEmoteSourceReceiptVersion']) is int and value['picoEmoteSourceReceiptVersion']==1
        and value['commandId']==nonce and value['builderSettled'] is True)
    proof=value['wire'];need(type(proof) is dict and set(proof)=={'leaf','maximumFileBytes','rootNode','sampleNode','sampleStamp','sha256','bytes'})
    need(proof['leaf']=='feature-pico-emote-source-transaction.wire'
        and type(proof['maximumFileBytes']) is int and proof['maximumFileBytes']==FILE_LIMIT
        and type(proof['bytes']) is int and proof['bytes']==size and proof['sha256']==digest
        and proof['rootNode']==physical_stamp(root)[:5] and proof['sampleNode']==physical_stamp(file)[:5]
        and proof['sampleStamp']==physical_stamp(file) and value['receiptNode']==physical_stamp(receipt)[:5])
    return SDKSourceExtent(offset,size,digest,process,root,file,receipt_offset,receipt_size,receipt)
