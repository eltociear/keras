# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
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
"""Tests for Adadelta Optimizer."""

import tensorflow.compat.v2 as tf

from absl.testing import parameterized
import numpy as np
from keras.testing_infra import test_combinations
from keras.optimizers.optimizer_v2 import adadelta

_DATA_TYPES = [tf.half, tf.float32, tf.float64, tf.complex64, tf.complex128]


class AdadeltaOptimizerTest(tf.test.TestCase, parameterized.TestCase):
    def doTestBasic(self, use_resource=False, use_callable_params=False):
        num_updates = 4  # number of ADADELTA steps to perform
        for dtype in _DATA_TYPES:
            for grad in [0.2, 0.1, 0.01]:
                for lr in [1.0, 0.5, 0.1]:
                    var0_init = [1.0, 2.0]
                    var1_init = [3.0, 4.0]
                    if use_resource:
                        var0 = tf.Variable(var0_init, dtype=dtype)
                        var1 = tf.Variable(var1_init, dtype=dtype)
                    else:
                        var0 = tf.Variable(var0_init, dtype=dtype)
                        var1 = tf.Variable(var1_init, dtype=dtype)

                    grads = tf.constant([grad, grad], dtype=dtype)

                    accum = 0.0
                    accum_update = 0.0

                    # ADADELTA gradient optimizer
                    rho = 0.95
                    epsilon = 1e-8
                    if use_callable_params:
                        adadelta_opt = adadelta.Adadelta(
                            learning_rate=lambda: lr,  # pylint: disable=cell-var-from-loop
                            rho=lambda: rho,  # pylint: disable=cell-var-from-loop
                            epsilon=epsilon,
                        )  # pylint: disable=cell-var-from-loop
                    else:
                        adadelta_opt = adadelta.Adadelta(
                            learning_rate=lr, rho=rho, epsilon=epsilon
                        )
                    if not tf.executing_eagerly():
                        adadelta_update = adadelta_opt.apply_gradients(
                            zip([grads, grads], [var0, var1])
                        )
                        self.evaluate(
                            tf.compat.v1.global_variables_initializer()
                        )

                        # Assign slots
                        slot = [None] * 2
                        slot_update = [None] * 2
                        slot[0] = adadelta_opt.get_slot(var0, "accum_grad")
                        self.assertEqual(slot[0].shape, var0.shape)

                        slot_update[0] = adadelta_opt.get_slot(
                            var0, "accum_var"
                        )
                        self.assertEqual(slot_update[0].shape, var0.shape)

                        slot[1] = adadelta_opt.get_slot(var1, "accum_grad")
                        self.assertEqual(slot[1].shape, var1.shape)

                        slot_update[1] = adadelta_opt.get_slot(
                            var1, "accum_var"
                        )
                        self.assertEqual(slot_update[1].shape, var1.shape)

                    # Fetch params to validate initial values
                    self.assertAllClose(var0_init, self.evaluate(var0))
                    self.assertAllClose(var1_init, self.evaluate(var1))

                    update = [None] * num_updates
                    tot_update = 0
                    for step in range(num_updates):
                        # Run adadelta update for comparison
                        if not tf.executing_eagerly():
                            self.evaluate(adadelta_update)
                        else:
                            adadelta_opt.apply_gradients(
                                zip([grads, grads], [var0, var1])
                            )

                        # Perform initial update without previous accum values
                        accum = accum * rho + (grad**2) * (1 - rho)
                        update[step] = (
                            np.sqrt(accum_update + epsilon)
                            * (1.0 / np.sqrt(accum + epsilon))
                            * grad
                        )
                        accum_update = accum_update * rho + (
                            update[step] ** 2
                        ) * (1.0 - rho)
                        tot_update += update[step] * lr

                        if not tf.executing_eagerly():
                            # Check that the accumulators have been updated
                            # TODO(lxuechen): This is hard to test in eager mode
                            for slot_idx in range(2):
                                self.assertAllCloseAccordingToType(
                                    np.array(
                                        [accum, accum],
                                        dtype=dtype.as_numpy_dtype(0),
                                    ),
                                    self.evaluate(slot[slot_idx]),
                                    rtol=1e-5,
                                )

                                self.assertAllCloseAccordingToType(
                                    np.array(
                                        [accum_update, accum_update],
                                        dtype=dtype.as_numpy_dtype(0),
                                    ),
                                    self.evaluate(slot_update[slot_idx]),
                                    rtol=1e-5,
                                )

                            # Check that the parameters have been updated
                            self.assertAllCloseAccordingToType(
                                np.array(
                                    [
                                        var0_init[0] - tot_update,
                                        var0_init[1] - tot_update,
                                    ],
                                    dtype=dtype.as_numpy_dtype(0),
                                ),
                                self.evaluate(var0),
                                rtol=1e-5,
                            )

                            self.assertAllCloseAccordingToType(
                                np.array(
                                    [
                                        var1_init[0] - tot_update,
                                        var1_init[1] - tot_update,
                                    ],
                                    dtype=dtype.as_numpy_dtype(0),
                                ),
                                self.evaluate(var1),
                                rtol=1e-5,
                            )

    @test_combinations.generate(
        test_combinations.combine(mode=["graph", "eager"])
    )
    def testResourceBasic(self):
        self.doTestBasic(use_resource=True)

    @test_combinations.generate(test_combinations.combine(mode=["eager"]))
    def testBasicCallableParams(self):
        self.doTestBasic(use_resource=True, use_callable_params=True)

    def testMinimizeSparseResourceVariable(self):
        # TODO(tanzheny, omalleyt): Fix test in eager mode.
        with tf.Graph().as_default():
            for dtype in _DATA_TYPES:
                var0 = tf.Variable([[1.0, 2.0]], dtype=dtype)
                x = tf.constant([[4.0], [5.0]], dtype=dtype)

                def loss():
                    pred = tf.matmul(
                        tf.compat.v1.nn.embedding_lookup([var0], [0]), x
                    )  # pylint: disable=cell-var-from-loop
                    return pred * pred

                sgd_op = adadelta.Adadelta(1.0, 1.0, 1.0).minimize(
                    loss, var_list=[var0]
                )
                self.evaluate(tf.compat.v1.global_variables_initializer())
                # Fetch params to validate initial values
                self.assertAllCloseAccordingToType(
                    [[1.0, 2.0]], self.evaluate(var0)
                )
                # Run 1 step of sgd
                self.evaluate(sgd_op)
                # Validate updated params
                self.assertAllCloseAccordingToType(
                    [[-111, -138]], self.evaluate(var0)
                )

    def testConstructAdadeltaWithLR(self):
        opt = adadelta.Adadelta(lr=1.0, rho=0.9, epsilon=1.0)
        opt_2 = adadelta.Adadelta(
            learning_rate=0.1, rho=0.9, epsilon=1.0, lr=1.0
        )
        opt_3 = adadelta.Adadelta(learning_rate=0.1, rho=0.9, epsilon=1.0)
        self.assertIsInstance(opt.lr, tf.Variable)
        self.assertIsInstance(opt_2.lr, tf.Variable)
        self.assertIsInstance(opt_3.lr, tf.Variable)

        self.evaluate(tf.compat.v1.global_variables_initializer())
        self.assertAllClose(self.evaluate(opt.lr), (1.0))
        self.assertAllClose(self.evaluate(opt_2.lr), (1.0))
        self.assertAllClose(self.evaluate(opt_3.lr), (0.1))

    def testConstructAdadeltaWithEpsilonValues(self):
        opt = adadelta.Adadelta(epsilon=None)
        self.assertEqual(opt.epsilon, 1e-7)

        opt = adadelta.Adadelta(epsilon=1e-8)
        self.assertEqual(opt.epsilon, 1e-8)


if __name__ == "__main__":
    tf.test.main()
