# WPP brand font

Drop the WPP typeface here as **.woff2** and both the app and the PDF
report pick it up automatically. Nothing else to configure — with the
files missing, everything falls back to system fonts and still works.

Expected filenames (exactly these, case-sensitive):

| File                 | Weight | Used for                       |
| -------------------- | ------ | ------------------------------ |
| `WPP-Regular.woff2`  | 400    | Body copy                      |
| `WPP-Medium.woff2`   | 500    | Subheadings, emphasis          |
| `WPP-Bold.woff2`     | 700    | Headlines, the app header      |

Per the Brand Guidelines: WPP Bold for headlines and core messaging,
WPP Regular for body copy.

`.woff` and `.eot` versions aren't needed — `.woff2` covers every
browser the app runs in, and the PDF report converts it to TTF on the
fly (ReportLab can't read woff2 directly).

Note: the WPP typeface is licensed to WPP, so these files are for
internal use in this tool only.
