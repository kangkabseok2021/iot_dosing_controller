# Routing Mathematics

## Haversine Great-Circle Distance

Given two points (φ₁, λ₁) and (φ₂, λ₂) in decimal degrees, the great-circle distance is:

| Symbol | Meaning |
|--------|---------|
| R = 6371 km | Mean Earth radius |
| Δφ = φ₂ − φ₁ | Latitude difference (radians) |
| Δλ = λ₂ − λ₁ | Longitude difference (radians) |
| a | Haversine of the central angle |
| d | Great-circle distance (km) |

### Formula derivation

```
a = sin²(Δφ/2) + cos(φ₁) · cos(φ₂) · sin²(Δλ/2)

d = 2R · arcsin(√a)
```

The `haversine` function (hav θ = sin²(θ/2)) is numerically stable for small
distances where the standard spherical law of cosines loses precision.

### Known values used in unit tests

| Route | Expected distance |
|-------|-----------------|
| Same point | 0.000 km |
| Equatorial 1° longitude | 111.195 km ± 0.01 |
| London → Paris | 344.3 km ± 1 |
| Antipodal (0°,0°) → (0°,180°) | 20 015 km ± 1 |

---

## Nearest-Neighbour VRP Heuristic

**Complexity:** O(n²) — for each of n unvisited stops, scan all remaining stops.

**Algorithm:**

```
current ← depot
ordered ← []
remaining ← copy(waypoints)

while remaining:
    next ← argmin_{w ∈ remaining} haversine(current, w)
    current ← remaining.pop(next)
    ordered.append(current)

return ordered
```

**Optimality gap:** The nearest-neighbour heuristic produces tours that are on
average ~20–25% longer than the optimal tour (Rosenkrantz, Stearns & Lewis,
1977 — *An Analysis of Several Heuristics for the Traveling Salesman Problem*).
For production use, exact solvers (OR-Tools, Concorde) or metaheuristics
(2-opt, LKH) are recommended for n > 20.
