# Test fixtures — ALL SYNTHETIC

Every file in this directory was written by hand to exercise the pipeline.
None of it is research data: the names, channels, captions, page text,
tickers and prices are invented placeholders and describe no real person,
video, page, or trade. Tests load them with `is_synthetic=True`, and
`python -m pipeline purge-synthetic --yes` removes anything so flagged.

| file | used to test |
|---|---|
| `synthetic_captions.vtt` | WebVTT parsing, incl. YouTube-style roll-up duplicate lines and inline timing tags |
| `synthetic_captions.srt` | SRT parsing |
| `synthetic_page.html` | main-text extraction, metadata, link extraction |
| `synthetic_ytdlp_info.json` | yt-dlp info-dict normalisation (shape only; IDs are fake) |

The synthetic video used by the tests is generated on the fly with FFmpeg
(solid colour blocks + a sine tone) in `tests/conftest.py`.
