import copy
import unittest
from stagecraft.camera import solve, dot, cross
from helpers import WIDTH, HEIGHT, FOCAL, LOCATION, RIGHT, UP, BACK, alignment


class CameraTests(unittest.TestCase):
    def test_recovers_synthetic_camera(self):
        result = solve(WIDTH, HEIGHT, alignment())
        self.assertAlmostEqual(result["focal_px"], FOCAL, places=7)
        for a,b in zip(result["location"], LOCATION): self.assertAlmostEqual(a,b,places=7)
        for row, wanted in zip(result["rotation"], zip(RIGHT, UP, BACK)):
            for a,b in zip(row,wanted): self.assertAlmostEqual(a,b,places=7)
        r = result["rotation"]
        self.assertAlmostEqual(dot(r[0],cross(r[1],r[2])),1)

    def test_rejects_degenerate_and_impossible_guides(self):
        for replacement in ([[[1,1],[1,1]],[[2,2],[3,3]]], [[[1,1],[50,1]],[[1,10],[50,10]]]):
            value = alignment(); value["x"] = replacement
            with self.assertRaises(ValueError): solve(WIDTH, HEIGHT, value)
        value = alignment(); value['y'] = copy.deepcopy(value['x'])
        with self.assertRaises(ValueError): solve(WIDTH, HEIGHT, value)

    def test_rejects_bad_height_and_origin(self):
        for h in [0,-1,float('nan'),float('inf'),True,'5']:
            value = alignment(); value['camera_height'] = h
            with self.assertRaises(ValueError): solve(WIDTH, HEIGHT, value)
        for origin in [[-1,500],[500,801],[float('nan'),500],None]:
            value = alignment(); value['origin'] = origin
            with self.assertRaises(ValueError): solve(WIDTH, HEIGHT, value)

    def test_height_controls_scale_not_lens(self):
        a = solve(WIDTH, HEIGHT, alignment()); value = alignment(); value['camera_height'] *= 2
        b = solve(WIDTH, HEIGHT, value)
        self.assertEqual(a['lens_mm'], b['lens_mm'])
        for x,y in zip(a['location'],b['location']): self.assertAlmostEqual(2*x,y)

    def test_rejects_origin_above_visible_horizon(self):
        value = alignment()
        for axis in ('x', 'y'):
            for line in value[axis]:
                for p in line: p[1] += 250
        value['origin'] = [500, 0]
        with self.assertRaisesRegex(ValueError, 'below the horizon'):
            solve(WIDTH, HEIGHT, value)
