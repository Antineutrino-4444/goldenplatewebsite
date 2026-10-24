# Rendered tutorial artifacts

This directory holds generated videos, subtitles, storyboards, and verification reports. They are intentionally not committed. The source tool and reusable registration recipe are in `tools/tutorial-studio`.

The latest version is `school-registration-animated-ending-3840x2160-60fps.mp4`: 74.5 seconds, native 4K at 60 FPS, silent SDR. The walkthrough ends after Login. A title introduces “Getting started in your school account,” then its gold arrow curls into the plate logo, the native leaf unfurls and the wordmark settles into a final branded hold. It contains no footage from that future tutorial.

Generate the finished tutorial with:

```sh
node tools/tutorial-studio/cli.mjs render --workers 2 --resume --out output/tutorial-studio/school-registration-animated-ending-3840x2160-60fps.mp4
```
