# Avatar original Vulkan sample ownership

`IOSAvatarSamples` acquires actual AvatarWorld and Renderer originals before
and after an owned Vulkan render-target image. A native clock acquisition
brackets those unchanged packets, the original GPU copy/chunk transcript and
independently observed native retirement. Original controlled phase metadata
is retained on both sides; phase crossing preserves the evidence but cannot
produce a current observation. Marker input, native ACKs and image-file delivery
supply no Avatar effect.

Each sample uses the committed `VulkanWorldFrameOwner`, actual private PNG
inode, chunk hashes and original GPU resource receipts. Its source record uses
`OriginalFrameStore` with the separate `avatar-sample` namespace and
`avatarSample` DTO prefix. The whole samples journal and individual record
contracts (`ios-avatar-samples`, `ios-avatar-sample`) write/read version 1.
Records keep the original ready Avatar MarkerScope snapshot and never relabel
Emote source facts. Avatar self/remote subjects use their actual Renderer4
mesh bounds and independent actual root-body collection. Unavailable geometry
can use only a prior retained genuine loaded sample of that same subject and
unchanged actual root/scale; current missing mesh is never assigned old bounds.
The PNG still needs the full fresh marker challenge.

Normal capture is issued once. Lost native capture/chunk/release responses,
post-image source failures, partially written source records and a lost final
journal return preserve ownership. `recover()` retires the actual old GPU owner
or inspects a previously issued release, keeps every returned packet plus the
failed writer's actual inode/bytes, and writes an abandoned record. It does not
complete missing image facts or resend capture/release. Nested interrupted
abandonment writes retain each preceding original owner and opened file. A
saved complete record can be adopted after a lost final journal CAS without
any SDK request. `drain()` resolves uncertainty and checks genuine retirement;
it retains the immutable original PNGs and source files.

Every future sample must extend all earlier actual World/Renderer/native/phase
prefixes, including abandoned reads. It also preserves original GPU source
identity/sequence and rejects reused draw IDs. Historical `history()`/`archive()`
validate only retained original bytes, private inodes, the independent original
marker owner and image geometry. They create no SDK, call no live guard, issue
no native command and publish nothing. A whole observation decoder must retain
this journal, validate all required non-abandoned source/GPU originals and
join separate genuine model/social/peer effects before publication.

Runtime factories bind the existing candidate SDK, exact source lock, role and
actual controlled metaverse origin. They neither create sessions nor advertise
a whole feature capability. Marker Entities API-return/birth/weak-expiry and
whole-run model/UI/VM/provider cleanup remain separately owned requirements.

Host tests use real private files, OriginalFrameStore, VulkanWorldFrameOwner,
PNG decoding, strict Avatar image composition and actual failure recovery.
Native/GPU/Qt/phase producers and the MarkerScope admission seam are explicitly
modeled; the marker's complete normal Script/Node/code/quiet path has separate
host tests. Native C++ is uncompiled. No device, simulator, build or laboratory
was used, and this packet does not qualify full Feature 3/14.
