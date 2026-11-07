"""Cuadro de torneo v10. Presentación aislada: no modifica el motor del partido."""
import math
import os
import random
import wave
from presentation import asset, screen_change
from functools import lru_cache

WHITE = '#ffffff'
GOLD = '#ffd400'
DARK = '#06351b'


def champion_focus(event, done):
    return done or (event and event['champion'])


def audio_seconds(path, fallback):
    try:
        with wave.open(path, 'rb') as sound:
            return sound.getnframes() / sound.getframerate()
    except (OSError, wave.Error):
        return fallback


def path_point(path, progress):
    lengths = [math.dist(a, b) for a, b in zip(path, path[1:])]
    target = max(0, min(1, progress)) * sum(lengths)
    for i, length in enumerate(lengths):
        if target <= length and length > 0:
            t = target / length
            return tuple(a + (b-a)*t for a, b in zip(path[i], path[i+1]))
        target -= length
    return path[-1]


@lru_cache(maxsize=8)
def bracket_geometry(width, height):
    """Reorganiza filas, márgenes y columnas; nunca gira una imagen."""
    portrait = height > width
    top = max(100, min(width, height)*.18)
    bottom = height - max(90, min(width, height)*.16)
    span = max(100, bottom-top)
    margin = width*.075
    columns = [margin, width*.22, width*.36, width*.44]
    levels = []
    for stage in range(4):
        count = 8 // (2**stage)
        row = []
        for side in range(2):
            x = columns[stage] if side == 0 else width-columns[stage]
            for j in range(count):
                # Más altura entre fichas en vertical, columnas amplias en horizontal.
                y = top + span*(j+.5)/count
                if stage == 3:
                    y = top + span*(.37 if side == 0 else .63)
                row.append((x, y))
        levels.append(row)
    levels.append([(width/2, top+span/2)])
    radius = min(width*(.027 if portrait else .018), span/27, 26)
    return levels, max(5, radius)


def connection(a, b):
    middle = (a[0]+b[0])/2
    return [a, (middle, a[1]), (middle, b[1]), b]


def make_fragments(kind, rng):
    """Tres particiones convexas recortadas contra el disco, sin perder la camiseta."""
    disk = [(math.cos(i*math.tau/48), math.sin(i*math.tau/48)) for i in range(48)]
    def clip(poly, nx, ny, c):
        out = []
        for p, q in zip(poly, poly[1:]+poly[:1]):
            dp, dq = p[0]*nx+p[1]*ny-c, q[0]*nx+q[1]*ny-c
            if dp <= 0: out.append(p)
            if (dp < 0) != (dq < 0):
                t = dp/(dp-dq)
                out.append((p[0]+(q[0]-p[0])*t, p[1]+(q[1]-p[1])*t))
        return out
    pieces = []
    if kind == 0:
        center = (rng.uniform(-.2,.2), rng.uniform(-.2,.2))
        angles = sorted(i*math.tau/9+rng.uniform(-.12,.12) for i in range(9))
        rim = [(math.cos(a), math.sin(a)) for a in angles]
        pieces = [[center, p, q] for p,q in zip(rim, rim[1:]+rim[:1])]
    elif kind == 1:
        cuts = [-1, -.55+rng.uniform(-.1,.1), rng.uniform(-.15,.15), .55+rng.uniform(-.1,.1), 1]
        for a,b in zip(cuts,cuts[1:]):
            strip = clip(clip(disk,1,0,b),-1,0,-a)
            cut = rng.uniform(-.3,.3)
            pieces += [clip(strip,0,1,cut), clip(strip,0,-1,-cut)]
    else:
        tilt = rng.uniform(-.35,.35)
        for i in range(3):
            for j in range(3):
                p = disk
                for edge in ((1,tilt,-1+(i+1)*2/3),(-1,-tilt,1-i*2/3),
                             (0,1,-1+(j+1)*2/3),(0,-1,1-j*2/3)):
                    p = clip(p,*edge)
                pieces.append(p)
    return [dict(poly=p, drift=(rng.uniform(-.16,.16), rng.uniform(-.16,.16)),
                 vx=rng.uniform(-55,55), vy=rng.uniform(-90,-25)) for p in pieces if len(p)>=3]


class TournamentView:
    def init_bracket(self):
        self.bracket_levels = [list(self.round_teams)] + [[None]*n for n in (8,4,2,1)]
        self.bracket_scores = {}
        self.broken = {}
        self.fragment_age = 0.0
        self.bracket_events = []
        self.bracket_event = None
        self.bracket_camera = None
        self.bracket_done = False
        self.bracket_sound = None
        self.bracket_audio_cache = {}
        self.defeat_music = None
        self.bracket_orientation = 'vertical' if self.ch > self.cw else 'horizontal'
        self.bracket_clock = self.last_t
        self.advance_duration = audio_seconds(self.asset_path('avanzar_nivel.wav'), 10.031)
        self.defeat_duration = audio_seconds(self.asset_path('perder.wav'), 7.872)

    def asset_path(self, name):
        return asset('sounds','effects',name)

    @screen_change
    def orient_bracket(self, mode):
        self.bracket_orientation = mode
        # Android: pedir orientación real a la actividad. PC: cambiar la ventana.
        if 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_ROOT' in os.environ:
            try:
                from jnius import autoclass
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                activity.setRequestedOrientation(1 if mode == 'vertical' else 0)
            except Exception:
                pass  # Sigue adaptándose al tamaño real aunque el sistema no permita el giro.
        else:
            from kivy.core.window import Window
            short, long = sorted((int(Window.width), int(Window.height)))
            Window.size = (short,long) if mode == 'vertical' else (long,short)
        self.recalc()
        self.render()

    def play_bracket_sound(self, filename):
        if not self.snd.on:
            return
        try:
            from kivy.core.audio import SoundLoader
            if self.bracket_sound:
                self.bracket_sound.stop()
            if filename not in self.bracket_audio_cache:
                self.bracket_audio_cache[filename] = SoundLoader.load(self.asset_path(filename))
            self.bracket_sound = self.bracket_audio_cache[filename]
            if self.bracket_sound:
                self.bracket_sound.volume = .8
                self.bracket_sound.play()
        except Exception:
            self.bracket_sound = None

    @screen_change
    def finish_user_match(self, winner, text):
        if self.state not in ('post','match','pens'):
            return
        stage = self.round
        res, winners = [], []
        self.bracket_events = []
        for i,(a,b) in enumerate(self.pairs()):
            mine = self.user in (a,b)
            w, result = (winner, text) if mine else self.sim_match(a,b)
            winners.append(w)
            res.append(('* ' if mine else '')+result)
            self.bracket_scores[(stage,i)] = result
            src = 2*i + (0 if w == a else 1)
            loser = 2*i + (1 if w == a else 0)
            if not mine or winner == self.user:
                team = b if w == a else a
                self.broken[(stage,loser)] = (team, make_fragments(random.randrange(3), random))
            event = dict(stage=stage, src=src, dest=i, loser=loser,
                         team=w, mine=mine, losing=mine and w != self.user,
                         champion=mine and w == self.user and stage == 3)
            if mine:
                self.bracket_events.append(event)
            else:
                self.bracket_levels[stage+1][i] = w
        self.results.append(res)
        self.fragment_age = 0.0
        self.round_teams = winners
        if winner == self.user and stage < 3:
            self.round += 1
        self.music.stop()
        self.state = 'bracket'
        self.recalc()
        self.next_bracket_event()
        self.render()

    def next_bracket_event(self):
        if not self.bracket_events:
            self.bracket_event = None
            return
        event = self.bracket_events.pop(0)
        event['elapsed'] = 0.0
        event['sound_started'] = False
        event['arrived'] = False
        event['duration'] = self.advance_duration
        self.bracket_event = event
        event['advance_audio'] = False
        if not getattr(getattr(self,'visual',None),'transitioning',False):
            self.start_bracket_audio()

    def start_bracket_audio(self):
        event=self.bracket_event
        if event and not event['advance_audio']:
            event['advance_audio']=True
            event['elapsed']=0.0
            self.play_bracket_sound('avanzar_nivel.wav')

    def start_defeat_music(self):
        if not getattr(self.snd,'on',True):return
        from kivy.core.audio import SoundLoader
        if self.defeat_music is None:
            self.defeat_music=SoundLoader.load(asset('sounds','music','derrota_musica.wav'))
        if self.defeat_music:
            self.defeat_music.volume=.24
            self.defeat_music.play()


    def bracket_update(self, dt):
        self.fragment_age += max(0,dt)
        e = self.bracket_event
        if not e:
            return
        e['elapsed'] += max(0,dt)
        t = e['elapsed']
        if t >= e['duration']/2 and not e['arrived']:
            self.bracket_levels[e['stage']+1][e['dest']] = e['team']
            e['arrived'] = True
        if e['losing']:
            zoom_start = e['duration']/2+2
            fall_start = zoom_start+2
            if t >= zoom_start and not e.get('defeat_music_started'):
                e['defeat_music_started']=True
                self.start_defeat_music()
            if t >= fall_start and not e['sound_started']:
                e['sound_started'] = True
                self.music.stop()
                self.play_bracket_sound('perder.wav')
                key = (e['stage'], e['loser'])
                self.broken[key] = (self.user, make_fragments(random.randrange(3),random))
            if t >= fall_start+self.defeat_duration+.25:
                if self.bracket_sound: self.bracket_sound.stop()
                self.bracket_event = None
                if self.defeat_music:self.defeat_music.stop()
                self.restart_tournament()
        elif e['champion']:
            if t >= e['duration'] and not e['sound_started']:
                e['sound_started'] = True
                self.snd.play('campeon',self.user,9)
                if hasattr(self,'visual'):self.visual.show_goal(3)
            if t >= e['duration']+7:
                self.bracket_done = True
                self.bracket_event = None
                self.bracket_camera = ('champion', 1)
        elif t >= e['duration']:
            self.next_bracket_event()

    def draw_bracket(self):
        from main import ROUND_NAMES, SHORT, ABBR, kit_for, clip, CIRCLE
        cv, w, h = self.cv, self.cw, self.ch
        self.pitch_bg()
        current = self.bracket_event
        special = self.bracket_done or (current and (
            (current['champion'] and current['elapsed'] >= current['duration']) or
            (current['losing'] and current['elapsed'] > current['duration']/2+2)))
        if not special:
            self.title(max(28,self.u*2), ROUND_NAMES[self.round].upper(), 1.8)
        bh = max(32,min(48,self.u*2.8))
        bw = min(w*.29,180)
        for x, mode, label in ((w*.33,'vertical','VERTICAL'),(w*.67,'horizontal','HORIZONTAL')):
            if not special:
                self.button(x,max(66,self.u*5),bw,bh,label,lambda mode=mode:self.orient_bracket(mode),
                            bg=GOLD if ((h>w)==(mode=='vertical')) else '#126436',font=self.F(.95))
        nodes, radius = bracket_geometry(w,h)
        e = self.bracket_event
        zoom, target, fall_time = 1.0, (w/2,h/2), None
        camera_progress = 0.0
        if e:
            t = e['elapsed']
            if e['losing']:
                zstart = e['duration']/2+2
                p = max(0,min(1,(t-zstart)/2))
                camera_progress = p*p*(3-2*p)
                target = nodes[e['stage']][e['loser']]
                zoom = 1+(min(w,h)/(radius*5)-1)*p*p*(3-2*p)
                if t >= zstart+2: fall_time = t-zstart-2
            elif e['champion'] and t >= e['duration']:
                p = min(1,(t-e['duration'])/2)
                camera_progress = p*p*(3-2*p)
                target = nodes[4][0]
                zoom = 1+(min(w,h)/(radius*6)-1)*p*p*(3-2*p)
        if self.bracket_camera:
            camera_progress = 1.0
            target = nodes[4][0]
            zoom = min(w,h)/(radius*6)
        def screen(point):
            # La cámara solo se activa en derrota o campeonato.
            center = (w/2+(target[0]-w/2)*camera_progress,
                      h/2+(target[1]-h/2)*camera_progress)
            return (w/2+(point[0]-center[0])*zoom, h/2+(point[1]-center[1])*zoom) if zoom != 1 else point
        r = radius*zoom
        for stage in range(4):
            if special and camera_progress > .95:
                continue
            for i, point in enumerate(nodes[stage]):
                dest = nodes[stage+1][i//2]
                line = connection(point,dest)
                for a,b in zip(line,line[1:]):
                    cv.create_line(*screen(a),*screen(b),fill=WHITE,width=max(3,radius*.24))
        for stage,row in enumerate(self.bracket_levels):
            for i,team in enumerate(row):
                if special and camera_progress > .95:
                    focus = (4,0) if champion_focus(current,self.bracket_done) else (current['stage'],current['loser'])
                    if (stage,i) != focus:
                        continue
                x,y = screen(nodes[stage][i])
                key = (stage,i)
                if key in self.broken:
                    broken_team, pieces = self.broken[key]
                    base, shapes, edge = kit_for(broken_team)
                    falling = fall_time if e and e['losing'] and key==(e['stage'],e['loser']) else None
                    for piece in pieces:
                        dx,dy = piece['drift']
                        spread = min(1,self.fragment_age/.7)
                        dx,dy = dx*spread,dy*spread
                        if falling is not None:
                            dx += piece['vx']*falling/max(r,1)
                            dy += (piece['vy']*falling+180*falling*falling)/max(r,1)
                        def polygon(poly, color):
                            flat = [v for px,py in poly for v in (x+(px+dx)*r,y+(py+dy)*r)]
                            cv.create_polygon(flat,fill=color,outline=DARK,width=1)
                        polygon(piece['poly'],base)
                        # Cache intersections once, retaining every piece of uniform detail.
                        if 'layers' not in piece:
                            layers=[]
                            area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(piece['poly'],piece['poly'][1:]+piece['poly'][:1]))
                            sign=1 if area>0 else -1
                            for shape,color in shapes:
                                poly=shape
                                for a,b in zip(piece['poly'],piece['poly'][1:]+piece['poly'][:1]):
                                    nx,ny=sign*(b[1]-a[1]),sign*(a[0]-b[0])
                                    poly=clip(poly,nx,ny,nx*a[0]+ny*a[1]) if poly else []
                                if len(poly)>=3:layers.append((poly,color))
                            piece['layers']=layers
                        for poly,color in piece['layers']:polygon(poly,color)
                    continue
                hidden = False  # Keep original at every previous round; only a visual copy moves.
                if not hidden:
                    if team:
                        if e and team==self.user and stage==e['stage'] and i==e['src'] and not e['losing']:
                            hr=r*1.25
                            cv.create_oval(x-hr,y-hr,x+hr,y+hr,outline=GOLD,width=max(2,r*.14))
                        self.jersey(x,y,r,team)
                    else:
                        cv.create_oval(x-r,y-r,x+r,y+r,fill=WHITE,outline=WHITE,width=1)
                if zoom == 1:
                    label = ABBR.get(team,'') if team else ('CAMPEÓN' if stage==4 else '')
                    cv.create_text(x,y+r+max(8,radius*.7),text=label,fill=GOLD if team==self.user else WHITE,
                                   font=('Helvetica',-max(7,int(radius*.68)),'bold'))
        if e:
            p = min(1,e['elapsed']/(e['duration']/2))
            x,y = screen(path_point(connection(nodes[e['stage']][e['src']],nodes[e['stage']+1][e['dest']]),p))
            if (not e['losing'] or not e['arrived']) and not (e['champion'] and special):
                halo = r*(1.25+.16*math.sin(max(0,e['elapsed']-e['duration']/2)*math.tau))
                if not e['losing']:
                    cv.create_oval(x-halo,y-halo,x+halo,y+halo,outline=GOLD,width=max(2,r*.14))
                self._moving_token=True
                self.jersey(x,y,r,e['team'])
                self._moving_token=False
        champion = self.bracket_done or (e and e['champion'] and e['elapsed']>=e['duration'])
        if champion:
            x,y = screen(nodes[4][0])
            t = e['elapsed']-e['duration'] if e else 7
            lift = min(1,max(0,(t-1)/2))
            for j in range(18):
                angle = j*math.tau/18+t*.25
                dist = r*(1.8+.3*math.sin(t+j))
                cx,cy = x+math.cos(angle)*dist,y+math.sin(angle)*dist
                cv.create_oval(cx-2,cy-2,cx+2,cy+2,fill=WHITE,width=0)
            cup_y = y-r*(.1+1.75*lift)
            # The supplied token/arms emblem stays attached to the jersey disc.
            self.visual.png('brazos_ganador.png',x-r*1.15,y-r*1.1-r*.25*lift,r*2.3,r*2.3,slot='champion-arms')
            self.jersey(x,y,r*.77,self.user)
            cup_h=r*1.8
            self.visual.png('copa_render.png',x-cup_h*130/300/2,cup_y-cup_h*.7,
                            cup_h*130/300,cup_h,slot='champion-cup')
            cv.create_text(w/2,h*.78,text='¡CAMPEÓN DEL MUNDO!',fill=GOLD,font=self.F(1.7),width=w*.94)
        if hasattr(self,'visual'):self.visual.draw_goal()
        if fall_time is not None:
            darkness = min(1,fall_time/max(.1,self.defeat_duration-.25))
            cv.create_rectangle(0,0,w,h,fill='#000000',width=0,alpha=darkness)
            if darkness < .96:
                cv.create_text(w/2,h*.22,text='PERDISTE',fill=GOLD,font=self.F(3),width=w*.9)
            self.buttons = []
        elif zoom != 1 and not self.bracket_done:
            self.buttons = []
        if not e:
            if self.bracket_done:
                self.button(w/2,h-42,min(w*.8,330),44,'VOLVER AL MENÚ',self.restart_tournament,font=self.F(1.05))
            else:
                opp = next(b if a==self.user else a for a,b in self.pairs() if self.user in (a,b))
                if self.results:
                    mine = next((x[2:] for x in self.results[-1] if x.startswith('* ')), '')
                    cv.create_text(w/2,h-78,text=mine,fill=WHITE,font=self.F(.85),width=w*.92)
                self.button(w/2,h-38,min(w*.8,330),44,'JUGAR PARTIDO',lambda:self.start_match(opp),font=self.F(1.05))
