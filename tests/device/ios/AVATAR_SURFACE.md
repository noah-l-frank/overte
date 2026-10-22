# Avatar observation navigation

`IOSAvatarSurface` owns ordinary People navigation independently of Avatar
recipes. Each actual UI reference, original native command UUID, returned
receipt and subsequent observation is saved before the next input. Unknown
input remains owned; reconstruction sends no replacement or repeated input.
Pending incoming/outgoing invitations retain the actual peer and request UUID.
Observation never grants consent.

Writer 2 adds one closed terminal case: the Actor may close its own actually
`cancelled` invitation during the actual `connection-cancel` phase. An earlier
completed Actor surface must already retain the matching original `incoming`
peer/request UUID. The original admitted Source reference remains attached to
the terminal call. The input boundary revalidates the same cancelled reference;
a different invitation from the same peer cannot be substituted. The sole
extra ordinary input is `people.cancel`, followed by actual idle readback and
the normal Connections first-page fetch. Primary and foreign SDK surfaces
continue waiting for their actual owner to close a terminal prompt.

Readers preserve exact writer-1 originals. Their old call grammar cannot carry
a terminal component or a `people.cancel` input. Reopening writer-1 metadata
alone performs no rewrite; a later writer-2 operation preserves original Source
references and adds explicit null terminal components to earlier calls.

Host tests use real source files, journals and normal-input transport with an
explicit Qt producer. They cover original matching cancelled closure, unknown
return without resend, changed same-peer UUID, absent earlier admission,
foreign subject, and legacy-v1 rejection. Native compilation/device execution
and complete Feature 3/14 qualification remain separate.
