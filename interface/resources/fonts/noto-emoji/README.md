# Noto Emoji fallback for the Phone client

Upstream: https://github.com/googlefonts/noto-emoji (monochrome Noto Emoji).
License: SIL Open Font License 1.1; the unmodified license is in `OFL.txt`.

The unmodified font was obtained from Fedora's
`google-noto-emoji-fonts-20260921-1.fc44.noarch` package.
SHA256 of `NotoEmoji-Regular.ttf`: `24aaa2a20c9c06ffe9bf04284bfd1f14376a329d10122f902abe2770817eb504`.

Qt 5 cannot paint the COLR v1 font supplied by newer Android releases. Phone
loads this outline font as an emoji fallback before the system color font.
Emoji are monochrome; ordinary text continues to use the requested font.
Other clients keep their existing font configuration.
