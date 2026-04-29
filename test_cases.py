import unittest
from Evaluation_Question import Engine, DB
class Tests(unittest.TestCase):
    def setUp(self): self.e=Engine(); self.db=DB(":memory:")
    def test_predict_valid(self): self.assertIn(self.e.predict("Karachi",0), range(101))
    def test_predict_bad_zone(self):
        with self.assertRaises(ValueError): self.e.predict("Moon")
    def test_predict_neg_hrs(self):
        with self.assertRaises(ValueError): self.e.predict("Karachi",-1)
    def test_route_valid(self):
        p,c=self.e.route("Lahore","Karachi"); self.assertEqual(p[0],"Lahore"); self.assertGreater(c,0)
    def test_route_same(self):
        p,c=self.e.route("Lahore","Lahore"); self.assertEqual(c,0.0)
    def test_route_bad_src(self):
        with self.assertRaises(ValueError): self.e.route("Mars","Karachi")
    def test_route_bad_dst(self):
        with self.assertRaises(ValueError): self.e.route("Lahore","Mars")
    def test_level_low(self): self.assertEqual(self.e.level(10)[0],"LOW")
    def test_level_critical(self): self.assertEqual(self.e.level(90)[0],"CRITICAL")
    def test_db_log_valid(self): self.assertIsNotNone(self.db.log("Karachi",55))
    def test_db_log_empty(self):
        with self.assertRaises(ValueError): self.db.log("",50)
    def test_db_log_high(self):
        with self.assertRaises(ValueError): self.db.log("Karachi",150)
    def test_db_log_neg(self):
        with self.assertRaises(ValueError): self.db.log("Karachi",-1)
    def test_accident_valid(self): self.assertIsNotNone(self.db.accident("Lahore","crash","high"))
    def test_accident_bad_sev(self):
        with self.assertRaises(ValueError): self.db.accident("Lahore","x","extreme")
    def test_accident_empty_loc(self):
        with self.assertRaises(ValueError): self.db.accident("","x","low")
    def test_recent_records(self): self.db.log("Islamabad",40); self.assertGreater(len(self.db.recent()),0)
    def test_active_accidents(self): self.db.accident("Peshawar","fire","critical"); self.assertGreater(len(self.db.active_accidents()),0)