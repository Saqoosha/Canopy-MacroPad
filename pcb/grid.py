"""A grid and an A* over it, which is what routing this board actually needs.

The first attempt drew L-shaped paths between pad pairs and failed on
almost everything: it could not leave the RP2040 at all -- "no way from
the pad to the channel" for all six key nets -- because an escape from a
0.4 mm-pitch QFN is a sequence of small dodges, not a corner. Nine other
nets failed as "local L blocked" for the same reason at a smaller scale.

So: rasterise every obstacle once, and search. The board is 139.6 x 21.59
mm, which at a 0.1 mm cell is 1396 x 216 per layer -- small enough that
being exhaustive costs nothing and being clever costs correctness.

The inflation is the whole game. A cell is blocked for a net if any
copper of ANOTHER net comes within (trace/2 + clearance) of it, so a path
through free cells is legal by construction and audit.py should find
nothing. Obstacles are inflated by their bounding box, which is exact for
the rectangles and circles this board is made of and conservative for the
rest -- conservative in the safe direction: it can refuse a legal route,
never permit an illegal one.
"""

import heapq
import math

import geom

MIL = 0.0254
MM = 1.0 / MIL

# A cell wanted by two different nets belongs to neither.
SHARED = "#shared"


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def point_shape_dist(px, py, poly):
    """Distance from a point to a convex polygon; 0 inside."""
    inside = True
    best = float("inf")
    n = len(poly)
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        ex, ey = bx - ax, by - ay
        L2 = ex * ex + ey * ey
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * ex
                                                   + (py - ay) * ey) / L2))
        dx, dy = px - (ax + t * ex), py - (ay + t * ey)
        best = min(best, math.hypot(dx, dy))
        if (bx - ax) * (py - ay) - (by - ay) * (px - ax) < 0:
            inside = False
    return 0.0 if inside else best


class Grid:
    def __init__(self, x0, y0, x1, y1, cell_mm, layers=(1, 2)):
        self.cell = cell_mm / MIL
        self.x0, self.y0 = x0, y0
        self.nx = int((x1 - x0) / self.cell) + 1
        self.ny = int((y1 - y0) / self.cell) + 1
        self.layers = list(layers)
        self.li = {l: i for i, l in enumerate(self.layers)}
        # owner[layer][y][x] -- None free, or a net name that owns it.
        self.owner = [[[None] * self.nx for _ in range(self.ny)]
                      for _ in self.layers]
        # A second, more generously inflated map, for deciding where a VIA
        # may go. A via is 0.45 mm across where a trace is 0.15, so a cell
        # that is free for a trace is very often not free for a via -- and
        # routing that did not know the difference put twenty-two vias
        # within 0.047 mm of a QFN pad, against a 0.102 mm rule. The search
        # consults this one, and only this one, before changing layer.
        self.via_owner = [[[None] * self.nx for _ in range(self.ny)]
                          for _ in self.layers]
        # Drill holes are physical voids, not copper. Same-net copper may
        # overlap; same-net drill holes may not.
        self.drill_blocked = [[False] * self.nx for _ in range(self.ny)]
        # Optional per-net lane preferences, populated by the board router.
        # Each value is (first_x_cell, last_x_cell, preferred_y_cell,
        # cost_per_cell).  This is a preference, not an obstacle: a net may
        # leave the lane when component escapes require it.
        self.preferred_lanes = {}

    def cell_of(self, x, y):
        return (int(round((x - self.x0) / self.cell)),
                int(round((y - self.y0) / self.cell)))

    def xy_of(self, i, j):
        return (self.x0 + i * self.cell, self.y0 + j * self.cell)

    def mark_shape(self, layer, poly, inflate, net, via=False):
        """Claim cells whose centre is within `inflate` of the SHAPE.

        Not of its bounding box. On a 0.4 mm-pitch QFN the difference is
        the whole game: a pin is 0.2 mm wide and 0.665 mm long, its
        neighbours are 0.4 mm away across, and inflating the box puts a
        0.205 mm wall off the END of the pad too -- where no neighbour is.
        Printed as a map, every KEY pin came out walled in on its own row
        with nowhere to go, and eight nets reported "no path" for a board
        that has room. Measured properly the first free cell past the pad
        end is 0.447 mm from the nearest other pin, twice the clearance.
        """
        b = bbox(poly)
        i0 = max(0, int(math.floor((b[0] - inflate - self.x0) / self.cell)))
        i1 = min(self.nx - 1,
                 int(math.ceil((b[2] + inflate - self.x0) / self.cell)))
        j0 = max(0, int(math.floor((b[1] - inflate - self.y0) / self.cell)))
        j1 = min(self.ny - 1,
                 int(math.ceil((b[3] + inflate - self.y0) / self.cell)))
        maps = ([self.via_owner[self.li[l]] for l in self.layers] if via
                else [self.owner[self.li[l]]
                      for l in ([layer] if layer in self.li else self.layers)])
        for j in range(j0, j1 + 1):
            y = self.y0 + j * self.cell
            for i in range(i0, i1 + 1):
                x = self.x0 + i * self.cell
                if point_shape_dist(x, y, poly) > inflate:
                    continue
                for m in maps:
                    cur = m[j][i]
                    if cur is None:
                        m[j][i] = net
                    elif cur != net:
                        m[j][i] = SHARED

    def mark_box(self, layer, b, inflate, net):
        """Claim every cell whose centre lies in the inflated box."""
        i0 = max(0, int(math.floor((b[0] - inflate - self.x0) / self.cell)))
        i1 = min(self.nx - 1,
                 int(math.ceil((b[2] + inflate - self.x0) / self.cell)))
        j0 = max(0, int(math.floor((b[1] - inflate - self.y0) / self.cell)))
        j1 = min(self.ny - 1,
                 int(math.ceil((b[3] + inflate - self.y0) / self.cell)))
        for l in ([layer] if layer in self.li else self.layers):
            g = self.owner[self.li[l]]
            for j in range(j0, j1 + 1):
                row = g[j]
                for i in range(i0, i1 + 1):
                    cur = row[i]
                    if cur is None:
                        row[i] = net
                    elif cur != net:
                        row[i] = SHARED

    def stamp_core(self, layer, b, net):
        """Re-claim a pad's own cells after the halos have been laid.

        A halo is the clearance around copper, and two pads close together
        have overlapping halos. Marked first-writer-wins, the overlap ends
        up owned by whichever pad was marked first -- and then routing the
        OTHER net finds those cells free and runs a trace 0.15 mm from
        copper it should be 0.10 from. That is where every one of the
        pad-via and pad-trace findings came from, and it was there from
        the first version. SHARED fixes it by blocking contested cells for
        everyone; this puts each pad's own body back afterwards, because a
        pad that its own net cannot reach is not routable at all.
        """
        i0, j0 = self.cell_of(b[0], b[1])
        i1, j1 = self.cell_of(b[2], b[3])
        for l in ([layer] if layer in self.li else self.layers):
            g = self.owner[self.li[l]]
            for j in range(max(0, j0), min(self.ny - 1, j1) + 1):
                for i in range(max(0, i0), min(self.nx - 1, i1) + 1):
                    g[j][i] = net

    def mark_box_via(self, b, inflate, net):
        """Claim via-map cells. A via is through-hole, so all layers."""
        i0 = max(0, int(math.floor((b[0] - inflate - self.x0) / self.cell)))
        i1 = min(self.nx - 1,
                 int(math.ceil((b[2] + inflate - self.x0) / self.cell)))
        j0 = max(0, int(math.floor((b[1] - inflate - self.y0) / self.cell)))
        j1 = min(self.ny - 1,
                 int(math.ceil((b[3] + inflate - self.y0) / self.cell)))
        for l in self.layers:
            g = self.via_owner[self.li[l]]
            for j in range(j0, j1 + 1):
                row = g[j]
                for i in range(i0, i1 + 1):
                    cur = row[i]
                    if cur is None:
                        row[i] = net
                    elif cur != net:
                        row[i] = SHARED

    def free_via(self, i, j, net):
        if i < 0 or j < 0 or i >= self.nx or j >= self.ny:
            return False
        if self.drill_blocked[j][i]:
            return False
        for l in self.layers:
            o = self.via_owner[self.li[l]][j][i]
            if not (o is None or o == net):
                return False
        return True

    def mark_drill(self, poly, inflate):
        """Forbid candidate via centres around an existing drilled hole."""
        b = bbox(poly)
        i0 = max(0, int(math.floor((b[0] - inflate - self.x0) / self.cell)))
        i1 = min(self.nx - 1,
                 int(math.ceil((b[2] + inflate - self.x0) / self.cell)))
        j0 = max(0, int(math.floor((b[1] - inflate - self.y0) / self.cell)))
        j1 = min(self.ny - 1,
                 int(math.ceil((b[3] + inflate - self.y0) / self.cell)))
        for j in range(j0, j1 + 1):
            y = self.y0 + j * self.cell
            for i in range(i0, i1 + 1):
                x = self.x0 + i * self.cell
                if point_shape_dist(x, y, poly) <= inflate:
                    self.drill_blocked[j][i] = True

    def free_for(self, layer, i, j, net):
        if i < 0 or j < 0 or i >= self.nx or j >= self.ny:
            return False
        o = self.owner[self.li[layer]][j][i]
        return o is None or o == net

    def search(self, starts, goals, net, via_cost=25.0, bend_cost=8.0):
        """A* from any start cell to any goal cell, over (layer, i, j).

        `starts` and `goals` are iterables of (layer, i, j). Returns a list
        of (layer, i, j) or None. Cost is in cells; a layer change costs
        `via_cost` cells, which is what stops it stitching vias every time
        a straight line would do.
        """
        goalset = set(goals)
        if not goalset:
            return None
        gx = sum(g[1] for g in goalset) / len(goalset)
        gy = sum(g[2] for g in goalset) / len(goalset)
        lane = self.preferred_lanes.get(net)

        def lane_cost(i, j):
            if lane is None:
                return 0.0
            i0, i1, preferred_j, cost = lane
            if i0 <= i <= i1:
                return abs(j - preferred_j) * cost
            return 0.0

        def h(n):
            return abs(n[1] - gx) + abs(n[2] - gy)

        # Direction is part of the state.  Without it, two paths arriving
        # at the same cell are treated as equivalent even when one arrives
        # straight and the other has just turned.  The old search therefore
        # won distance ties by heap order and produced hundreds of tiny
        # zig-zag segments on an otherwise empty layer.
        openq = []
        best = {}
        for s in starts:
            if not self.free_for(s[0], s[1], s[2], net):
                continue
            state = (s[0], s[1], s[2], 0, 0)
            best[state] = 0.0
            heapq.heappush(openq, (h(s), 0.0, state))
        if not openq:
            return None
        came = {}
        while openq:
            f, g, state = heapq.heappop(openq)
            if g > best.get(state, float("inf")):
                continue
            node = state[:3]
            if node in goalset:
                states = [state]
                while came.get(states[-1]) is not None:
                    states.append(came[states[-1]])
                states.reverse()
                return [s[:3] for s in states]
            l, i, j, pdi, pdj = state
            for dl, di, dj, cost in (
                    (0, 1, 0, 1.0), (0, -1, 0, 1.0),
                    (0, 0, 1, 1.0), (0, 0, -1, 1.0),
                    (0, 1, 1, 1.414), (0, 1, -1, 1.414),
                    (0, -1, 1, 1.414), (0, -1, -1, 1.414)):
                nb = (l, i + di, j + dj)
                if not self.free_for(l, nb[1], nb[2], net):
                    continue
                # A diagonal step cuts the corner between two cells, and
                # the copper drawn along it sits where neither cell centre
                # was tested. Routing that let it produced real overlaps of
                # up to 0.07 mm against pads the grid thought were cleared.
                # So a diagonal is only legal when both of the orthogonal
                # cells it passes are free too.
                if di and dj and not (self.free_for(l, i + di, j, net)
                                      and self.free_for(l, i, j + dj, net)):
                    continue
                turn = 0.0 if (pdi, pdj) in ((0, 0), (di, dj)) else bend_cost
                ng = g + cost + turn + lane_cost(nb[1], nb[2])
                ns = (nb[0], nb[1], nb[2], di, dj)
                if ng < best.get(ns, float("inf")):
                    best[ns] = ng
                    came[ns] = state
                    heapq.heappush(openq, (ng + h(nb), ng, ns))
            if not self.free_via(i, j, net):
                continue
            for other in self.layers:
                if other == l:
                    continue
                nb = (other, i, j)
                if not self.free_for(other, i, j, net):
                    continue
                ng = g + via_cost
                ns = (nb[0], nb[1], nb[2], 0, 0)
                if ng < best.get(ns, float("inf")):
                    best[ns] = ng
                    came[ns] = state
                    heapq.heappush(openq, (ng + h(nb), ng, ns))
        return None


def simplify(path):
    """Collapse a cell path into the fewest straight runs, plus vias.

    The last cell of the path MUST be reached. An earlier version ended
    with `if len(run) > 1: emit(run[0], run[-1])`, which silently dropped
    the final hop whenever the path turned a corner on its second-to-last
    cell -- the run left over was one cell long and emitted nothing. The
    search had reached the goal pad; the drawing stopped one cell short.
    Ten nets came back "not fully connected" against a board whose router
    reported 30/30, which is the worst kind of disagreement: both halves
    were telling the truth about different things.
    """
    if not path:
        return []
    out = []
    run = [path[0]]
    for node in path[1:]:
        if node[0] != run[-1][0]:
            if len(run) > 1:
                out.append(("line", run[0], run[-1]))
            out.append(("via", run[-1], node))
            run = [node]
            continue
        if len(run) >= 2:
            ax = run[-1][1] - run[-2][1]
            ay = run[-1][2] - run[-2][2]
            bx = node[1] - run[-1][1]
            by = node[2] - run[-1][2]
            if (ax, ay) != (bx, by):
                out.append(("line", run[0], run[-1]))
                run = [run[-1]]
        run.append(node)
    if len(run) > 1:
        out.append(("line", run[0], run[-1]))
    elif run and out:
        # One cell left over after a bend: join it to wherever the last
        # emitted piece finished, so the path's end is always drawn.
        last = out[-1][2]
        if last != run[0]:
            out.append(("line", last, run[0]))
    return out


def chamfer_orthogonal_corners(path, grid, net):
    """Replace a one-cell square corner with one legal diagonal step.

    The electrical effect of a right-angle corner on the slow pixel chain
    is negligible. The board still has no reason to draw one. A diagonal is
    inserted only when the same corner-cutting rule used by A* says both
    orthogonal cells are free, so smoothing cannot trade appearance for a
    clearance violation.
    """
    if len(path) < 3:
        return path
    out = [path[0]]
    i = 1
    while i < len(path) - 1:
        a, b, c = out[-1], path[i], path[i + 1]
        same_layer = a[0] == b[0] == c[0]
        ab = (b[1] - a[1], b[2] - a[2])
        bc = (c[1] - b[1], c[2] - b[2])
        cardinal = (
            abs(ab[0]) + abs(ab[1]) == 1
            and abs(bc[0]) + abs(bc[1]) == 1
        )
        right_angle = ab[0] * bc[0] + ab[1] * bc[1] == 0
        if same_layer and cardinal and right_angle:
            other = (a[0], a[1] + bc[0], a[2] + bc[1])
            if grid.free_for(other[0], other[1], other[2], net):
                out.append(c)
                i += 2
                continue
        out.append(b)
        i += 1
    if out[-1] != path[-1]:
        out.append(path[-1])
    return out
