import unittest, math
from unittest.mock import patch
from main import Game,Body,PR,PM,BR,BM,FX0,FX1,FY0,FY1,MY,GY0,GY1,GD,PEN_GY0,PEN_GY1,PEN_GD,step,vnow,MARKS
from ai import difficulty_threshold,ENHANCED_COOLDOWN

class UpdateRules(unittest.TestCase):
    def game(self,stage=0):
        g=Game.__new__(Game);g.state='match';g.round=stage;g.score=[0,0];g.ai_reset()
        g.next_shot_at=[10,10];g.gk_next=[0,0];g.ai_at=10;g.kick_team=None
        g.bodies=[];g.fire_reset();g.teams=['Argentina','Brasil'];g.clock=0;g.shots=0;g.held=None
        g.snd=type('Sound',(),{'play':lambda *a,**kw:None})();return g
    def test_three_goals_activate_nonfinal(self):
        for stage in (0,1,2):
            g=self.game(stage);g.score=[2,0];g.ai_update_difficulty();self.assertFalse(g.ai_hard())
            with patch('main.vnow',return_value=1):
                g.score[0]=3;g.ai_update_difficulty()
            self.assertTrue(g.ai_hard());self.assertEqual(g.next_shot_at,[10,1.5]);self.assertEqual(g.ai_at,1.5)
    def test_final_one_goal(self):
        g=self.game(3);g.ai_update_difficulty();self.assertFalse(g.ai_hard())
        g.score=[1,0];g.ai_update_difficulty();self.assertTrue(g.ai_hard());self.assertEqual(difficulty_threshold(3),1)
    def test_latch_extra_time_and_new_match_reset(self):
        g=self.game();g.score=[3,0];g.ai_update_difficulty()
        for clock in (150,300,MARKS[-1]):
            g.clock=clock;g.score=[4,5];g.ai_update_difficulty();self.assertTrue(g.ai_hard())
        g.ai_reset();self.assertFalse(g.ai_hard())
    def test_half_second_ai_recharge_player_unchanged(self):
        g=self.game();g.ai_enhanced=True
        with patch('main.vnow',return_value=10):g.shoot(Body(700,MY,PR,PM,1),-10,0)
        self.assertEqual(g.next_shot_at,[10,10.5]);self.assertEqual(g.ai_at,10.5)
        with patch('main.vnow',return_value=10):g.shoot(Body(300,MY,PR,PM,0),10,0)
        self.assertEqual(g.next_shot_at,[11,10.5]);self.assertEqual(ENHANCED_COOLDOWN,.5)
    def test_penalties_normal_and_no_enhanced_timer(self):
        g=self.game();g.ai_enhanced=True;g.state='pens';self.assertFalse(g.ai_hard())
        before=g.next_shot_at[:];g.shoot(Body(900,MY,BR,BM),10,0);self.assertEqual(g.next_shot_at,before)
    def test_goal_150_percent_both_dimensions(self):
        self.assertEqual(PEN_GY1-PEN_GY0,(GY1-GY0)*1.5);self.assertEqual(PEN_GD,GD*1.5)
    def test_enlarged_penalty_zone_accepts_shot_normal_rejects(self):
        def ball():
            b=Body(FX1-2,MY+90,BR,BM);b.vx=20;return b
        b=ball();step([b],b);self.assertLess(b.x,FX1)
        b=ball();step([b],b,goal=(PEN_GY0,PEN_GY1,PEN_GD));self.assertGreater(b.x,FX1)
    def test_penalty_aim_spans_new_goal(self):
        g=self.game();g.state='pens';g.ball=Body(900,MY,BR,BM);g.aim_y=MY
        g.move_aim(999);self.assertEqual(g.aim_y,PEN_GY1+25)
        g.move_aim(-999);self.assertEqual(g.aim_y,PEN_GY0-25)
    def test_fire_rejects_backward_and_perpendicular_pass(self):
        g=self.game();g.ball=Body(300,MY,BR,BM)
        for x,y in ((260,MY),(300,MY+80),(340,MY+40)):
            self.assertIsNone(g.ai_fire_plan([Body(x,y,PR,PM,1)]))
    def test_fire_direct_goal_without_noise_or_pass(self):
        g=self.game();g.ball=Body(300,MY,BR,BM);p=Body(350,MY,PR,PM,1)
        g.bodies=[p,g.ball];g.score=[3,0]
        g.ai_shoot();self.assertEqual(g.fire.shots[1]['phase'],'launch');self.assertLess(p.vx,0);self.assertEqual(p.vy,0)
    def test_fire_valid_bank_finishes_in_goal(self):
        g=self.game();g.ball=Body(300,MY,BR,BM)
        projected=2*(FY0+BR)-MY
        slope=(projected-MY)/(FX0-300)
        p=Body(335,MY+slope*35,PR,PM,1)
        plan=g.ai_fire_plan([p]);self.assertIsNotNone(plan);self.assertTrue(plan[-1]);self.assertAlmostEqual(plan[-2],MY)
    def test_special_cooldown_not_shortened_by_difficulty(self):
        g=self.game(3);g.ai_enhanced=True;g.ball=Body(300,MY,BR,BM);p=Body(350,MY,PR,PM,1);g.bodies=[p,g.ball];g.score=[1,0]
        with patch('main.vnow',return_value=10):g.ai_shoot()
        self.assertEqual(g.fire.ready_at[1],15);self.assertEqual(g.next_shot_at[1],10.5)

if __name__=='__main__':unittest.main()
