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
"""Tests add_loss API correctness."""

import tensorflow.compat.v2 as tf

import numpy as np
from keras import Input
from keras.testing_infra import test_combinations
from keras import layers
from keras import losses
from keras import Model
from keras.optimizers import optimizer_v2
from keras import Sequential
from keras.testing_infra import test_utils
from tensorflow.python.platform import tf_logging as logging
from tensorflow.python.training.rmsprop import (
    RMSPropOptimizer,
)

MAE = losses.MeanAbsoluteError
mae = losses.mean_absolute_error


def get_ctl_train_step(model):
    optimizer = optimizer_v2.gradient_descent.SGD(0.05)

    def train_step(x, y, w=None):
        with tf.GradientTape() as tape:
            if w is not None:
                model([x, y, w])
            else:
                model([x, y])
            loss = tf.reduce_sum(model.losses)
        gradients = tape.gradient(loss, model.trainable_weights)
        optimizer.apply_gradients(zip(gradients, model.trainable_weights))
        return loss

    return train_step


# TODO(psv): Add tests cases where a model is used in loss function but is
# not part of the training model.


class TestAddLossCorrectness(test_combinations.TestCase):
    def setUp(self):
        super().setUp()
        self.x = np.array([[0.0], [1.0], [2.0]], dtype="float32")
        self.y = np.array([[0.5], [2.0], [3.5]], dtype="float32")
        self.w = np.array([[1.25], [0.5], [1.25]], dtype="float32")

    @test_combinations.run_all_keras_modes
    def test_loss_on_model_fit(self):
        inputs = Input(shape=(1,))
        targets = Input(shape=(1,))
        outputs = test_utils.Bias()(inputs)
        model = Model([inputs, targets], outputs)
        model.add_loss(MAE()(targets, outputs))
        model.add_loss(tf.reduce_mean(mae(targets, outputs)))
        model.compile(
            optimizer_v2.gradient_descent.SGD(0.05),
            run_eagerly=test_utils.should_run_eagerly(),
        )

        history = model.fit([self.x, self.y], batch_size=3, epochs=5)
        self.assertAllClose(
            history.history["loss"], [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3
        )

    @test_combinations.run_with_all_model_types(exclude_models=["sequential"])
    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_loss_callable_on_model_fit(self):
        model = test_utils.get_model_from_layers(
            [test_utils.Bias()], input_shape=(1,)
        )

        def callable_loss():
            return tf.reduce_sum(model.weights)

        model.add_loss(callable_loss)
        model.compile(
            optimizer_v2.gradient_descent.SGD(0.1),
            run_eagerly=test_utils.should_run_eagerly(),
        )

        history = model.fit(self.x, batch_size=3, epochs=5)
        self.assertAllClose(
            history.history["loss"], [0.0, -0.1, -0.2, -0.3, -0.4], 1e-3
        )

    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_loss_on_model_ctl(self):
        def get_model_and_train_step():
            inputs = Input(shape=(1,))
            targets = Input(shape=(1,))
            outputs = test_utils.Bias()(inputs)
            model = Model([inputs, targets], outputs)
            model.add_loss(MAE()(targets, outputs))
            model.add_loss(tf.reduce_mean(mae(targets, outputs)))
            return get_ctl_train_step(model)

        train_step = get_model_and_train_step()
        loss = [train_step(self.x, self.y) for _ in range(5)]
        self.assertAllClose(loss, [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3)

        train_step = tf.function(get_model_and_train_step())
        loss = [train_step(self.x, self.y) for _ in range(5)]
        self.assertAllClose(loss, [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3)

    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_loss_callable_on_model_ctl(self):
        def get_model_and_train_step():
            inputs = Input(shape=(1,))
            targets = Input(shape=(1,))
            outputs = test_utils.Bias()(inputs)
            model = Model([inputs, targets], outputs)

            def callable_loss():
                return tf.reduce_sum(model.weights)

            model.add_loss(callable_loss)
            return get_ctl_train_step(model)

        train_step = get_model_and_train_step()
        loss = [train_step(self.x, self.y) for _ in range(5)]
        self.assertAllClose(loss, [0.0, -0.05, -0.1, -0.15, -0.2], 1e-3)

        train_step = tf.function(get_model_and_train_step())
        loss = [train_step(self.x, self.y) for _ in range(5)]
        self.assertAllClose(loss, [0.0, -0.05, -0.1, -0.15, -0.2], 1e-3)

    @test_combinations.run_all_keras_modes
    def test_loss_with_sample_weight_on_model_fit(self):
        inputs = Input(shape=(1,))
        targets = Input(shape=(1,))
        sw = Input(shape=(1,))
        outputs = test_utils.Bias()(inputs)
        model = Model([inputs, targets, sw], outputs)
        model.add_loss(MAE()(targets, outputs, sw))
        model.add_loss(3 * tf.reduce_mean(sw * mae(targets, outputs)))
        model.compile(
            optimizer_v2.gradient_descent.SGD(0.025),
            run_eagerly=test_utils.should_run_eagerly(),
        )

        history = model.fit([self.x, self.y, self.w], batch_size=3, epochs=5)
        self.assertAllClose(
            history.history["loss"], [4.0, 3.6, 3.2, 2.8, 2.4], 1e-3
        )

    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_loss_with_sample_weight_on_model_ctl(self):
        def get_model_and_train_step():
            inputs = Input(shape=(1,))
            targets = Input(shape=(1,))
            sw = Input(shape=(1,))
            outputs = test_utils.Bias()(inputs)
            model = Model([inputs, targets, sw], outputs)
            model.add_loss(MAE()(targets, outputs, sw))
            model.add_loss(tf.reduce_mean(sw * mae(targets, outputs)))
            return get_ctl_train_step(model)

        train_step = get_model_and_train_step()
        loss = [train_step(self.x, self.y, self.w) for _ in range(5)]
        self.assertAllClose(loss, [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3)

        train_step = tf.function(get_model_and_train_step())
        loss = [train_step(self.x, self.y, self.w) for _ in range(5)]
        self.assertAllClose(loss, [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3)

    @test_combinations.run_all_keras_modes
    def test_loss_with_sample_weight_in_model_call(self):
        class MyModel(Model):
            def __init__(self):
                super().__init__()
                self.bias = test_utils.Bias()

            def call(self, inputs):
                outputs = self.bias(inputs[0])
                self.add_loss(MAE()(inputs[1], outputs, inputs[2]))
                self.add_loss(
                    tf.reduce_mean(inputs[2] * mae(inputs[1], outputs))
                )
                return outputs

        model = MyModel()
        model.predict([self.x, self.y, self.w])
        model.compile(
            optimizer_v2.gradient_descent.SGD(0.05),
            run_eagerly=test_utils.should_run_eagerly(),
        )

        history = model.fit([self.x, self.y, self.w], batch_size=3, epochs=5)
        self.assertEqual(len(model.losses), 2)
        self.assertAllClose(
            history.history["loss"], [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3
        )

        eval_out = model.evaluate([self.x, self.y, self.w])
        self.assertAlmostEqual(eval_out, 1.0, 3)

    @test_combinations.run_all_keras_modes
    def test_loss_with_sample_weight_in_layer_call(self):
        class MyLayer(layers.Layer):
            def __init__(self):
                super().__init__()
                self.bias = test_utils.Bias()

            def call(self, inputs):
                out = self.bias(inputs[0])
                self.add_loss(MAE()(inputs[1], out, inputs[2]))
                self.add_loss(tf.reduce_mean(inputs[2] * mae(inputs[1], out)))
                return out

        inputs = Input(shape=(1,))
        targets = Input(shape=(1,))
        sw = Input(shape=(1,))

        outputs = MyLayer()([inputs, targets, sw])
        model = Model([inputs, targets, sw], outputs)
        model.predict([self.x, self.y, self.w])
        model.compile(
            optimizer_v2.gradient_descent.SGD(0.05),
            run_eagerly=test_utils.should_run_eagerly(),
        )

        history = model.fit([self.x, self.y, self.w], batch_size=3, epochs=5)
        self.assertAllClose(
            history.history["loss"], [2.0, 1.8, 1.6, 1.4, 1.2], 1e-3
        )

        output = model.evaluate([self.x, self.y, self.w])
        self.assertAlmostEqual(output, 1.0, 3)

        output = model.test_on_batch([self.x, self.y, self.w])
        self.assertAlmostEqual(output, 1.0, 3)

    @test_combinations.run_all_keras_modes
    def test_loss_on_layer(self):
        class MyLayer(layers.Layer):
            def call(self, inputs):
                self.add_loss(tf.reduce_sum(inputs))
                return inputs

        inputs = Input((3,))
        layer = MyLayer()
        outputs = layer(inputs)
        model = Model(inputs, outputs)
        self.assertEqual(len(model.losses), 1)
        model.compile("sgd", "mse", run_eagerly=test_utils.should_run_eagerly())
        loss = model.train_on_batch(np.ones((2, 3)), np.ones((2, 3)))
        self.assertEqual(loss, 2 * 3)

    @test_combinations.run_all_keras_modes
    @test_combinations.run_with_all_model_types
    def test_activity_regularizer(self):
        loss = {}
        for reg in [None, "l2"]:
            model_layers = [
                layers.Dense(
                    10,
                    activation="relu",
                    activity_regularizer=reg,
                    kernel_initializer="ones",
                    use_bias=False,
                ),
                layers.Dense(
                    1,
                    activation="sigmoid",
                    kernel_initializer="ones",
                    use_bias=False,
                ),
            ]

            model = test_utils.get_model_from_layers(
                model_layers, input_shape=(10,)
            )

            x = np.ones((10, 10), "float32")
            y = np.zeros((10, 1), "float32")

            optimizer = RMSPropOptimizer(learning_rate=0.001)
            model.compile(
                optimizer,
                "binary_crossentropy",
                run_eagerly=test_utils.should_run_eagerly(),
            )
            model.fit(x, y, batch_size=2, epochs=5)
            loss[reg] = model.evaluate(x, y)
        self.assertLess(loss[None], loss["l2"])

    @test_combinations.run_all_keras_modes
    @test_combinations.run_with_all_model_types
    def test_activity_regularizer_loss_value(self):
        layer = layers.Dense(
            1,
            kernel_initializer="zeros",
            bias_initializer="ones",
            activity_regularizer="l2",
        )

        model = test_utils.get_model_from_layers([layer], input_shape=(10,))

        x = np.ones((10, 10), "float32")
        optimizer = RMSPropOptimizer(learning_rate=0.001)
        model.compile(optimizer, run_eagerly=test_utils.should_run_eagerly())
        loss = model.test_on_batch(x)
        self.assertAlmostEqual(0.01, loss, places=4)

    @test_combinations.run_all_keras_modes
    def test_activity_regularizer_batch_independent(self):
        inputs = layers.Input(shape=(10,))
        x = layers.Dense(10, activation="relu", activity_regularizer="l2")(
            inputs
        )
        outputs = layers.Dense(1, activation="sigmoid")(x)
        model = Model(inputs, outputs)

        optimizer = RMSPropOptimizer(learning_rate=0.001)
        model.compile(optimizer, run_eagerly=test_utils.should_run_eagerly())

        loss_small_batch = model.test_on_batch(np.ones((10, 10), "float32"))
        loss_big_batch = model.test_on_batch(np.ones((20, 10), "float32"))
        self.assertAlmostEqual(loss_small_batch, loss_big_batch, places=4)

    @test_combinations.run_all_keras_modes
    def test_with_shared_layer(self):
        class LayerWithLoss(layers.Layer):
            def call(self, inputs):
                self.add_loss(tf.reduce_sum(inputs))
                return inputs * 2

        shared_layer = LayerWithLoss()

        m = Sequential([shared_layer])
        m2 = Sequential([shared_layer, m])
        m2(tf.constant([1, 2, 3]))
        self.assertEqual(len(m2.losses), 2)
        self.assertAllClose(m2.losses, [6, 12])

    @test_combinations.run_all_keras_modes
    def test_with_shared_nested_layer(self):
        class LayerWithLoss(layers.Layer):
            def call(self, inputs):
                self.add_loss(tf.reduce_sum(inputs))
                return inputs * 2

        class LayerWithNestedLayerWithLoss(layers.Layer):
            def __init__(self):
                super().__init__()
                self.loss_layer = LayerWithLoss()

            def call(self, inputs):
                return self.loss_layer(inputs)

        shared_layer = LayerWithNestedLayerWithLoss()

        m = Sequential([shared_layer])
        m2 = Sequential([shared_layer, m])
        m2(tf.constant([1, 2, 3]))
        self.assertEqual(len(m2.losses), 2)
        self.assertAllClose(m2.losses, [6, 12])

    @test_combinations.run_all_keras_modes
    def test_clear_losses(self):
        class LayerWithSharedNestedLossLayer(layers.Layer):
            def __init__(self):
                super().__init__()
                self.loss_layer = layers.ActivityRegularization(l2=0.001)
                self.add_weight(shape=(1,), regularizer="l2")

            def call(self, x):
                x = self.loss_layer(x)
                return self.loss_layer(x)

        inputs = Input(shape=(1,))
        l = LayerWithSharedNestedLossLayer()  # Weight loss + 2 activity losses.

        x1 = tf.ones((1, 1))
        _ = l(x1)
        if not tf.executing_eagerly():
            self.assertEqual(len(l.get_losses_for(x1)), 2)
            self.assertEqual(len(l.get_losses_for(None)), 1)

        x2 = tf.ones((1, 1))
        _ = l(x2)
        if not tf.executing_eagerly():
            self.assertEqual(len(l.get_losses_for(x1)), 2)
            self.assertEqual(len(l.get_losses_for(x2)), 2)
            self.assertEqual(len(l.get_losses_for(None)), 1)

        outputs = l(inputs)
        model = Model(inputs, outputs)
        if not tf.executing_eagerly():
            self.assertEqual(len(model.losses), 7)
            self.assertEqual(len(l.get_losses_for(x1)), 2)
            self.assertEqual(len(l.get_losses_for(x2)), 2)
            self.assertEqual(len(l.get_losses_for(None)), 1)

        x3 = tf.ones((1, 1))
        model(x3)
        x4 = tf.ones((1, 1))
        model(x4)
        if tf.executing_eagerly():
            # Eager losses are cleared every `__call__`.
            self.assertEqual(len(model.losses), 3)
        else:
            self.assertEqual(len(model.losses), 11)
            self.assertEqual(len(model.get_losses_for(x3)), 2)
            self.assertEqual(len(model.get_losses_for(x4)), 2)
            self.assertEqual(len(model.get_losses_for(None)), 1)

    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_invalid_constant_input(self):
        inputs = Input(shape=(1,))
        outputs = test_utils.Bias()(inputs)
        model = Model(inputs, outputs)
        with self.assertRaisesRegex(
            ValueError,
            "Expected a symbolic Tensors or a callable for the loss value",
        ):
            model.add_loss(1.0)

    @test_combinations.run_all_keras_modes(always_skip_v1=True)
    def test_invalid_variable_input(self):
        inputs = Input(shape=(1,))
        outputs = test_utils.Bias()(inputs)
        model = Model(inputs, outputs)
        with self.assertRaisesRegex(
            ValueError,
            "Expected a symbolic Tensors or a callable for the loss value",
        ):
            model.add_loss(model.weights[0])

    @test_combinations.run_all_keras_modes
    def test_add_entropy_loss_on_functional_model(self):
        inputs = Input(shape=(1,))
        targets = Input(shape=(1,))
        outputs = test_utils.Bias()(inputs)
        model = Model([inputs, targets], outputs)
        model.add_loss(losses.binary_crossentropy(targets, outputs))
        model.compile("sgd", run_eagerly=test_utils.should_run_eagerly())
        with tf.compat.v1.test.mock.patch.object(
            logging, "warning"
        ) as mock_log:
            model.fit([self.x, self.y], batch_size=3, epochs=5)
            self.assertNotIn(
                "Gradients do not exist for variables", str(mock_log.call_args)
            )


if __name__ == "__main__":
    tf.test.main()
