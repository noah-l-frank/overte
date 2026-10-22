# Emote image slot ownership

Active Emote samples now use the same original slot-authority predicate as the
original restoration-frame owner. A native capture's first inspection must have
proved that this request's slot was empty. A preexisting occupied or unknown
slot grants no authority to capture, release, drain or recover that resource.

The guard applies to capture's failure cleanup, explicit sample drainage,
interrupted sample recovery, retained partial PNG validation and historical
successful sample validation. An unqualified slot remains unresolved with its
actual private metadata and inode responsibility. It is never turned into an
abandoned-success receipt by releasing someone else's resource.

The transport/owner/sample DTOs and versions remain unchanged. The original
protocol already required the proven-empty initial inspection before writing a
read intent. Reservations that have not created a native owner retain their
existing once-release tombstone and unknown-release inspection rules.

Twenty-nine host checks cover active samples, sample recovery and original
restoration ownership. The new occupied-slot counterexample observes only the
initial inspection: no native read or release occurs through capture failure,
explicit drain or attempted recovery, and the foreign request, pixels and
resource state remain unchanged. Native compilation and device execution remain
unperformed.
