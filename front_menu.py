"""New Kivy front end composed around the original Game; no duplicate match engine."""
import math
import random
import time
import uuid
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, Mesh
from presentation import asset
from local_store import LocalStore
from menu_audio import MenuAudio
from mode_rules import Navigation, next_country


class FrontMenu:
    def front_init(self):
        app = App.get_running_app()
        if app is None:
            raise RuntimeError('Create Game inside MundialApp.build or a running App')
        self.store = LocalStore(app.user_data_dir)
        self.nav = Navigation()
        self.mode = 'tournament'
        self.friend_index = 0
        self.friendly_id = None
        self.menu_audio = MenuAudio(lambda: self.snd.on)
        self.front_press = None
        self.front_paused_at = None
        self.front_error = ''
        self.cv.opacity = 1
        self.state = 'home'
        self.menu_audio.start()
        Window.bind(on_keyboard=self.front_keyboard)
        # Widget starts at its default 100x100 before attachment to Window.
        # Render again after layout AND whenever its position/size changes.
        self.cv.bind(pos=lambda *_: self.front_first_frame())
        Clock.schedule_once(lambda _: self.front_first_frame(), 0)
        Clock.schedule_once(lambda _: self.front_first_frame(), .1)

    def front_first_frame(self):
        self.recalc()
        self.render()

    def F(self, k, bold=True):
        return ('Oswald', -max(8, int(k*self.u)), 'normal')

    def front_font(self, pixels, title=False):
        return ('Teko' if title else 'Oswald', -max(8, int(pixels)), 'normal')

    def title(self, y, text, size=2.2, col='#ffd400'):
        self.cv.create_text(self.cw/2+2,y+2,text=text,fill='#052919',font=self.front_font(size*self.u,True),width=self.cw*.9)
        self.cv.create_text(self.cw/2,y,text=text,fill=col,font=self.front_font(size*self.u,True),width=self.cw*.9)

    def render(self):
        if not hasattr(self, 'nav'):
            return
        self.cv.delete('all')
        self.buttons = []
        if self.state == 'home':
            self.draw_home()
        elif self.state == 'loading':
            self.draw_loading()
        elif self.state == 'friends':
            self.draw_friends()
        elif self.state == 'friendly_post':
            self.draw_friendly_post()
        else:
            super().render()
            if self.state not in ('match','pens'):
                self.draw_back()

    def draw(self):
        if self.state in ('home','friends','loading','friendly_post'):
            self.render()
            return
        super().draw()
        self.draw_back()

    def go(self, state):
        if state == 'menu' and hasattr(self,'nav'):
            self.front_navigate('home')
            return
        return super().go(state)

    def restart_tournament(self):
        self.front_navigate('home')

    def front_cleanup(self):
        from main import clock_pause
        self.gen += 1
        self.paused = False
        clock_pause(False)
        self.drag = None
        self.pending = None
        self.pen_hold = 0
        self.music.stop()
        self.magnetic_finish()
        self.fire.clear()
        self.pausa.finish()
        self.ability_reset()
        self.gk_reset()
        self.visual.gif_until = 0
        self.bracket_event = None
        self.bracket_events = []
        self.bracket_levels = []
        self.round_teams = []
        self.results = []
        for name in ('bracket_sound','defeat_music'):
            sound = getattr(self,name,None)
            if sound: sound.stop()
        self.bodies = []
        self.ball = None
        self.cv.opacity = 1

    def front_navigate(self, target):
        if self.visual.transitioning or not self.nav.begin(target,time.monotonic()):
            return False
        # Trigger once, synchronously in the original touch-down handler.
        self.menu_audio.transition_effect()
        self.menu_audio.leave()
        from main import clock_pause
        if self.state in ('match','pens'):
            self.music.pause()
            self.magnetic_pause()
        clock_pause(True)
        return True

    def front_tick(self):
        if not hasattr(self,'nav') or self.front_paused_at is not None:
            return
        self.menu_audio.update()
        event = self.nav.update(time.monotonic())
        if event == 'show':
            self.menu_audio.stop()
            self.state = 'loading'
            self.cv.opacity = 1
            self.render()
        elif event == 'complete':
            target = self.nav.target
            self.front_cleanup()
            self._transition_commit = True
            try:
                if target == 'home':
                    self.mode = 'tournament'
                    self.friendly_id = None
                    self.selected_country = None
                    self.state = 'home'
                    self.menu_audio.start()
                elif target == 'tournament':
                    self.mode = 'tournament'
                    self.state = 'menu'  # Original country selector, unchanged.
                    self.selected_country = None
                elif target == 'friends':
                    self.mode = 'friendly'
                    self.state = 'friends'
                    self.friendly_stats = self.store.stats()
                elif target == 'friendly_match':
                    from main import TEAMS
                    self.mode = 'friendly'
                    self.user = tuple(TEAMS)[self.friend_index]
                    opponent = random.choice([n for n in TEAMS if n != self.user])
                    self.round = 0  # Uses the existing ordinary first-round match settings.
                    self.results = []
                    self.friendly_id = uuid.uuid4().hex
                    self.start_match(opponent)
                self.recalc()
                self.render()
            finally:
                self._transition_commit = False
                from main import clock_pause, vnow
                clock_pause(False)
                self.last_t = vnow()
        if self.state in ('loading','home') or (self.state == 'friends' and self.front_press and time.monotonic()-self.front_press[4]<.3):
            self.render()

    def on_press(self, ev):
        if self.nav.busy or self.front_paused_at is not None:
            return
        if self.state != 'home' and not self.visual.transitioning:
            x0,y0,x1,y1 = self.back_rect()
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self.front_navigate('home')
                return
        if self.state in ('home','friends','friendly_post'):
            for x0,y0,x1,y1,cmd in list(self.buttons):
                if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                    self.front_press = (x0,y0,x1,y1,time.monotonic())
                    cmd()
                    self.render()
                    return
            return
        super().on_press(ev)

    def on_motion(self, ev):
        if not self.nav.busy: super().on_motion(ev)

    def on_release(self, ev):
        if not self.nav.busy and self.state not in ('home','friends','loading','friendly_post'):
            super().on_release(ev)

    def front_keyboard(self, window, key, *_):
        if key != 27: return False
        if self.nav.busy: return True
        if self.state == 'home': return False
        self.front_navigate('home')
        return True

    def pause_rect(self):
        # Keep the original pause control, moving it to the right of the HUD.
        x0,y0,x1,y1 = super().pause_rect()
        return (self.cw-x1,y0,self.cw-x0,y1)

    def draw_hud(self):
        # La flecha ocupa su propio espacio; el marcador conserva todo el ancho y su escala.
        super().draw_hud()

    def back_rect(self):
        margin = max(10,min(self.cw,self.ch)*.025)
        size = min(54,max(42,self.cw*.105))
        return margin,margin,margin+size,margin+size

    def draw_back(self):
        if self.state in ('home','loading'): return
        x0,y0,x1,y1 = self.back_rect()
        c,y=(x0+x1)/2,(y0+y1)/2
        self.cv.create_oval(x0,y0,x1,y1,fill='#073322',width=0)
        self.cv.create_line(c+10,y,c-10,y,fill='#ff4343',width=4)
        self.cv.create_line(c-10,y,c-2,y-8,fill='#ff4343',width=4)
        self.cv.create_line(c-10,y,c-2,y+8,fill='#ff4343',width=4)

    def front_button(self,cx,cy,width,height,text,action,color='#ffd52a',fg='#0b261b'):
        x,y=cx-width/2,cy-height/2
        scale = 1
        p = self.front_press
        if p and abs(p[0]-x)<2 and abs(p[1]-y)<2:
            elapsed=time.monotonic()-p[4]
            if elapsed<.25: scale=1-.04*math.sin(math.pi*elapsed/.25)
        w,h=width*scale,height*scale
        with self.cv.canvas:
            Color(.015,.07,.035,1)
            RoundedRectangle(pos=(cx-w/2,self.ch-cy-h/2-5),size=(w,h),radius=[8])
            color_rgb=tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
            Color(*color_rgb,1)
            RoundedRectangle(pos=(cx-w/2,self.ch-cy-h/2),size=(w,h),radius=[8])
            Color(1,1,1,.4)
            Line(points=(cx-w*.45,self.ch-cy+h*.35,cx+w*.45,self.ch-cy+h*.35),width=1)
        self.cv.create_text(cx,cy,text=text,fill=fg,font=self.front_font(min(height*.4,width/(max(1,len(text))*.52))),width=width*.92)
        self.buttons.append((x,y,x+width,y+height,action))

    def draw_home(self):
        w,h=self.cw,self.ch
        self.cv.create_rectangle(0,0,w,h,fill='#052d20',width=0)
        try:
            image=self.visual.texture('menu_mundial.png').texture
        except Exception:
            try:
                image=self.visual.texture('menu_mundial.jpg').texture
            except Exception:
                image=None  # imagen no empaquetada: el menú sigue con fondo verde
        if image is not None:
            # Cover sin deformar: cubre toda la pantalla hasta el borde inferior.
            # En pantallas más altas que la ilustración solo se recortan los
            # bordes laterales por igual; la copa y la montaña quedan centradas.
            s=max(w/image.width,h/image.height)
            iw,ih=image.width*s,image.height*s
            with self.cv.canvas:
                Color(1,1,1,1)
                Rectangle(texture=image,pos=((w-iw)/2,h-ih),size=(iw,ih))
        title_size=min(w*.17,h*.073)
        center=h*.485
        self.cv.create_text(w*.46,center,text='MUNDIAL',fill='#b5f65a',font=self.front_font(title_size,True))
        self.cv.create_text(w*.53,center+title_size*.79,text='DE CHAPAS',fill='#ff761b',font=self.front_font(title_size*.92,True))
        # Small vector football tucked into the title's right edge.
        r=title_size*.21;x=w*.81;y=center-title_size*.05
        self.cv.create_oval(x-r,y-r,x+r,y+r,fill='#ffffff',outline='#163b25',width=1.5)
        self.cv.create_oval(x-r*.35,y-r*.35,x+r*.35,y+r*.35,fill='#172a20',width=0)
        for i in range(5):
            a=i*math.tau/5;px=x+math.cos(a)*r*.65;py=y+math.sin(a)*r*.65
            self.cv.create_oval(px-r*.15,py-r*.15,px+r*.15,py+r*.15,fill='#172a20',width=0)
        bh=min(66,max(46,h*.072));bw=min(w*.8,420)
        shop_h=min(52,max(42,h*.055))
        self.front_button(w/2,h*.66,bw,shop_h,'TIENDA',self.open_shop,'#e6c98e')
        self.front_button(w/2,h*.76,bw,bh,'TORNEO MUNDIAL',lambda:self.front_navigate('tournament'))
        self.front_button(w/2,h*.76+bh*1.3,bw,bh,'AMISTOSOS',lambda:self.front_navigate('friends'),'#ff7939')
        if getattr(self,'shop',None):
            self._coin(w-27,24,13)
            self.cv.create_text(w-47,24,text=str(self.shop.balance),fill='#ffd45c',font=self.front_font(20,True),anchor='e')

    def draw_loading(self):
        w,h=self.cw,self.ch;t=max(0,time.monotonic()-self.nav.shown_at)
        self.cv.create_rectangle(0,0,w,h,fill='#06452f',width=0)
        # Reference: huge sweeping diagonal slabs, curved green corners and white
        # flashes. Recreated as bounded Kivy meshes; no video/slide playback.
        with self.cv.canvas:
            for i in range(12):
                depth=(i+1)/12
                travel=((t*.43+i*.137)%1.8)-.4
                x=(travel-.3)*w*2
                y=(i%4)*h*.28-h*.2
                size=w*(.7+depth*.8)
                rgb=(.08+.36*depth,.35+.45*depth,.15+.12*depth)
                Color(*rgb,1)
                vertices=[x,y,0,0,x+size,y+h*.3,0,0,x+size,y+h*.8,0,0,x,y+h*.5,0,0]
                Mesh(vertices=vertices,indices=[0,1,2,0,2,3],mode='triangles')
                Color(.76,1,.27,.35)
                Line(points=[x,y+h*.5,x+size,y+h*.8],width=1+depth*2)
            for i in range(3):
                p=(t*.6+i*.33)%1
                Color(.9,1,.86,.22*(1-p))
                Line(points=[-w+p*w*3,0,p*w*3,h],width=2+i)
        pulse=1+.035*math.sin(t*math.tau)
        self.cv.create_text(w/2,h*.46,text='MUNDIAL',fill='#c6ff61',font=self.front_font(min(w*.23,h*.095)*pulse,True))
        self.cv.create_text(w/2,h*.55,text='DE CHAPAS',fill='#ffffff',font=self.front_font(min(w*.18,h*.075),True))
        span=w*.62
        self.cv.create_rectangle((w-span)/2,h*.67,(w+span)/2,h*.67+4,fill='#143925',width=0)
        self.cv.create_rectangle((w-span)/2,h*.67,(w-span)/2+span*min(1,t/5),h*.67+4,fill='#d3ff4a',width=0)

    def change_friend(self,delta):
        from main import TEAMS
        self.friend_index=next_country(self.friend_index,delta,len(TEAMS))
        self.render()

    def draw_friends(self):
        from main import TEAMS,FULL_NAME
        w,h=self.cw,self.ch
        self.pitch_bg()
        self.title(h*.14,'AMISTOSOS',2.7,'#d5ff5e')
        team=tuple(TEAMS)[self.friend_index]
        r=min(w*.19,h*.105)
        self.jersey(w/2,h*.34,r,team,num=10)
        for x,d in ((w*.13,-1),(w*.87,1)):
            size=min(54,max(44,w*.12));y=h*.34
            self.front_button(x,y,size,size,'',lambda d=d:self.change_friend(d),'#dbefda')
            self.cv.create_line(x-d*8,y-10,x+d*5,y,fill='#123c24',width=3)
            self.cv.create_line(x+d*5,y,x-d*8,y+10,fill='#123c24',width=3)
        name=FULL_NAME.get(team,team)
        self.cv.create_text(w/2,h*.48,text=name,fill='#ffffff',font=self.front_font(min(w*.065,h*.032)),width=w*.8)
        stats=getattr(self,'friendly_stats',None) or self.store.stats()
        for i,(key,label,color) in enumerate((('losses','DERROTAS','#ff5c55'),('wins','VICTORIAS','#8bed76'),('best','MAYOR RACHA','#ffd944'))):
            x=w*(.18+i*.32);bw=w*.27;y=h*.58;bh=h*.15
            self.cv.create_rectangle(x-bw/2,y,x+bw/2,y+bh,fill='#083725',outline=color,width=2)
            self.cv.create_text(x,y+bh*.36,text=str(stats[key]),fill=color,font=self.front_font(min(w*.115,h*.06),True))
            self.cv.create_text(x,y+bh*.8,text=label,fill='#ffffff',font=self.front_font(min(w*.031,bw/(len(label)*.6))),width=bw*.93)
        self.front_button(w/2,h*.85,min(w*.83,430),min(68,max(48,h*.075)),'JUGAR',lambda:self.front_navigate('friendly_match'))
        self.draw_back()

    def match_over(self,pen_text=''):
        if self.mode != 'friendly': return super().match_over(pen_text)
        if self.state not in ('match','pens'): return
        self.fire.clear();self.pausa.finish();self.magnetic_finish()
        a,b=self.teams
        winner=pen_text.split('gana ')[-1] if pen_text else (a if self.score[0]>self.score[1] else b)
        self.post_w=winner
        self.post_txt=f'{a} {self.score[0]}-{self.score[1]} {b}'+(f' ({pen_text})' if pen_text else '')
        # Commit before navigation/celebration. INSERT primary key provides idempotence.
        try:
            recorded=self.store.record(self.friendly_id,a,b,winner==self.user,self.post_txt)
            if recorded and winner==self.user and getattr(self.store,'last_reward',None):
                reward=self.store.last_reward
                self.start_reward(reward['amount'],reward['balance'])
            self.front_error=''
        except Exception:
            # Never report an uncommitted result as saved; allow explicit retry.
            self.front_error='No se pudo guardar el resultado. Reintentar'
        self.paused=False
        from main import clock_pause
        clock_pause(False)
        self.music.fade_out_end()
        self.state='friendly_post'
        self.render()
        self.later(1100,lambda:self.state=='friendly_post' and self.snd.play('gana',winner,4))

    def retry_friendly(self):
        try:
            recorded=self.store.record(self.friendly_id,self.teams[0],self.teams[1],self.post_w==self.user,self.post_txt)
            if recorded and self.post_w==self.user and getattr(self.store,'last_reward',None):
                reward=self.store.last_reward
                self.start_reward(reward['amount'],reward['balance'])
            self.front_error=''
            self.friendly_stats=self.store.stats()
        except Exception:
            self.front_error='No se pudo guardar el resultado. Reintentar'
        self.render()

    def draw_friendly_post(self):
        self.pitch_bg();w,h=self.cw,self.ch
        self.title(h*.22,'VICTORIA' if self.post_w==self.user else 'DERROTA',3,'#b8ff72' if self.post_w==self.user else '#ff6255')
        for x,team in ((w*.28,self.teams[0]),(w*.72,self.teams[1])):self.jersey(x,h*.42,min(w*.12,h*.07),team,num=10)
        self.cv.create_text(w/2,h*.42,text=f'{self.score[0]} - {self.score[1]}',fill='#ffffff',font=self.front_font(w*.1,True))
        self.cv.create_text(w/2,h*.58,text=self.post_txt,fill='#ffffff',font=self.front_font(w*.045),width=w*.86)
        if self.front_error:
            self.cv.create_text(w/2,h*.67,text=self.front_error,fill='#ffca73',font=self.front_font(min(18,w*.04)),width=w*.88)
        self.front_button(w/2,h*.87,min(w*.88,460),min(84,max(60,h*.08)),'REINTENTAR' if self.front_error else 'OTRO AMISTOSO',self.retry_friendly if self.front_error else lambda:self.front_navigate('friends'))
        self.draw_back()

    def front_suspend(self):
        if self.front_paused_at is not None:return
        self.front_paused_at=time.monotonic()
        self.menu_audio.suspend()
        if self.state in ('match','pens') and not self.paused:self.toggle_pause()
        elif not self.nav.busy:
            from main import clock_pause
            clock_pause(True)

    def front_resume(self):
        if self.front_paused_at is None:return
        delay=time.monotonic()-self.front_paused_at
        self.front_paused_at=None
        if self.nav.busy:
            self.nav.pressed_at+=delay
            self.nav.shown_at+=delay
        self.menu_audio.resume()
        if self.state not in ('match','pens') and not self.nav.busy:
            from main import clock_pause,vnow
            clock_pause(False);self.last_t=vnow()
        self.render()

    def front_stop(self):
        self.menu_audio.stop()
        if self.menu_audio.effect:self.menu_audio.effect.stop()
        self.music.stop();self.magnetic_finish()
        Window.unbind(on_keyboard=self.front_keyboard)
        self.store.close()
