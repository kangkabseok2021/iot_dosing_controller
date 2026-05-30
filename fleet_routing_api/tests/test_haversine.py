from app.routing.haversine import haversine


def test_same_point():
    assert haversine(51.5, -0.1, 51.5, -0.1) == 0.0


def test_equatorial_one_degree():
    result = haversine(0.0, 0.0, 0.0, 1.0)
    assert abs(result - 111.195) < 0.01


def test_london_to_paris():
    result = haversine(51.5074, -0.1278, 48.8566, 2.3522)
    assert abs(result - 344.3) < 1.0


def test_antipodal():
    result = haversine(0.0, 0.0, 0.0, 180.0)
    assert abs(result - 20015.0) < 1.0
