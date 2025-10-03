import tensorflow as tf
import numpy as np
import string

"""
Image preprocessing functions for CAPTCHA recognition.
"""

# Constants
IMG_HEIGHT, IMG_WIDTH = 50, 200
CHARACTERS = sorted(list(set(string.ascii_letters + string.digits)))

# Character mapping layers (need to be created once)
char_to_num = tf.keras.layers.StringLookup(vocabulary=list(CHARACTERS), mask_token=None)
num_to_char = tf.keras.layers.StringLookup(
    vocabulary=char_to_num.get_vocabulary(), mask_token=None, invert=True
)

def remove_lines(x, ksize=2): #Remove lines from image using morphological operations
    
    eroded = -tf.nn.max_pool(-x[None, ...], ksize=[1, ksize, ksize, 1],
                             strides=[1, 1, 1, 1], padding="SAME")
    opened = tf.nn.max_pool(eroded, ksize=[1, ksize, ksize, 1],
                            strides=[1, 1, 1, 1], padding="SAME")
    return opened[0]

def preprocess_image(image_path): # Read and decode image
    img = tf.io.read_file(image_path)
    img = tf.io.decode_png(img, channels=1)
    img = tf.image.convert_image_dtype(img, tf.float32)
    
    
    img = 1.0 - img   # Invert colors (background becomes black, text becomes white)
    
    img = remove_lines(img)
    
    img = 1 - img
    
    img = tf.image.resize(img, [IMG_HEIGHT, IMG_WIDTH])
    
    img = tf.transpose(img, perm=[1, 0, 2])
    
    # Add batch dimension
    img = tf.expand_dims(img, 0)
    
    return img

def decode_predictions(predictions):
    input_len = np.ones(predictions.shape[0]) * predictions.shape[1]
    
    # Use greedy CTC decoding
    results = tf.keras.backend.ctc_decode(
        predictions, input_length=input_len, greedy=True
    )[0][0]
    
    # Convert predictions to text
    output_text = []
    for res in results:
        
        res = tf.gather(res, tf.where(tf.not_equal(res, -1)))
        
        res = tf.strings.reduce_join(num_to_char(res)).numpy().decode("utf-8")
        output_text.append(res)
    
    return output_text

def get_vocab_info():
    
    return {
        'characters': ''.join(CHARACTERS),
        'vocab_size': len(char_to_num.get_vocabulary()),
        'char_to_num': char_to_num,
        'num_to_char': num_to_char
    }