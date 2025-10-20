import os
import sys
import tensorflow as tf
from tensorflow import keras
import warnings

# Import preprocessing functions
from app.captcha_solver.preprocess import preprocess_image, decode_predictions, get_vocab_info

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Model configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'my_model.h5')
IMG_HEIGHT, IMG_WIDTH = 50, 200

# Custom CTCLayer definition (needed for model loading)
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

class CaptchaPredictor:

    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.prediction_model = None
        self.vocab_info = get_vocab_info()
        self._load_model()
    
    def _load_model(self):  # Load the trained model
        try:
            # print(f"Loading model from: {self.model_path}")
            self.model = keras.models.load_model(
                self.model_path, 
                custom_objects={'CTCLayer': CTCLayer}
            )
            # print("Model loaded successfully")
            self._create_prediction_model()
            
        except Exception as e:
            # Only print in debug mode
            if os.environ.get('DEBUG'):
                print(f"Error loading model: {e}")
                print("Please ensure the model file exists and is valid.")
            sys.exit(1)
    
    def _create_prediction_model(self):
        """Create a lighter prediction model (exclude CTC loss layer)"""
        try:
            dense_layer = None  # Find the dense layer (before CTC)
            for layer in reversed(self.model.layers):
                if 'dense' in layer.name.lower() and 'ctc' not in layer.name.lower():
                    dense_layer = layer
                    break
            
            if dense_layer:
                self.prediction_model = keras.models.Model(
                    inputs=self.model.inputs[0],  # Only image input
                    outputs=dense_layer.output
                )
                # print(f"Prediction model created using layer: {dense_layer.name}")
            else:
                # Fallback: use second-to-last layer
                self.prediction_model = keras.models.Model(
                    inputs=self.model.inputs[0],
                    outputs=self.model.layers[-2].output
                )
                # print("Prediction model created using second-to-last layer")
                
        except Exception as e:
            # Only print in debug mode
            if os.environ.get('DEBUG'):
                print(f"Error creating prediction model: {e}")
            sys.exit(1)
    
    def predict(self, image_content):
        """Run prediction on a single image"""
        try:
            if not image_content:
                raise ValueError("Image content is empty or None")

            preprocessed_image = preprocess_image(image_content)
            predictions = self.prediction_model.predict(preprocessed_image, verbose=0)
            decoded_texts = decode_predictions(predictions)
            
            return decoded_texts[0] if decoded_texts else ""
            
        except Exception as e:
            # Only print in debug mode
            if os.environ.get('DEBUG'):
                print(f"Error during prediction: {e}")
            return ""

def predict(image_content):
    predictor = CaptchaPredictor()
    # Make prediction
    result = predictor.predict(image_content)
    return result