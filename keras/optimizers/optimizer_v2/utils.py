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
"""Optimizer utilities."""

import tensorflow.compat.v2 as tf
from tensorflow.python.platform import tf_logging as logging


def all_reduce_sum_gradients(grads_and_vars):
    """Returns all-reduced gradients aggregated via summation.

    Args:
      grads_and_vars: List of (gradient, variable) pairs.

    Returns:
      List of (gradient, variable) pairs where gradients have been all-reduced.
    """
    grads_and_vars = list(grads_and_vars)
    filtered_grads_and_vars = filter_empty_gradients(grads_and_vars)
    if filtered_grads_and_vars:
        if tf.__internal__.distribute.strategy_supports_no_merge_call():
            grads = [pair[0] for pair in filtered_grads_and_vars]
            reduced = tf.distribute.get_replica_context().all_reduce(
                tf.distribute.ReduceOp.SUM, grads
            )
        else:
            # TODO(b/183257003): Remove this branch
            reduced = tf.distribute.get_replica_context().merge_call(
                _all_reduce_sum_fn, args=(filtered_grads_and_vars,)
            )
    else:
        reduced = []
    # Copy 'reduced' but add None gradients back in
    reduced_with_nones = []
    reduced_pos = 0
    for g, v in grads_and_vars:
        if g is None:
            reduced_with_nones.append((None, v))
        else:
            reduced_with_nones.append((reduced[reduced_pos], v))
            reduced_pos += 1
    assert reduced_pos == len(reduced), "Failed to add all gradients"
    return reduced_with_nones


def filter_empty_gradients(grads_and_vars):
    """Filter out `(grad, var)` pairs that have a gradient equal to `None`."""
    grads_and_vars = tuple(grads_and_vars)
    if not grads_and_vars:
        return grads_and_vars

    filtered = []
    vars_with_empty_grads = []
    for grad, var in grads_and_vars:
        if grad is None:
            vars_with_empty_grads.append(var)
        else:
            filtered.append((grad, var))
    filtered = tuple(filtered)

    if not filtered:
        variable = ([v.name for _, v in grads_and_vars],)
        raise ValueError(
            f"No gradients provided for any variable: {variable}. "
            f"Provided `grads_and_vars` is {grads_and_vars}."
        )
    if vars_with_empty_grads:
        logging.warning(
            (
                "Gradients do not exist for variables %s when minimizing the loss. "
                "If you're using `model.compile()`, did you forget to provide a `loss`"
                "argument?"
            ),
            ([v.name for v in vars_with_empty_grads]),
        )
    return filtered


def make_gradient_clipnorm_fn(clipnorm):
    """Creates a gradient transformation function for clipping by norm."""
    if clipnorm is None:
        return lambda grads_and_vars: grads_and_vars

    def gradient_clipnorm_fn(grads_and_vars):

        if isinstance(
            tf.distribute.get_strategy(),
            (
                tf.distribute.experimental.CentralStorageStrategy,
                tf.compat.v1.distribute.experimental.CentralStorageStrategy,
            ),
        ):
            raise ValueError(
                "`clipnorm` is not supported with `CenteralStorageStrategy`. "
                f"The strategy used is {tf.distribute.get_strategy()}."
            )

        clipped_grads_and_vars = [
            (tf.clip_by_norm(g, clipnorm), v) for g, v in grads_and_vars
        ]
        return clipped_grads_and_vars

    return gradient_clipnorm_fn


def make_global_gradient_clipnorm_fn(clipnorm):
    """Creates a gradient transformation function for clipping by norm."""
    if clipnorm is None:
        return lambda grads_and_vars: grads_and_vars

    def gradient_clipnorm_fn(grads_and_vars):

        if isinstance(
            tf.distribute.get_strategy(),
            (
                tf.distribute.experimental.CentralStorageStrategy,
                tf.compat.v1.distribute.experimental.CentralStorageStrategy,
            ),
        ):
            raise ValueError(
                "`global_clipnorm` is not supported with `CenteralStorageStrategy`. "
                f"The strategy used is {tf.distribute.get_strategy()}."
            )

        grads, variables = zip(*grads_and_vars)
        clipped_grads, _ = tf.clip_by_global_norm(grads, clipnorm)
        clipped_grads_and_vars = list(zip(clipped_grads, variables))
        return clipped_grads_and_vars

    return gradient_clipnorm_fn


def make_gradient_clipvalue_fn(clipvalue):
    """Creates a gradient transformation function for clipping by value."""
    if clipvalue is None:
        return lambda grads_and_vars: grads_and_vars

    def gradient_clipvalue_fn(grads_and_vars):

        if isinstance(
            tf.distribute.get_strategy(),
            (
                tf.distribute.experimental.CentralStorageStrategy,
                tf.compat.v1.distribute.experimental.CentralStorageStrategy,
            ),
        ):
            raise ValueError(
                "`clipvalue` is not supported with `CenteralStorageStrategy`. "
                f"The strategy used is {tf.distribute.get_strategy()}."
            )

        clipped_grads_and_vars = [
            (tf.clip_by_value(g, -clipvalue, clipvalue), v)
            for g, v in grads_and_vars
        ]
        return clipped_grads_and_vars

    return gradient_clipvalue_fn


def _all_reduce_sum_fn(distribution, grads_and_vars):
    return distribution.extended.batch_reduce_to(
        tf.distribute.ReduceOp.SUM, grads_and_vars
    )
