"""SAUD -- Kuwait Fighter :: the parked street cars (Unreal-only)
==============================================================================
Asked 2026-10-01 (Riyadh) as "use unity for build cars instead blender",
settled as: parked Kuwaiti street cars, scenery only, not drivable, built by
a Unity editor tool (the Unity tree's Assets/CarTool, the one part of the
frozen port that is live) and placed by this file in the open world's
streets. The browser build has no cars, so every number here is this
build's own, not the browser's.

WHAT THIS FILE OWNS

    CARS, SLOTS   the four cars and their materials: sizes, wheels, the body
                  line, the roof line, the glass, the seams, the paint. Sizes
                  are a typical car of each kind, from memory, not measured
                  off any real model; no make is named or copied.
    colours       every colour through the souq's weathering curve
                  (build_souq._worn) and held at the look's ink floor, so a
                  car stands in the same soot band as the stone around it
    cars.json     Content/Models/Cars/cars.json, WRITTEN from the two tables
                  with --json. The Unity tool reads it and nothing else;
                  check() fails if it has drifted from the tables.
    PARKING       how many cars a street holds, of which kinds, and where
                  one may stand; park_district() lays them along each
                  district's street, check() holds every rule, bite() breaks
                  each rule and proves it is caught.

WHAT IT DOES NOT: build a car. The meshes and the paint are the Unity tool's
(ahmed-fighter-unity/Assets/CarTool): it writes Content/Models/Cars/
SM_Car_<Name>.fbx and Content/Textures/Cars/T_Car_<Name>_Paint.png. The world
(build_world.py) imports those inside the editor and places the rows here.

    python3 Tools/levels/park_cars.py --json     write cars.json
    python3 Tools/levels/park_cars.py --check    the world's cars, checked
    python3 Tools/levels/park_cars.py --bite     every rule, broken
==============================================================================
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
CARS_DIR = os.path.join(PROJECT, "Content", "Models", "Cars")
TEX_DIR = os.path.join(PROJECT, "Content", "Textures", "Cars")
JSON_PATH = os.path.join(CARS_DIR, "cars.json")
MESH_DIR = "/Game/Models/Cars"
TEX_ASSET_DIR = "/Game/Textures/Cars"
MAT_DIR = "/Game/Materials/Cars"

SOUQ = None          # build_souq, handed in by use() (build_world has it loaded already)


def use(souq):
    global SOUQ
    SOUQ = souq


# ----------------------------------------------------------------- the cars
# Metres. x forward (the nose is +x), y left, z up; the origin on the ground
# under the middle of the car's length. Lines run tail to nose.
#   body     the top of the lower body, (x, z): the bonnet, the belt under
#            the cabin, the boot or the bed floor
#   roof     the cabin's top, (x, z), from where it leaves the body at the
#            back to where the windscreen meets the bonnet; its two ends sit
#            on the body line
#   belt     where the cabin stands on the body
#   tumble   the roof's half-width over the belt's
#   glass    side: the side windows' spans in x (a pillar between two);
#            front / rear: the spans of the roof line that are the
#            windscreen and the rear screen
#   seams    the door cuts in x; hood / deck: the bonnet's and the boot's
#            rear and front edges
#   wheel    r, width, rim r; track (centre to centre); axles in x;
#            arch_gap the air between the tyre and its arch
#   clear    the sill's height off the ground
CARS = [
    dict(name="SUV", what="a full-size 4x4 -- the Gulf's commonest big car",
         length=4.95, width=1.97, clear=0.23,
         wheel=dict(r=0.40, width=0.27, rim_r=0.235, track=1.64, axles=(1.525, -1.325), arch_gap=0.05),
         body=((-2.475, 1.02), (-2.44, 1.12), (0.80, 1.12), (1.30, 1.10), (2.30, 1.05), (2.475, 0.96)),
         roof=((-2.44, 1.12), (-2.41, 1.78), (-2.33, 1.87), (0.00, 1.89), (0.12, 1.87), (0.80, 1.14)),
         belt=1.12, tumble=0.84,
         glass=dict(side=((-2.22, -0.42), (-0.30, 0.60)), front=(0.13, 0.80), rear=(-2.44, -2.40)),
         seams=(0.70, -0.36, -1.05), hood=0.80, deck=None,
         paint=dict(hex="#e9e8e3", chroma=0.42), rack=True),
    dict(name="Sedan", what="a long rear-drive saloon, the old family car",
         length=5.16, width=1.90, clear=0.15,
         wheel=dict(r=0.34, width=0.245, rim_r=0.20, track=1.60, axles=(1.60, -1.41), arch_gap=0.045),
         body=((-2.58, 0.92), (-2.50, 0.99), (-1.82, 1.00), (0.64, 0.97), (1.60, 0.93), (2.45, 0.86), (2.58, 0.78)),
         roof=((-1.82, 1.00), (-1.30, 1.40), (-1.10, 1.45), (-0.05, 1.46), (0.10, 1.43), (0.64, 0.98)),
         belt=0.97, tumble=0.82,
         glass=dict(side=((-1.20, -0.50), (-0.40, 0.36)), front=(0.10, 0.64), rear=(-1.82, -1.30)),
         seams=(0.58, -0.45, -1.25), hood=0.66, deck=-1.86,
         paint=dict(hex="#1f2024", chroma=0.42)),
    dict(name="Pickup", what="a double-cab pickup, the working truck",
         length=5.33, width=1.855, clear=0.28,
         wheel=dict(r=0.37, width=0.265, rim_r=0.215, track=1.54, axles=(1.735, -1.35), arch_gap=0.05),
         body=((-2.665, 1.12), (-2.62, 1.18), (-1.14, 1.18), (-1.13, 1.16), (0.76, 1.16), (1.70, 1.12), (2.55, 1.06), (2.665, 0.96)),
         roof=((-1.13, 1.16), (-1.10, 1.76), (-1.02, 1.80), (0.05, 1.815), (0.16, 1.79), (0.76, 1.17)),
         belt=1.16, tumble=0.84,
         glass=dict(side=((-0.98, -0.25), (-0.14, 0.58)), front=(0.16, 0.76), rear=(-1.13, -1.10)),
         seams=(0.66, -0.20, -1.00), hood=0.78, deck=None,
         paint=dict(hex="#c4b08a", chroma=0.42),
         bed=dict(tail=-2.64, front=-1.145, floor=0.86, wall=0.045)),
    dict(name="Taxi", what="the saloon as a cab: a roof sign and a painted band (the colours are this build's, not a real livery)",
         length=5.16, width=1.90, clear=0.15,
         wheel=dict(r=0.34, width=0.245, rim_r=0.20, track=1.60, axles=(1.60, -1.41), arch_gap=0.045),
         body=((-2.58, 0.92), (-2.50, 0.99), (-1.82, 1.00), (0.64, 0.97), (1.60, 0.93), (2.45, 0.86), (2.58, 0.78)),
         roof=((-1.82, 1.00), (-1.30, 1.40), (-1.10, 1.45), (-0.05, 1.46), (0.10, 1.43), (0.64, 0.98)),
         belt=0.97, tumble=0.82,
         glass=dict(side=((-1.20, -0.50), (-0.40, 0.36)), front=(0.10, 0.64), rear=(-1.82, -1.30)),
         seams=(0.58, -0.45, -1.25), hood=0.66, deck=-1.86,
         paint=dict(hex="#e6e4dd", chroma=0.42),
         band=dict(hex="#d2742c", chroma=0.42, z=(0.50, 0.62)),
         sign=dict(x=-0.55, size=(0.26, 0.62, 0.17))),
]
# What sticks out past the body's width: the door mirrors, each side (m).
MIRROR_OUT = 0.17
# The grime every car wears (hexes, weathered like the paint): road dust,
# rust where the paint has gone, and the seams, which are held one 8-bit step
# over the ink floor (ink_hold) -- dark, never the ink itself.
GRIME = dict(dust="#9c8a72", rust="#6b3a1f")
# The materials that are not paint. rough is the Unreal roughness; chroma a
# WEATHER chroma (default: the stone's). The tail lamp keeps a lamp's red.
SLOTS = {
    "Glass":  dict(hex="#1b2126", rough=0.06),
    "Trim":   dict(hex="#202022", rough=0.75),
    "Chrome": dict(hex="#8e9398", rough=0.30),
    "Tyre":   dict(hex="#1c1c1c", rough=0.92),
    "Rim":    dict(hex="#7d8288", rough=0.45),
    "Lamp":   dict(hex="#cfd0c8", rough=0.12),
    "Tail":   dict(hex="#9a1c1c", rough=0.20, chroma="blood_chroma"),
    "Plate":  dict(hex="#dcd8cc", rough=0.60),
    "Sign":   dict(hex="#e9dfc0", rough=0.50),
}
PAINT_ROUGH = 0.55
# The palest a car may be, weathered: the souq's stone stops at 0.17
# (WEATHER hi); a white car is allowed a little over it, not a lamp's glow.
PAINT_HI = 0.22

# ---------------------------------------------------------------- parking
# Cars per 100 m of street, per district theme; the island has none (it has
# no street a car could reach). Kinds by weight, per theme where it differs.
PARKING = dict(
    per_100m={"Souq": 0.8, "Gym": 2.5, "Fishmarket": 2.0, "Towers": 3.5, "Marina": 2.5,
              "Highway": 3.0, "Desert": 0.8, "Arena": 3.0},
    mix={"default": (("SUV", 0.35), ("Sedan", 0.30), ("Pickup", 0.20), ("Taxi", 0.15)),
         "Fishmarket": (("Pickup", 0.55), ("SUV", 0.25), ("Sedan", 0.20)),
         "Desert": (("Pickup", 0.50), ("SUV", 0.50))},
    verge_m=0.20,         # a derived district's car stands on the verge, its street side this far off the paving
    kerb_in_m=0.10,       # the souq's stands on its flagstones (its street is walled), this far in from the edge
    lane_m=4.0,           # the street left clear beside a car, at least
    gap_m=1.20,           # between two cars along the street, bumper to bumper
    site_margin_m=0.50,   # outside a fight's or the gate's own room
    fire_clear_m=2.50,    # from a fire's post, like the souq's crates
    prop_gap_m=0.30,      # from a crate or a barrel
    door_clear_m=4.0,     # from a way out
    edge_in_m=1.50,       # inside the district's rim
    jitter=0.35,          # of a step, along the street
    yaw_jitter=4.0,       # degrees, so a row of cars is not a ruler
    tries=(0.12, -0.12, 0.25, -0.25, 0.38, -0.38),   # of a step, up and down the street, when its spot is taken
    fill=(0.50, 1.30))    # a district's count, as a share of its street's density x length


def car(name):
    return next(c for c in CARS if c["name"] == name)


def span_of(c):
    """The footprint: length, and width with the mirrors (m)."""
    return c["length"], c["width"] + 2.0 * MIRROR_OUT


def total_height(c):
    """The roof's top, the rack's or the sign's if it has one (m)."""
    h = max(z for _, z in c["roof"])
    if c.get("rack"):
        h += RACK_TOP
    if c.get("sign"):
        h += c["sign"]["size"][2]
    return h


RACK_TOP = 0.08      # the rack's rails stand this far over the roof (the Unity tool builds them to it)


# ---------------------------------------------------------------- colours
def colours(souq=None):
    """Every colour weathered through the souq's curve, linear RGB, and held
    at the ink floor: nothing a car wears is darker than the stone may be."""
    S = souq or SOUQ
    floor, hold = S.ink_floor(), S.ink_hold()

    def worn(h, chroma=None):
        k = S.WEATHER[chroma] if isinstance(chroma, str) else chroma
        c = S._worn(h, k)[:3]
        y = S._luma(c)
        if y < hold:
            c = tuple(v * hold / max(y, 1e-9) for v in c) if y > 1e-9 else (hold, hold, hold)
        return tuple(round(v, 5) for v in c)

    out = dict(ink_floor=floor, ink_hold=round(hold, 5),
               slots={k: dict(albedo=worn(v["hex"], v.get("chroma")), rough=v["rough"]) for k, v in SLOTS.items()},
               grime={k: worn(h) for k, h in GRIME.items()},
               paint={c["name"]: worn(c["paint"]["hex"], c["paint"]["chroma"]) for c in CARS},
               band={c["name"]: worn(c["band"]["hex"], c["band"]["chroma"]) for c in CARS if c.get("band")})
    return out


def spec_json(souq=None):
    """What the Unity tool reads: the cars, their weathered colours, the
    constants it builds to. One file, written by --json, never by hand."""
    col = colours(souq)
    cars = []
    for c in CARS:
        d = copy.deepcopy(c)
        d.pop("what", None)
        d["paint"] = dict(albedo=col["paint"][c["name"]], rough=PAINT_ROUGH)
        if c.get("band"):
            d["band"] = dict(albedo=col["band"][c["name"]], z=list(c["band"]["z"]))
        d["body"] = [list(p) for p in c["body"]]
        d["roof"] = [list(p) for p in c["roof"]]
        d["glass"] = dict(side=[list(s) for s in c["glass"]["side"]], front=list(c["glass"]["front"]),
                          rear=list(c["glass"]["rear"]))
        d["seams"] = list(c["seams"])
        d["wheel"] = dict(c["wheel"], axles=list(c["wheel"]["axles"]))
        if c.get("sign"):
            d["sign"] = dict(x=c["sign"]["x"], size=list(c["sign"]["size"]))
        d["total_height"] = round(total_height(c), 4)
        cars.append(d)
    return dict(note="WRITTEN by Tools/levels/park_cars.py --json from its CARS and SLOTS tables; "
                     "read by the Unity tool ahmed-fighter-unity/Assets/CarTool. Never edit by hand. "
                     "Metres, x forward, y left, z up; colours linear RGB albedo. Unreal-only.",
                ink_floor=col["ink_floor"], ink_hold=col["ink_hold"], paint_hi=PAINT_HI,
                mirror_out=MIRROR_OUT, rack_top=RACK_TOP,
                grime=dict((k, list(v)) for k, v in col["grime"].items()),
                slots=dict((k, dict(albedo=list(v["albedo"]), rough=v["rough"])) for k, v in col["slots"].items()),
                cars=cars)


def json_text(souq=None):
    return json.dumps(spec_json(souq), indent=1) + "\n"


# ---------------------------------------------------------------- placing
def _mix(theme):
    return PARKING["mix"].get(theme, PARKING["mix"]["default"])


def _rect(x, y, yaw, L, W):
    """A footprint as (x, y, yaw, L, W) -- SOUQ._rect_dist's box."""
    return (x, y, yaw, L, W)


def _corners(r, inset=0.0):
    x, y, yaw, L, W = r
    a = math.radians(yaw); c, s = math.cos(a), math.sin(a)
    out = []
    for fx, fy in ((0.5, 0.5), (0.5, -0.5), (-0.5, -0.5), (-0.5, 0.5)):
        lx, ly = fx * (L - inset), fy * (W - inset)
        out.append((x + lx * c - ly * s, y + lx * s + ly * c))
    return out


def _edge_samples(r, n=9):
    """Points round a footprint's outline."""
    pts = _corners(r)
    out = []
    for i in range(4):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 4]
        for k in range(n):
            t = k / float(n)
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def _seg_rect(a, b, r):
    """Distance from a segment to a footprint (sampled every 20 cm, cm)."""
    (ax, ay), (bx, by) = a, b
    n = max(2, int(math.hypot(bx - ax, by - ay) / 20.0) + 1)
    best = 1e18
    for k in range(n + 1):
        t = k / float(n)
        best = min(best, SOUQ._rect_dist(ax + (bx - ax) * t, ay + (by - ay) * t, r))
    for px, py in _corners(r):
        best = min(best, SOUQ._seg_dist(px, py, a, b))
    return best


def _overlap(r1, r2):
    """Do two footprints overlap (separating axes)?"""
    c1, c2 = _corners(r1), _corners(r2)
    for poly in (c1, c2):
        for i in range(4):
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % 4]
            nx, ny = -(by - ay), bx - ax
            p1 = [nx * x + ny * y for x, y in c1]
            p2 = [nx * x + ny * y for x, y in c2]
            if max(p1) < min(p2) or max(p2) < min(p1):
                return False
    return True


def world_of(d):
    """What a district's cars are placed against, in its own frame (cm):
    the street, the fights, the fires, what stands, the rim, the doors."""
    if "souq" in d:
        P = d["souq"]
        Q = SOUQ.night_of(P)
        props = [dict(x=p["x"], y=p["y"], half=max(P["meshes"][p["mesh"]]["w"], P["meshes"][p["mesh"]]["d"]) * 0.5)
                 for p in P["props"] if p["kind"] not in SOUQ.FIRE_KINDS and p.get("mesh") in P["meshes"]]
        return dict(name=d["stage"]["Name"], theme=d["stage"]["Theme"], where="souq", path=Q["path"], sites=Q["sites"],
                    spurs=SOUQ._spurs(Q), fires=Q["fires"] + Q["door_fires"], solids=list(P["solids"]),
                    props=props, rim=Q["rim_rects"], doors=dict(Q["doors"]), extent=d["extent"])
    Q = d["night"]
    return dict(name=d["stage"]["Name"], theme=d["stage"]["Theme"], where="world", path=Q["path"], sites=Q["sites"],
                spurs=SOUQ._spurs(Q), fires=Q["fires"] + Q["door_fires"], solids=list(Q["solids"]),
                props=[], rim=Q["rim_rects"], doors=dict(Q["doors"]), extent=d["extent"])


def across_of(c, where):
    """How far a car's centre stands from the street's centre line (cm)."""
    hw = c["width"] * 0.5 * 100.0
    if where == "souq":
        return SOUQ.STREET_HALF_WIDTH - hw - PARKING["kerb_in_m"] * 100.0
    return SOUQ.STREET_HALF_WIDTH + hw + MIRROR_OUT * 100.0 + PARKING["verge_m"] * 100.0


def fault(W, row, others=()):
    """Why a car may not stand here, or None. The ONE rule set: park()
    places by it, check() holds every placed car to it."""
    P = PARKING
    r = row["rect"]
    x, y = row["x"], row["y"]
    pts = _edge_samples(r)
    if any(math.hypot(px, py) > W["extent"] - P["edge_in_m"] * 100.0 for px, py in pts):
        return "off its district's edge"
    for s in W["sites"]:
        if SOUQ._rect_dist(s["x"], s["y"], r) < s["r"] + P["site_margin_m"] * 100.0:
            return "in the %s %d fight" % (s["kind"], s["i"] + 1)
    for f in W["fires"]:
        if SOUQ._rect_dist(f["x"], f["y"], r) < f["half"] + P["fire_clear_m"] * 100.0:
            return "on a %s" % f["kind"]
    for sx, sy, sh in W["solids"]:
        if SOUQ._rect_dist(sx, sy, r) < sh + 10.0:
            return "in a block"
    for p in W["props"]:
        if SOUQ._rect_dist(p["x"], p["y"], r) < p["half"] + P["prop_gap_m"] * 100.0:
            return "on a crate"
    for a, b, w in W["spurs"]:
        if _seg_rect(a, b, r) < w + 20.0:
            return "across the paving out to a site or a door"
    for rr in W["rim"]:
        if any(SOUQ._rect_dist(px, py, rr) < 30.0 for px, py in pts):
            return "in the rim"
    for side, (dx, dy) in W["doors"].items():
        if SOUQ._rect_dist(dx, dy, r) < P["door_clear_m"] * 100.0:
            return "in the %s way out" % side
    # the lane: the car's street side stays this far from the centre line,
    # so the street beside it is at least lane_m across -- measured to the
    # body, since a mirror at a metre up does not narrow a way on foot
    inner = min(SOUQ.dist_to_path(W["path"], px, py) for px, py in pts) + MIRROR_OUT * 100.0
    if inner < P["lane_m"] * 100.0 - SOUQ.STREET_HALF_WIDTH - 1.0:
        return "in the lane (%.0f cm left)" % (SOUQ.STREET_HALF_WIDTH + inner)
    # at the kerb, not out in the field or the middle of the street
    centre = SOUQ.dist_to_path(W["path"], x, y)
    if abs(centre - row["across"]) > 40.0:
        return "off its kerb (%.0f cm from the centre line, wants %.0f)" % (centre, row["across"])
    for o in others:
        if o is row:
            continue
        if _overlap(r, o["rect"]):
            return "on another car"
        if abs(o["s"] - row["s"]) < (o["L"] + row["L"]) * 0.5 + P["gap_m"] * 100.0:
            return "bumper to bumper with another car"
    return None


def park(W, idx):
    """Cars along one district's street: every step (its density, jittered)
    a kind by the theme's mix, a hashed kerb, parallel to the street and
    either way round; kept only where fault() finds nothing."""
    density = PARKING["per_100m"].get(W["theme"], 0.0)
    if density <= 0.0:
        return []
    path = W["path"]; s_ = SOUQ._arc(path); total = s_[-1]
    step = 100.0 * 100.0 / density
    mix = _mix(W["theme"]); acc = sum(w for _, w in mix)
    out = []
    ss, n = step * 0.5, 0
    while ss < total - 300.0:
        seed = idx * 9203 + n * 41 + 11
        at_s = ss + (SOUQ.hash01(seed + 1) - 0.5) * 2.0 * PARKING["jitter"] * step
        pick, a = SOUQ.hash01(seed + 2) * acc, 0.0
        name = mix[-1][0]
        for k, w in mix:
            a += w
            if pick <= a:
                name = k
                break
        c = car(name)
        first = 1.0 if SOUQ.hash01(seed + 3) < 0.5 else -1.0
        L, Wd = span_of(c)
        across = across_of(c, W["where"])
        flip = 180.0 if SOUQ.hash01(seed + 4) < 0.5 else 0.0
        wobble = (SOUQ.hash01(seed + 5) - 0.5) * 2.0 * PARKING["yaw_jitter"]
        # its kerb first, then the other, then a little up and down the street
        for shift, side in [(0.0, first), (0.0, -first)] + [(f * step, sd) for f in PARKING["tries"]
                                                             for sd in (first, -first)]:
            px, py, tx, ty = SOUQ._at(path, s_, at_s + shift)
            x, y = px - ty * side * across, py + tx * side * across
            yaw = math.degrees(math.atan2(ty, tx)) + flip + wobble
            # on the souq's flagstones, or on the ground beside a district's paving
            z = SOUQ.STREET_Z_CM if W["where"] == "souq" else 0.0
            row = dict(kind="car", car=name, mesh="SM_Car_%s" % name, x=x, y=y, z=z, yaw=yaw,
                       s=at_s + shift, side=side, across=across, L=L * 100.0, W=Wd * 100.0,
                       H=total_height(c) * 100.0, rect=_rect(x, y, yaw, L * 100.0, Wd * 100.0))
            if 0.0 < row["s"] < total and fault(W, row, out) is None:
                out.append(row)
                break
        ss += step; n += 1
    return out


def park_district(d, idx):
    """A district's cars in world coordinates, or none (the island)."""
    if "island" in d:
        return []
    W = world_of(d)
    rows = park(W, idx)
    d["cars"] = dict(world=W, rows=rows)
    out = []
    for r in rows:
        w = dict(r)
        w["x"] += d["ox"]; w["y"] += d["oy"]
        w["rect"] = _rect(w["x"], w["y"], r["yaw"], r["L"], r["W"])
        w["district"] = idx
        out.append(w)
    return out


# ------------------------------------------------------------------ check
def check_spec(souq=None, on_disk=True):
    """C1-C4: the tables can be built, and cars.json is what they say."""
    S = souq or SOUQ
    col = colours(S)
    floor = col["ink_floor"]
    for c in CARS:
        n = c["name"]
        w = c["wheel"]
        # C1. the wheelbase and the wheels fit the car and its arches
        front, rear = w["axles"]
        assert -c["length"] / 2 + w["r"] + w["arch_gap"] < rear < front < c["length"] / 2 - w["r"] - w["arch_gap"], \
            "%s: a wheel stands past the end of the car" % n
        assert w["track"] / 2 + w["width"] / 2 <= c["width"] / 2 - 0.02, "%s: the tyres stand out past the body" % n
        assert w["rim_r"] < w["r"] - 0.08, "%s: the rim leaves no tyre" % n
        arch_top = 2.0 * w["r"] + w["arch_gap"]
        for x in w["axles"]:
            top = _line_at(c["body"], x)
            assert top - arch_top >= 0.12, "%s: the arch over the %s axle leaves %.0f mm of body under the %s" \
                % (n, "front" if x > 0 else "rear", (top - arch_top) * 1000.0, "bonnet" if x > 0 else "boot")
        assert c["clear"] < w["r"], "%s: the sill is higher than the axle" % n
        # C2. the lines run tail to nose and stay inside the car; the roof
        #     stands on the body at both ends and over it between
        for key in ("body", "roof"):
            xs = [p[0] for p in c[key]]
            assert xs == sorted(xs) and len(set(xs)) == len(xs), "%s: its %s line does not run tail to nose" % (n, key)
            assert xs[0] >= -c["length"] / 2 - 1e-9 and xs[-1] <= c["length"] / 2 + 1e-9, "%s: its %s line leaves the car" % (n, key)
        for x, z in (c["roof"][0], c["roof"][-1]):
            assert abs(z - _line_at(c["body"], x)) <= 0.03, "%s: the roof does not stand on the body at x %.2f" % (n, x)
        assert all(z >= c["belt"] - 1e-9 for _, z in c["roof"]), "%s: the roof dips under the belt" % n
        rx0, rx1 = c["roof"][0][0], c["roof"][-1][0]
        for a, b in list(c["glass"]["side"]) + [c["glass"]["front"], c["glass"]["rear"]]:
            assert rx0 - 1e-9 <= a < b <= rx1 + 1e-9, "%s: a window (%.2f..%.2f) is off the cabin" % (n, a, b)
        sides = sorted(c["glass"]["side"])
        for (a0, a1), (b0, b1) in zip(sides, sides[1:]):
            assert b0 - a1 >= 0.08, "%s: a pillar between two windows is %.0f mm" % (n, (b0 - a1) * 1000.0)
        if c.get("bed"):
            b = c["bed"]
            assert b["tail"] > -c["length"] / 2 and b["front"] < rx0 + 0.02, "%s: the bed runs into the cab" % n
            assert b["floor"] < _line_at(c["body"], (b["tail"] + b["front"]) / 2) - 0.2, "%s: the bed is not a bed" % n
    # C3. every colour is in the soot band: over the ink, a car's paint no
    #     paler than PAINT_HI, and cars.json is the tables' own
    for k, v in list(col["paint"].items()) + list(col["band"].items()) + list(col["grime"].items()):
        y = S._luma(v)
        assert y >= floor - 1e-6, "%s's paint is %.4f, under the ink floor %.3f" % (k, y, floor)
        assert y <= PAINT_HI, "%s's paint is %.3f, a glow in the souq's soot (at most %.2f)" % (k, y, PAINT_HI)
    for k, v in col["slots"].items():
        assert S._luma(v["albedo"]) >= floor - 1e-6, "%s is %.4f, under the ink floor %.3f" % (k, S._luma(v["albedo"]), floor)
    if on_disk:
        assert os.path.exists(JSON_PATH), "cars.json is not written: park_cars.py --json"
        have = open(JSON_PATH, encoding="utf-8").read()
        assert have == json_text(S), "cars.json has drifted from CARS / SLOTS: park_cars.py --json"
    return col


def _line_at(line, x):
    for (x0, z0), (x1, z1) in zip(line, line[1:]):
        if x0 <= x <= x1:
            return z0 + (z1 - z0) * ((x - x0) / (x1 - x0) if x1 > x0 else 0.0)
    return line[0][1] if x < line[0][0] else line[-1][1]


def check(P, on_disk=True):
    """C1-C4 over the tables; C5-C7 over every car the world placed."""
    check_spec(SOUQ, on_disk=on_disk)
    by = {}
    for r in P["cars"]:
        by.setdefault(r["district"], []).append(r)
    n_all = 0
    for idx, d in P["districts"].items():
        rows = d.get("cars", {}).get("rows", [])
        if "island" in d:
            assert not rows and not by.get(idx), "the island has cars"
            continue
        W = d["cars"]["world"]
        # C5. every car where one may stand: fault() finds nothing
        for r in rows:
            why = fault(W, r, rows)
            assert why is None, "%s: a %s is %s" % (W["name"], r["car"], why)
        # C6. the street holds its share: not a car here and there
        L = SOUQ._arc(W["path"])[-1] / 100.0
        want = PARKING["per_100m"].get(W["theme"], 0.0) * L / 100.0
        lo, hi = PARKING["fill"]
        assert lo * want <= len(rows) <= hi * want + 1, "%s holds %d cars along %.0f m (wants %.1f, %.0f-%.0f %%)" \
            % (W["name"], len(rows), L, want, lo * 100.0, hi * 100.0)
        # C7. the world has what the district planned, moved to its origin
        placed = by.get(idx, [])
        assert len(placed) == len(rows), "%s planned %d cars and the world has %d" % (W["name"], len(rows), len(placed))
        for a, b in zip(rows, placed):
            assert abs(a["x"] + d["ox"] - b["x"]) < 0.01 and abs(a["y"] + d["oy"] - b["y"]) < 0.01, \
                "%s: a car moved between the district and the world" % W["name"]
        n_all += len(rows)
    kinds = sorted({r["car"] for r in P["cars"]})
    assert kinds == sorted(c["name"] for c in CARS), "the world parks %s, not all four" % ", ".join(kinds)
    return n_all


# ------------------------------------------------------------------- bite
def bite(P, verbose=True):
    """Each rule, broken once on a copy of the world's cars; each must be
    caught by its own line. The unbroken world passes first."""
    check(P)
    first = max((idx for idx, d in P["districts"].items() if d.get("cars", {}).get("rows")),
                key=lambda i: len(P["districts"][i]["cars"]["rows"]))
    D = P["districts"][first]; W = D["cars"]["world"]

    def moved(r, x, y, yaw=None):
        r = dict(r, x=x, y=y, yaw=r["yaw"] if yaw is None else yaw)
        r["rect"] = _rect(r["x"], r["y"], r["yaw"], r["L"], r["W"])
        return r

    def along(r, ds, d_across=0.0):
        s_ = SOUQ._arc(W["path"])
        px, py, tx, ty = SOUQ._at(W["path"], s_, r["s"] + ds)
        a = r["across"] + d_across
        rr = moved(r, px - ty * r["side"] * a, py + tx * r["side"] * a, math.degrees(math.atan2(ty, tx)))
        rr["s"] = r["s"] + ds
        return rr

    def one(make, needle):
        """The first car whose sabotaged self breaks exactly this rule --
        so the case proves the rule, not a neighbouring one."""
        def go(rows):
            for i, r in enumerate(rows):
                for bad in make(r):
                    why = fault(W, bad, rows[:i] + [bad] + rows[i + 1:])
                    if why and needle in why:
                        return rows[:i] + [bad] + rows[i + 1:]
            return rows
        return go

    def on_rows(fn):
        def go(Pc):
            rows = Pc["districts"][first]["cars"]["rows"]
            rows[:] = fn(rows)
            Pc["cars"] = [r for r in Pc["cars"] if r["district"] != first] + [
                dict(r, x=r["x"] + D["ox"], y=r["y"] + D["oy"], district=first) for r in rows]
        return go

    cases = [
        ("in a fight", on_rows(one(lambda r: [moved(r, s["x"], s["y"]) for s in W["sites"]], "fight")), "fight"),
        ("on a fire", on_rows(one(lambda r: [moved(r, f["x"] + dx, f["y"]) for f in W["fires"] for dx in (150.0, -150.0)],
                                  "on a ")), "on a "),
        ("in the lane", on_rows(one(lambda r: [along(r, 0.0, -d) for d in (150.0, 250.0, 330.0)], "in the lane")),
         "in the lane"),
        ("off the kerb", on_rows(one(lambda r: [along(r, 0.0, 150.0)], "kerb")), "kerb"),
        ("on another car", on_rows(lambda rows: rows + [along(rows[0], 60.0)]), "car"),
        ("off the edge", on_rows(one(lambda r: [moved(r, W["extent"] * 0.999, 0.0)], "edge")), "edge"),
        ("a sparse street", on_rows(lambda rows: rows[:1]), "holds"),
        ("a car lost on the way", lambda Pc: Pc.__setitem__("cars", Pc["cars"][:-1]), "planned"),
    ]
    caught = 0
    for name, sabotage, needle in cases:
        Pc = dict(P, cars=[dict(r) for r in P["cars"]],
                  districts={k: dict(v, cars=dict(v["cars"], rows=[dict(r) for r in v["cars"]["rows"]]))
                             if v.get("cars") else v for k, v in P["districts"].items()})
        sabotage(Pc)
        try:
            check(Pc)
            got = None
        except AssertionError as e:
            got = str(e)
        ok = got is not None and needle in got
        caught += ok
        if verbose:
            print("  %-22s %s  (%s)" % (name, "caught" if ok else "NOT CAUGHT", got or "passed"))
    # the tables
    raw = lambda h, k=None: SOUQ._lin(SOUQ._hex(h))
    spec_cases = [
        ("a wheel too big", lambda: car("Sedan")["wheel"].__setitem__("r", 0.44), "arch"),
        ("a dark paint, unheld", lambda: car("Sedan")["paint"].__setitem__("hex", "#000000") or
         setattr(SOUQ, "ink_hold", lambda floor=None: 0.0), "Sedan's paint"),
        ("paint not weathered", lambda: setattr(SOUQ, "_worn", raw), "glow"),
        ("a window off the cab", lambda: car("Pickup")["glass"].__setitem__("front", (0.16, 0.95)), "window"),
        ("cars.json by hand", lambda: car("SUV").__setitem__("length", 4.96), "drifted"),
    ]
    worn, hold = SOUQ._worn, SOUQ.ink_hold
    for name, sabotage, needle in spec_cases:
        saved = copy.deepcopy(CARS)
        sabotage()
        try:
            check_spec(SOUQ)
            got = None
        except AssertionError as e:
            got = str(e)
        CARS[:] = saved
        SOUQ._worn, SOUQ.ink_hold = worn, hold
        ok = got is not None and needle in got
        caught += ok
        if verbose:
            print("  %-22s %s  (%s)" % (name, "caught" if ok else "NOT CAUGHT", got or "passed"))
    total = len(cases) + len(spec_cases)
    check(P)
    print("  %d of %d car sabotages caught" % (caught, total))
    return caught == total


def describe(P):
    by = {}
    for r in P["cars"]:
        by.setdefault(r["district"], []).append(r)
    for idx, d in P["districts"].items():
        rows = by.get(idx, [])
        if not d.get("cars"):
            continue
        kinds = {}
        for r in rows:
            kinds[r["car"]] = kinds.get(r["car"], 0) + 1
        L = SOUQ._arc(d["cars"]["world"]["path"])[-1] / 100.0
        print("  %-16s %3d cars along %4.0f m  (%s)" % (d["stage"]["Name"], len(rows), L,
              ", ".join("%d %s" % (v, k) for k, v in sorted(kinds.items()))))
    print("  %d cars in the world" % len(P["cars"]))


# ----------------------------------------------------------------- editor
def build_in_editor(P, spawn):
    """Inside the editor: the Unity tool's FBX and paint into /Game, one
    material per slot, and a StaticMeshActor per placed car. Read-reviewed,
    not run.

    The Unity FBX Exporter writes a Y-up, left-handed scene converted for
    FBX; which way Unreal's importer then lays the car's length has never
    been seen. So nothing about the import is assumed: each car's mesh is
    measured after it lands, its long axis turned onto the actor's X, its
    size taken to the spec's length, its footprint centred and its lowest
    point put on the ground -- and a mesh whose height is not the spec's
    (lying on its side) is refused, never placed."""
    import unreal  # noqa: E402  (only importable inside the editor)
    EAL = unreal.EditorAssetLibrary
    MEL = unreal.MaterialEditingLibrary
    AT = unreal.AssetToolsHelpers.get_asset_tools()
    spec = json.load(open(JSON_PATH, encoding="utf-8"))
    names = sorted({r["car"] for r in P["cars"]})
    have = [n for n in names if os.path.exists(os.path.join(CARS_DIR, "SM_Car_%s.fbx" % n))
            and os.path.exists(os.path.join(TEX_DIR, "T_Car_%s_Paint.png" % n))]
    for n in sorted(set(names) - set(have)):
        unreal.log_error("SM_Car_%s.fbx or its paint is not built: run SAUD > Build Street Cars in the Unity "
                         "project (ahmed-fighter-unity) first. Its cars are not placed." % n)
    if not have:
        return 0

    tasks = []
    for n in have:
        t = unreal.AssetImportTask()
        t.filename = os.path.join(TEX_DIR, "T_Car_%s_Paint.png" % n); t.destination_path = TEX_ASSET_DIR
        t.automated = True; t.save = True; t.replace_existing = True
        tasks.append(t)
        t = unreal.AssetImportTask()
        t.filename = os.path.join(CARS_DIR, "SM_Car_%s.fbx" % n); t.destination_path = MESH_DIR
        t.automated = True; t.save = True; t.replace_existing = True
        ui = unreal.FbxImportUI(); ui.import_mesh = True; ui.import_materials = False; ui.import_textures = False
        ui.import_as_skeletal = False; ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        ui.static_mesh_import_data.set_editor_property("combine_meshes", True)
        t.options = ui; tasks.append(t)
    AT.import_asset_tasks(tasks)

    def asset(name, cls, factory):
        path = "%s/%s" % (MAT_DIR, name)
        if EAL.does_asset_exist(path):
            return unreal.load_asset(path), False
        return AT.create_asset(name, MAT_DIR, cls, factory), True

    paint, new = asset("M_Car_Paint", unreal.Material, unreal.MaterialFactoryNew())
    if new:
        tex = MEL.create_material_expression(paint, unreal.MaterialExpressionTextureSampleParameter2D, -400, 0)
        tex.set_editor_property("parameter_name", "Paint")
        rough = MEL.create_material_expression(paint, unreal.MaterialExpressionScalarParameter, -400, 250)
        rough.set_editor_property("parameter_name", "Rough")
        MEL.connect_material_property(tex, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(paint)
    flat, new = asset("M_Car_Flat", unreal.Material, unreal.MaterialFactoryNew())
    if new:
        base = MEL.create_material_expression(flat, unreal.MaterialExpressionVectorParameter, -400, 0)
        base.set_editor_property("parameter_name", "Base")
        rough = MEL.create_material_expression(flat, unreal.MaterialExpressionScalarParameter, -400, 200)
        rough.set_editor_property("parameter_name", "Rough")
        MEL.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
        MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(flat)

    def mi_of(name, parent):
        mi, _ = asset(name, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        return mi

    flats = {}
    for slot, v in spec["slots"].items():
        mi = mi_of("MI_Car_%s" % slot, flat)
        MEL.set_material_instance_vector_parameter_value(mi, "Base", unreal.LinearColor(*(v["albedo"] + [1.0])))
        MEL.set_material_instance_scalar_parameter_value(mi, "Rough", v["rough"])
        EAL.save_loaded_asset(mi)
        flats[slot] = mi

    fit = {}
    for n in have:
        c = next(x for x in spec["cars"] if x["name"] == n)
        mesh = unreal.load_asset("%s/SM_Car_%s" % (MESH_DIR, n))
        mi = mi_of("MI_Car_%s_Paint" % n, paint)
        MEL.set_material_instance_texture_parameter_value(
            mi, "Paint", unreal.load_asset("%s/T_Car_%s_Paint" % (TEX_ASSET_DIR, n)))
        MEL.set_material_instance_scalar_parameter_value(mi, "Rough", c["paint"]["rough"])
        EAL.save_loaded_asset(mi)
        # every slot by the name the Unity tool gave its material: M_Car_<Name>_<Slot>
        for i, sm in enumerate(mesh.get_editor_property("static_materials")):
            slot = str(sm.get_editor_property("material_slot_name")).split("_")[-1]
            mesh.set_material(i, mi if slot == "Paint" else flats.get(slot, flats["Trim"]))
        EAL.save_loaded_asset(mesh)
        # measured, not assumed
        box = mesh.get_bounding_box()
        lo, hi = box.min, box.max
        ex, ey, ez = hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
        turn = 0.0 if ex >= ey else 90.0
        long_ = max(ex, ey)
        k = c["length"] * 100.0 / long_ if long_ > 0 else 0.0
        want_h = c["total_height"] * 100.0
        if k <= 0 or abs(ez * k - want_h) > 0.08 * want_h:
            unreal.log_error("SM_Car_%s came in %.0f x %.0f x %.0f cm: its height is not the spec's %.0f at its "
                             "length, so it is lying down or scaled apart. Not placed." % (n, ex, ey, ez, want_h))
            continue
        fit[n] = dict(mesh=mesh, turn=turn, k=k, cx=(lo.x + hi.x) * 0.5, cy=(lo.y + hi.y) * 0.5, z0=lo.z)

    placed = 0
    for i, r in enumerate(P["cars"]):
        f = fit.get(r["car"])
        if f is None:
            continue
        yaw = r["yaw"] + f["turn"]
        a = math.radians(yaw)
        # the mesh's own footprint centre, turned and scaled, put on the row's point
        ox = (f["cx"] * math.cos(a) - f["cy"] * math.sin(a)) * f["k"]
        oy = (f["cx"] * math.sin(a) + f["cy"] * math.cos(a)) * f["k"]
        name = P["districts"][r["district"]]["stage"]["Name"]
        act = spawn(unreal.StaticMeshActor, "Car_%s_%03d" % (r["car"], i), r["x"] - ox, r["y"] - oy,
                    r["z"] - f["z0"] * f["k"], yaw, folder="Cars/%s" % name)
        comp = act.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_static_mesh(f["mesh"])
        act.set_actor_scale3d(unreal.Vector(f["k"], f["k"], f["k"]))
        act.set_mobility(unreal.ComponentMobility.STATIC)
        placed += 1
    unreal.log("The cars: %d placed of %d planned" % (placed, len(P["cars"])))
    return placed


if __name__ == "__main__":
    a = sys.argv[1:]
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_world", os.path.join(HERE, "build_world.py"))
    BW = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(BW)
    M = BW.PARK                          # the copy the world plans with, handed its build_souq
    if "--json" in a:
        M.check_spec(M.SOUQ, on_disk=False)
        os.makedirs(CARS_DIR, exist_ok=True)
        with open(JSON_PATH, "w", encoding="utf-8") as fh:
            fh.write(M.json_text(M.SOUQ))
        print("wrote %s" % os.path.relpath(JSON_PATH, PROJECT))
        sys.exit(0)
    P = BW.plan(*BW.load())
    if "--bite" in a:
        sys.exit(0 if M.bite(P) else 1)
    n = M.check(P)
    M.describe(P)
    print("checked: %d cars, every one at its kerb, out of every fight, fire, block, way out and lane" % n)
