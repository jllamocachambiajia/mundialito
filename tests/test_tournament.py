import os,sys,unittest,random
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from tournament import TournamentView, bracket_geometry, connection, path_point, make_fragments

class Fake(TournamentView):
    def __init__(self):
        self.user='Argentina'; self.round_teams=['Argentina']+[str(i) for i in range(15)]
        self.ch=800; self.cw=400; self.last_t=0; self.round=0; self.results=[]; self.state='match'
        self.music=type('Music',(),{'stop':lambda s:None})(); self.snd=type('Sound',(),{'play':lambda *a:None})()
        self.recalc=lambda:None; self.render=lambda:None; self.sounds=[]
        self.init_bracket()
    def play_bracket_sound(self,n): self.sounds.append(n)
    def pairs(self):return list(zip(self.round_teams[::2],self.round_teams[1::2]))
    def sim_match(self,a,b):return a,a+' 1-0 '+b
    def restart_tournament(self):self.state='menu'

class Rules(unittest.TestCase):
    def test_sixteen_teams_and_empty_future(self):
        f=Fake(); self.assertEqual([len(x) for x in f.bracket_levels],[16,8,4,2,1]); self.assertTrue(all(t is None for row in f.bracket_levels[1:] for t in row))
    def test_advance_every_round_half_audio(self):
        f=Fake()
        for stage in range(4):
            f.state='match';f.finish_user_match(f.user,'Argentina 1-0 rival'); e=f.bracket_event
            self.assertEqual(e['stage'],stage);self.assertEqual(f.sounds[-1],'avanzar_nivel.wav')
            f.bracket_update(e['duration']/2-.01); self.assertIsNone(f.bracket_levels[stage+1][e['dest']])
            f.bracket_update(.01);self.assertEqual(f.bracket_levels[stage+1][e['dest']],f.user)
            self.assertEqual(path_point(connection((0,0),(20,30)),1),(20,30))
            f.bracket_update(e['duration']/2+.02)
        f.bracket_update(7);self.assertTrue(f.bracket_done)
    def test_defeat_order_and_return(self):
        f=Fake(); opp=f.round_teams[1];f.finish_user_match(opp,'lost');e=f.bracket_event
        f.bracket_update(e['duration']/2);self.assertEqual(f.bracket_levels[1][0],opp);self.assertNotIn((0,0),f.broken)
        f.bracket_update(4);self.assertIn((0,0),f.broken);self.assertEqual(f.sounds[-1],'perder.wav');self.assertEqual(f.state,'bracket')
        f.bracket_update(f.defeat_duration+.26);self.assertEqual(f.state,'menu')
    def test_three_random_breaks(self):
        pieces=[make_fragments(i,random.Random(100)) for i in range(3)]
        self.assertTrue(all(len(p)>=6 for p in pieces));self.assertNotEqual(pieces[0],pieces[1]);self.assertNotEqual(pieces[1],pieces[2])
    def test_eliminated_rival_never_advances(self):
        f=Fake();loser=f.round_teams[1];f.finish_user_match(f.user,'win');self.assertIn((0,1),f.broken)
        f.bracket_update(f.advance_duration);self.assertNotIn(loser,f.bracket_levels[1]);self.assertIsNone(f.bracket_camera)

if __name__=='__main__':unittest.main()
