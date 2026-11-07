"""Reusable PNG resources, bounded GIF and Kivy screen transitions."""
import functools
import json
import os
import time
from pathlib import Path
from kivy.animation import Animation
from kivy.graphics import Color, Rectangle, InstructionGroup
from kivy.core.image import Image as CoreImage

BASE = Path(__file__).resolve().parent

def asset(*parts):
    return str(BASE.joinpath('assets', *parts))

def screen_change(fn):
    @functools.wraps(fn)
    def call(self, *args, **kwargs):
        if getattr(self, '_transition_commit', False) or not hasattr(self, 'visual'):
            return fn(self, *args, **kwargs)
        self.visual.transition(lambda: fn(self, *args, **kwargs))
    return call

class VisualResources:
    def __init__(self, game):
        self.game = game
        self.images = {}
        self.textures = {}
        self.transitioning = False
        self.gif_until = 0
        self.gif_started = 0
        self.gif = None
        self.frames = []
        self.timings = []
        self.metrics = {'frames': 0, 'render_ms': [], 'update_ms': []}

    def png(self, filename, x, y, width, height, slot=None):
        """Reuse PNG textures and draw instructions without changing screen placement."""
        cv = self.game.cv
        key = (filename, slot if slot is not None else (round(x), round(y), round(width), round(height)))
        cached = self.images.get(key)
        if cached is None:
            image = self.textures.get(filename)
            if image is None:
                image = CoreImage(asset('images', filename), keep_data=False)
                self.textures[filename] = image
            group = InstructionGroup()
            group.add(Color(1, 1, 1, 1))
            rectangle = Rectangle(texture=image.texture)
            group.add(rectangle)
            cached = (group, rectangle)
            self.images[key] = cached
        group, rectangle = cached
        rectangle.pos = (x, cv.height-y-height)
        rectangle.size = (width, height)
        cv.canvas.add(group)

    def show_goal(self, seconds=3):
        self.preload_gif()
        from main import vnow
        self.gif_started = vnow(); self.gif_until = self.gif_started+seconds

    def preload_gif(self):
        if self.gif is None:
            # PIL provider retains the supplied 500x500 GIF resolution and transparency.
            self.gif = CoreImage(asset('animations', 'gol.gif'), anim_delay=-1, keep_data=False)
            self.frames = list(self.gif.image.textures)
            manifest = json.loads(Path(asset('animations', 'gol_timing.json')).read_text())
            self.timings = manifest['cumulative_seconds']

    def draw_goal(self):
        from main import vnow
        now = vnow()
        if now >= self.gif_until or not self.frames:
            return
        import bisect
        elapsed = now-self.gif_started
        index = min(len(self.frames)-1, bisect.bisect_right(self.timings, elapsed))
        g = self.game
        size = min(g.cw*.27, g.ch*.2, 170)
        with g.cv.canvas:
            Color(1,1,1,1)
            Rectangle(texture=self.frames[index], pos=((g.cw-size)/2, g.ch-g.hud-size),size=(size,size))

    def transition(self, action):
        if self.transitioning:
            return
        from main import clock_pause, vnow
        g=self.game
        self.transitioning=True
        if g.state in ('match','pens'):
            g.music.pause()
        clock_pause(True)
        Animation.cancel_all(g.cv, 'opacity')
        def midpoint(*_):
            g._transition_commit=True
            try:
                action()
                g.render()
            finally:
                g._transition_commit=False
            clock_pause(True)
            anim=Animation(opacity=1, duration=.32, t='in_out_quad')
            anim.bind(on_complete=complete)
            anim.start(g.cv)
        def complete(*_):
            self.transitioning=False
            clock_pause(g.paused)
            g.last_t=vnow()
            if g.state == 'bracket' and g.bracket_event:
                g.start_bracket_audio()
            if g.state in ('match','pens') and not g.paused:
                g.music.resume()
        fade=Animation(opacity=0, duration=.28, t='in_out_quad')
        fade.bind(on_complete=midpoint)
        fade.start(g.cv)

    def record(self, update, render):
        self.metrics['frames']+=1
        for key,value in (('update_ms',update*1000),('render_ms',render*1000)):
            samples=self.metrics[key];samples.append(value)
            if len(samples)>300:del samples[:100]
