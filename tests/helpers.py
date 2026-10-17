from stagecraft.camera import cross, dot, unit
WIDTH, HEIGHT, FOCAL = 1000, 800, 900
LOCATION = [-6, -8, 5]
FORWARD = unit([-v for v in LOCATION])
RIGHT = unit(cross(FORWARD, [0, 0, 1]))
UP = cross(RIGHT, FORWARD)
BACK = [-v for v in FORWARD]


def project(p):
    q = [v-c for v, c in zip(p, LOCATION)]
    x, y, z = [dot(axis, q) for axis in (RIGHT, UP, BACK)]
    return [WIDTH/2-FOCAL*x/z, HEIGHT/2+FOCAL*y/z]


def alignment():
    return {"x": [[project(a), project(b)] for a, b in [([-2,-2,0],[2,-2,0]), ([-2,2,0],[2,2,0])]],
            "y": [[project(a), project(b)] for a, b in [([-2,-2,0],[-2,2,0]), ([2,-2,0],[2,2,0])]],
            "origin": project([0,0,0]), "camera_height": 5}
