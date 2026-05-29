import os
import pytest
import joblib
from sklearn.ensemble import IsolationForest
from app.services.anomaly import ModelStore

def test_model_store_fit_saves_to_disk(tmp_path):
    store = ModelStore(str(tmp_path))
    # Create some dummy training data (X: 10 windows, 5 features each)
    X = [[1.0, 0.1, 1.0, 0.2, 0.0] for _ in range(10)]
    
    key = store.fit("device_01", "temp", X)
    assert key == "device_01__temp"
    
    expected_path = os.path.join(str(tmp_path), "device_01__temp.joblib")
    assert os.path.exists(expected_path)
    assert "device_01__temp" in store._cache

def test_model_store_get_model_from_cache(tmp_path):
    store = ModelStore(str(tmp_path))
    X = [[1.0, 0.1, 1.0, 0.2, 0.0] for _ in range(10)]
    store.fit("device_01", "temp", X)
    
    model = store.get_model("device_01", "temp")
    assert isinstance(model, IsolationForest)
    # Check that it returns the cached instance
    assert model is store._cache["device_01__temp"]

def test_model_store_get_model_loads_from_disk(tmp_path):
    store = ModelStore(str(tmp_path))
    X = [[1.0, 0.1, 1.0, 0.2, 0.0] for _ in range(10)]
    store.fit("device_01", "temp", X)
    
    # Manually clear cache to force loading from disk
    store._cache.clear()
    
    model = store.get_model("device_01", "temp")
    assert isinstance(model, IsolationForest)
    assert "device_01__temp" in store._cache

def test_model_store_get_model_not_found(tmp_path):
    store = ModelStore(str(tmp_path))
    with pytest.raises(ValueError) as exc:
        store.get_model("device_nonexistent", "temp")
    assert "No trained model found" in str(exc.value)
