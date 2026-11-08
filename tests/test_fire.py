import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from fire import FireState, FireAbility, PLAYER_RECHARGE, AI_RECHARGE, POWER_FACTOR, TIME_FACTOR
from main import Body, PR, BR, PM, BM, MAX_DRAG, POWER, FX0, FX1, MY
from main import Game, step, vnow, clock_pause

class FakeSound:
    def __init__(self):self.sounds=[]
    def play(self,name,team='',dur=1):self.sounds.append(name)

class Fake(FireAbility):
    def __init__(self):
        self.fire_reset();self.snd=FakeSound();self.gk_mode=False;self.messages=[];self.phase='play';self.kick_team=None;self.drag=None
        self.cw,self.ch,self.ctrl_pad,self.s=400,800,90,1
    def flash(self,t,s):self.messages.append(t)

class FireRules(unittest.TestCase):
    def test_power_and_slow_motion_values(self):
        self.assertEqual(POWER_FACTOR,1.5);self.assertEqual(TIME_FACTOR,.5)
    def test_player_recharge_is_twenty_every_round(self):
        for stage in range(4):
            f=FireState();p=Body(300,MY,PR,PM,0);f.arm(0,10);f.select(p,10);f.launch(p,1,0,12,stage)
            self.assertEqual(f.ready_at[0],32)
    def test_ai_recharge_by_round(self):
        self.assertEqual(AI_RECHARGE,(20,20,10,5))
        for stage,seconds in enumerate(AI_RECHARGE):
            f=FireState();p=Body(800,MY,PR,PM,1);f.arm(1,0);f.select(p,0);f.launch(p,1,0,3,stage)
            self.assertEqual(f.ready_at[1],3+seconds)
    def test_keeper_cannot_receive_fire(self):
        f=FireState();k=Body(FX0+20,MY,PR,PM,0,True);f.arm(0,0);self.assertFalse(f.select(k,0))
    def test_one_shot_per_activation(self):
        f=FireState();p=Body(300,MY,PR,PM,0);f.arm(0,0);f.select(p,0)
        self.assertTrue(f.launch(p,1,0,0,0));self.assertFalse(f.launch(p,1,0,0,0));self.assertFalse(f.arm(0,19.9))
    def test_button_activates_on_release_with_sound(self):
        g=Fake();x0,y0,x1,y1=g.fire_rect();x,y=(x0+x1)/2,(y0+y1)/2
        self.assertTrue(g.fire_press(x,y));self.assertFalse(g.fire.armed[0]);self.assertTrue(g.fire_release(x,y))
        self.assertTrue(g.fire.armed[0]);self.assertEqual(g.snd.sounds,['fuego'])
    def setup_flight(self,origin,keeper_team=1):
        g=Fake();ball=Body(500,MY,BR,BM);p=Body(origin,MY,PR,PM,0);g.ball=ball
        g.fire.arm(0,0);g.fire.select(p,0);g.fire.launch(p,1,0,0,0);g.fire.shots[0]['phase']='flight'
        ball.vx=5;keeper=Body(ball.x+BR+PR-1,MY,PR,PM,keeper_team,True);return g,ball,keeper
    def test_ball_passes_teammates_and_rivals(self):
        g,ball,_=self.setup_flight(300)
        self.assertFalse(g.fire_collision(ball,Body(ball.x+5,MY,PR,PM,0)))
        self.assertFalse(g.fire_collision(ball,Body(ball.x+5,MY,PR,PM,1)))
    def test_keeper_blocks_only_from_own_half(self):
        g,ball,keeper=self.setup_flight(FX0+100)
        self.assertTrue(g.fire_collision(ball,keeper));g.fire_update(0);self.assertEqual(g.messages,['¡BLOQUEO DEL ARQUERO!'])
        self.assertFalse(g.fire.shots)
        g,ball,keeper=self.setup_flight(FX1-100)
        self.assertFalse(g.fire_collision(ball,keeper));self.assertTrue(g.fire.shots)
    def test_ai_keeper_rules_are_mirrored(self):
        f=FireState();p=Body(FX1-100,MY,PR,PM,1);k=Body(FX0+30,MY,PR,PM,0,True)
        f.arm(1,0);f.select(p,0);f.launch(p,-1,0,0,3)
        self.assertTrue(f.keeper_blocks(f.shots[1],k,(FX0+FX1)/2))
        f.shots[1]['origin']=FX0+200
        self.assertFalse(f.keeper_blocks(f.shots[1],k,(FX0+FX1)/2))
    def test_actual_physics_ignores_field_collisions_during_fire(self):
        g,ball,_=self.setup_flight(300);other=Body(ball.x+20,MY,PR,PM,1)
        step([other,ball],ball,.5,collision_policy=g.fire_collision)
        self.assertAlmostEqual(other.vx,0);self.assertGreater(ball.vx,0)
    def test_independent_fire_cooldowns_allow_immediate_reply(self):
        f=FireState();a=Body(300,MY,PR,PM,0);b=Body(800,MY,PR,PM,1)
        f.arm(0,0);f.select(a,0);f.launch(a,1,0,0,0)
        self.assertTrue(f.arm(1,0));f.select(b,0);f.launch(b,-1,0,0,0)
        self.assertEqual(f.ready_at,[20,20]);self.assertEqual(len(f.shots),2)
    def test_ai_decides_to_use_fire_for_scoring_attempt(self):
        g=Fake();g.ball=Body(300,MY,BR,BM);p=Body(340,MY,PR,PM,1)
        g.score=[1,0];g.clock=100
        self.assertTrue(g.fire_ai(p,'tiro',240));self.assertTrue(g.fire.selected(p))
    def test_shot_cap_normal_special_and_keeper(self):
        g=Game.__new__(Game);g.fire_reset();g.state='match';g.held=None;g.round=0;g.snd=FakeSound()
        g.shots=0;g.kick_team=None;g.gk_next=[0,0];g.next_shot_at=[0,0]
        p=Body(300,MY,PR,PM,0)
        g.shoot(p,999,0);self.assertAlmostEqual(p.speed(),MAX_DRAG*POWER)
        g.fire.arm(0,vnow());g.fire.select(p,vnow());g.shoot(p,999,0)
        self.assertAlmostEqual(p.speed(),MAX_DRAG*POWER*1.5)
        k=Body(FX0+30,MY,PR,PM,0,True);g.shoot(k,999,0)
        self.assertAlmostEqual(k.speed(),MAX_DRAG*POWER*.5)
    def test_pause_clock_freezes_fire_recharge(self):
        import time
        f=FireState();f.ready_at[0]=vnow()+20;clock_pause(True)
        try:
            before=f.ready_at[0]-vnow();time.sleep(.025)
            self.assertEqual(f.ready_at[0]-vnow(),before)
        finally:clock_pause(False)
    def test_contact_transfers_max_power_to_ball(self):
        g=Fake();ball=Body(300,MY,BR,BM);p=Body(300-BR-PR+1,MY,PR,PM,0);g.ball=ball
        cap=MAX_DRAG*POWER*POWER_FACTOR;g.fire.arm(0,0);g.fire.select(p,0);g.fire.launch(p,cap,0,0,0);p.vx=cap
        self.assertFalse(g.fire_collision(p,ball));self.assertAlmostEqual(ball.speed(),cap*1.44)
    def test_effects_clear_and_speed_recovers(self):
        f=FireState();p=Body(300,MY,PR,PM,0);f.arm(0,0);f.select(p,0)
        self.assertEqual(f.scale(.1),.5);f.clear();self.assertFalse(f.shots);self.assertFalse(any(f.armed))
        self.assertGreater(f.scale(.2),.5);self.assertEqual(f.scale(1),1)

if __name__=='__main__':unittest.main()
