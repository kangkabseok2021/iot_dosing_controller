import os
import joblib
from sklearn.ensemble import IsolationForest

class ModelStore:
    def __init__(self, model_dir: str = "models") -> None:
        self.model_dir = model_dir
        self._cache = {}
        os.makedirs(self.model_dir, exist_ok=True)

    def _key(self, device_id: str, sensor_type: str) -> str:
        return f"{device_id}__{sensor_type}"

    def _path(self, key: str) -> str:
        return os.path.join(self.model_dir, f"{key}.joblib")

    def fit(self, device_id: str, sensor_type: str, X: list[list[float]]) -> str:
        key = self._key(device_id, sensor_type)
        path = self._path(key)

        # Train Isolation Forest model
        clf = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        clf.fit(X)

        # Persist model and cache
        joblib.dump(clf, path)
        self._cache[key] = clf

        return key

    def get_model(self, device_id: str, sensor_type: str) -> IsolationForest:
        key = self._key(device_id, sensor_type)
        if key in self._cache:
            return self._cache[key]

        path = self._path(key)
        if not os.path.exists(path):
            raise ValueError(f"No trained model found for device {device_id} and sensor {sensor_type}.")

        # Load from disk and cache
        clf = joblib.load(path)
        self._cache[key] = clf
        return clf

    def predict(self, device_id: str, sensor_type: str, features: list[float]) -> float:
        clf = self.get_model(device_id, sensor_type)
        # decision_function returns the anomaly score (lower/more negative is more anomalous)
        score = float(clf.decision_function([features])[0])
        return score
