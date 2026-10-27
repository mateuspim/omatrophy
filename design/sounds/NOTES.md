# OmaTrophy synthesized unlock sounds

Run `python3 tools/sounds.py` from the repo root to rebuild the four WAVs in
`assets/sounds/` and this measured report. Standard-library Python only. Original deterministic additive synthesis;
no samples, downloads, external instruments, or random assets.

## Musical idea

All four use D major, equal temperament, A4 = 440 Hz. One rounded mallet
voice combines a sine fundamental with quiet second, third and fourth
harmonics. The upper harmonics decay faster than the body. A shallow 6.1 Hz
amplitude movement supplies shimmer without deliberately detuning pitches.
No fundamentals below D4 (293.66 Hz), no bass thump, and no noise burst.

- **Bronze:** D5 with a quiet A5 overtone-like companion. One compact
  tick-ding, with a 2.5 ms attack and a rapidly settling body.
- **Silver:** D5–F#5–A5, three rounded strokes spaced 95 ms apart. The same
  timbre becomes brighter through pitch and a slightly longer final ring.
- **Gold:** a quiet D4 anchor under D5–F#5–A5–D6, with very soft F#6 and A6
  glints. More motion and register, without a louder peak.
- **Platinum:** an immediate D4–A4–D5–F#5 struck chord, followed by a slow
  D5–F#5–A5–D6 bloom. Quiet upper glints and E6 add a major ninth colour.
  The bloom overlaps the strike; the low chord gives weight without sub-bass.
  Mono cannot supply stereo width, so register and overlapping envelopes
  suggest an opening card instead.

## Measurement method and limits

Measurements are taken from the written, re-read 48 kHz / mono / 16-bit PCM
files. Peak is normalized to -3 dBFS. The first sample is zero and each
strike has a raised-sine attack; onset is the first sample above -50 dBFS.
Audible end is the end of the last 10 ms RMS block at or above -50 dBFS;
this is a repeatable proxy for inaudibility, not a perceptual guarantee.
Natural exponential decays precede a cosine-squared fade. Only the region
below -70 dBFS is trimmed, retaining 15 ms and fading the final 10 ms to zero.

The complete envelope below uses nonoverlapping 50 ms blocks (the final
block can be shorter). Spectral centroids are power-weighted, using a Hann
window and a zero-padded 4096-point FFT. Band percentages are approximate
RMS-energy-weighted averages of these short-time spectra. Centroids in
near-silent blocks increasingly reflect 16-bit quantization, not timbre.

At the player's linear 60% gain all reported peaks and RMS levels drop by
4.44 dB. No clipping, limiting, compression or playback changes are needed.
Absolute loudness depends on the playback system; this has not been heard
or calibrated against a reference desktop notification. Frequency balance
and measured levels support the design but cannot establish pleasantness.

## Results

| Tier | File s | End at -50 dB s | Peak dBFS | RMS dBFS | Onset ms | <150 Hz % | 2–5 kHz % |
|---|---:|---:|---:|---:|---:|---:|---:|
| bronze | 0.483 | 0.32 | -3.00 | -18.90 | 0.146 | 0.00000 | 0.001 |
| silver | 0.901 | 0.70 | -3.00 | -16.80 | 0.167 | 0.00000 | 0.009 |
| gold | 1.460 | 1.04 | -3.00 | -17.53 | 0.146 | 0.00002 | 0.171 |
| platinum | 3.238 | 2.64 | -3.00 | -22.59 | 0.167 | 0.00001 | 0.017 |

### Bronze: 50 ms envelope and centroid

| Start s | RMS dBFS | Centroid Hz |
|---:|---:|---:|
| 0.00 | -9.99 | 599.4 |
| 0.05 | -17.31 | 593.6 |
| 0.10 | -23.67 | 590.8 |
| 0.15 | -29.73 | 589.4 |
| 0.20 | -37.22 | 588.6 |
| 0.25 | -44.03 | 588.1 |
| 0.30 | -49.84 | 587.9 |
| 0.35 | -56.99 | 588.1 |
| 0.40 | -64.38 | 590.0 |
| 0.45 | -72.55 | 615.1 |

### Silver: 50 ms envelope and centroid

| Start s | RMS dBFS | Centroid Hz |
|---:|---:|---:|
| 0.00 | -10.70 | 591.9 |
| 0.05 | -15.85 | 589.2 |
| 0.10 | -11.31 | 733.3 |
| 0.15 | -13.38 | 735.4 |
| 0.20 | -10.30 | 876.0 |
| 0.25 | -15.17 | 872.9 |
| 0.30 | -18.74 | 875.9 |
| 0.35 | -22.69 | 876.3 |
| 0.40 | -27.65 | 875.2 |
| 0.45 | -31.51 | 877.0 |
| 0.50 | -35.07 | 878.0 |
| 0.55 | -39.92 | 877.5 |
| 0.60 | -44.21 | 878.2 |
| 0.65 | -47.55 | 879.0 |
| 0.70 | -52.10 | 879.0 |
| 0.75 | -56.80 | 879.4 |
| 0.80 | -60.32 | 880.3 |
| 0.85 | -68.19 | 886.5 |
| 0.90 | -120.00 | 0.0 |

### Gold: 50 ms envelope and centroid

| Start s | RMS dBFS | Centroid Hz |
|---:|---:|---:|
| 0.00 | -9.51 | 551.3 |
| 0.05 | -13.07 | 540.0 |
| 0.10 | -11.85 | 688.9 |
| 0.15 | -12.72 | 756.6 |
| 0.20 | -12.84 | 847.5 |
| 0.25 | -12.96 | 978.7 |
| 0.30 | -12.17 | 1121.1 |
| 0.35 | -15.19 | 1124.6 |
| 0.40 | -17.01 | 1166.1 |
| 0.45 | -19.79 | 1160.1 |
| 0.50 | -22.79 | 1198.2 |
| 0.55 | -25.10 | 1183.6 |
| 0.60 | -27.57 | 1176.6 |
| 0.65 | -30.95 | 1168.8 |
| 0.70 | -33.38 | 1169.1 |
| 0.75 | -35.35 | 1169.6 |
| 0.80 | -38.64 | 1166.6 |
| 0.85 | -41.41 | 1167.8 |
| 0.90 | -43.18 | 1170.3 |
| 0.95 | -46.09 | 1169.3 |
| 1.00 | -49.28 | 1169.4 |
| 1.05 | -51.08 | 1171.7 |
| 1.10 | -53.54 | 1171.8 |
| 1.15 | -56.96 | 1171.5 |
| 1.20 | -59.02 | 1173.2 |
| 1.25 | -61.11 | 1174.0 |
| 1.30 | -64.44 | 1174.9 |
| 1.35 | -66.98 | 1177.2 |
| 1.40 | -69.73 | 1182.0 |
| 1.45 | -79.11 | 1465.4 |

### Platinum: 50 ms envelope and centroid

| Start s | RMS dBFS | Centroid Hz |
|---:|---:|---:|
| 0.00 | -11.71 | 472.5 |
| 0.05 | -13.52 | 471.2 |
| 0.10 | -14.21 | 470.1 |
| 0.15 | -14.88 | 469.9 |
| 0.20 | -16.69 | 478.1 |
| 0.25 | -17.02 | 504.1 |
| 0.30 | -16.54 | 536.4 |
| 0.35 | -17.58 | 591.9 |
| 0.40 | -18.28 | 641.9 |
| 0.45 | -18.47 | 648.7 |
| 0.50 | -19.49 | 672.4 |
| 0.55 | -20.64 | 712.6 |
| 0.60 | -21.23 | 692.6 |
| 0.65 | -21.97 | 698.0 |
| 0.70 | -23.11 | 734.9 |
| 0.75 | -23.81 | 734.5 |
| 0.80 | -24.34 | 722.9 |
| 0.85 | -25.39 | 759.3 |
| 0.90 | -26.31 | 757.2 |
| 0.95 | -26.81 | 733.4 |
| 1.00 | -27.72 | 760.6 |
| 1.05 | -28.65 | 773.7 |
| 1.10 | -29.17 | 745.9 |
| 1.15 | -30.00 | 759.3 |
| 1.20 | -30.94 | 783.2 |
| 1.25 | -31.46 | 759.4 |
| 1.30 | -32.22 | 757.6 |
| 1.35 | -33.09 | 785.8 |
| 1.40 | -33.76 | 771.8 |
| 1.45 | -34.40 | 756.8 |
| 1.50 | -35.19 | 782.9 |
| 1.55 | -36.00 | 781.9 |
| 1.60 | -36.55 | 758.6 |
| 1.65 | -37.26 | 777.0 |
| 1.70 | -38.18 | 788.3 |
| 1.75 | -38.71 | 763.0 |
| 1.80 | -39.33 | 769.9 |
| 1.85 | -40.25 | 790.1 |
| 1.90 | -40.84 | 769.4 |
| 1.95 | -41.43 | 763.5 |
| 2.00 | -42.31 | 787.5 |
| 2.05 | -42.92 | 776.5 |
| 2.10 | -43.55 | 759.5 |
| 2.15 | -44.34 | 781.4 |
| 2.20 | -44.99 | 782.4 |
| 2.25 | -45.66 | 758.9 |
| 2.30 | -46.34 | 773.2 |
| 2.35 | -47.06 | 785.6 |
| 2.40 | -47.73 | 761.6 |
| 2.45 | -48.35 | 764.7 |
| 2.50 | -49.14 | 785.1 |
| 2.55 | -49.81 | 766.8 |
| 2.60 | -50.34 | 757.7 |
| 2.65 | -51.19 | 780.8 |
| 2.70 | -51.88 | 772.7 |
| 2.75 | -52.36 | 753.7 |
| 2.80 | -53.22 | 773.5 |
| 2.85 | -53.91 | 777.6 |
| 2.90 | -54.43 | 753.6 |
| 2.95 | -55.21 | 764.8 |
| 3.00 | -55.91 | 779.7 |
| 3.05 | -56.55 | 756.8 |
| 3.10 | -57.27 | 756.3 |
| 3.15 | -60.85 | 778.3 |
| 3.20 | -72.59 | 799.2 |

## With more time

Listen at the actual 60% setting on laptop speakers and headphones, then
audition ten bronze unlocks over representative game audio. Compare the
platinum bloom against the card animation before changing its delay or
duration. Adjust the upper glints and perceived loudness by ear; peak and
RMS matching alone cannot determine equal subjective loudness. A calibrated
desktop-notification reference would make the volume target testable.
