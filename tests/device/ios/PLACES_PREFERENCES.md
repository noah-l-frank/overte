# Original loaded iOS Places preferences, version 1

This passive source extends Places model v2 and controls v2. Worlds/navigation
remains partial: the whole owner, independent actor, arrival/images, restart and
combined retirement are still pending. Native code is uncompiled and devices
are untested.

`PlacesPreferenceObservation.h` reads only the existing Setting::Manager on the
GUI thread, under the dedicated E2E/iOS/`--testScript` gates. One recursive read
lock captures presence and original values for `placesAppPinnedMetaverse`,
`placesAppMetaverseToFetch` and `placesAppMaturityFilter`. Each field retains its
actual kind: absent, null, unsupported, QVariantList or QStringList. Supported
string lists preserve exact order/multiplicity; an unsupported value remains
unsupported. A SHA-256 of the original QDataStream presence/value serialization
preserves the original Qt type independently from its JSON representation.
Values are bounded to 1,024 strings of at most 4,096 characters and serialized
values to 65,536 bytes. Oversized values make observation unavailable.

The source also reads the actual native MetaverseAPI origin and supported
protocol signature. The model's original native clock pair brackets this read
alongside its actual roots/models. A requested provider origin/signature cannot
replace these measurements. The existing fixed private atomic file and normal
HTTP/AFC reader carry them unchanged; no extra input or arbitrary-path command
is introduced. There is no preference setter, removal, default coercion or
settings-file timestamp in this source.

These are actual loaded settings, not an independent read of the physical
settings file. A whole adapter must compare fresh observations across actual
process replacement before claiming persistence. An accepted UI input or a
loaded value before restart cannot establish a completed disk write. The
separate bookmark observer retains its own real backing-file bytes.

`restored` compares the complete original typed preference record. An absent key
differs from an empty list, a QStringList differs from a QVariantList, and reordered
or changed unowned values differ from the baseline. Actual UI defaults may also
differ from stored values: the current metaverse is fetched by product logic
even when the stored fetch list is empty. Both sources remain separate.

`ordinary_maturity_plan` is an input admission plan, not a measured state or
whole-run owner. If everyone is already included, no write is planned. An
originally absent setting is left untouched; the owning adapter must still
independently verify the actual model's filter. Adding everyone to an existing
supported QVariantList can be reversed through its ordinary checkbox: the
original product function removes the added element while preserving the other
ratings and their original order. A required mutation of a QStringList is
refused before input because the normal script writes QVariantList. No ordinary
control can remove an originally absent key or repair an unsupported value, and
this adapter does not add such a product operation.

The ordinary server controls similarly expose actual URL/index/checked identity.
An owned external server is removed from the built list after normal unfetch and
unpin; current/federated unowned servers remain. No delete-server API is added.
The future owner must capture the original arrays and ordering before input,
prove exact restoration and preserve unrelated servers/drafts. Unsupported
baselines must fail admission before mutation, rather than silently broadening
ownership or inventing cleanup success.

Nineteen host tests exercise original Python parsers and HTTP/AFC input/observation
codecs, and execute the unchanged product QML toggle and server-list construction
functions in Node. They cover ignored checkbox ACKs, changed source references,
foreign row indices, popup eligibility, legacy/mixed versions, typed restoration,
unrepresentable mutations, unsafe server text, model/preference independence,
retained hidden popups and v2 source acquisition. SDK/native/Qt boundaries are
modeled. These tests do not compile or execute the native survey and cannot
qualify actual device behavior.

Reconcile `ios-places-preferences` v1, `ios-places-controls` v2 (reads 1,2) and
`ios-places-model` v2 (reads 1,2). Existing acquisition receipts remain v1. All
changes are local to the iOS adapter branch; no parallel or protected branch has
been integrated.
