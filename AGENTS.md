# Architecture
- Keep match simulation/AI/penalty rules in main.py and tournament presentation in TournamentView so visual updates do not change mechanics.
- Load bundled media only through relative assets paths; never synthesize sound or download resources during play.
- Use one atomic opacity transition controller and pause the simulation clock during transitions to prevent hidden actions.
- Cache SVG instructions, static pitch geometry and clipped fragment layers without downsampling graphics.
