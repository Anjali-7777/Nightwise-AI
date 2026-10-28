import unittest
from backend.app.routing import plan_routes
from backend.app.scoring import score_route
from backend.app.agent import parse_request
class CoreTests(unittest.TestCase):
 def test_routes_and_scores(self):
  routes=plan_routes(); self.assertGreaterEqual(len(routes),2); self.assertTrue(all(0<=score_route(r)<=100 for r in routes))
 def test_parser(self):
  p=parse_request('Compare routes with main roads and shops'); self.assertEqual(p['intent'],'compare_routes'); self.assertTrue(p['preferences']['main_road_preference'])
 def test_invalid_location(self):
  with self.assertRaises(ValueError): plan_routes('unknown','campus')
if __name__=='__main__':unittest.main()
