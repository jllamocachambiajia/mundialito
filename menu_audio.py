"""One native looping menu stream with monotonic envelopes and one transition SFX."""
import time
import wave
from presentation import asset


class MenuAudio:
    LEVEL = .22
    EDGE = 1.5

    def __init__(self, enabled, loader=None, clock=time.monotonic):
        if loader is None:
            from kivy.core.audio import SoundLoader
            loader = SoundLoader.load
        self.clock, self.enabled = clock, enabled
        def safe(path):
            try:
                return loader(path)
            except Exception:
                return None  # sonido ausente o no compatible: el juego sigue sin él
        self.music = safe(asset('sounds', 'music', 'musica.wav'))
        self.effect = safe(asset('sounds', 'effects', 'carga.wav'))
        try:
            with wave.open(asset('sounds', 'music', 'musica.wav')) as f:
                self.duration = f.getnframes() / f.getframerate()
        except Exception:
            self.duration = 87.516
        self.started = None
        self.depart = None
        self.depart_volume = 0
        self.suspended = None
        if self.music:
            self.music.loop = True
            self.music.volume = 0

    def start(self):
        self.stop()
        self.started = self.clock()
        if self.music:
            self.music.volume = 0
            self.music.play()

    def stop(self):
        if self.music:
            self.music.stop()
            self.music.volume = 0
        self.started = self.depart = self.suspended = None

    def leave(self):
        if self.started is not None and self.depart is None:
            self.depart = self.clock()
            self.depart_volume = self.music.volume if self.music else 0

    def transition_effect(self):
        if self.effect:
            self.effect.stop()
            self.effect.volume = .6 if self.enabled() else 0
            self.effect.play()

    def update(self):
        if self.started is None or self.suspended is not None:
            return
        now = self.clock()
        if self.depart is not None:
            fraction = max(0, 1-(now-self.depart)/.5)
            volume = self.depart_volume*fraction
            if fraction == 0:
                self.stop()
                return
        else:
            position = (now-self.started) % self.duration
            # Native looping never stops the stream. Fade both sides of its seam.
            volume = self.LEVEL * min(1, position/self.EDGE, (self.duration-position)/self.EDGE)
        if self.music:
            self.music.volume = volume if self.enabled() else 0

    def suspend(self):
        if self.started is not None and self.suspended is None:
            self.suspended = self.clock()
            if self.music:
                self.music.stop()
        if self.effect:
            self.effect.stop()

    def resume(self):
        if self.suspended is None:
            return
        delay = self.clock()-self.suspended
        self.started += delay
        if self.depart is not None:
            self.depart += delay
        self.suspended = None
        if self.music:
            self.music.volume = 0
            self.music.play()
            self.music.seek((self.clock()-self.started) % self.duration)
        self.update()
