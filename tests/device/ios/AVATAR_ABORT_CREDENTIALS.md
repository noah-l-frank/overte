# Interrupted Avatar credential carrier cleanup

`AvatarAbortCredentials` retires one actual private input nonce retained by an
interrupted Avatar Login input. It requires the existing role source lock,
unchanged SDK/process binding and the original child-account ownership record.
The caller must separately join that child account to its failed whole owner.
The component never enters credentials, resumes Login or grants authority.

Before retiring a possibly unfinished transfer, the owner records responsibility
for the actual serialized private RPC readback fence. Neither the private bytes,
their length nor their hash enters this journal. The returned fence has its own
original host bracket, bounded by the existing five-second private-file fence
contract. Its recorded return precedes the original Retire admission. This is an
ordering handoff; the fence return alone proves no native file absence.

The exact Retire nonce is durable before dispatch. It is sent once, under its
original 25-second input deadline and the last actual transport guard. A lost
return is retained as an abandoned query. Subsequent cleanup uses distinct
Inspect commands and never dispatches Retire again. Later passive Inspects may
settle an earlier issued Retire without renewing its original input deadline.
Each observation retains the unchanged native PrivateLoginInput-v2 DTO and its
own original host acquisition, including the final journal-save freshness check.

Two independently received Inspect originals must show `retired`, no file,
no pending work and zero actual open descriptors before the original private
input journal can retire. An ignored Retire acknowledgement or a remaining
native descriptor keeps ownership. Actual nonce, native-instance, sequence and
time prefixes remain checked across reconstruction. Foreign or malformed reply
payloads are refused before they can enter a host artifact.

Lost private-journal discard returns are adopted only from those already
retained actual absence originals. Historical `archive` reopens the same
closed owner without any SDK/native query. It cannot enter a live cleanup path.
The new local owner writes and reads `iosAvatarAbortCredentialsVersion: 1`;
native PrivateLoginInput-v2 and existing Login/Abort codecs remain unchanged.

Nine host tests execute real private files, inodes, descriptors, CAS journals
and the existing iOS private-transport/fence code. The native lease/AFC boundary
is explicitly modeled. Cases include delayed transfer, lost Retire/discard
returns, descriptor retention, ignored acknowledgement, changed ownership,
unsafe payload, missing/reordered fence metadata and both input and observation
deadline failures. No compiler, device or simulator runs.

This is one part of failed preparation. Marker/Script/GPU cleanup, ordinary
account cancellation/logout, preference restoration, provider revocation,
callback/key/UI quiet, process/SDK end and full canonical archival remain
independent whole-owner obligations. No Scene, Complete or full failed-run
cleanup result is produced by this component.
