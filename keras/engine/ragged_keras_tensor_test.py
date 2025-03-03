# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
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
"""RaggedKerasTensor tests."""

import tensorflow.compat.v2 as tf

from absl.testing import parameterized
import numpy as np
from keras.testing_infra import test_combinations
from keras import layers
from keras.testing_infra import test_utils
from keras.engine import training


@test_utils.run_v2_only
class RaggedKerasTensorTest(test_combinations.TestCase):
    @parameterized.parameters(
        {"batch_size": None, "shape": (None, 5), "ragged_rank": 1},
        {"batch_size": None, "shape": (None, 3, 5), "ragged_rank": 1},
        {"batch_size": None, "shape": (5, None), "ragged_rank": 2},
        {"batch_size": None, "shape": (3, 5, None), "ragged_rank": 3},
        {"batch_size": None, "shape": (None, 3, 5, None), "ragged_rank": 4},
        {
            "batch_size": None,
            "shape": (2, 3, None, 4, 5, None),
            "ragged_rank": 6,
        },
        {"batch_size": 8, "shape": (None, 5), "ragged_rank": 1},
        {"batch_size": 9, "shape": (None, 3, 5), "ragged_rank": 1},
        {"batch_size": 1, "shape": (5, None), "ragged_rank": 2},
        {"batch_size": 4, "shape": (3, 5, None), "ragged_rank": 3},
        {"batch_size": 7, "shape": (None, 3, 5, None), "ragged_rank": 4},
        {"batch_size": 12, "shape": (2, 3, None, 4, 5, None), "ragged_rank": 6},
    )
    def test_to_placeholder(self, shape, batch_size, ragged_rank):
        inp = layers.Input(shape=shape, batch_size=batch_size, ragged=True)
        self.assertEqual(inp.ragged_rank, ragged_rank)
        self.assertAllEqual(inp.shape, [batch_size] + list(shape))
        with tf.__internal__.FuncGraph("test").as_default():
            placeholder = inp._to_placeholder()
            self.assertEqual(placeholder.ragged_rank, ragged_rank)
            self.assertAllEqual(placeholder.shape, [batch_size] + list(shape))

    def test_add(self):
        inp = layers.Input(shape=[None], ragged=True)
        out = inp + inp
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        self.assertAllEqual(model(x), x + x)

    def test_mul(self):
        inp = layers.Input(shape=[None], ragged=True)
        out = inp * inp
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        self.assertAllEqual(model(x), x * x)

    def test_sub(self):
        inp = layers.Input(shape=[None], ragged=True)
        out = inp - inp
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        self.assertAllEqual(model(x), x - x)

    def test_div(self):
        inp = layers.Input(shape=[None], ragged=True)
        out = inp / inp
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        self.assertAllEqual(model(x), x / x)

    def test_getitem(self):
        # Test slicing / getitem
        inp = layers.Input(shape=(None, 2), ragged=True)
        out = inp[:, :2]
        model = training.Model(inp, out)

        x = tf.RaggedTensor.from_row_lengths(
            tf.cast(np.random.randn(6, 2), dtype=tf.float32), [3, 1, 2]
        )
        expected = x[:, :2]

        self.assertAllEqual(model(x), expected)

        # Test that models w/ slicing are correctly serialized/deserialized
        config = model.get_config()
        model = training.Model.from_config(config)

        self.assertAllEqual(model(x), expected)

    @parameterized.parameters(
        {"property_name": "values"},
        {"property_name": "flat_values"},
        {"property_name": "row_splits"},
        {"property_name": "nested_row_splits"},
    )
    def test_instance_property(self, property_name):
        inp = layers.Input(shape=[None], ragged=True)
        out = getattr(inp, property_name)
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        expected_property = getattr(x, property_name)
        self.assertAllEqual(model(x), expected_property)

        # Test that it works with serialization and deserialization as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected_property)

    @parameterized.parameters(
        {"name": "value_rowids"},
        {"name": "nested_value_rowids"},
        {"name": "nrows"},
        {"name": "row_starts"},
        {"name": "row_limits"},
        {"name": "row_lengths"},
        {"name": "nested_row_lengths"},
        {"name": "bounding_shape"},
        {"name": "with_values", "args": [[1, 2, 3, 4, 5, 6]]},
        {
            "name": "with_flat_values",
            "kwargs": {"new_values": [1, 2, 3, 4, 5, 6]},
        },
        {"name": "with_row_splits_dtype", "kwargs": {"dtype": tf.int32}},
        {"name": "merge_dims", "args": [0], "kwargs": {"inner_axis": 1}},
        {"name": "to_tensor"},
        {"name": "to_sparse"},
    )
    def test_instance_method(self, name, args=None, kwargs=None):
        if not args:
            args = []
        if not kwargs:
            kwargs = {}

        inp = layers.Input(shape=[None], ragged=True)
        out = getattr(inp, name)(*args, **kwargs)
        model = training.Model(inp, out)

        x = tf.ragged.constant([[3, 4], [1, 2], [3, 5]])
        expected_property = getattr(x, name)(*args, **kwargs)
        # We expand composites before checking equality because
        # assertAllEqual otherwise wouldn't work for SparseTensor outputs
        for a, b in zip(
            tf.nest.flatten(model(x), expand_composites=True),
            tf.nest.flatten(expected_property, expand_composites=True),
        ):
            self.assertAllEqual(a, b)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        for a, b in zip(
            tf.nest.flatten(model2(x), expand_composites=True),
            tf.nest.flatten(expected_property, expand_composites=True),
        ):
            self.assertAllEqual(a, b)


@test_utils.run_v2_only
class RaggedTensorClassMethodAsLayerTest(test_combinations.TestCase):
    def test_from_value_rowids(self):
        inp = layers.Input(shape=[None])
        out = tf.RaggedTensor.from_value_rowids(
            inp, value_rowids=[0, 0, 0, 0, 2, 2, 2, 3], nrows=5
        )
        model = training.Model(inp, out)

        x = tf.constant([3, 1, 4, 1, 5, 9, 2, 6])
        expected = tf.RaggedTensor.from_value_rowids(
            x, value_rowids=[0, 0, 0, 0, 2, 2, 2, 3], nrows=5
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_row_splits(self):
        inp = layers.Input(shape=[None])
        out = tf.RaggedTensor.from_row_splits(
            inp, row_splits=[0, 4, 4, 7, 8, 8]
        )
        model = training.Model(inp, out)

        x = tf.constant([3, 1, 4, 1, 5, 9, 2, 6])
        expected = tf.RaggedTensor.from_row_splits(
            x, row_splits=[0, 4, 4, 7, 8, 8]
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_row_lengths(self):
        inp = layers.Input(shape=[None])
        out = tf.RaggedTensor.from_row_lengths(inp, row_lengths=[4, 0, 3, 1, 0])
        model = training.Model(inp, out)

        x = tf.constant([3, 1, 4, 1, 5, 9, 2, 6])
        expected = tf.RaggedTensor.from_row_lengths(
            x, row_lengths=[4, 0, 3, 1, 0]
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_row_starts(self):
        inp = layers.Input(shape=[None])
        out = tf.RaggedTensor.from_row_starts(inp, row_starts=[0, 4, 4, 7, 8])
        model = training.Model(inp, out)

        x = tf.constant([3, 1, 4, 1, 5, 9, 2, 6])
        expected = tf.RaggedTensor.from_row_starts(
            x, row_starts=[0, 4, 4, 7, 8]
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_row_limits(self):
        row_limits = tf.constant([2, 2, 5, 6, 7], tf.int64)

        inp = layers.Input(shape=[None], dtype=tf.string)
        out = tf.RaggedTensor.from_row_limits(inp, row_limits, validate=False)
        model = training.Model(inp, out)

        x = tf.constant(["a", "b", "c", "d", "e", "f", "g"])
        expected = tf.RaggedTensor.from_row_limits(
            x, row_limits, validate=False
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_uniform_row_length(self):
        inp = layers.Input(shape=[None])
        out = tf.RaggedTensor.from_uniform_row_length(inp, 2, 8)
        model = training.Model(inp, out)

        x = tf.constant([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])
        expected = tf.RaggedTensor.from_uniform_row_length(x, 2, 8)
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_nested_value_row_ids(self):
        nested_value_rowids = [
            tf.constant([0, 0, 1, 3, 3], tf.int64),
            tf.constant([0, 0, 2, 2, 2, 3, 4], tf.int64),
        ]
        inp = layers.Input(shape=[None], dtype=tf.string)
        out = tf.RaggedTensor.from_nested_value_rowids(inp, nested_value_rowids)
        model = training.Model(inp, out)

        x = tf.constant(["a", "b", "c", "d", "e", "f", "g"])
        expected = tf.RaggedTensor.from_nested_value_rowids(
            x, nested_value_rowids
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_nested_row_splits(self):
        nested_row_splits = [
            tf.constant([0, 2, 3, 3, 5], tf.int64),
            tf.constant([0, 2, 2, 5, 6, 7], tf.int64),
        ]
        inp = layers.Input(shape=[None], dtype=tf.string)
        out = tf.RaggedTensor.from_nested_row_splits(inp, nested_row_splits)
        model = training.Model(inp, out)

        x = tf.constant(["a", "b", "c", "d", "e", "f", "g"])
        expected = tf.RaggedTensor.from_nested_row_splits(x, nested_row_splits)
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_nested_row_lengths(self):
        nested_row_lengths = [
            tf.constant([2, 1, 0, 2], tf.int64),
            tf.constant([2, 0, 3, 1, 1], tf.int64),
        ]
        inp = layers.Input(shape=[None], dtype=tf.string)
        out = tf.RaggedTensor.from_nested_row_lengths(inp, nested_row_lengths)
        model = training.Model(inp, out)

        x = tf.constant(["a", "b", "c", "d", "e", "f", "g"])
        expected = tf.RaggedTensor.from_nested_row_lengths(
            x, nested_row_lengths
        )
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_tensor(self):
        inp = layers.Input(shape=[None], ragged=False)
        out = tf.RaggedTensor.from_tensor(inp)
        model = training.Model(inp, out)

        x = tf.constant([[3.0, 4.0], [1.0, 2.0], [3.0, 5.0]])
        expected = tf.RaggedTensor.from_tensor(x)
        self.assertAllEqual(model(x), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(x), expected)

    def test_from_sparse(self):
        inp = layers.Input(shape=[None], sparse=True, dtype=tf.string)
        out = tf.RaggedTensor.from_sparse(inp)
        model = training.Model(inp, out)

        indices = [[0, 0], [1, 0], [1, 1], [2, 0]]
        values = [b"a", b"b", b"c", b"d"]
        shape = [4, 5]
        sp_value = tf.SparseTensor(indices, values, shape)

        expected = tf.RaggedTensor.from_sparse(sp_value)
        self.assertAllEqual(model(sp_value), expected)

        # Test that the model can serialize and deserialize as well
        model_config = model.get_config()
        model2 = training.Model.from_config(model_config)
        self.assertAllEqual(model2(sp_value), expected)


if __name__ == "__main__":
    tf.test.main()
