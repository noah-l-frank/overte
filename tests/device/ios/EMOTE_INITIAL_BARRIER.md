# First direct Emote action admission

The normal runner observes its baseline before activating the first action.
A direct `act` also needs a genuine baseline and actual image before input.
The coordinator therefore acquires and retains the idle baseline first, then
acquires a distinct original pre-input source before any ordinary action.

`begin_initial_input` admits this source only for the first retained idle
baseline, in the same actual fixture ticket, with no episode and no new native
override or restore calls. It preserves the original baseline image and all
original clocks. Historical reconstruction repeats the same native prefix and
call-count checks. An older source, a later actual phase, or an override followed
by restoration cannot replace that admission even if the latest Rig is idle.

The whole coordinator journals the same admitted source before input and
recovers it after an interrupted outer metadata write. It does not substitute
a later input snapshot or restart an acquisition deadline. Observer metadata
remains version 2; record/reference/original DTOs remain unchanged. Whole
Feature 5 dispatch remains a separate integration requirement.
