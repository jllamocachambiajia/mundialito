import unittest, math
from unittest.mock import patch
from main import Game, Body, step, PR, BR, PM, BM, FX0, FX1, MY, MAX_DRAG, POWER, clock_pause, vnow
from campo_magnetico import MagneticState, MagneticAudio, ElectricAudio

class FakeSound:
    def __init__(self): self.plays=0; self.stops=0; self.volume=0; self.length=1
    def play(self): self.plays+=1
    def stop(self): self.stops+=1
    def seek(self, value): pass

def game(owner=0):
    g=Game.__new__(Game);g.state='match';g.phase='play';g.paused=False;g.round=0
    g.drag=None;g.pending=None;g.held=None;g.gk_mode=False;g.dash=None;g.kick_team=None
    g.snd=type('Sound',(),{'on':False,'play':lambda *a,**kw:None})();g.flash=lambda *a:None
    g.ai_reset();g.fire_reset();g.pausa_reset();g.magnetic_reset();g.gk_next=[0,0];g.next_shot_at=[0,0];g.ai_at=0
    g.teams=['Argentina','Brasil'];g.score=[0,0];g.clock=0;g.shots=0
    g.ball=Body(500,MY,BR,BM);g.bodies=[g.ball]
    for audio in g.magnetic_audio+g.magnetic_stun_audio: audio.loaded=True
    g.magnetic.activate(owner,100)
    return g

class MagneticRules(unittest.TestCase):
    def test_twelve_seconds_exact_both_teams(self):
        for team in (0,1):
            s=MagneticState();s.activate(team,100)
            self.assertTrue(s.active(team,111.999));self.assertFalse(s.active(team,112))
            self.assertEqual(s.ready_at[team],130)
    def test_protects_ball_and_six_discs_not_rivals(self):
        for owner in (0,1):
            g=game(owner)
            with patch('main.vnow',return_value=101):
                self.assertEqual(g.magnetic_shield_team(g.ball),owner)
                for i in range(6):
                    q=Body(200,MY,PR,PM,owner,keeper=i==0)
                    self.assertEqual(g.magnetic_shield_team(q),owner)
                self.assertIsNone(g.magnetic_shield_team(Body(200,MY,PR,PM,1-owner)))
    def test_sixty_percent_return_both_directions_and_bodies(self):
        for owner in (0,1):
            for protected_ball in (False,True):
                g=game(owner);guard=g.ball if protected_ball else Body(500,MY,PR,PM,owner)
                rival=Body(guard.x+guard.r*2+PR-1,MY,PR,PM,1-owner);rival.vx=-10
                with patch('main.vnow',return_value=101):g.match_collision(guard,rival)
                self.assertAlmostEqual(rival.vx,6);self.assertEqual(guard.vx,0)
    def test_moving_protected_ball_repels_without_enemy_shot(self):
        for owner in (0,1):
            g=game(owner);g.ball.vx=12;r=Body(537,MY,PR,PM,1-owner)
            with patch('main.vnow',return_value=101):g.match_collision(g.ball,r)
            self.assertEqual(r.vx,12);self.assertEqual(g.ball.vx,12)
    def test_repeated_overlap_does_not_accumulate_energy(self):
        g=game();r=Body(537,MY,PR,PM,1);r.vx=-10
        with patch('main.vnow',return_value=101):
            for _ in range(100):
                r.x=537;g.match_collision(g.ball,r)
                self.assertLessEqual(r.speed(),10)
    def test_stun_five_seconds_survives_field_end_no_restart(self):
        for owner in (0,1):
            g=game(owner);k=Body(FX1-PR if owner==0 else FX0+PR,MY,PR,PM,1-owner,True)
            g.bodies.append(k);g.ball.x=k.x+(30 if owner else -30)
            with patch('main.vnow',return_value=111):g.match_collision(g.ball,k)
            self.assertEqual(g.magnetic_stuns[k]['until'],116)
            with patch('main.vnow',return_value=113):
                self.assertTrue(g.magnetic_stunned(k));self.assertIsNone(g.magnetic_ball_team())
                g.match_collision(g.ball,k);self.assertEqual(g.magnetic_stuns[k]['until'],116)
                self.assertFalse(g.match_collision(g.ball,k));g.shoot(k,10,0);self.assertEqual(k.speed(),0)
            with patch('main.vnow',return_value=116):
                g.magnetic_update();self.assertFalse(g.magnetic_stunned(k))
    def test_keeper_inside_area_after_repulsion_and_substep(self):
        for owner in (0,1):
            g=game(owner);k=Body(FX1-PR if owner==0 else FX0+PR,MY,PR,PM,1-owner,True)
            g.bodies.append(k);g.ball.x=k.x+(-30 if owner==0 else 30);g.ball.vx=20 if owner==0 else -20
            with patch('main.vnow',return_value=101):
                step(g.bodies,g.ball,limit=g.keeper_limit,collision_policy=g.match_collision,body_scale=g.magnetic_body_scale)
            self.assertEqual((k.x,k.y),g.clamp_area(k,k.x,k.y))
    def test_fire_half_power_40_seconds_both_teams_selected_only(self):
        for owner in (0,1):
            for speed in (MAX_DRAG*POWER*1.5,10):
                g=game(owner);attacker=1-owner;q=Body(473,MY,PR,PM,attacker);q.vx=speed
                g.fire.arm(attacker,101);g.fire.select(q,101);g.fire.launch(q,speed,0,101,0)
                with patch('main.vnow',return_value=101.2):g.match_collision(q,g.ball)
                self.assertAlmostEqual(g.ball.vx,speed*1.44*.5)
                self.assertEqual(g.fire.ready_at[attacker],141);self.assertEqual(g.magnetic_fire_penalty[attacker],141)
                self.assertIs(g.magnetic_fire_override['shot']['body'],q)
    def test_outer_shield_does_not_prevent_selected_fire_reaching_ball(self):
        g=game(1);q=Body(465,MY,PR,PM,0);q.vx=20
        g.fire.arm(0,101);g.fire.select(q,101);g.fire.launch(q,20,0,101,0)
        with patch('main.vnow',return_value=101):self.assertTrue(g.match_collision(q,g.ball))
        self.assertEqual(q.x,465);self.assertEqual(g.fire.ready_at[0],121)
    def test_missed_fire_keeps_20_second_cooldown(self):
        for owner in (0,1):
            g=game(owner);t=1-owner;q=Body(300,MY+150,PR,PM,t)
            g.fire.arm(t,101);g.fire.select(q,101);g.fire.launch(q,20,0,101,0)
            with patch('main.vnow',return_value=103):g.magnetic_update()
            self.assertEqual(g.fire.ready_at[t],121);self.assertEqual(g.magnetic_fire_penalty[t],0)
    def test_normal_fire_unchanged_without_field(self):
        g=game();g.magnetic.finish();q=Body(473,MY,PR,PM,0);q.vx=20
        g.fire.arm(0,101);g.fire.select(q,101);g.fire.launch(q,20,0,101,0)
        with patch('main.vnow',return_value=101):g.match_collision(q,g.ball)
        self.assertAlmostEqual(g.ball.vx,28.8);self.assertEqual(g.fire.ready_at[0],121)
    def test_defending_shield_can_intervene_only_during_special_shot(self):
        g=game(1);q=Body(473,MY,PR,PM,0);q.vx=20
        g.fire.arm(0,101);g.fire.select(q,101);g.fire.launch(q,20,0,101,0)
        with patch('main.vnow',return_value=101):g.match_collision(q,g.ball)
        r=Body(g.ball.x+27,MY,PR,PM,1);r.vx=-30
        with patch('main.vnow',return_value=101.1):g.match_collision(g.ball,r)
        self.assertLessEqual(g.ball.speed(),14.4)
        with patch('main.vnow',return_value=104):g.magnetic_update()
        self.assertIsNone(g.magnetic_fire_override)
    def test_ai_activates_and_shoots_to_goal_without_waiting(self):
        g=game();g.magnetic.finish();g.ball.x=300;q=Body(350,MY,PR,PM,1);g.bodies.append(q)
        with patch('main.vnow',return_value=101):
            self.assertTrue(g.magnetic_ai());self.assertTrue(g.magnetic_attack())
        self.assertLess(q.vx,0);self.assertAlmostEqual(q.vy,0);self.assertEqual(g.shots,1)
    def test_ai_rejects_incoherent_opportunity(self):
        g=game();g.magnetic.finish();g.bodies.append(Body(450,MY,PR,PM,1))
        with patch('main.vnow',return_value=101):self.assertFalse(g.magnetic_ai())
    def test_independent_sound_loops_fade_and_resume_after_pause(self):
        g=game();audio=g.magnetic_stun_audio[1];sound=FakeSound();audio.sounds[0]=sound
        audio.begin(111);audio.update(112);audio.update(114);self.assertEqual(sound.plays,1)
        volume=sound.volume;audio.update(115.9);self.assertLess(sound.volume,volume)
        k=Body(1000,MY,PR,PM,1,True);g.bodies.append(k)
        g.magnetic_stuns[k]=dict(started=111,until=116,position=(k.x,k.y))
        g.snd.on=True
        with patch('main.vnow',return_value=115):g.magnetic_pause();g.magnetic_resume()
        self.assertEqual(sound.plays,2)
        audio.update(116);self.assertIsNone(audio.started);self.assertGreater(sound.stops,0)
    def test_game_pause_freezes_effect_clock(self):
        with patch('main.time.monotonic',return_value=100):clock_pause(True);first=vnow()
        with patch('main.time.monotonic',return_value=120):self.assertEqual(vnow(),first);clock_pause(False)
    def test_penalties_and_cleanup_restore_normal(self):
        g=game();g.state='pens'
        with patch('main.vnow',return_value=101):
            self.assertTrue(g.match_collision(g.ball,Body(527,MY,PR,PM,1,True)))
            self.assertFalse(g.magnetic_activate(0))
        g.magnetic_finish();self.assertEqual(g.magnetic_stuns,{});self.assertIsNone(g.magnetic_fire_override)

if __name__=='__main__':unittest.main()
