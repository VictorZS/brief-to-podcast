# Provenance and dependencies

The renderer and editorial checks were extracted and generalized from the
author's personal briefing workflow, developed with AI assistance. The public
examples were written specifically for this release and describe fictional
events. No mailbox contents, personal configuration, reference recordings, model
weights or generated audio are distributed here.

The repository's source code and documentation use the [MIT license](LICENSE).
That license does not grant rights to input articles, voices, external software,
or recordings you supply or generate.

The core uses the Python standard library. macOS speech output invokes the
system-installed `say` and `afconvert` tools; these are not bundled or licensed by
this repository.

Optional MP3 export uses a separately installed FFmpeg executable. The optional
[`imageio-ffmpeg` 0.6.0 package](https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0)
is licensed under
[BSD-2-Clause](https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/LICENSE);
its wheels can include an FFmpeg binary with its own licensing terms. Consult
your selected binary's notices and the
[FFmpeg licensing page](https://ffmpeg.org/legal.html) if redistributing it.
This repository does not vendor either package or executable.
