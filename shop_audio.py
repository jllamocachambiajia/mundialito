"""Sonidos originales de tienda: una reproducción por compra confirmada."""
import time


class ShopAudio:
    FILES = {'cosmetic': 'compra_cosmetico.wav', 'passive': 'compra_pasiva.wav',
             'coin': 'monedita.wav'}

    def __init__(self, enabled, loader=None, clock=None):
        self.enabled = enabled
        self.clock = clock or time.monotonic
        self.sounds = {}
        self.last_coin = 0.0
        if loader is None:
            try:
                from kivy.core.audio import SoundLoader
                from presentation import asset
                loader = lambda name: SoundLoader.load(asset('sounds', 'effects', name))
            except Exception:
                loader = lambda name: None
        for key, name in self.FILES.items():
            try:
                self.sounds[key] = loader(name)
            except Exception:
                self.sounds[key] = None

    def _play(self, key, volume):
        if not self.enabled():
            return False
        sound = self.sounds.get(key)
        if sound is None:
            return False
        try:
            sound.stop()
            sound.volume = volume
            sound.play()
            return True
        except Exception:
            return False

    def purchase(self, kind):
        # Solo ShopController llama aquí tras una transacción exitosa.
        return self._play('passive' if kind == 'passive' else 'cosmetic', .42)

    def coin_tick(self):
        now = self.clock()
        if now - self.last_coin < .055:
            return False
        self.last_coin = now
        return self._play('coin', .20)

    def stop(self):
        for sound in self.sounds.values():
            try:
                if sound:
                    sound.stop()
            except Exception:
                pass
