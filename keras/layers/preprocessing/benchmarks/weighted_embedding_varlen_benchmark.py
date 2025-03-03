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
"""Benchmark for KPL implementation of weighted embedding column with varying-length inputs."""

import tensorflow.compat.v2 as tf

import keras
from tensorflow.python.eager.def_function import (
    function as tf_function,
)
from keras.layers.preprocessing.benchmarks import (
    feature_column_benchmark as fc_bm,
)

NUM_REPEATS = 10
BATCH_SIZES = [32, 256]


### KPL AND FC IMPLEMENTATION BENCHMARKS ###
def embedding_varlen(batch_size, max_length):
    """Benchmark a variable-length embedding."""
    # Data and constants.
    embedding_size = 32768
    data = fc_bm.create_data(
        max_length, batch_size * NUM_REPEATS, embedding_size - 1, dtype=int
    )
    weight = tf.ones_like(data, dtype=tf.float32)

    # Keras implementation
    data_input = keras.Input(
        shape=(None,), ragged=True, name="data", dtype=tf.int64
    )
    weight_input = keras.Input(
        shape=(None,), ragged=True, name="weight", dtype=tf.float32
    )
    embedded_data = keras.layers.Embedding(embedding_size, 256)(data_input)
    weighted_embedding = tf.multiply(
        embedded_data, tf.expand_dims(weight_input, -1)
    )
    reduced_embedding = tf.reduce_sum(weighted_embedding, axis=1)
    model = keras.Model([data_input, weight_input], reduced_embedding)

    # FC implementation
    fc = tf.feature_column.embedding_column(
        tf.feature_column.weighted_categorical_column(
            tf.feature_column.categorical_column_with_identity(
                "data", num_buckets=embedding_size - 1
            ),
            weight_feature_key="weight",
        ),
        dimension=256,
    )

    # Wrap the FC implementation in a tf.function for a fair comparison
    @tf_function()
    def fc_fn(tensors):
        fc.transform_feature(
            tf.__internal__.feature_column.FeatureTransformationCache(tensors),
            None,
        )

    # Benchmark runs
    keras_data = {"data": data, "weight": weight}
    k_avg_time = fc_bm.run_keras(keras_data, model, batch_size, NUM_REPEATS)

    fc_data = {"data": data.to_sparse(), "weight": weight.to_sparse()}
    fc_avg_time = fc_bm.run_fc(fc_data, fc_fn, batch_size, NUM_REPEATS)

    return k_avg_time, fc_avg_time


class BenchmarkLayer(fc_bm.LayerBenchmark):
    """Benchmark the layer forward pass."""

    def benchmark_layer(self):
        for batch in BATCH_SIZES:
            name = "weighted_embedding|varlen|batch_%s" % batch
            k_time, f_time = embedding_varlen(batch_size=batch, max_length=256)
            self.report(name, k_time, f_time, NUM_REPEATS)


if __name__ == "__main__":
    tf.test.main()
