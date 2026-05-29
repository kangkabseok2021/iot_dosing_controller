import pytest
import math
import numpy as np
import scipy.stats
from app.services.features import extract_features

def test_extract_features_too_few_values():
    with pytest.raises(ValueError) as exc:
        extract_features([10.0])
    assert "Feature extraction requires at least 2 values" in str(exc.value)

def test_extract_features_two_values():
    values = [2.0, 4.0]
    # Mean: 3.0
    # Std: 1.0 (population std in numpy is 1.0 for [2, 4])
    # RMS: sqrt((4 + 16)/2) = sqrt(10) = 3.162277
    # Peak-to-peak: 4.0 - 2.0 = 2.0
    # Kurtosis: 0.0 (since len < 4)
    features = extract_features(values)
    assert len(features) == 5
    assert features[0] == 3.0
    assert features[1] == 1.0
    assert math.isclose(features[2], math.sqrt(10.0))
    assert features[3] == 2.0
    assert features[4] == 0.0

def test_extract_features_three_values():
    values = [1.0, 2.0, 3.0]
    # Mean: 2.0
    # Std: np.std([1, 2, 3]) = sqrt(((1-2)^2 + (2-2)^2 + (3-2)^2)/3) = sqrt(2/3)
    # RMS: sqrt((1 + 4 + 9)/3) = sqrt(14/3)
    # Peak-to-peak: 3.0 - 1.0 = 2.0
    # Kurtosis: 0.0 (since len < 4)
    features = extract_features(values)
    assert len(features) == 5
    assert features[0] == 2.0
    assert math.isclose(features[1], math.sqrt(2.0 / 3.0))
    assert math.isclose(features[2], math.sqrt(14.0 / 3.0))
    assert features[3] == 2.0
    assert features[4] == 0.0

def test_extract_features_four_values():
    values = [1.0, 2.0, 3.0, 4.0]
    # len >= 4, so Kurtosis should be scipy.stats.kurtosis(values, fisher=True, bias=False)
    features = extract_features(values)
    assert len(features) == 5
    expected_kurt = float(scipy.stats.kurtosis(values, fisher=True, bias=False))
    assert math.isclose(features[4], expected_kurt)

def test_extract_features_zero_variance():
    # Four identical values, std = 0, kurtosis would be nan from scipy, but should be 0.0 in features
    values = [5.0, 5.0, 5.0, 5.0]
    features = extract_features(values)
    assert len(features) == 5
    assert features[0] == 5.0
    assert features[1] == 0.0
    assert features[2] == 5.0
    assert features[3] == 0.0
    assert features[4] == 0.0
