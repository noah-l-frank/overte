# Durable original navigation admission

`navigation_admission_owner.NavigationAdmissionOwner` acquires the
[original scene prerequisites](NAVIGATION_SCENE_ADMISSION.md) through the
existing candidate-qualified iOS runtime. It records intent before reading the
static fixture source, then preserves the actual native clock start, each of
eight original packets and the actual native clock end before validating the
join. Static server time, host acquisition time and original client time stay
separate. No source is retimed or replaced by its requested value.

The private `ios-navigation-scene-admission.json` record has one fixed path in
the existing source directory and uses the existing source lock and atomic
private writer. Binding, run and provider identity cannot change during an
attempt. A different run cannot bypass a retained partial acquisition by
choosing another record name. Every accepted source remains in the journal
when a later source or final validation fails.

Reconstruction refuses a second acquisition. Recovery can only resolve a
fully retained lost final result, without HTTP/native reads or new clocks.
Historical validation preserves the original proof and does not qualify it for
input. `for_input` requires a live unchanged candidate/process and enforces the
original 1.5-second acquisition deadline across static-source reading, native
reading, persistence and validation. An expired original remains available for
audit but cannot authorize an input.

The factory uses the existing installed-candidate/session gate, original native
clock source and typed HTTP/AFC readers. It does not create a session, launch,
load a scene, alter bookmarks/preferences or deliver an input. The static-source
reader retains immutable provider history separately from active-run scene and
directory histories; it remains available after run retirement.

The whole Worlds owner still needs the durable normal-input journal, actual
arrival, independent publication, restart ownership, restoration and repeated
quiet cleanup. This acquisition cannot discharge those obligations, delete its
journal or advertise a complete feature capability. Host tests exercise real
private files and static loopback HTTP with modeled native/SDK ports; native
compilation, actual timing and devices remain unverified.
