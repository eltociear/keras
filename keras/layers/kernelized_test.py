# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for kernelized.py."""

import tensorflow.compat.v2 as tf

import functools
import math
import os
import shutil

from absl.testing import parameterized
import numpy as np
from tensorflow.python.framework import (
    test_util as tf_test_utils,
)
from keras import backend as keras_backend
from keras.testing_infra import test_combinations
from keras import initializers
from keras.testing_infra import test_utils
from keras.engine import base_layer_utils
from keras.engine import input_layer
from keras.engine import training
from keras.layers import kernelized as kernel_layers
from keras.saving import save
from keras.utils import kernelized_utils


def _exact_gaussian(stddev):
    return functools.partial(
        kernelized_utils.exact_gaussian_kernel, stddev=stddev
    )


def _exact_laplacian(stddev):
    return functools.partial(
        kernelized_utils.exact_laplacian_kernel, stddev=stddev
    )


@test_combinations.generate(test_combinations.combine(mode=["graph", "eager"]))
class RandomFourierFeaturesTest(tf.test.TestCase, parameterized.TestCase):
    def _assert_all_close(self, expected, actual, atol=0.001):
        if not tf.executing_eagerly():
            with self.cached_session() as sess:
                keras_backend._initialize_variables(sess)
                self.assertAllClose(expected, actual, atol=atol)
        else:
            self.assertAllClose(expected, actual, atol=atol)

    @test_utils.run_v2_only
    def test_state_saving_and_loading(self):
        with self.cached_session():
            input_data = np.random.random((1, 2))
            rff_layer = kernel_layers.RandomFourierFeatures(
                output_dim=10, scale=3.0
            )
            inputs = input_layer.Input((2,))
            outputs = rff_layer(inputs)
            model = training.Model(inputs, outputs)
            output_data = model.predict(input_data)
            temp_dir = self.get_temp_dir()
            self.addCleanup(shutil.rmtree, temp_dir)
            saved_model_dir = os.path.join(temp_dir, "rff_model")
            model.save(saved_model_dir)
            new_model = save.load_model(saved_model_dir)
            new_output_data = new_model.predict(input_data)
            self.assertAllClose(output_data, new_output_data, atol=1e-4)

    def test_invalid_output_dim(self):
        with self.assertRaisesRegex(
            ValueError, "`output_dim` should be a positive integer"
        ):
            _ = kernel_layers.RandomFourierFeatures(output_dim=-3, scale=2.0)

    def test_unsupported_kernel_type(self):
        with self.assertRaisesRegex(
            ValueError, "Unsupported `kernel_initializer`"
        ):
            _ = kernel_layers.RandomFourierFeatures(
                3, "unsupported_kernel", stddev=2.0
            )

    def test_invalid_scale(self):
        with self.assertRaisesRegex(
            ValueError, "When provided, `scale` should be a positive float"
        ):
            _ = kernel_layers.RandomFourierFeatures(output_dim=10, scale=0.0)

    def test_invalid_input_shape(self):
        inputs = tf.random.uniform((3, 2, 4), seed=1)
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=10, scale=3.0
        )
        with self.assertRaisesRegex(
            ValueError, "The rank of the input tensor should be 2"
        ):
            _ = rff_layer(inputs)

    @parameterized.named_parameters(
        ("gaussian", "gaussian", 10.0, False),
        ("random", tf.compat.v1.random_uniform_initializer, 1.0, True),
    )
    def test_random_features_properties(self, initializer, scale, trainable):
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=10,
            kernel_initializer=initializer,
            scale=scale,
            trainable=trainable,
        )
        self.assertEqual(rff_layer.output_dim, 10)
        self.assertEqual(rff_layer.kernel_initializer, initializer)
        self.assertEqual(rff_layer.scale, scale)
        self.assertEqual(rff_layer.trainable, trainable)

    @parameterized.named_parameters(
        ("gaussian", "gaussian", False),
        ("laplacian", "laplacian", True),
        ("other", tf.compat.v1.ones_initializer, True),
    )
    def test_call(self, initializer, trainable):
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=10,
            kernel_initializer=initializer,
            scale=1.0,
            trainable=trainable,
            name="random_fourier_features",
        )
        inputs = tf.random.uniform((3, 2), seed=1)
        outputs = rff_layer(inputs)
        self.assertListEqual([3, 10], outputs.shape.as_list())
        num_trainable_vars = 1 if trainable else 0
        self.assertLen(
            rff_layer.non_trainable_variables, 3 - num_trainable_vars
        )

    @tf_test_utils.assert_no_new_pyobjects_executing_eagerly
    def test_no_eager_Leak(self):
        # Tests that repeatedly constructing and building a Layer does not leak
        # Python objects.
        inputs = tf.random.uniform((5, 4), seed=1)
        kernel_layers.RandomFourierFeatures(output_dim=4, name="rff")(inputs)
        kernel_layers.RandomFourierFeatures(output_dim=10, scale=2.0)(inputs)

    def test_output_shape(self):
        inputs = tf.random.uniform((3, 2), seed=1)
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=7, name="random_fourier_features", trainable=True
        )
        outputs = rff_layer(inputs)
        self.assertEqual([3, 7], outputs.shape.as_list())

    @parameterized.named_parameters(
        ("gaussian", "gaussian"),
        ("laplacian", "laplacian"),
        ("other", tf.compat.v1.random_uniform_initializer),
    )
    def test_call_on_placeholder(self, initializer):
        with tf.Graph().as_default():
            inputs = tf.compat.v1.placeholder(
                dtype=tf.float32, shape=[None, None]
            )
            rff_layer = kernel_layers.RandomFourierFeatures(
                output_dim=5,
                kernel_initializer=initializer,
                name="random_fourier_features",
            )
            with self.assertRaisesRegex(
                ValueError,
                "The last dimension of the input tensor should be defined",
            ):
                rff_layer(inputs)

            inputs = tf.compat.v1.placeholder(dtype=tf.float32, shape=[2, None])
            rff_layer = kernel_layers.RandomFourierFeatures(
                output_dim=5,
                kernel_initializer=initializer,
                name="random_fourier_features",
            )
            with self.assertRaisesRegex(
                ValueError,
                "The last dimension of the input tensor should be defined",
            ):
                rff_layer(inputs)

            inputs = tf.compat.v1.placeholder(dtype=tf.float32, shape=[None, 3])
            rff_layer = kernel_layers.RandomFourierFeatures(
                output_dim=5, name="random_fourier_features"
            )
            rff_layer(inputs)

    @parameterized.named_parameters(
        ("gaussian", 10, "gaussian", 2.0),
        ("laplacian", 5, "laplacian", None),
        ("other", 10, tf.compat.v1.ones_initializer, 1.0),
    )
    def test_compute_output_shape(self, output_dim, initializer, scale):
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim, initializer, scale=scale, name="rff"
        )
        with self.assertRaises(ValueError):
            rff_layer.compute_output_shape(tf.TensorShape(None))
        with self.assertRaises(ValueError):
            rff_layer.compute_output_shape(tf.TensorShape([]))
        with self.assertRaises(ValueError):
            rff_layer.compute_output_shape(tf.TensorShape([3]))
        with self.assertRaises(ValueError):
            rff_layer.compute_output_shape(tf.TensorShape([3, 2, 3]))

        with self.assertRaisesRegex(
            ValueError,
            "The last dimension of the input tensor should be defined",
        ):
            rff_layer.compute_output_shape(tf.TensorShape([3, None]))

        self.assertEqual(
            [None, output_dim],
            rff_layer.compute_output_shape((None, 3)).as_list(),
        )
        self.assertEqual(
            [None, output_dim],
            rff_layer.compute_output_shape(tf.TensorShape([None, 2])).as_list(),
        )
        self.assertEqual(
            [4, output_dim], rff_layer.compute_output_shape((4, 1)).as_list()
        )

    @parameterized.named_parameters(
        ("gaussian", 10, "gaussian", 3.0, False),
        ("laplacian", 5, "laplacian", 5.5, True),
        ("other", 7, tf.compat.v1.random_uniform_initializer(), None, True),
    )
    def test_get_config(self, output_dim, initializer, scale, trainable):
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim,
            initializer,
            scale=scale,
            trainable=trainable,
            name="random_fourier_features",
        )
        expected_initializer = initializer
        if not isinstance(initializer, str):
            expected_initializer = initializers.serialize(initializer)

        expected_dtype = (
            "float32" if base_layer_utils.v2_dtype_behavior_enabled() else None
        )
        expected_config = {
            "output_dim": output_dim,
            "kernel_initializer": expected_initializer,
            "scale": scale,
            "name": "random_fourier_features",
            "trainable": trainable,
            "dtype": expected_dtype,
        }
        self.assertLen(expected_config, len(rff_layer.get_config()))
        self.assertSameElements(
            list(expected_config.items()), list(rff_layer.get_config().items())
        )

    @parameterized.named_parameters(
        ("gaussian", 5, "gaussian", None, True),
        ("laplacian", 5, "laplacian", 5.5, False),
        ("other", 7, tf.compat.v1.ones_initializer(), 2.0, True),
    )
    def test_from_config(self, output_dim, initializer, scale, trainable):
        model_config = {
            "output_dim": output_dim,
            "kernel_initializer": initializer,
            "scale": scale,
            "trainable": trainable,
            "name": "random_fourier_features",
        }
        rff_layer = kernel_layers.RandomFourierFeatures.from_config(
            model_config
        )
        self.assertEqual(rff_layer.output_dim, output_dim)
        self.assertEqual(rff_layer.kernel_initializer, initializer)
        self.assertEqual(rff_layer.scale, scale)
        self.assertEqual(rff_layer.trainable, trainable)

        inputs = tf.random.uniform((3, 2), seed=1)
        outputs = rff_layer(inputs)
        self.assertListEqual([3, output_dim], outputs.shape.as_list())
        num_trainable_vars = 1 if trainable else 0
        self.assertLen(rff_layer.trainable_variables, num_trainable_vars)
        if trainable:
            self.assertEqual(
                "random_fourier_features/kernel_scale:0",
                rff_layer.trainable_variables[0].name,
            )
        self.assertLen(
            rff_layer.non_trainable_variables, 3 - num_trainable_vars
        )

    @parameterized.named_parameters(
        ("gaussian", 10, "gaussian", 3.0, True),
        ("laplacian", 5, "laplacian", 5.5, False),
        ("other", 10, tf.compat.v1.random_uniform_initializer(), None, True),
    )
    def test_same_random_features_params_reused(
        self, output_dim, initializer, scale, trainable
    ):
        """Applying the layer on the same input twice gives the same output."""
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=output_dim,
            kernel_initializer=initializer,
            scale=scale,
            trainable=trainable,
            name="random_fourier_features",
        )
        inputs = tf.constant(np.random.uniform(low=-1.0, high=1.0, size=(2, 4)))
        output1 = rff_layer(inputs)
        output2 = rff_layer(inputs)
        self._assert_all_close(output1, output2)

    @parameterized.named_parameters(
        ("gaussian", "gaussian", 5.0),
        ("laplacian", "laplacian", 3.0),
        ("other", tf.compat.v1.random_uniform_initializer(), 5.0),
    )
    def test_different_params_similar_approximation(self, initializer, scale):
        tf.compat.v1.set_random_seed(12345)
        rff_layer1 = kernel_layers.RandomFourierFeatures(
            output_dim=3000,
            kernel_initializer=initializer,
            scale=scale,
            name="rff1",
        )
        rff_layer2 = kernel_layers.RandomFourierFeatures(
            output_dim=2000,
            kernel_initializer=initializer,
            scale=scale,
            name="rff2",
        )
        # Two distinct inputs.
        x = tf.constant([[1.0, -1.0, 0.5]])
        y = tf.constant([[-1.0, 1.0, 1.0]])

        # Apply both layers to both inputs.
        output_x1 = math.sqrt(2.0 / 3000.0) * rff_layer1(x)
        output_y1 = math.sqrt(2.0 / 3000.0) * rff_layer1(y)
        output_x2 = math.sqrt(2.0 / 2000.0) * rff_layer2(x)
        output_y2 = math.sqrt(2.0 / 2000.0) * rff_layer2(y)

        # Compute the inner products of the outputs (on inputs x and y) for both
        # layers. For any fixed random features layer rff_layer, and inputs x, y,
        # rff_layer(x)^T * rff_layer(y) ~= K(x,y) up to a normalization factor.
        approx_kernel1 = kernelized_utils.inner_product(output_x1, output_y1)
        approx_kernel2 = kernelized_utils.inner_product(output_x2, output_y2)
        self._assert_all_close(approx_kernel1, approx_kernel2, atol=0.08)

    @parameterized.named_parameters(
        ("gaussian", "gaussian", 5.0, _exact_gaussian(stddev=5.0)),
        ("laplacian", "laplacian", 20.0, _exact_laplacian(stddev=20.0)),
    )
    def test_bad_kernel_approximation(
        self, initializer, scale, exact_kernel_fn
    ):
        """Approximation is bad when output dimension is small."""
        # Two distinct inputs.
        x = tf.constant([[1.0, -1.0, 0.5]])
        y = tf.constant([[-1.0, 1.0, 1.0]])

        small_output_dim = 10
        tf.compat.v1.set_random_seed(1234)
        # Initialize layer.
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=small_output_dim,
            kernel_initializer=initializer,
            scale=scale,
            name="random_fourier_features",
        )

        # Apply layer to both inputs.
        output_x = math.sqrt(2.0 / small_output_dim) * rff_layer(x)
        output_y = math.sqrt(2.0 / small_output_dim) * rff_layer(y)

        # The inner products of the outputs (on inputs x and y) approximates the
        # real value of the RBF kernel but poorly since the output dimension of the
        # layer is small.
        exact_kernel_value = exact_kernel_fn(x, y)
        approx_kernel_value = kernelized_utils.inner_product(output_x, output_y)
        abs_error = tf.abs(exact_kernel_value - approx_kernel_value)
        if not tf.executing_eagerly():
            with self.cached_session() as sess:
                keras_backend._initialize_variables(sess)
                abs_error_eval = sess.run([abs_error])
                self.assertGreater(abs_error_eval[0][0], 0.01)
                self.assertLess(abs_error_eval[0][0], 0.5)
        else:
            self.assertGreater(abs_error, 0.01)
            self.assertLess(abs_error, 0.5)

    @parameterized.named_parameters(
        ("gaussian", "gaussian", 5.0, _exact_gaussian(stddev=5.0)),
        ("laplacian", "laplacian", 10.0, _exact_laplacian(stddev=10.0)),
    )
    def test_good_kernel_approximation_multiple_inputs(
        self, initializer, scale, exact_kernel_fn
    ):
        # Parameters.
        input_dim = 5
        output_dim = 2000
        x_rows = 20
        y_rows = 30

        x = tf.constant(
            np.random.uniform(size=(x_rows, input_dim)), dtype=tf.float32
        )
        y = tf.constant(
            np.random.uniform(size=(y_rows, input_dim)), dtype=tf.float32
        )

        tf.compat.v1.set_random_seed(1234)
        rff_layer = kernel_layers.RandomFourierFeatures(
            output_dim=output_dim,
            kernel_initializer=initializer,
            scale=scale,
            name="random_fourier_features",
        )

        # The shapes of output_x and output_y are (x_rows, output_dim) and
        # (y_rows, output_dim) respectively.
        output_x = math.sqrt(2.0 / output_dim) * rff_layer(x)
        output_y = math.sqrt(2.0 / output_dim) * rff_layer(y)

        approx_kernel_matrix = kernelized_utils.inner_product(
            output_x, output_y
        )
        exact_kernel_matrix = exact_kernel_fn(x, y)
        self._assert_all_close(
            approx_kernel_matrix, exact_kernel_matrix, atol=0.05
        )


if __name__ == "__main__":
    tf.test.main()
