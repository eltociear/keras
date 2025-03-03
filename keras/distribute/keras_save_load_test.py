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
"""Tests for saving and loading using keras save/load APIs with DS."""

from keras.distribute import saved_model_test_base as test_base
from keras.saving import save
from keras.testing_infra import test_utils
import tensorflow.compat.v2 as tf


@test_utils.run_all_without_tensor_float_32(
    "Uses Dense layers, which call matmul"
)
class KerasSaveLoadTest(test_base.TestSavedModelBase):
    def setUp(self):
        self._root_dir = "keras_save_load"
        super().setUp()

    def _save_model(self, model, saved_dir):
        model.save(saved_dir, save_format="tf")

    def _load_and_run_model(
        self, distribution, saved_dir, predict_dataset, output_name="output_1"
    ):
        restored_keras_model = save.load_model(saved_dir)
        return restored_keras_model.predict(
            predict_dataset, steps=test_base.PREDICT_STEPS
        )

    @tf.__internal__.distribute.combinations.generate(
        test_base.simple_models_with_strategies()
    )
    def test_save_no_strategy_restore_strategy(
        self, model_and_input, distribution
    ):
        self.run_test_save_no_strategy_restore_strategy(
            model_and_input, distribution
        )

    @tf.__internal__.distribute.combinations.generate(
        tf.__internal__.test.combinations.times(
            test_base.simple_models_with_strategies(),
            tf.__internal__.test.combinations.combine(
                save_in_scope=[True, False]
            ),
        )
    )
    def test_save_strategy_restore_no_strategy(
        self, model_and_input, distribution, save_in_scope
    ):
        self.run_test_save_strategy_restore_no_strategy(
            model_and_input, distribution, save_in_scope
        )

    @tf.__internal__.distribute.combinations.generate(
        tf.__internal__.test.combinations.times(
            test_base.simple_models_with_strategy_pairs(),
            tf.__internal__.test.combinations.combine(
                save_in_scope=[True, False]
            ),
        )
    )
    def test_save_strategy_restore_strategy(
        self,
        model_and_input,
        distribution_for_saving,
        distribution_for_restoring,
        save_in_scope,
    ):
        self.run_test_save_strategy_restore_strategy(
            model_and_input,
            distribution_for_saving,
            distribution_for_restoring,
            save_in_scope,
        )


if __name__ == "__main__":
    tf.compat.v1.enable_eager_execution()
    tf.test.main()
