import ast,hashlib,json,unittest,wave
from pathlib import Path
from main import COOLDOWN,HALF_REAL,ET_REAL,GK_POWER,SLOWMO_MATCH,TEAMS,Game,Body,PR,PM,vnow,clock_pause
BASE=Path(__file__).resolve().parents[1]
class Rules(unittest.TestCase):
 def test_countries_24(self):self.assertEqual(len(TEAMS),24)
 def test_each_team_recharge_one_second(self):
  g=Game.__new__(Game);g.next_shot_at=[1,0];g.gk_next=[0,0];g.kick_team=None;g.phase='play'
  self.assertEqual(COOLDOWN,1.0)
  self.assertFalse(g.can_shoot(0,.999));self.assertTrue(g.can_shoot(1,0));self.assertTrue(g.can_shoot(0,1))
 def test_half_duration(self):self.assertEqual(HALF_REAL,150.0)
 def test_extra_time_proportion(self):self.assertAlmostEqual(ET_REAL,20*300/90)
 def test_keeper_power(self):self.assertEqual(GK_POWER,.5)
 def test_keeper_slow_motion(self):self.assertEqual(SLOWMO_MATCH,.5)
 def test_victory_files_distinct(self):
  catalog=json.loads((BASE/'assets/sounds/victory/catalog.json').read_text());self.assertEqual(set(catalog),set(TEAMS))
  hashes=[]
  for info in catalog.values():
   path=BASE/'assets/sounds/victory'/info['victory']
   with wave.open(str(path)) as f:self.assertGreater(f.getnframes(),0)
   hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
  self.assertEqual(len(set(hashes)),24)
 def test_gif_bounded(self):
  m=json.loads((BASE/'assets/animations/gol_timing.json').read_text());self.assertEqual(m['play_once_seconds'],3);self.assertEqual(m['source_frames'],75)
 def test_defeat_music_separate(self):
  a=BASE/'assets/sounds/music/derrota_musica.wav';b=BASE/'assets/sounds/effects/perder.wav'
  self.assertNotEqual(a.read_bytes(),b.read_bytes())
if __name__=='__main__':unittest.main()

class Regression(unittest.TestCase):
 def test_match_mechanics_unchanged(self):
  tree=ast.parse((BASE/'main.py').read_text())
  functions={n.name:ast.dump(ast.Module(body=n.body,type_ignores=[]),include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
  baseline=json.loads((BASE/'tests/mechanics_baseline.json').read_text())
  for name,body in baseline.items():
   with self.subTest(function=name):self.assertEqual(functions[name],body)
