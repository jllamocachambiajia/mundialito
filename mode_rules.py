"""Mode/navigation rules are separate from the unchanged match simulation."""
from dataclasses import dataclass


@dataclass
class Navigation:
    target: str = ''
    pressed_at: float = 0
    busy: bool = False
    shown: bool = False
    shown_at: float = 0
    VISUAL_DELAY = .5
    LOADING_DURATION = 5.0

    def begin(self, target, now):
        if self.busy:
            return False
        self.target, self.pressed_at = target, now
        self.busy, self.shown = True, False
        return True

    def update(self, now):
        if not self.busy:
            return None
        if not self.shown and now >= self.pressed_at+self.VISUAL_DELAY:
            self.shown = True
            # Absolute deadline, never frame count, even after a late frame.
            self.shown_at = self.pressed_at+self.VISUAL_DELAY
            return 'show'
        if self.shown and now >= self.shown_at+self.LOADING_DURATION:
            self.busy = False
            return 'complete'
        return None


def next_country(index, delta, count):
    return (index+delta) % count
