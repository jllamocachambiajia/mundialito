# Architecture
- Keep match simulation/AI/penalty rules in main.py and tournament presentation in TournamentView so visual updates do not change mechanics.
- Load bundled media only through relative assets paths; never synthesize sound or download resources during play.
- Use one atomic opacity transition controller and pause the simulation clock during transitions to prevent hidden actions.
- Cache bundled PNG textures/draw instructions, static pitch geometry and clipped fragment layers to avoid repeated decoding; keep PNG loading in presentation.py so rendering changes cannot alter match rules.
- Keep fire rules in fire.py with an optional substep collision policy; ordinary and penalty collision paths retain their original behavior.
- Route every fire exit through FireState.finish and use the pause-aware gameplay clock for expiry; collision policy checks expiry before each pair so both teams recover symmetrically.
