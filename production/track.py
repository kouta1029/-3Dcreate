"""Analytic step-chain centerline and wheel loci, in metres."""
from bisect import bisect_right
from math import atan, cos, hypot, pi, sin, sqrt

PITCH = 0.408
RADIUS = 0.32718
AXLE_OFFSET = 0.036
STEP_COUNT = 50
REAR_AXLE = (-0.265, -0.129)
LANDING = 1.16
TRANSITION = 1.18
SLOPE = 1 / sqrt(3)


def progression(t):
    return t**3 * (10 + t * (-15 + 6 * t))


def centerline(run):
    """Return (x, z, outward angle, step angle) samples in travel order."""
    end = run + 2 * LANDING + 2 * TRANSITION
    rise = SLOPE * (run + TRANSITION)

    def deck(x):
        if x < LANDING:
            return 0, 0
        t = (x - LANDING) / TRANSITION
        if t < 1:
            return SLOPE * TRANSITION * (t**3 - 0.5*t**4), SLOPE * t*t*(3-2*t)
        if x <= LANDING + TRANSITION + run:
            return SLOPE * (x - LANDING - TRANSITION/2), SLOPE
        if x > end - LANDING:
            return rise, 0
        z, grade = deck(end - x)
        return rise - z, grade

    samples = []
    for i in range(801):
        x = end * i/800
        z, grade = deck(x)
        samples.append((x, z, -atan(grade), 0))
    for i in range(1, 241):
        t = i/240
        a = pi*t
        samples.append((end + RADIUS*sin(a), rise + RADIUS*(cos(a)-1),
                        a, pi*progression(t)))
    for i in range(1, 801):
        x = end * (1-i/800)
        z, grade = deck(x)
        norm = hypot(1, grade)
        samples.append((x + 2*RADIUS*grade/norm, z - 2*RADIUS/norm,
                        pi-atan(grade), pi))
    for i in range(1, 241):
        t = i/240
        a = pi*(1+t)
        samples.append((RADIUS*sin(a), RADIUS*(cos(a)-1),
                        a, pi*(1+progression(t))))
    return samples


def lengths(points):
    distance = [0.0]
    for a, b in zip(points, points[1:]):
        distance.append(distance[-1]+hypot(b[0]-a[0], b[1]-a[1]))
    return distance


class Track:
    def __init__(self):
        low, high = 0., 12.
        for _ in range(36):
            mid = (low+high)/2
            if lengths(centerline(mid))[-1] < STEP_COUNT * PITCH:
                low = mid
            else:
                high = mid
        self.samples = centerline((low+high)/2)
        self.distances = lengths(self.samples)
        self.length = self.distances[-1]
        self.upper = self.samples[800][:2]

    def state(self, distance):
        s = distance % self.length
        i = bisect_right(self.distances, s)-1
        f = (s-self.distances[i])/(self.distances[i+1]-self.distances[i])
        x, z, normal, angle = (
            a + f*(b-a) for a,b in zip(self.samples[i], self.samples[i+1])
        )
        front = (x + AXLE_OFFSET*sin(normal), z + AXLE_OFFSET*cos(normal))
        dx, dz = REAR_AXLE
        rear = (front[0]+dx*cos(angle)+dz*sin(angle),
                front[1]-dx*sin(angle)+dz*cos(angle))
        return (x, z), front, rear, angle
