import logging
import os
import sys
import warnings

# ⚡ LAZY IMPORT: TensorFlow is only imported when actually needed
# This prevents slow startup time when TensorFlow is not required
from app.core.logger import setup_logging

logger = setup_logging()

# Lazy import tensorflow
_tensorflow_imported = False
_tf = None
_keras = None
_CTCLayer = None

def _lazy_import_tensorflow():
    """Lazy import TensorFlow only when needed"""
    global _tensorflow_imported, _tf, _keras, _CTCLayer
    if not _tensorflow_imported:
        try:
            import tensorflow as tf
            from tensorflow import keras
            _tf = tf
            _keras = keras
            
            # Suppress warnings
            warnings.filterwarnings('ignore')
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
            
            # Define CTCLayer after TensorFlow is imported
            @tf.keras.utils.register_keras_serializable()
            class CTCLayer(keras.layers.Layer):
                def __init__(self, name=None, **kwargs):
                    super().__init__(name=name, **kwargs)
                    self.loss_fn = keras.backend.ctc_batch_cost

                def call(self, y_true, y_pred, input_length, label_length):
                    loss = self.loss_fn(y_true, y_pred, input_length, label_length)
                    self.add_loss(loss)
                    return y_pred

                def get_config(self):
                    config = super().get_config()
                    return config

                @classmethod
                def from_config(cls, config):
                    return cls(**config)
            
            _CTCLayer = CTCLayer
            _tensorflow_imported = True
            logger.info("TensorFlow loaded (lazy import)")
        except ImportError as e:
            logger.error(f"Failed to import TensorFlow: {e}")
            raise
    return _tf, _keras, _CTCLayer

# Model configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'my_model.h5')
IMG_HEIGHT, IMG_WIDTH = 50, 200

class CaptchaPredictor:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.prediction_model = None
        from app.captcha_solver.preprocess import get_vocab_info
        self.vocab_info = get_vocab_info()
        self._load_model()
    
    def _load_model(self):
        """Load the trained model"""
        try:
            # Lazy import TensorFlow
            tf, keras, CTCLayer = _lazy_import_tensorflow()
            
            self.model = keras.models.load_model(
                self.model_path, 
                custom_objects={'CTCLayer': CTCLayer}
            )
            self._create_prediction_model()
            
        except Exception as e:
            if os.environ.get('DEBUG'):
                logger.error(f"Error loading model: {e}")
                logger.debug("Please ensure the model file exists and is valid.")
            logger.error(f"Error loading captcha model: {e}")
            return  # Graceful error recovery
    
    def _create_prediction_model(self):
        """Create a lighter prediction model (exclude CTC loss layer)"""
        try:
            tf, keras, _ = _lazy_import_tensorflow()
            
            dense_layer = None
            for layer in reversed(self.model.layers):
                if 'dense' in layer.name.lower() and 'ctc' not in layer.name.lower():
                    dense_layer = layer
                    break
            
            if dense_layer:
                self.prediction_model = keras.models.Model(
                    inputs=self.model.inputs[0],
                    outputs=dense_layer.output
                )
            else:
                self.prediction_model = keras.models.Model(
                    inputs=self.model.inputs[0],
                    outputs=self.model.layers[-2].output
                )
                
        except Exception as e:
            if os.environ.get('DEBUG'):
                logger.error(f"Error creating prediction model: {e}")
            logger.error(f"Error creating prediction model: {e}")
            return  # Graceful error recovery
    
    def predict(self, image_content):
        """Run prediction on a single image"""
        try:
            if not image_content:
                raise ValueError("Image content is empty or None")

            from app.captcha_solver.preprocess import preprocess_image, decode_predictions
            preprocessed_image = preprocess_image(image_content)
            predictions = self.prediction_model.predict(preprocessed_image, verbose=0)
            decoded_texts = decode_predictions(predictions)
            
            return decoded_texts[0] if decoded_texts else ""
            
        except Exception as e:
            if os.environ.get('DEBUG'):
                logger.error(f"Error during prediction: {e}")
            logger.error(f"Error during captcha prediction: {e}")
            return ""

_cached_predictor = None

def _predict_via_api(image_content: bytes, api_url: str) -> str:
    """Predict captcha text via remote REST API endpoint."""
    try:
        import requests
        files = {"file": ("captcha.png", image_content, "image/png")}
        resp = requests.post(api_url, files=files, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("captcha_text") or data.get("text") or data.get("prediction") or ""
            if text:
                logger.info(f"Captcha solved via remote API successfully: {text}")
                return str(text).strip()
        logger.warning(f"Captcha API returned status {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        logger.warning(f"Failed to solve captcha via remote API ({e}), falling back to local solver.")
    return ""

def predict(image_content):
    """
    Predict captcha text from image content.
    If CAPTCHA_API_URL environment variable is set, delegates to remote API.
    Otherwise (or if API request fails), falls back to local TensorFlow model.
    """
    global _cached_predictor
    api_url = os.getenv("CAPTCHA_API_URL", "").strip()
    if api_url:
        result = _predict_via_api(image_content, api_url)
        if result:
            return result

    # Fallback to local TensorFlow model
    if _cached_predictor is None:
        _cached_predictor = CaptchaPredictor()
    return _cached_predictor.predict(image_content)
