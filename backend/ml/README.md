# ML adapter boundary

`backend/ml` contains explicit adapters for the model types described in the
patent: disease classification and severity, crop suitability, fertilizer
suitability, irrigation requirement, yield prediction, and agricultural risk
prediction.

All adapters are dummy integrations (`dummy: true`, `model_loaded: false`).
They do not load the `.pt` files or perform inference. The disease endpoint
uses the disease-classification adapter while preserving its deterministic
sample behaviour until a real model is intentionally integrated.
