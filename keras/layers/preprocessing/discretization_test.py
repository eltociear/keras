# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
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
"""Tests for Keras discretization preprocessing layer."""

import os

from absl.testing import parameterized
import keras
from keras.layers.preprocessing import discretization
from keras.layers.preprocessing import preprocessing_test_utils
from keras.testing_infra import test_combinations
from keras.testing_infra import test_utils
import numpy as np
import tensorflow.compat.v2 as tf


@test_combinations.run_all_keras_modes
class DiscretizationTest(
    test_combinations.TestCase, preprocessing_test_utils.PreprocessingLayerTest
):
    def test_bucketize_with_explicit_buckets_integer(self):
        input_array = np.array([[-1.5, 1.0, 3.4, 0.5], [0.0, 3.0, 1.3, 0.0]])

        expected_output = [[0, 2, 3, 1], [1, 3, 2, 1]]
        expected_output_shape = [None, 4]

        input_data = keras.Input(shape=(4,))
        layer = discretization.Discretization(bin_boundaries=[0.0, 1.0, 2.0])
        bucket_data = layer(input_data)
        self.assertAllEqual(expected_output_shape, bucket_data.shape.as_list())

        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array)
        self.assertAllEqual(expected_output, output_dataset)

    def test_bucketize_with_explicit_buckets_int_input(self):
        input_array = np.array([[-1, 1, 3, 0], [0, 3, 1, 0]], dtype=np.int64)

        expected_output = [[0, 2, 3, 1], [1, 3, 2, 1]]
        expected_output_shape = [None, 4]

        input_data = keras.Input(shape=(4,), dtype=tf.int64)
        layer = discretization.Discretization(bin_boundaries=[-0.5, 0.5, 1.5])
        bucket_data = layer(input_data)
        self.assertAllEqual(expected_output_shape, bucket_data.shape.as_list())

        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array)
        self.assertAllEqual(expected_output, output_dataset)

    def test_bucketize_with_explicit_buckets_sparse_float_input(self):
        indices = [[0, 1], [0, 2], [1, 1]]
        input_array = tf.SparseTensor(
            indices=indices, values=[-1.5, 1.0, 3.4], dense_shape=[2, 3]
        )
        expected_output = [0, 2, 3]
        input_data = keras.Input(shape=(3,), dtype=tf.float32, sparse=True)
        layer = discretization.Discretization(bin_boundaries=[-0.5, 0.5, 1.5])
        bucket_data = layer(input_data)

        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array, steps=1)
        self.assertAllEqual(indices, output_dataset.indices)
        self.assertAllEqual(expected_output, output_dataset.values)

    def test_bucketize_with_explicit_buckets_ragged_float_input(self):
        input_array = tf.ragged.constant(
            [[-1.5, 1.0, 3.4, 0.5], [0.0, 3.0, 1.3]]
        )

        expected_output = [[0, 2, 3, 1], [1, 3, 2]]
        expected_output_shape = [None, None]

        input_data = keras.Input(shape=(None,), ragged=True)
        layer = discretization.Discretization(bin_boundaries=[0.0, 1.0, 2.0])
        bucket_data = layer(input_data)
        self.assertAllEqual(expected_output_shape, bucket_data.shape.as_list())

        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array)
        self.assertAllEqual(expected_output, output_dataset)

    def test_bucketize_with_explicit_buckets_ragged_int_input(self):
        input_array = tf.ragged.constant(
            [[-1, 1, 3, 0], [0, 3, 1]], dtype=tf.int64
        )

        expected_output = [[0, 2, 3, 1], [1, 3, 2]]
        expected_output_shape = [None, None]

        input_data = keras.Input(shape=(None,), ragged=True, dtype=tf.int64)
        layer = discretization.Discretization(bin_boundaries=[-0.5, 0.5, 1.5])
        bucket_data = layer(input_data)
        self.assertAllEqual(expected_output_shape, bucket_data.shape.as_list())
        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array)
        self.assertAllEqual(expected_output, output_dataset)

    def test_bucketize_with_explicit_buckets_sparse_int_input(self):
        indices = [[0, 1], [0, 2], [1, 1]]
        input_array = tf.SparseTensor(
            indices=indices, values=[-1, 1, 3], dense_shape=[2, 3]
        )
        expected_output = [0, 2, 3]
        input_data = keras.Input(shape=(3,), dtype=tf.int32, sparse=True)
        layer = discretization.Discretization(bin_boundaries=[-0.5, 0.5, 1.5])
        bucket_data = layer(input_data)

        model = keras.Model(inputs=input_data, outputs=bucket_data)
        output_dataset = model.predict(input_array, steps=1)
        self.assertAllEqual(indices, output_dataset.indices)
        self.assertAllEqual(expected_output, output_dataset.values)

    def test_one_hot_output(self):
        input_data = np.array([-1.5, 1.0, 3.4, 3.5])

        expected_output = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        expected_output_shape = [None, 4]

        inputs = keras.Input(shape=(1,))
        layer = discretization.Discretization(
            bin_boundaries=[0.0, 1.0, 2.0], output_mode="one_hot"
        )
        outputs = layer(inputs)
        self.assertAllEqual(expected_output_shape, outputs.shape.as_list())

        model = keras.Model(inputs, outputs)
        output_data = model(input_data)
        self.assertAllEqual(expected_output, output_data)

    def test_multi_hot_output(self):
        input_data = np.array([-1.5, 1.0, 3.4, 3.5])

        expected_output = [1.0, 0.0, 1.0, 1.0]
        expected_output_shape = [None, 4]

        inputs = keras.Input(shape=(4,))
        layer = discretization.Discretization(
            bin_boundaries=[0.0, 1.0, 2.0], output_mode="multi_hot"
        )
        outputs = layer(inputs)
        self.assertAllEqual(expected_output_shape, outputs.shape.as_list())

        model = keras.Model(inputs, outputs)
        output_data = model(input_data)
        self.assertAllEqual(expected_output, output_data)

    def test_count_output(self):
        input_data = np.array([-1.5, 1.0, 3.4, 3.5])

        expected_output = [1.0, 0.0, 1.0, 2.0]
        expected_output_shape = [None, 4]

        inputs = keras.Input(shape=(4,))
        layer = discretization.Discretization(
            bin_boundaries=[0.0, 1.0, 2.0], output_mode="count"
        )
        outputs = layer(inputs)
        self.assertAllEqual(expected_output_shape, outputs.shape.as_list())

        model = keras.Model(inputs, outputs)
        output_data = model(input_data)
        self.assertAllEqual(expected_output, output_data)

    def test_output_shape(self):
        inputs = keras.Input(batch_size=16, shape=(4,), dtype=tf.int64)
        layer = discretization.Discretization(bin_boundaries=[-0.5, 0.5, 1.5])
        outputs = layer(inputs)
        self.assertAllEqual(outputs.shape.as_list(), [16, 4])

    @parameterized.named_parameters(
        ("int32", tf.int32),
        ("int64", tf.int64),
    )
    def test_output_dtype(self, dtype):
        inputs = keras.Input(batch_size=16, shape=(4,), dtype="float32")
        layer = discretization.Discretization(
            bin_boundaries=[-0.5, 0.5, 1.5], dtype=dtype
        )
        outputs = layer(inputs)
        self.assertAllEqual(outputs.dtype, dtype)

    def test_legacy_dtype_compat(self):
        inputs = keras.Input(batch_size=16, shape=(4,), dtype="float32")
        layer = discretization.Discretization(
            bin_boundaries=[-0.5, 0.5, 1.5], dtype="float32"
        )
        outputs = layer(inputs)
        self.assertAllEqual(outputs.dtype, tf.int64)
        # In TF1 we sometimes face an explicit dtype=None in the config.
        layer = discretization.Discretization(
            bin_boundaries=[-0.5, 0.5, 1.5], dtype=None
        )
        outputs = layer(inputs)
        self.assertAllEqual(outputs.dtype, tf.int64)

    @parameterized.named_parameters(
        ("float32", tf.float32),
        ("float64", tf.float64),
    )
    def test_one_hot_output_dtype(self, dtype):
        inputs = keras.Input(batch_size=16, shape=(1,), dtype="float32")
        layer = discretization.Discretization(
            bin_boundaries=[-0.5, 0.5, 1.5], output_mode="one_hot", dtype=dtype
        )
        outputs = layer(inputs)
        self.assertAllEqual(outputs.dtype, dtype)

    def test_num_bins_negative_fails(self):
        with self.assertRaisesRegex(
            ValueError, "`num_bins` must be.*num_bins=-7"
        ):
            _ = discretization.Discretization(num_bins=-7)

    def test_num_bins_and_bins_set_fails(self):
        with self.assertRaisesRegex(
            ValueError,
            r"`num_bins` and `bin_boundaries` should not be set.*5.*\[1, 2\]",
        ):
            _ = discretization.Discretization(num_bins=5, bins=[1, 2])


@test_combinations.run_all_keras_modes(always_skip_v1=True)
class DiscretizationAdaptTest(
    test_combinations.TestCase, preprocessing_test_utils.PreprocessingLayerTest
):
    @parameterized.named_parameters(
        [
            {
                "testcase_name": "2d_single_element",
                "adapt_data": np.array([[1.0], [2.0], [3.0], [4.0], [5.0]]),
                "test_data": np.array([[1.0], [2.0], [3.0]]),
                "use_dataset": True,
                "expected": np.array([[1], [2], [3]]),
                "num_bins": 5,
                "epsilon": 0.01,
            },
            {
                "testcase_name": "2d_multi_element",
                "adapt_data": np.array(
                    [
                        [1.0, 6.0],
                        [2.0, 7.0],
                        [3.0, 8.0],
                        [4.0, 9.0],
                        [5.0, 10.0],
                    ]
                ),
                "test_data": np.array([[1.0, 10.0], [2.0, 6.0], [3.0, 8.0]]),
                "use_dataset": True,
                "expected": np.array([[0, 4], [1, 3], [1, 4]]),
                "num_bins": 5,
                "epsilon": 0.01,
            },
            {
                "testcase_name": "1d_single_element",
                "adapt_data": np.array([3.0, 2.0, 1.0, 5.0, 4.0]),
                "test_data": np.array([1.0, 2.0, 3.0]),
                "use_dataset": True,
                "expected": np.array([1, 2, 3]),
                "num_bins": 5,
                "epsilon": 0.01,
            },
            {
                "testcase_name": "300_batch_1d_single_element_1",
                "adapt_data": np.arange(300),
                "test_data": np.arange(300),
                "use_dataset": True,
                "expected": np.concatenate(
                    [np.zeros(101), np.ones(99), 2 * np.ones(100)]
                ),
                "num_bins": 3,
                "epsilon": 0.01,
            },
            {
                "testcase_name": "300_batch_1d_single_element_2",
                "adapt_data": np.arange(300) ** 2,
                "test_data": np.arange(300) ** 2,
                "use_dataset": True,
                "expected": np.concatenate(
                    [np.zeros(101), np.ones(99), 2 * np.ones(100)]
                ),
                "num_bins": 3,
                "epsilon": 0.01,
            },
            {
                "testcase_name": "300_batch_1d_single_element_large_epsilon",
                "adapt_data": np.arange(300),
                "test_data": np.arange(300),
                "use_dataset": True,
                "expected": np.concatenate([np.zeros(136), np.ones(164)]),
                "num_bins": 2,
                "epsilon": 0.1,
            },
        ]
    )
    def test_layer_computation(
        self,
        adapt_data,
        test_data,
        use_dataset,
        expected,
        num_bins=5,
        epsilon=0.01,
    ):

        input_shape = tuple(list(test_data.shape)[1:])
        np.random.shuffle(adapt_data)
        if use_dataset:
            # Keras APIs expect batched datasets
            adapt_data = tf.data.Dataset.from_tensor_slices(adapt_data).batch(
                test_data.shape[0] // 2
            )
            test_data = tf.data.Dataset.from_tensor_slices(test_data).batch(
                test_data.shape[0] // 2
            )

        layer = discretization.Discretization(
            epsilon=epsilon, num_bins=num_bins
        )
        layer.adapt(adapt_data)

        input_data = keras.Input(shape=input_shape)
        output = layer(input_data)
        model = keras.Model(input_data, output)
        model._run_eagerly = test_utils.should_run_eagerly()
        output_data = model.predict(test_data)
        self.assertAllClose(expected, output_data)

    def test_multiple_adapts(self):
        first_adapt = [[1], [2], [3]]
        second_adapt = [[4], [5], [6]]
        predict_input = [[2], [2]]
        expected_first_output = [[2], [2]]
        expected_second_output = [[0], [0]]

        inputs = keras.Input(shape=(1,), dtype=tf.int32)
        layer = discretization.Discretization(num_bins=3)
        layer.adapt(first_adapt)
        outputs = layer(inputs)
        model = keras.Model(inputs=inputs, outputs=outputs)

        actual_output = model.predict(predict_input)
        self.assertAllClose(actual_output, expected_first_output)

        # Re-adapt the layer on new inputs.
        layer.adapt(second_adapt)
        # Re-compile the model.
        model.compile()
        # `predict` should now use the new model state.
        actual_output = model.predict(predict_input)
        self.assertAllClose(actual_output, expected_second_output)

    def test_saved_model_tf(self):
        input_data = [[1], [2], [3]]
        predict_data = [[0.5], [1.5], [2.5]]
        expected_output = [[0], [1], [2]]

        inputs = keras.Input(shape=(1,), dtype=tf.float32)
        layer = discretization.Discretization(num_bins=3)
        layer.adapt(input_data)
        outputs = layer(inputs)
        model = keras.Model(inputs=inputs, outputs=outputs)

        output_data = model.predict(predict_data)
        self.assertAllClose(output_data, expected_output)

        # Save the model to disk.
        output_path = os.path.join(self.get_temp_dir(), "tf_saved_model")
        tf.saved_model.save(model, output_path)
        loaded_model = tf.saved_model.load(output_path)
        f = loaded_model.signatures["serving_default"]

        # Ensure that the loaded model is unique (so that the save/load is real)
        self.assertIsNot(model, loaded_model)

        # Validate correctness of the new model.
        new_output_data = f(tf.constant(predict_data))["discretization"]
        self.assertAllClose(new_output_data, expected_output)

    @parameterized.product(
        save_format=["tf", "h5"],
        adapt=[True, False],
    )
    def test_saved_model_keras(self, save_format, adapt):
        input_data = [[1], [2], [3]]
        predict_data = [[0.5], [1.5], [2.5]]
        expected_output = [[0], [1], [2]]

        cls = discretization.Discretization
        inputs = keras.Input(shape=(1,), dtype=tf.float32)
        if adapt:
            layer = cls(num_bins=3)
            layer.adapt(input_data)
        else:
            layer = cls(bin_boundaries=[1.0, 2.0])
        outputs = layer(inputs)
        model = keras.Model(inputs=inputs, outputs=outputs)

        output_data = model.predict(predict_data)
        self.assertAllClose(output_data, expected_output)

        # Save the model to disk.
        output_path = os.path.join(self.get_temp_dir(), "tf_keras_saved_model")
        model.save(output_path, save_format=save_format)
        loaded_model = keras.models.load_model(
            output_path, custom_objects={"Discretization": cls}
        )

        # Ensure that the loaded model is unique (so that the save/load is real)
        self.assertIsNot(model, loaded_model)

        # Validate correctness of the new model.
        new_output_data = loaded_model.predict(predict_data)
        self.assertAllClose(new_output_data, expected_output)

    def test_saved_weights_keras(self):
        input_data = [[1], [2], [3]]
        predict_data = [[0.5], [1.5], [2.5]]
        expected_output = [[0], [1], [2]]

        cls = discretization.Discretization
        inputs = keras.Input(shape=(1,), dtype=tf.float32)
        layer = cls(num_bins=3)
        layer.adapt(input_data)
        outputs = layer(inputs)
        model = keras.Model(inputs=inputs, outputs=outputs)

        output_data = model.predict(predict_data)
        self.assertAllClose(output_data, expected_output)

        # Save the model to disk.
        output_path = os.path.join(
            self.get_temp_dir(), "tf_keras_saved_weights"
        )
        model.save_weights(output_path, save_format="tf")
        new_model = keras.Model.from_config(
            model.get_config(), custom_objects={"Discretization": cls}
        )
        new_model.load_weights(output_path)

        # Validate correctness of the new model.
        new_output_data = new_model.predict(predict_data)
        self.assertAllClose(new_output_data, expected_output)


if __name__ == "__main__":
    tf.test.main()
