"""Génère le pack de sons "classic" par synthèse -- pas de fichier audio
externe à trouver/télécharger, donc aucune question de droits d'auteur.
Utilise uniquement la bibliothèque standard (wave, struct, math).

Relancer ce script régénère les fichiers dans
web/assets/sounds/packs/classic/ -- pratique si tu veux ajuster les
fréquences/durées plus tard sans dépendre de moi.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "web" / "assets" / "sounds" / "packs" / "classic"


def _envelope(i: int, total: int, fade_samples: int) -> float:
    """Fade in/out linéaire pour éviter les clics au début/à la fin."""
    if i < fade_samples:
        return i / fade_samples
    if i > total - fade_samples:
        return (total - i) / fade_samples
    return 1.0


def _tone(freq_hz: float, duration_s: float, volume: float = 0.5) -> list[float]:
    total = int(SAMPLE_RATE * duration_s)
    fade = max(1, int(SAMPLE_RATE * 0.01))  # 10ms de fondu
    return [
        volume * _envelope(i, total, fade) * math.sin(2 * math.pi * freq_hz * i / SAMPLE_RATE)
        for i in range(total)
    ]


def _sweep(freq_start: float, freq_end: float, duration_s: float, volume: float = 0.5) -> list[float]:
    """Glissando linéaire d'une fréquence à l'autre."""
    total = int(SAMPLE_RATE * duration_s)
    fade = max(1, int(SAMPLE_RATE * 0.01))
    samples = []
    phase = 0.0
    for i in range(total):
        freq = freq_start + (freq_end - freq_start) * (i / total)
        phase += 2 * math.pi * freq / SAMPLE_RATE
        samples.append(volume * _envelope(i, total, fade) * math.sin(phase))
    return samples


def _sequence(*parts: list[float]) -> list[float]:
    result: list[float] = []
    for part in parts:
        result.extend(part)
    return result


def _silence(duration_s: float) -> list[float]:
    return [0.0] * int(SAMPLE_RATE * duration_s)


def _write_wav(name: str, samples: list[float]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.wav"
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)  # 16 bits
        f.setframerate(SAMPLE_RATE)
        frames = b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
            for s in samples
        )
        f.writeframes(frames)
    print(f"  {path.relative_to(OUTPUT_DIR.parents[3])}")


SOUNDS = {
    "prep_start": lambda: _tone(440, 0.2),
    "shoot_start": lambda: _tone(880, 0.5),
    "warning_orange": lambda: _tone(660, 0.2),
    "countdown_tick": lambda: _tone(550, 0.12),
    # Urgence : alternance de deux tons, façon alarme -- doit se distinguer
    # sans ambiguïté de tous les autres sons.
    "emergency_start": lambda: _sequence(
        _tone(220, 0.15), _tone(330, 0.15), _tone(220, 0.15), _tone(330, 0.15),
    ),
    # Fin d'urgence : un seul glissando montant, rassurant ("tout va bien").
    "emergency_end": lambda: _sweep(500, 740, 0.3),
    "end_of_volee": lambda: _tone(500, 0.3),
    # Pause manuelle du DOS (différente de la fin de volée) : un glissando
    # descendant pour la mise en pause, montant pour la reprise.
    "pause_start": lambda: _sweep(600, 400, 0.25),
    "pause_end": lambda: _sweep(400, 600, 0.25),
    # Fin de concours : petite fanfare à deux notes montantes.
    "end_of_match": lambda: _sequence(_tone(700, 0.25), _silence(0.03), _tone(1000, 0.4)),
}


def main() -> None:
    print("Génération du pack de sons 'classic' :")
    for name, generator in SOUNDS.items():
        _write_wav(name, generator())
    print("Terminé.")


if __name__ == "__main__":
    main()
