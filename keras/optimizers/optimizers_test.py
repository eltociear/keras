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
"""Tests for Keras optimizers."""

import tensorflow.compat.v2 as tf

import gc
import weakref

import numpy as np

import keras
from keras.optimizers import optimizer_v1
from keras.testing_infra import test_combinations
from keras.testing_infra import test_utils
from keras.utils import np_utils
from tensorflow.python.training.adam import AdamOptimizer
from tensorflow.python.training.experimental.loss_scale_optimizer import (
    MixedPrecisionLossScaleOptimizer,
)


def _get_model(input_dim, num_hidden, output_dim):
    model = keras.models.Sequential()
    model.add(
        keras.layers.Dense(
            num_hidden, activation="relu", input_shape=(input_dim,)
        )
    )
    model.add(keras.layers.Dense(output_dim, activation="softmax"))
    return model


@test_combinations.run_all_keras_modes
class KerasOptimizersTest(test_combinations.TestCase):
    def _test_optimizer(self, optimizer, target=0.75):
        if tf.executing_eagerly():
            self.skipTest("v1 optimizer does not run in eager mode")
        np.random.seed(1337)
        (x_train, y_train), _ = test_utils.get_test_data(
            train_samples=1000,
            test_samples=200,
            input_shape=(10,),
            num_classes=2,
        )
        y_train = np_utils.to_categorical(y_train)
        model = _get_model(x_train.shape[1], 20, y_train.shape[1])
        model.compile(
            loss="categorical_crossentropy",
            optimizer=optimizer,
            metrics=["acc"],
            run_eagerly=test_utils.should_run_eagerly(),
        )
        np.testing.assert_equal(
            keras.backend.get_value(model.optimizer.iterations), 0
        )
        history = model.fit(
            x_train, y_train, epochs=2, batch_size=16, verbose=0
        )
        np.testing.assert_equal(
            keras.backend.get_value(model.optimizer.iterations), 126
        )  # 63 steps per epoch
        self.assertGreaterEqual(history.history["acc"][-1], target)
        config = keras.optimizers.serialize(optimizer)
        optim = keras.optimizers.deserialize(config)
        new_config = keras.optimizers.serialize(optim)
        new_config["class_name"] = new_config["class_name"].lower()
        new_config["config"].pop("name", None)
        if "amsgrad" not in config["config"]:
            new_config["config"].pop("amsgrad", None)
        if (
            "decay" in new_config["config"]
            and "schedule_decay" in config["config"]
        ):
            new_config["config"]["schedule_decay"] = new_config["config"].pop(
                "decay"
            )
        if "momentum" not in config["config"]:
            new_config["config"].pop("momentum", None)
        if "centered" not in config["config"]:
            new_config["config"].pop("centered", None)
        self.assertDictEqual(config, new_config)

        # Test constraints.
        model = keras.models.Sequential()
        dense = keras.layers.Dense(
            10,
            input_shape=(x_train.shape[1],),
            kernel_constraint=lambda x: 0.0 * x + 1.0,
            bias_constraint=lambda x: 0.0 * x + 2.0,
            activation="relu",
        )
        model.add(dense)
        model.add(keras.layers.Dense(y_train.shape[1], activation="softmax"))
        model.compile(
            loss="categorical_crossentropy",
            optimizer=optimizer,
            metrics=["accuracy"],
            run_eagerly=test_utils.should_run_eagerly(),
        )
        np.testing.assert_equal(
            keras.backend.get_value(model.optimizer.iterations), 126
        )  # Using same optimizer from before
        model.train_on_batch(x_train[:10], y_train[:10])
        np.testing.assert_equal(
            keras.backend.get_value(model.optimizer.iterations), 127
        )
        kernel, bias = dense.get_weights()
        np.testing.assert_allclose(kernel, 1.0, atol=1e-3)
        np.testing.assert_allclose(bias, 2.0, atol=1e-3)

    def test_sgd(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.SGD())

    def test_momentum(self):
        with self.cached_session():
            self._test_optimizer(
                optimizer_v1.SGD(lr=0.01, momentum=0.9, nesterov=True)
            )

    def test_rmsprop(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.RMSprop())
            self._test_optimizer(optimizer_v1.RMSprop(decay=1e-3))

    def test_adagrad(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.Adagrad())
            self._test_optimizer(optimizer_v1.Adagrad(decay=1e-3))

    def test_adadelta(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.Adadelta(), target=0.6)
            # Accuracy seems dependent on the initialization. Even adding
            # tf.compat.v1.Print nodes in the graph seemed to affect the
            # initialization seed, and hence the accuracy.
            self._test_optimizer(optimizer_v1.Adadelta(decay=1e-3), target=0.4)

    def test_adam(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.Adam())
            # Accuracy seems dependent on the seed initialization.
            # TODO(b/121051441): fix test flakiness.
            self._test_optimizer(optimizer_v1.Adam(decay=1e-3), target=0.73)
            self._test_optimizer(optimizer_v1.Adam(amsgrad=True))

    def test_adamax(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.Adamax())
            self._test_optimizer(optimizer_v1.Adamax(decay=1e-3))

    def test_nadam(self):
        with self.cached_session():
            self._test_optimizer(optimizer_v1.Nadam())

    def test_clipnorm(self):
        with self.cached_session():
            self._test_optimizer(
                optimizer_v1.SGD(lr=0.01, momentum=0.9, clipnorm=0.5)
            )

    def test_clipvalue(self):
        with self.cached_session():
            self._test_optimizer(
                optimizer_v1.SGD(lr=0.01, momentum=0.9, clipvalue=0.5)
            )

    def test_tf_optimizer(self):
        if tf.executing_eagerly():
            self.skipTest("v1 optimizer does not run in eager mode")
        optimizer = optimizer_v1.TFOptimizer(AdamOptimizer(0.01))
        model = keras.models.Sequential()
        model.add(
            keras.layers.Dense(
                2,
                input_shape=(3,),
                kernel_constraint=keras.constraints.MaxNorm(1),
            )
        )
        # This is possible
        model.compile(
            loss="mean_squared_error",
            optimizer=optimizer,
            run_eagerly=test_utils.should_run_eagerly(),
        )
        keras.backend.track_tf_optimizer(optimizer)
        model.fit(
            np.random.random((5, 3)),
            np.random.random((5, 2)),
            epochs=1,
            batch_size=5,
            verbose=0,
        )
        # not supported
        with self.assertRaises(NotImplementedError):
            _ = optimizer.weights
        with self.assertRaises(NotImplementedError):
            optimizer.get_config()
        with self.assertRaises(NotImplementedError):
            optimizer.from_config(None)

    def test_optimizer_garbage_collection(self):
        if tf.executing_eagerly():
            self.skipTest("v1 optimizer does not run in eager mode")
        graph = tf.Graph()
        with graph.as_default():
            optimizer = optimizer_v1.TFOptimizer(AdamOptimizer(0.01))
            keras.backend.track_tf_optimizer(optimizer)
            optimizer_weak = weakref.ref(optimizer)
        graph_weak = weakref.ref(graph)
        del graph, optimizer
        gc.collect()
        # Check that the weak references are dead now.
        self.assertIs(graph_weak(), None)
        self.assertIs(optimizer_weak(), None)

    def test_tf_optimizer_iterations(self):
        if tf.executing_eagerly():
            self.skipTest("v1 optimizer does not run in eager mode")
        with self.cached_session():
            optimizer = optimizer_v1.TFOptimizer(AdamOptimizer(0.01))
            model = keras.models.Sequential()
            model.add(
                keras.layers.Dense(
                    2,
                    input_shape=(3,),
                    kernel_constraint=keras.constraints.MaxNorm(1),
                )
            )
            model.compile(
                loss="mean_squared_error",
                optimizer=optimizer,
                run_eagerly=test_utils.should_run_eagerly(),
            )
            keras.backend.track_tf_optimizer(optimizer)
            self.assertEqual(
                keras.backend.get_value(model.optimizer.iterations), 0
            )

            model.fit(
                np.random.random((55, 3)),
                np.random.random((55, 2)),
                epochs=1,
                batch_size=5,
                verbose=0,
            )
            self.assertEqual(
                keras.backend.get_value(model.optimizer.iterations), 11
            )

    def test_negative_clipvalue_or_clipnorm(self):
        with self.assertRaises(ValueError):
            _ = optimizer_v1.SGD(lr=0.01, clipvalue=-0.5)
        with self.assertRaises(ValueError):
            _ = optimizer_v1.Adam(clipnorm=-2.0)

    def test_mixed_precision_loss_scale_optimizer(self):
        if tf.executing_eagerly():
            self.skipTest("v1 optimizer does not run in eager mode")
        optimizer = MixedPrecisionLossScaleOptimizer(AdamOptimizer(), "dynamic")
        model = keras.models.Sequential()
        model.add(
            keras.layers.Dense(
                2,
                input_shape=(3,),
                kernel_constraint=keras.constraints.MaxNorm(1),
            )
        )
        model.compile(
            loss="mean_squared_error",
            optimizer=optimizer,
            run_eagerly=test_utils.should_run_eagerly(),
        )
        model.fit(
            np.random.random((5, 3)),
            np.random.random((5, 2)),
            epochs=1,
            batch_size=5,
            verbose=0,
        )

    def test_deserialization_error(self):
        with self.assertRaisesRegex(
            ValueError, "Could not interpret optimizer"
        ):
            keras.optimizers.get(0)


if __name__ == "__main__":
    tf.test.main()
