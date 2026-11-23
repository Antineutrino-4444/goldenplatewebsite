# Assembly fonts

The editable presentation uses Newsreader Regular for headlines, Georgia Regular and Bold for supporting text, and Georgia Italic for lunch dates. PowerPoint embeds Newsreader and refers to Georgia by its native family name.

| Embedded file | Google Fonts original | Static instance |
| --- | --- | --- |
| Newsreader-Regular.eot | [Newsreader variable TrueType, version 1.003](https://github.com/google/fonts/tree/main/ofl/newsreader) | Weight 400 and optical size 60 |

FontTools instantiated Newsreader at the specified axes. The static face uses the Newsreader family name and Regular style in its TrueType name table. Fontello's ttf2eot 3.1.0 wrapped the TrueType file without compression. The browser compiler and PDF renderer read the same TrueType payload.

The original variable Newsreader font has SHA-256 `8a08d13f8a6c0d51be379a60af84f945f65369a67e509ee3c3bdcc421254d7c1`. [Newsreader license](Newsreader-OFL.txt)

The browser compiler and PDF renderer prefer installed Georgia faces. Each missing style falls back to the matching Gelasio face, designed to match Georgia’s character widths. The repository includes the designer’s unmodified static TrueType faces, version 1.008. [Upstream source](https://github.com/SorkinType/Gelasio/tree/7ab20e7e5c42791e603b9ee3201a0b49849cfdb2/fonts/ttf) · [Metric compatibility](https://github.com/SorkinType/Gelasio/blob/7ab20e7e5c42791e603b9ee3201a0b49849cfdb2/README.md) · [Gelasio license](Gelasio-OFL.txt)

| File | SHA-256 |
| --- | --- |
| Gelasio-Regular.ttf | `48c797fbe0e07c48a18cb962e7bdfa23f19618327dddf54093265328dc9eb39d` |
| Gelasio-Bold.ttf | `e0ef3addf1acf35f5c6aef2be00d0a2c01363bf70a5950e16650976051a0c462` |
| Gelasio-Italic.ttf | `1d8bda4ff258bb8251eae4f7d7500c8d97d084136192bb264bc2305168765d1b` |
