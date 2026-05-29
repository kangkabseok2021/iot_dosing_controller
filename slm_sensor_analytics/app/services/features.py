import math
import numpy as np
import scipy.stats

FEATURE_NAMES = ["mean", "std", "rms", "peak_to_peak", "kurtosis"]


def extract_features(values: list[float]) -> list[float]:
    if len(values) < 2:
        raise ValueError("Feature extraction requires at least 2 values.")

    arr = np.array(values, dtype=float)
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    rms_val = float(np.sqrt(np.mean(np.square(arr))))
    peak_to_peak_val = float(np.max(arr) - np.min(arr))

    if len(arr) >= 4:
        # Calculate Fisher's kurtosis (normal distribution = 0.0)
        # bias=False gives the corrected sample kurtosis
        kurt_val = float(scipy.stats.kurtosis(arr, fisher=True, bias=False))
        # Handle cases where kurt_val becomes nan due to zero variance
        if math.isnan(kurt_val):
            kurt_val = 0.0
    else:
        kurt_val = 0.0

    return [mean_val, std_val, rms_val, peak_to_peak_val, kurt_val]
