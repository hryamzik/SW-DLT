# SW-DLT

SW-DLT ("Shortcuts Wrapper for -DL Tools") is an iOS shortcut that allows you to easily use, install and manage the popular and open source utilities [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) and [`gallery-dl`](https://github.com/mikf/gallery-dl). This shortcut aims to be compatible with [`yt-dlp's`](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) & [`gallery-dl's`](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md) collections of supported websites.

## About this fork

This repository is maintained separately from [net00-1/SW-DLT](https://github.com/net00-1/SW-DLT). The upstream author has not responded to pull requests for over ten months; this fork carries fixes and features we need locally (SponsorBlock settings, quick download shortcuts, yt-dlp import fixes, and related work).

- **`main`** — active development and releases for this fork ([Releases](https://github.com/hryamzik/SW-DLT/releases))
- **`master`** — sync branch aligned with upstream `net00-1/SW-DLT` for comparison and occasional merges

Credit for the original project goes to **net00**. When upstream picks up changes again, we intend to contribute back where it makes sense.

<div align="center">
  <img src="images/all_stages.png" width="60%"/>
</div>

Compatible with **iOS/iPadOS 18, 26**

## How to Use
1. **Download either the [a-Shell](https://apps.apple.com/us/app/a-shell/id1473805438) or [a-Shell Mini](https://apps.apple.com/us/app/a-shell-mini/id1543537943) app**
2. Copy a link to the clipboard (or use the share button if applicable)
3. Run the shortcut from either the Shortcuts app (if using a copied link) or from the Share Sheet
4. Select the option you need (or use a [quick shortcut](#quick-shortcuts-no-menu))
5. Wait for the process to finish
6. Use the Share menu to export the download to your chosen destination

### Quick shortcuts (no menu)
Build and import **SW-DLT Audio** and **SW-DLT Video 720p** alongside the main **SW-DLT** shortcut (see [Build the Shortcut](#build-the-shortcut)). They use the same SponsorBlock settings as the main shortcut and skip format menus:

- **SW-DLT Audio** — M4A/AAC (~192 kbps), single linked item only (`noplaylist`)
- **SW-DLT Video 720p** — up to 720p / 30 fps, H.264 + AAC in MP4 when FFmpeg is needed (good iPhone playback)

Share a URL or run with a link on the clipboard, same as the main shortcut.

## Main Features
See [Docs.md](Docs.md) for full feature documentation.

- Download video at custom qualities and framerates
- Download audio (audio only or extracted from video)
- Download playlists (video or audio choices available)
- Download images/clips/GIFs (from single items to massive albums)
- Configurable SponsorBlock segment removal (main shortcut settings)
- Support for both a-Shell and a-Shell Mini apps

## Build the Shortcut
1. Run `make build` (or manually copy and sign each plist under `src/`)
2. Source files: `src/SW-DLT.plist`, `src/SW-DLT-Audio.plist`, `src/SW-DLT-Video-720p.plist`
3. Change the extension from `.plist` to `.shortcut` if signing manually
4. Sign the shortcut with Apple (see "Ways to sign shortcuts" section below)
5. Import the signed `.shortcut` files to the Shortcuts app (main shortcut required for quick wrappers)

**Ways to sign shortcuts**
- From a Mac: follow [Apple documentation](https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac)
- From iPad/iPhone: use a tool to connect remotely to a Mac, such as [Shortcuts Source Helper](https://routinehub.co/shortcut/10060/). Credits to [@gluebyte](https://routinehub.co/user/gluebyte). If using this tool, pass the **unmodified plist (without extension change)** as input.

**NOTE**: if you do not want to use a remote service to sign the shortcut, nor have access to a Mac, you can still preview the source code as Shortcuts actions. Follow the first two steps of build instructions, then from the iPhone/iPad Files app hold on the .shortcut file, then press on the QuickLook option.

## Roadmap Features

- [ ] Implement full progress bar on gallery-dl downloads
- [ ] Add quality options for video playlists
- [ ] Add option to customize yt-dlp and gallery-dl with persistent settings
- [ ] Allow file inputs with multiple URLs

## Disclaimers
- This software is only intended to provide a way to archive and/or download content with yt-dlp & gallery-dl that you have **explicit permission to download** (for instance content owned by you). Use of this software to download copyrighted content could lead to breach of Terms of Service of hosting websites. License of this software does not include liability.
- All software used (`yt-dlp`, `gallery-dl`, `yt-dlp-apple-webkit-jsi`, SW-DLT, a-Shell) is open source and free
- It is recommended to have the VLC app or another universal media player app to play unsupported media formats in iOS/iPadOS.
