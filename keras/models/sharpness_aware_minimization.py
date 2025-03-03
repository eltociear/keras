# Copyright 2022 The TensorFlow Authors. All Rights Reserved.
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
"""Sharpness Aware Minimization implementation."""

import copy

from keras.engine import data_adapter
from keras.layers import deserialize as deserialize_layer
from keras.models import Model
from keras.utils import generic_utils
import tensorflow.compat.v2 as tf

from tensorflow.python.util.tf_export import keras_export

# pylint: disable=g-classes-have-attributes


@generic_utils.register_keras_serializable()
@keras_export("keras.models.experimental.SharpnessAwareMinimization", v1=[])
class SharpnessAwareMinimization(Model):
    """Sharpness aware minimization (SAM) training flow.

    Sharpness-aware minimization (SAM) is a technique that improves the model
    generalization and provides robustness to label noise. Mini-batch splitting is
    proven to improve the SAM's performance, so users can control how mini batches
    are split via setting the `num_batch_splits` argument.

    Args:
      model: `tf.keras.Model` instance. The inner model that does the
        forward-backward pass.
      rho: float, defaults to 0.05. The gradients scaling factor.
      num_batch_splits: int, defaults to None. The number of mini batches to
        split into from each data batch. If None, batches are not split into
        sub-batches.
      name: string, defaults to None. The name of the SAM model.

    Reference:
      [Pierre Foret et al., 2020](https://arxiv.org/abs/2010.01412)
    """

    def __init__(self, model, rho=0.05, num_batch_splits=None, name=None):
        super().__init__(name=name)
        self.model = model
        self.rho = rho
        self.num_batch_splits = num_batch_splits

    def train_step(self, data):
        """The logic of one SAM training step.

        Args:
          data: A nested structure of `Tensor`s. It should be of structure
            (x, y, sample_weight) or (x, y).

        Returns:
          A dict mapping metric names to running average values.
        """
        x, y, sample_weight = data_adapter.unpack_x_y_sample_weight(data)

        if self.num_batch_splits is not None:
            x_split = tf.split(x, self.num_batch_splits)
            y_split = tf.split(y, self.num_batch_splits)
        else:
            x_split = [x]
            y_split = [y]

        gradients_all_batches = []
        pred_all_batches = []
        for (x_batch, y_batch) in zip(x_split, y_split):
            epsilon_w_cache = []
            with tf.GradientTape() as tape:
                pred = self.model(x_batch)
                loss = self.compiled_loss(y_batch, pred)
            pred_all_batches.append(pred)
            trainable_variables = self.model.trainable_variables
            gradients = tape.gradient(loss, trainable_variables)

            gradients_order2_norm = self._gradients_order2_norm(gradients)
            scale = self.rho / (gradients_order2_norm + 1e-12)

            for (gradient, variable) in zip(gradients, trainable_variables):
                epsilon_w = gradient * scale
                self._distributed_apply_epsilon_w(
                    variable, epsilon_w, tf.distribute.get_strategy()
                )
                epsilon_w_cache.append(epsilon_w)

            with tf.GradientTape() as tape:
                pred = self(x_batch)
                loss = self.compiled_loss(y_batch, pred)
            gradients = tape.gradient(loss, trainable_variables)
            if len(gradients_all_batches) == 0:
                for gradient in gradients:
                    gradients_all_batches.append([gradient])
            else:
                for (gradient, gradient_all_batches) in zip(
                    gradients, gradients_all_batches
                ):
                    gradient_all_batches.append(gradient)
            for (variable, epsilon_w) in zip(
                trainable_variables, epsilon_w_cache
            ):
                # Restore the variable to its original value before `apply_gradients()`.
                self._distributed_apply_epsilon_w(
                    variable, -epsilon_w, tf.distribute.get_strategy()
                )

        gradients = []
        for gradient_all_batches in gradients_all_batches:
            gradients.append(tf.reduce_sum(gradient_all_batches, axis=0))
        self.optimizer.apply_gradients(zip(gradients, trainable_variables))

        pred = tf.concat(pred_all_batches, axis=0)
        self.compiled_metrics.update_state(y, pred, sample_weight)
        return {m.name: m.result() for m in self.metrics}

    def call(self, inputs):
        """Forward pass of SAM.

        SAM delegates the forward pass call to the wrapped model.

        Args:
          inputs: Tensor. The model inputs.

        Returns:
          A Tensor, the outputs of the wrapped model for given `inputs`.
        """
        return self.model(inputs)

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "model": generic_utils.serialize_keras_object(self.model),
                "rho": self.rho,
            }
        )
        return config

    @classmethod
    def from_config(cls, config, custom_objects=None):
        # Avoid mutating the input dict.
        config = copy.deepcopy(config)
        model = deserialize_layer(
            config.pop("model"), custom_objects=custom_objects
        )
        config["model"] = model
        return super().from_config(config, custom_objects)

    def _distributed_apply_epsilon_w(self, var, epsilon_w, strategy):
        # Helper function to apply epsilon_w on model variables.
        if isinstance(
            tf.distribute.get_strategy(),
            (
                tf.distribute.experimental.ParameterServerStrategy,
                tf.distribute.experimental.CentralStorageStrategy,
            ),
        ):
            # Under PSS and CSS, the AggregatingVariable has to be kept in sync.
            def distribute_apply(strategy, var, epsilon_w):
                strategy.extended.update(
                    var,
                    lambda x, y: x.assign_add(y),
                    args=(epsilon_w,),
                    group=False,
                )

            tf.__internal__.distribute.interim.maybe_merge_call(
                distribute_apply, tf.distribute.get_strategy(), var, epsilon_w
            )
        else:
            var.assign_add(epsilon_w)

    def _gradients_order2_norm(self, gradients):
        norm = tf.norm(
            tf.stack([tf.norm(grad) for grad in gradients if grad is not None])
        )
        return norm
