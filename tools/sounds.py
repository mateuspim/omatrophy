"""Write assets/sounds/<tier>.wav and design/sounds/NOTES.md: OmaTrophy's
unlock chimes, one family in D major, from bronze's tick to platinum's bloom.

Written by Codex from design/sounds/BRIEF.md; platinum's decays lengthened
by hand to ring out within the brief. Deterministic, standard library only.
Run from the repo root after changing a recipe; the asserts check each tier
against the brief:
  python3 tools/sounds.py
"""

import math
from pathlib import Path
import struct
import wave


RATE = 48000
STEP = 2400
PEAK = 10 ** (-3 / 20)
TIERS = {
    "bronze": (0.54, (0.3, 0.6), [
        (0, 74, 1, 0.065, 0.0025),
        (0, 81, 0.18, 0.050, 0.0035),
    ]),
    "silver": (0.94, (0.6, 1.0), [
        (0, 74, 0.80, 0.075, 0.0025),
        (0.095, 78, 0.72, 0.085, 0.003),
        (0.190, 81, 0.82, 0.105, 0.0035),
    ]),
    "gold": (1.52, (1.0, 1.6), [
        (0, 62, 0.33, 0.14, 0.003),
        (0, 74, 0.85, 0.10, 0.0025),
        (0.090, 78, 0.66, 0.11, 0.003),
        (0.180, 81, 0.66, 0.13, 0.003),
        (0.280, 86, 0.66, 0.17, 0.004),
        (0.390, 90, 0.11, 0.105, 0.009),
        (0.480, 93, 0.07, 0.090, 0.011),
    ]),
    # Struck chord, then the bloom; decays are Codex's x1.4 (chord) and x1.7
    # (bloom) so the tail lasts to about 2.6 s, as long as the card's landing.
    "platinum": (3.25, (2.0, 3.5), [
        (0, 62, 0.70, 0.36, 0.003),
        (0, 69, 0.42, 0.31, 0.003),
        (0, 74, 0.58, 0.39, 0.0025),
        (0, 78, 0.38, 0.34, 0.0035),
        (0.140, 74, 0.32, 0.66, 0.19),
        (0.180, 78, 0.24, 0.63, 0.22),
        (0.220, 81, 0.28, 0.65, 0.23),
        (0.270, 86, 0.19, 0.60, 0.24),
        (0.410, 90, 0.055, 0.41, 0.026),
        (0.550, 93, 0.040, 0.39, 0.030),
        (0.720, 88, 0.045, 0.44, 0.045),
    ]),
}


def frequency(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def db(amplitude):
    return 20 * math.log10(amplitude) if amplitude > 0 else -120.0


def strike(length, midi, decay, attack):
    """A tuned, rounded mallet with a fleeting glass edge, no noise sample."""
    fundamental = frequency(midi)
    # Weak upper modes decay first so repeated notifications stay gentle.
    modes = ((1, 1, 1), (2, 0.105, 0.60), (3, 0.022, 0.40),
             (4, 0.008, 0.28))
    samples = []
    for index in range(length):
        seconds = index / RATE
        ramp = math.sin(min(1, seconds / attack) * math.pi / 2) ** 2
        # Slow amplitude motion gives the bloom life without detuning the notes.
        shimmer = 1 - 0.065 * (1 - math.cos(2 * math.pi * 6.1 * seconds))
        sample = sum(
            gain * math.exp(-seconds / (decay * damping))
            * math.sin(2 * math.pi * fundamental * harmonic * seconds)
            for harmonic, gain, damping in modes
        )
        samples.append(sample * ramp * shimmer)
    return samples


def finish(samples):
    """Normalize with headroom, then fade and remove only negligible silence."""
    scale = PEAK / max(abs(sample) for sample in samples)
    rendered = [sample * scale for sample in samples]
    fade = min(len(rendered), int(0.12 * RATE))
    for index in range(fade):
        rendered[-fade + index] *= math.cos(index / (fade - 1) * math.pi / 2) ** 2
    # Keep the entire -50 dB decay; trimming happens a further 20 dB down.
    last = max(index for index, sample in enumerate(rendered)
               if abs(sample) >= 10 ** (-70 / 20))
    rendered = rendered[:min(len(rendered), last + 1 + int(0.015 * RATE))]
    fade = min(len(rendered), int(0.010 * RATE))
    for index in range(fade):
        rendered[-fade + index] *= math.cos(index / (fade - 1) * math.pi / 2) ** 2
    return [round(sample * 32767) for sample in rendered]


def synthesize(tier):
    duration, _, notes = TIERS[tier]
    samples = [0.0] * round(duration * RATE)
    for start, midi, gain, decay, attack in notes:
        offset = round(start * RATE)
        voice = strike(len(samples) - offset, midi, decay, attack)
        for index, sample in enumerate(voice):
            samples[offset + index] += gain * sample
    return finish(samples)


def fft(values):
    """Radix-two FFT for measured spectra; no third-party numerical package."""
    count = len(values)
    if count == 0 or count & (count - 1):
        raise ValueError("FFT length must be a nonzero power of two")
    result = [complex(value) for value in values]
    reverse = 0
    for index in range(1, count):
        bit = count >> 1
        while reverse & bit:
            reverse ^= bit
            bit >>= 1
        reverse ^= bit
        if index < reverse:
            result[index], result[reverse] = result[reverse], result[index]
    width = 2
    while width <= count:
        angle = -2 * math.pi / width
        root = complex(math.cos(angle), math.sin(angle))
        for start in range(0, count, width):
            rotation = 1 + 0j
            for index in range(start, start + width // 2):
                even = result[index]
                odd = rotation * result[index + width // 2]
                result[index] = even + odd
                result[index + width // 2] = even - odd
                rotation *= root
        width *= 2
    return result


def spectrum(samples):
    count = len(samples)
    size = 1 << (count - 1).bit_length()
    windowed = [sample * (0.5 - 0.5 * math.cos(2 * math.pi * index / (count - 1)))
                for index, sample in enumerate(samples)]
    bins = fft(windowed + [0.0] * (size - count))
    # Power weighting describes dominant audible tones without magnifying
    # tiny PCM quantization components in the almost-silent tail.
    power = [abs(value) ** 2 for value in bins[:size // 2 + 1]]
    total = sum(power)
    if total == 0:
        return 0.0, 0.0, 0.0
    centroid = sum(index * RATE / size * value for index, value in enumerate(power)) / total
    low = sum(value for index, value in enumerate(power) if index * RATE / size < 150) / total
    harsh = sum(value for index, value in enumerate(power)
                if 2000 <= index * RATE / size <= 5000) / total
    return centroid, low, harsh


def measure(pcm):
    samples = [sample / 32768 for sample in pcm]
    windows = []
    low_energy = harsh_energy = energy = 0.0
    for offset in range(0, len(samples), STEP):
        block = samples[offset:offset + STEP]
        rms = math.sqrt(sum(sample * sample for sample in block) / len(block))
        padded = block + [0.0] * (STEP - len(block))
        centroid, low, harsh = spectrum(padded)
        weight = rms * rms * len(block)
        energy += weight
        low_energy += weight * low
        harsh_energy += weight * harsh
        windows.append((offset / RATE, db(rms), centroid))
    threshold = 10 ** (-50 / 20)
    onset = next(index for index, sample in enumerate(samples) if abs(sample) >= threshold) / RATE
    # A 10 ms RMS gate distinguishes a sustained tail from zero crossings.
    audible_end = 0
    for offset in range(0, len(samples), 480):
        block = samples[offset:offset + 480]
        if math.sqrt(sum(sample * sample for sample in block) / len(block)) >= threshold:
            audible_end = min(len(samples), offset + 480) / RATE
    return {
        "duration": len(samples) / RATE,
        "peak": db(max(abs(sample) for sample in samples)),
        "rms": db(math.sqrt(energy / len(samples))),
        "onset_ms": onset * 1000,
        "audible_end": audible_end,
        "low_pct": 100 * low_energy / energy,
        "harsh_pct": 100 * harsh_energy / energy,
        "windows": windows,
    }


def write_wav(path, pcm):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))


def read_wav(path):
    with wave.open(str(path), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, RATE)
        return list(struct.unpack(f"<{source.getnframes()}h", source.readframes(source.getnframes())))


IDEA = """# OmaTrophy synthesized unlock sounds

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
"""


def report(measurements):
    lines = [IDEA, "| Tier | File s | End at -50 dB s | Peak dBFS | RMS dBFS | Onset ms | <150 Hz % | 2–5 kHz % |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for tier, result in measurements.items():
        lines.append(f"| {tier} | {result['duration']:.3f} | {result['audible_end']:.2f} | "
                     f"{result['peak']:.2f} | {result['rms']:.2f} | {result['onset_ms']:.3f} | "
                     f"{result['low_pct']:.5f} | {result['harsh_pct']:.3f} |")
    for tier, result in measurements.items():
        lines.extend([f"\n### {tier.capitalize()}: 50 ms envelope and centroid\n",
                      "| Start s | RMS dBFS | Centroid Hz |", "|---:|---:|---:|"])
        lines.extend(f"| {start:.2f} | {rms:.2f} | {centroid:.1f} |"
                     for start, rms, centroid in result["windows"])
    lines.append("""
## With more time

Listen at the actual 60% setting on laptop speakers and headphones, then
audition ten bronze unlocks over representative game audio. Compare the
platinum bloom against the card animation before changing its delay or
duration. Adjust the upper glints and perceived loudness by ear; peak and
RMS matching alone cannot determine equal subjective loudness. A calibrated
desktop-notification reference would make the volume target testable.
""")
    return "\n".join(lines)


def main():
    root = Path(__file__).resolve().parent.parent
    folder = root / "assets" / "sounds"
    folder.mkdir(parents=True, exist_ok=True)
    measurements = {}
    for tier, (_, limits, _) in TIERS.items():
        path = folder / f"{tier}.wav"
        write_wav(path, synthesize(tier))
        pcm = read_wav(path)
        result = measure(pcm)
        assert limits[0] <= result["audible_end"] <= limits[1], (tier, result)
        assert limits[0] <= result["duration"] <= limits[1], (tier, result)
        assert result["onset_ms"] <= 5
        assert abs(result["peak"] + 3) < 0.01
        assert pcm[0] == pcm[-1] == 0 and max(abs(value) for value in pcm) < 32767
        assert result["low_pct"] < 0.1 and result["harsh_pct"] < 2
        measurements[tier] = result
    notes = report(measurements)
    (root / "design" / "sounds" / "NOTES.md").write_text(notes, encoding="utf-8")
    for tier, result in measurements.items():
        print(f"{folder.relative_to(root)}/{tier}.wav  {result['audible_end']:.2f} s to -50 dB")


if __name__ == "__main__":
    main()
