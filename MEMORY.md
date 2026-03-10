# MEMORY.md - Long-term Memory

## LanceDB Vector Store

- Location: `/home/alice/.openclaw/workspace/memory/lance_db/memories.lance`
- Used for semantic search and long-term memory storage
- Should be updated alongside MEMORY.md for important memories

## Video Merger Project

- Original working version: Git commit 83f5560
- Current stable version: v0.0.1 (commit 3a2b504)
- This version has perfect video stacking (2, 3, or 4 videos) with auto-scaling to handle different resolutions
- Attempted to add audio support but encountered FFmpeg issues:
  - iPhone videos have audio codec issues (apac encoding not supported)
  - When using filter_complex with video stacking, the `-map [v]` syntax conflicts with `-map 0:a`
  - Tried various syntax combinations but output files become corrupted/invalid
- v0.0.1 fixes: Scaled videos to same resolution before stacking to avoid "Invalid argument" error

## Whisper Transcription

- Installed faster-whisper for audio-to-text transcription
- Works with .ogg voice messages from Telegram
- Tested successfully on Kevin's voice message about oil prices

## Services

- video.chiangkevin.com - Video merger web app (v0.0.1)
- subtitle.chiangkevin.com - Subtitle extraction
- reviewcloud.net - Review website

## GitHub Repositories

- https://github.com/movemove/video-merger (v0.0.1)
- https://github.com/movemove/subtitle
- https://github.com/movemove/reviewcloud
