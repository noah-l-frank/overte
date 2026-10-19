# Recorded preview acoustic signal, version 1

The actual Record-and-Play UI captures three seconds in memory. The established
`voice-v1` twelve-symbol roundtrip signal lasts 4.84 seconds and cannot prove
that shorter product flow. Its generator, detector defaults, wire results and
existing fixture bytes remain unchanged.

The separate closed profile `recorded-preview-v1` uses the same twelve-symbol
detector, frequencies, SNR/coverage thresholds, clipping limit and channel
handling. Each symbol lasts 120 ms in a 160 ms cell, after a 200 ms lead. All
twelve finish before 2.1 seconds. The generated WAV and minimum positive or
quiet capture are still **three full seconds**; trailing silence allows acoustic
startup margin. The challenge derivation uses the separate
`overte-recorded-preview-v1:` domain. Wrong profiles cannot cross-qualify.

`feature_journeys/fixtures.py` serves this controlled input as
`preview-challenge.v1.wav`, derived from the owned run/ticket. The existing
`challenge.wav` is unchanged. This new input resource does not implement an
audio adapter or change the draft v1 audio workflow. A corrected actual-UI
journey must explicitly select this profile and use original microphone and
preview-output/peer PCM, not native phase flags alone.

The independent acoustic actor must start its input in response to the actual
native capturing event, within the real three-second window. Merely activating
a runner ticket is not evidence that recording started. Missing/late audio,
missing symbols, retired challenges, clipping, insufficient capture length and
nonquiet negative controls fail. Timing and acoustic delivery remain unqualified
until a later Proxmox device run. Host tests synthesize only detector inputs.
