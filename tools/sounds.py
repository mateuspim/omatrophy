#!/usr/bin/env python3
"""Write assets/sounds/<tier>.wav: one chime family, four tiers.

Every tier is mallet-and-glass notes in C major, so they sound related; a
higher tier adds notes, brightness and shimmer. Platinum is the only long
one: it plays when the platinum trophy lands. Run from the repo root after
changing a recipe:
  python3 tools/sounds.py
"""
import math, os, random, struct, wave

RATE = 48000
OUT = 'assets/sounds'


def hz(note):
    """'C6' -> frequency; sharps as 'F#5'."""
    names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    semi = names[note[0]] + (1 if '#' in note else 0)
    octave = int(note[-1])
    return 440 * 2 ** ((semi + 12 * (octave + 1) - 69) / 12)


# Partials as (ratio, gain, decay seconds). A mallet is warm and short; glass
# adds a bright, slightly inharmonic top that rings on.
MALLET = [(1, 1.0, 0.16), (2, 0.35, 0.07), (3.01, 0.12, 0.04), (4.2, 0.05, 0.03)]
GLASS = [(1, 1.0, 0.5), (2, 0.5, 0.35), (2.76, 0.32, 0.25), (5.4, 0.14, 0.14), (8.93, 0.05, 0.08)]


def note(buf, start, freq, gain, partials, length=4.0, attack=0.003):
    """Add one struck note to buf at start seconds."""
    i0 = int(start * RATE)
    for ratio, g, decay in partials:
        f = freq * ratio
        if f > RATE / 2.2:
            continue
        w = 2 * math.pi * f / RATE
        k = math.exp(-1 / (decay * RATE))
        env = gain * g
        a = int(attack * RATE)
        for n in range(int(min(length, decay * 7) * RATE)):
            if i0 + n >= len(buf):
                break
            ramp = n / a if n < a else 1
            buf[i0 + n] += env * ramp * math.sin(w * n)
            env *= k


def pad(buf, start, freqs, gain, rise, length):
    """A soft chord that swells in and fades out, under the notes."""
    i0, rise_n, total = int(start * RATE), int(rise * RATE), int(length * RATE)
    for f in freqs:
        for v, detune in ((0.5, 0.998), (0.5, 1.002)):
            w = 2 * math.pi * f * detune / RATE
            for n in range(total):
                if i0 + n >= len(buf):
                    break
                env = (n / rise_n if n < rise_n else math.exp(-(n - rise_n) / (0.35 * total)))
                buf[i0 + n] += gain * v * env * math.sin(w * n)


def sparkle(buf, start, count, spread, gain, seed):
    """Tiny high pings scattered after start: the glitter in the sound."""
    rng = random.Random(seed)
    for _ in range(count):
        t = start + rng.random() * spread
        f = hz(rng.choice(['C', 'E', 'G']) + '8') * rng.choice([1, 1.5])
        note(buf, t, f, gain * (0.5 + rng.random() / 2), [(1, 1, 0.07), (2, 0.2, 0.04)], 0.4)


def reverb(buf, mix=0.22):
    """A small room: four feedback combs into the dry signal."""
    out = list(buf)
    for delay_ms, fb in ((29.7, 0.72), (37.1, 0.7), (41.1, 0.68), (43.7, 0.66)):
        d = int(delay_ms / 1000 * RATE)
        comb = [0.0] * len(buf)
        for n in range(d, len(buf)):
            comb[n] = buf[n - d] + fb * comb[n - d]
        for n in range(len(buf)):
            out[n] += mix / 4 * comb[n]
    return out


def write(name, buf, peak=0.7):
    top = max(abs(s) for s in buf) or 1
    # Trim the tail below -50 dB, then fade the last 30 ms so it never clicks.
    end = len(buf)
    while end > 0 and abs(buf[end - 1]) < top * 0.003:
        end -= 1
    buf = buf[:end]
    fade = int(0.03 * RATE)
    for n in range(max(0, end - fade), end):
        buf[n] *= (end - n) / fade
    os.makedirs(OUT, exist_ok=True)
    with wave.open(f'{OUT}/{name}.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b''.join(struct.pack('<h', int(s / top * peak * 32767)) for s in buf))
    print(f'{OUT}/{name}.wav  {end / RATE:.2f} s')


def bronze():
    # Two warm mallet notes, a fifth apart: a quick "tuk-ting".
    buf = [0.0] * int(1.5 * RATE)
    note(buf, 0.00, hz('G5'), 0.8, MALLET)
    note(buf, 0.09, hz('D6'), 1.0, MALLET)
    return reverb(buf, 0.15)


def silver():
    # A rising major triad, glass over mallet.
    buf = [0.0] * int(2.0 * RATE)
    for i, n in enumerate(['C6', 'E6', 'G6']):
        note(buf, i * 0.075, hz(n), 0.8 + i * 0.1, MALLET)
        note(buf, i * 0.075, hz(n), 0.35, GLASS)
    return reverb(buf, 0.2)


def gold():
    # The triad to the octave, a soft chord under it, then glitter.
    buf = [0.0] * int(3.0 * RATE)
    pad(buf, 0.0, [hz('C5'), hz('G5'), hz('E6')], 0.07, 0.12, 1.6)
    for i, n in enumerate(['C6', 'E6', 'G6', 'C7']):
        note(buf, i * 0.065, hz(n), 0.7 + i * 0.1, MALLET)
        note(buf, i * 0.065, hz(n), 0.5, GLASS)
    sparkle(buf, 0.28, 9, 0.6, 0.12, seed=3)
    return reverb(buf, 0.25)


def platinum():
    # Lands with the trophy: a struck chord, a two-octave climb, a held
    # major-seventh shimmer and a long tail of glitter.
    buf = [0.0] * int(4.5 * RATE)
    pad(buf, 0.0, [hz('C4'), hz('G4'), hz('E5'), hz('B5')], 0.08, 0.25, 3.0)
    for n in ['C5', 'G5', 'E6']:
        note(buf, 0.0, hz(n), 0.6, MALLET)
        note(buf, 0.0, hz(n), 0.45, GLASS)
    for i, n in enumerate(['C6', 'E6', 'G6', 'B6', 'C7', 'E7', 'G7']):
        note(buf, 0.22 + i * 0.07, hz(n), 0.5 + i * 0.04, GLASS)
    note(buf, 0.75, hz('C7'), 0.7, GLASS)
    note(buf, 0.75, hz('G7'), 0.3, GLASS)
    sparkle(buf, 0.6, 22, 1.8, 0.1, seed=7)
    return reverb(buf, 0.3)


if __name__ == '__main__':
    for name, make in (('bronze', bronze), ('silver', silver), ('gold', gold), ('platinum', platinum)):
        write(name, make())
