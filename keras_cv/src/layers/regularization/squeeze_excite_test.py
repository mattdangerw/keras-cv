# Copyright 2022 The KerasCV Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import tensorflow as tf

from keras_cv.src.layers import SqueezeAndExcite2D
from keras_cv.src.tests.test_case import TestCase


class SqueezeAndExcite2DTest(TestCase):
    def test_maintains_shape(self):
        input_shape = (1, 4, 4, 8)
        inputs = tf.random.uniform(input_shape)

        layer = SqueezeAndExcite2D(8, 2)
        outputs = layer(inputs)
        self.assertEqual(inputs.shape, outputs.shape)

    def test_custom_activation(self):
        def custom_activation(x):
            return x * tf.random.uniform(x.shape, seed=42)

        input_shape = (1, 4, 4, 8)
        inputs = tf.random.uniform(input_shape)

        layer = SqueezeAndExcite2D(
            8,
            2,
            squeeze_activation=custom_activation,
            excite_activation=custom_activation,
        )
        outputs = layer(inputs)
        self.assertEqual(inputs.shape, outputs.shape)

    def test_raises_invalid_ratio_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "`bottleneck_filters` should be smaller than `filters`",
        ):
            _ = SqueezeAndExcite2D(8, 9)

    def test_raises_invalid_filters_error(self):
        with self.assertRaisesRegex(
            ValueError, "`filters` should be a positive" " integer. Got (.*?)"
        ):
            _ = SqueezeAndExcite2D(-8.7)
