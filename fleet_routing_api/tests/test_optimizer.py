from app.routing.optimizer import RouteWaypoint, nearest_neighbor_route, total_route_distance


def test_empty_waypoints():
    depot = RouteWaypoint(id=0, lat=0.0, lon=0.0)
    assert nearest_neighbor_route(depot, []) == []


def test_single_waypoint():
    depot = RouteWaypoint(id=0, lat=0.0, lon=0.0)
    wp = RouteWaypoint(id=1, lat=1.0, lon=0.0)
    result = nearest_neighbor_route(depot, [wp])
    assert len(result) == 1
    assert result[0].id == 1


def test_three_waypoint_greedy_order():
    # depot=(0,0); wp1=(0,1)~111km, wp3=(0,2)~222km, wp2=(0,10)~1112km from depot
    # greedy: pick wp1 first, then nearest to wp1 is wp3, then wp2
    depot = RouteWaypoint(id=0, lat=0.0, lon=0.0)
    wp1 = RouteWaypoint(id=1, lat=0.0, lon=1.0)
    wp2 = RouteWaypoint(id=2, lat=0.0, lon=10.0)
    wp3 = RouteWaypoint(id=3, lat=0.0, lon=2.0)
    result = nearest_neighbor_route(depot, [wp1, wp2, wp3])
    assert [w.id for w in result] == [1, 3, 2]


def test_total_distance_empty():
    depot = RouteWaypoint(id=0, lat=0.0, lon=0.0)
    assert total_route_distance(depot, []) == 0.0


def test_total_distance_single():
    depot = RouteWaypoint(id=0, lat=0.0, lon=0.0)
    wp = RouteWaypoint(id=1, lat=0.0, lon=1.0)
    result = total_route_distance(depot, [wp])
    assert abs(result - 111.195) < 0.01
