# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
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
"""Tests for Keras activation functions."""

import tensorflow.compat.v2 as tf

from absl.testing import parameterized
import numpy as np

from keras import activations
from keras import backend
from keras.testing_infra import test_combinations
import keras.layers.activation as activation_layers
from keras.layers import core
from keras.layers import serialization


def _ref_softmax(values):
    m = np.max(values)
    e = np.exp(values - m)
    return e / np.sum(e)


@test_combinations.generate(test_combinations.combine(mode=["graph", "eager"]))
class KerasActivationsTest(tf.test.TestCase, parameterized.TestCase):
    def test_serialization(self):
        all_activations = [
            "softmax",
            "relu",
            "elu",
            "tanh",
            "sigmoid",
            "hard_sigmoid",
            "linear",
            "softplus",
            "softsign",
            "selu",
            "gelu",
            "relu6",
        ]
        for name in all_activations:
            fn = activations.get(name)
            ref_fn = getattr(activations, name)
            assert fn == ref_fn
            config = activations.serialize(fn)
            fn = activations.deserialize(config)
            assert fn == ref_fn

    def test_serialization_v2(self):
        activation_map = {tf.math.softmax: "softmax"}
        for fn_v2_key in activation_map:
            fn_v2 = activations.get(fn_v2_key)
            config = activations.serialize(fn_v2)
            fn = activations.deserialize(config)
            assert fn.__name__ == activation_map[fn_v2_key]

    def test_serialization_with_layers(self):
        activation = activation_layers.LeakyReLU(alpha=0.1)
        layer = core.Dense(3, activation=activation)
        config = serialization.serialize(layer)
        # with custom objects
        deserialized_layer = serialization.deserialize(
            config, custom_objects={"LeakyReLU": activation}
        )
        self.assertEqual(
            deserialized_layer.__class__.__name__, layer.__class__.__name__
        )
        self.assertEqual(
            deserialized_layer.activation.__class__.__name__,
            activation.__class__.__name__,
        )
        # without custom objects
        deserialized_layer = serialization.deserialize(config)
        self.assertEqual(
            deserialized_layer.__class__.__name__, layer.__class__.__name__
        )
        self.assertEqual(
            deserialized_layer.activation.__class__.__name__,
            activation.__class__.__name__,
        )

    def test_softmax(self):
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.softmax(x)])
        test_values = np.random.random((2, 5))

        result = f([test_values])[0]
        expected = _ref_softmax(test_values[0])
        self.assertAllClose(result[0], expected, rtol=1e-05)

        x = backend.placeholder(ndim=1)
        with self.assertRaises(ValueError):
            activations.softmax(x)

    def test_softmax_2d_axis_0(self):
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.softmax(x, axis=0)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = np.zeros((2, 5))
        for i in range(5):
            expected[:, i] = _ref_softmax(test_values[:, i])
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_softmax_3d_axis_tuple(self):
        x = backend.placeholder(ndim=3)
        f = backend.function([x], [activations.softmax(x, axis=(1, 2))])
        test_values = np.random.random((2, 3, 5))
        result = f([test_values])[0]
        expected = np.zeros((2, 3, 5))
        for i in range(2):
            expected[i, :, :] = _ref_softmax(test_values[i, :, :])
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_temporal_softmax(self):
        x = backend.placeholder(shape=(2, 2, 3))
        f = backend.function([x], [activations.softmax(x)])
        test_values = np.random.random((2, 2, 3)) * 10
        result = f([test_values])[0]
        expected = _ref_softmax(test_values[0, 0])
        self.assertAllClose(result[0, 0], expected, rtol=1e-05)

    def test_selu(self):
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.selu(x)])
        alpha = 1.6732632423543772848170429916717
        scale = 1.0507009873554804934193349852946

        positive_values = np.array([[1, 2]], dtype=backend.floatx())
        result = f([positive_values])[0]
        self.assertAllClose(result, positive_values * scale, rtol=1e-05)

        negative_values = np.array([[-1, -2]], dtype=backend.floatx())
        result = f([negative_values])[0]
        true_result = (np.exp(negative_values) - 1) * scale * alpha
        self.assertAllClose(result, true_result)

    def test_softplus(self):
        def softplus(x):
            return np.log(np.ones_like(x) + np.exp(x))

        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.softplus(x)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = softplus(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_softsign(self):
        def softsign(x):
            return np.divide(x, np.ones_like(x) + np.absolute(x))

        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.softsign(x)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = softsign(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_sigmoid(self):
        def ref_sigmoid(x):
            if x >= 0:
                return 1 / (1 + np.exp(-x))
            else:
                z = np.exp(x)
                return z / (1 + z)

        sigmoid = np.vectorize(ref_sigmoid)

        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.sigmoid(x)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = sigmoid(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_hard_sigmoid(self):
        def ref_hard_sigmoid(x):
            x = (x * 0.2) + 0.5
            z = 0.0 if x <= 0 else (1.0 if x >= 1 else x)
            return z

        hard_sigmoid = np.vectorize(ref_hard_sigmoid)
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.hard_sigmoid(x)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = hard_sigmoid(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_relu(self):
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.relu(x)])
        positive_values = np.random.random((2, 5))
        result = f([positive_values])[0]
        self.assertAllClose(result, positive_values, rtol=1e-05)

        negative_values = np.random.uniform(-1, 0, (2, 5))
        result = f([negative_values])[0]
        expected = np.zeros((2, 5))
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_gelu(self):
        def gelu(x, approximate=False):
            if approximate:
                return (
                    0.5
                    * x
                    * (
                        1.0
                        + np.tanh(
                            np.sqrt(2.0 / np.pi)
                            * (x + 0.044715 * np.power(x, 3))
                        )
                    )
                )
            else:
                from scipy.stats import (
                    norm,
                )  # pylint: disable=g-import-not-at-top

                return x * norm.cdf(x)

        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.gelu(x)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = gelu(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

        f = backend.function([x], [activations.gelu(x, True)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        expected = gelu(test_values, True)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_elu(self):
        x = backend.placeholder(ndim=2)
        f = backend.function([x], [activations.elu(x, 0.5)])
        test_values = np.random.random((2, 5))
        result = f([test_values])[0]
        self.assertAllClose(result, test_values, rtol=1e-05)
        negative_values = np.array([[-1, -2]], dtype=backend.floatx())
        result = f([negative_values])[0]
        true_result = (np.exp(negative_values) - 1) / 2
        self.assertAllClose(result, true_result)

    def test_tanh(self):
        test_values = np.random.random((2, 5))
        x = backend.placeholder(ndim=2)
        exp = activations.tanh(x)
        f = backend.function([x], [exp])
        result = f([test_values])[0]
        expected = np.tanh(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_exponential(self):
        test_values = np.random.random((2, 5))
        x = backend.placeholder(ndim=2)
        exp = activations.exponential(x)
        f = backend.function([x], [exp])
        result = f([test_values])[0]
        expected = np.exp(test_values)
        self.assertAllClose(result, expected, rtol=1e-05)

    def test_linear(self):
        x = np.random.random((10, 5))
        self.assertAllClose(x, activations.linear(x))

    def test_invalid_usage(self):
        with self.assertRaises(ValueError):
            activations.get("unknown")

        # The following should be possible but should raise a warning:
        activations.get(activation_layers.LeakyReLU())


if __name__ == "__main__":
    tf.test.main()
