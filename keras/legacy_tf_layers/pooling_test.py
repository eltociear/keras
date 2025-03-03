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
"""Tests for tf.layers.pooling."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow.compat.v2 as tf

from tensorflow.python.framework import (
    test_util as tf_test_utils,
)
from keras.legacy_tf_layers import pooling as pooling_layers


class PoolingTest(tf.test.TestCase):
    def testInvalidDataFormat(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 3), seed=1)
        with self.assertRaisesRegex(ValueError, "data_format"):
            pooling_layers.max_pooling2d(
                images, 3, strides=2, data_format="invalid"
            )

    def testInvalidStrides(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 3), seed=1)
        with self.assertRaisesRegex(ValueError, "strides"):
            pooling_layers.max_pooling2d(images, 3, strides=(1, 2, 3))

        with self.assertRaisesRegex(ValueError, "strides"):
            pooling_layers.max_pooling2d(images, 3, strides=None)

    def testInvalidPoolSize(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 3), seed=1)
        with self.assertRaisesRegex(ValueError, "pool_size"):
            pooling_layers.max_pooling2d(images, (1, 2, 3), strides=2)

        with self.assertRaisesRegex(ValueError, "pool_size"):
            pooling_layers.max_pooling2d(images, None, strides=2)

    def testCreateMaxPooling2D(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 4))
        layer = pooling_layers.MaxPooling2D([2, 2], strides=2)
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 3, 4, 4])

    def testCreateAveragePooling2D(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 4))
        layer = pooling_layers.AveragePooling2D([2, 2], strides=2)
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 3, 4, 4])

    @tf_test_utils.run_deprecated_v1
    def testCreateMaxPooling2DChannelsFirst(self):
        height, width = 7, 9
        images = tf.random.uniform((5, 2, height, width))
        layer = pooling_layers.MaxPooling2D(
            [2, 2], strides=1, data_format="channels_first"
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 2, 6, 8])

    @tf_test_utils.run_deprecated_v1
    def testCreateAveragePooling2DChannelsFirst(self):
        height, width = 5, 6
        images = tf.random.uniform((3, 4, height, width))
        layer = pooling_layers.AveragePooling2D(
            (2, 2),
            strides=(1, 1),
            padding="valid",
            data_format="channels_first",
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [3, 4, 4, 5])

    @tf_test_utils.run_deprecated_v1
    def testCreateAveragePooling2DChannelsFirstWithNoneBatch(self):
        height, width = 5, 6
        images = tf.compat.v1.placeholder(
            dtype="float32", shape=(None, 4, height, width)
        )
        layer = pooling_layers.AveragePooling2D(
            (2, 2),
            strides=(1, 1),
            padding="valid",
            data_format="channels_first",
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [None, 4, 4, 5])

    def testCreateMaxPooling1D(self):
        width = 7
        channels = 3
        images = tf.random.uniform((5, width, channels))
        layer = pooling_layers.MaxPooling1D(2, strides=2)
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, width // 2, channels]
        )

    def testCreateAveragePooling1D(self):
        width = 7
        channels = 3
        images = tf.random.uniform((5, width, channels))
        layer = pooling_layers.AveragePooling1D(2, strides=2)
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, width // 2, channels]
        )

    def testCreateMaxPooling1DChannelsFirst(self):
        width = 7
        channels = 3
        images = tf.random.uniform((5, channels, width))
        layer = pooling_layers.MaxPooling1D(
            2, strides=2, data_format="channels_first"
        )
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, channels, width // 2]
        )

    def testCreateAveragePooling1DChannelsFirst(self):
        width = 7
        channels = 3
        images = tf.random.uniform((5, channels, width))
        layer = pooling_layers.AveragePooling1D(
            2, strides=2, data_format="channels_first"
        )
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, channels, width // 2]
        )

    def testCreateMaxPooling3D(self):
        depth, height, width = 6, 7, 9
        images = tf.random.uniform((5, depth, height, width, 4))
        layer = pooling_layers.MaxPooling3D([2, 2, 2], strides=2)
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 3, 3, 4, 4])

    def testCreateAveragePooling3D(self):
        depth, height, width = 6, 7, 9
        images = tf.random.uniform((5, depth, height, width, 4))
        layer = pooling_layers.AveragePooling3D([2, 2, 2], strides=2)
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 3, 3, 4, 4])

    def testMaxPooling3DChannelsFirst(self):
        depth, height, width = 6, 7, 9
        images = tf.random.uniform((5, 2, depth, height, width))
        layer = pooling_layers.MaxPooling3D(
            [2, 2, 2], strides=2, data_format="channels_first"
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 2, 3, 3, 4])

    def testAveragePooling3DChannelsFirst(self):
        depth, height, width = 6, 7, 9
        images = tf.random.uniform((5, 2, depth, height, width))
        layer = pooling_layers.AveragePooling3D(
            [2, 2, 2], strides=2, data_format="channels_first"
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 2, 3, 3, 4])

    def testCreateMaxPooling2DIntegerPoolSize(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 4))
        layer = pooling_layers.MaxPooling2D(2, strides=2)
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 3, 4, 4])

    def testMaxPooling2DPaddingSame(self):
        height, width = 7, 9
        images = tf.random.uniform((5, height, width, 4), seed=1)
        layer = pooling_layers.MaxPooling2D(
            images.get_shape()[1:3], strides=2, padding="same"
        )
        output = layer(images)
        self.assertListEqual(output.get_shape().as_list(), [5, 4, 5, 4])

    def testCreatePooling2DWithStrides(self):
        height, width = 6, 8
        # Test strides tuple
        images = tf.random.uniform((5, height, width, 3), seed=1)
        layer = pooling_layers.MaxPooling2D(
            [2, 2], strides=(2, 2), padding="same"
        )
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, height / 2, width / 2, 3]
        )

        # Test strides integer
        layer = pooling_layers.MaxPooling2D([2, 2], strides=2, padding="same")
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, height / 2, width / 2, 3]
        )

        # Test unequal strides
        layer = pooling_layers.MaxPooling2D(
            [2, 2], strides=(2, 1), padding="same"
        )
        output = layer(images)
        self.assertListEqual(
            output.get_shape().as_list(), [5, height / 2, width, 3]
        )


if __name__ == "__main__":
    tf.test.main()
