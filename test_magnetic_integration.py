import unittest
from unittest.mock import patch
from main import Game, tk, _Ev, MY, PR, BR, FX1, FX0, _Window

class RealGameIntegration(unittest.TestCase):
    def test_menu_match_buttons_shot_both_keepers_pause_and_penalties(self):
        g=Game(tk.Tk());g.cv.size=(411,814);g.recalc();g.snd.on=False
        g._transition_commit=True;g.visual.transitioning=False;g.start_tournament('Argentina');g.visual.transitioning=False
        opponent=next(t for t in g.round_teams if t != 'Argentina')
        g.start_match(opponent);g.visual.transitioning=False
        x0,y0,x1,y1=g.ability_rect(2)
        g.on_press(_Ev((x0+x1)/2+8,(y0+y1)/2+8));g.on_release(_Ev((x0+x1)/2+8,(y0+y1)/2+8))
        self.assertTrue(g.magnetic.active(0,g.magnetic_now()))
        disc=next(q for q in g.bodies if q.team==0 and not q.keeper)
        x,y=g.to_s(disc.x,disc.y);g.on_press(_Ev(x,y));self.assertIs(g.drag,disc)
        g.on_release(_Ev(*g.to_s(disc.x+100,disc.y)));self.assertEqual(g.shots,1)
        for _ in range(30):g.match_update(.016);g.draw()
        for owner in (0,1):
            g.magnetic_reset();g.magnetic.activate(owner,g.magnetic_now())
            k=next(q for q in g.bodies if q.team==1-owner and q.keeper)
            g.ball.x=k.x+(-30 if owner==0 else 30);g.ball.y=k.y
            g.match_collision(g.ball,k);self.assertTrue(g.magnetic_stunned(k))
            g.draw();g.toggle_pause();g.toggle_pause()
            with patch('main.vnow',return_value=g.magnetic_stuns[k]['until']):g.magnetic_update()
            self.assertFalse(g.magnetic_stunned(k));self.assertEqual((k.x,k.y),g.clamp_area(k,k.x,k.y))
        g.start_penalties();g.visual.transitioning=False;g.draw();g.pens_update()
        self.assertEqual(g.state,'pens');self.assertEqual(g.magnetic_stuns,{})
        g.restart_tournament();g.visual.transitioning=False;self.assertEqual(g.state,'menu')

if __name__=='__main__':unittest.main()
