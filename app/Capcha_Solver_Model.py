# import library
import os
os.environ["KERAS_BACKEND"] = "tensorflow"
import numpy as np
import tensorflow as tf
import keras
from keras import ops
from keras import layers

# Pass Image Path
path_img = r'D:\Chopolovsky\Capcha_Solver\test_captcha\captcha_20250924103701004_6601.png'      # Example

# put size for picture
img_height = 50
img_width  = 140
channels   = 3
batch_size = 16
seed = 42
downsample_factor = 4

# Define Characters for prediction
characters = ['1', '2', '3', '4', '5', '6', '7', '8', '9',
              'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'K', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
              'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'k', 'm', 'n', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
# Mapping characters to integers
char_to_num = layers.StringLookup(vocabulary=list(characters), mask_token=None)

# Mapping integers back to original characters
num_to_char = layers.StringLookup(
    vocabulary=char_to_num.get_vocabulary(), mask_token=None, invert=True
)


# Function for Encoding Image
def encode_single_sample(img_path, label):
    # Read image
    img = tf.io.read_file(img_path)
    img = tf.io.decode_png(img, channels=1)
    img = tf.image.convert_image_dtype(img, tf.float32)

    img = 1.0 - img

    def remove_lines(x, ksize):
        # erode
        eroded = -tf.nn.max_pool(-x[None, ...], ksize=[1, ksize, ksize, 1],
                                 strides=[1,1,1,1], padding="SAME")
        # dilate
        opened = tf.nn.max_pool(eroded, ksize=[1, ksize, ksize, 1],
                                strides=[1,1,1,1], padding="SAME")
        return opened[0]

    img = remove_lines(img, 2)
    img = 1 - img
    img = ops.image.resize(img, [img_height, img_width])
    # dimension to correspond to the width of the image.
    img = ops.transpose(img, axes=[1, 0, 2])
    label = char_to_num(tf.strings.unicode_split(label, input_encoding="UTF-8"))
    # Return a dict as our model is expecting two inputs
    return {"image": img, "label": label}


# Function For CTC
def ctc_batch_cost(y_true, y_pred, input_length, label_length):
    label_length = ops.cast(ops.squeeze(label_length, axis=-1), dtype="int32")
    input_length = ops.cast(ops.squeeze(input_length, axis=-1), dtype="int32")
    sparse_labels = ops.cast(
        ctc_label_dense_to_sparse(y_true, label_length), dtype="int32"
    )

    y_pred = ops.log(ops.transpose(y_pred, axes=[1, 0, 2]) + keras.backend.epsilon())

    return ops.expand_dims(
        tf.compat.v1.nn.ctc_loss(
            inputs=y_pred, labels=sparse_labels, sequence_length=input_length
        ),
        1,
    )


# Function for convert to sparse
def ctc_label_dense_to_sparse(labels, label_lengths):
    label_shape = ops.shape(labels)
    num_batches_tns = ops.stack([label_shape[0]])
    max_num_labels_tns = ops.stack([label_shape[1]])

    def range_less_than(old_input, current_input):
        return ops.expand_dims(ops.arange(ops.shape(old_input)[1]), 0) < tf.fill(
            max_num_labels_tns, current_input
        )

    init = ops.cast(tf.fill([1, label_shape[1]], 0), dtype="bool")
    dense_mask = tf.compat.v1.scan(
        range_less_than, label_lengths, initializer=init, parallel_iterations=1
    )
    dense_mask = dense_mask[:, 0, :]

    label_array = ops.reshape(
        ops.tile(ops.arange(0, label_shape[1]), num_batches_tns), label_shape
    )
    label_ind = tf.compat.v1.boolean_mask(label_array, dense_mask)

    batch_array = ops.transpose(
        ops.reshape(
            ops.tile(ops.arange(0, label_shape[0]), max_num_labels_tns),
            tf.reverse(label_shape, [0]),
        )
    )
    batch_ind = tf.compat.v1.boolean_mask(batch_array, dense_mask)
    indices = ops.transpose(
        ops.reshape(ops.concatenate([batch_ind, label_ind], axis=0), [2, -1])
    )

    vals_sparse = tf.compat.v1.gather_nd(labels, indices)

    return tf.SparseTensor(
        ops.cast(indices, dtype="int64"),
        vals_sparse,
        ops.cast(label_shape, dtype="int64")
    )   


# CTC Loss Class
class CTCLayer(layers.Layer):
    def __init__(self, name="ctc_loss", **kwargs):
        super().__init__(name=name, **kwargs)
        self.loss_fn = ctc_batch_cost

    def call(self, y_true, y_pred):
        batch_len = tf.cast(tf.shape(y_true)[0], dtype=tf.int64)
        input_length = tf.cast(tf.shape(y_pred)[1], dtype=tf.int64)
        label_length = tf.cast(tf.shape(y_true)[1], dtype=tf.int64)

        input_length = input_length * tf.ones(shape=(batch_len, 1), dtype=tf.int64)
        label_length = label_length * tf.ones(shape=(batch_len, 1), dtype=tf.int64)

        loss = self.loss_fn(y_true, y_pred, input_length, label_length)
        self.add_loss(loss)
        return y_pred

    def get_config(self):
        base_config = super().get_config()
        return {**base_config}


# Decode CTC Function
# --- CTC decode ---
def ctc_decode(y_pred, input_length, greedy=True, beam_width=100, top_paths=1):
    input_shape = ops.shape(y_pred)
    num_samples, num_steps = input_shape[0], input_shape[1]
    # Log probabilities (CTC expects time major)
    y_pred = ops.log(ops.transpose(y_pred, axes=[1, 0, 2]) + keras.backend.epsilon())
    input_length = ops.cast(input_length, dtype="int32")

    if greedy:
        (decoded, log_prob) = tf.nn.ctc_greedy_decoder(inputs=y_pred, sequence_length=input_length)
    else:
        (decoded, log_prob) = tf.compat.v1.nn.ctc_beam_search_decoder(
            inputs=y_pred,
            sequence_length=input_length,
            beam_width=beam_width,
            top_paths=top_paths,
        )

    decoded_dense = []
    for st in decoded:
        st = tf.SparseTensor(st.indices, st.values, (num_samples, num_steps))
        decoded_dense.append(tf.sparse.to_dense(sp_input=st, default_value=-1))
    return decoded_dense, log_prob


# Function For Predict text from image
def predict_from_path(img_path, max_length=32):
    # Load Model
    save_path = "ocr_model_v2_full.h5"

    custom_objects = {
        "CTCLayer": CTCLayer,
        "ctc_batch_cost": ctc_batch_cost
    }

    loaded_model = keras.models.load_model(
        save_path,
        custom_objects=custom_objects,
        compile=False)

    prediction_model = keras.models.Model(
        inputs=loaded_model.input[0],
        outputs=loaded_model.get_layer(name="dense_logits").output
    )

    # Use from Encode Function
    sample = encode_single_sample(img_path, label="")  # Empty Label
    img = sample["image"]
    img = np.expand_dims(img, axis=0)

    # Predict
    pred = prediction_model.predict(img)
    input_len = np.ones(pred.shape[0]) * pred.shape[1]
    decoded, _ = ctc_decode(pred, input_length=input_len, greedy=True)

    # Decode to Text
    result = decoded[0][:, :max_length]
    res = tf.ragged.boolean_mask(result[0], result[0] >= 0)
    text = tf.strings.reduce_join(num_to_char(res)).numpy().decode("utf-8")

    return text
