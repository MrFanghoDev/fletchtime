"""Petite démo pour valider visuellement le moteur, sans terminal : ouvrir
ce fichier dans Pydroid et appuyer sur "Run". Affiche le déroulé d'une
manche Indoor puis d'une manche Flint, étape par étape.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fletchtime_engine import (  # noqa: E402
    FlintConfig,
    FlintMode,
    IndoorConfig,
    IndoorMode,
    MatchEngine,
)


def play_a_few_steps(engine: MatchEngine, nb_steps: int) -> None:
    for _ in range(nb_steps):
        state = engine.current_state
        events = engine.pop_pending_events()
        print(
            f"  end={state.end_number}/{state.total_ends} "
            f"unit={state.unit_number} turn={state.current_turn or '-':4} "
            f"arrow={state.arrow_in_end or '-'} "
            f"phase={state.phase.value:9} time_left={state.time_left:5.1f}s "
            f"dist={state.distance_label:10} events={events}"
        )
        if state.finished:
            print("  -- terminé --")
            break
        engine.next()


def main() -> None:
    print("=== Indoor (2 séries x 6 volées x 5 flèches, réduit pour la démo) ===")
    indoor_cfg = IndoorConfig(series=1, ends_per_series=2)
    indoor_engine = MatchEngine(IndoorMode(indoor_cfg))
    play_a_few_steps(indoor_engine, 12)

    print()
    print("=== Flint (1 unité standard, réduit pour la démo) ===")
    flint_cfg = FlintConfig(units=1)
    flint_engine = MatchEngine(FlintMode(flint_cfg))
    play_a_few_steps(flint_engine, 30)


if __name__ == "__main__":
    main()
