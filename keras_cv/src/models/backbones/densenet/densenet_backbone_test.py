# Copyright 2023 The KerasCV Authors
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

import os

import numpy as np
import pytest
from absl.testing import parameterized

from keras_cv.src.backend import keras
from keras_cv.src.backend import ops
from keras_cv.src.models.backbones.densenet.densenet_aliases import (
    DenseNet121Backbone,
)
from keras_cv.src.models.backbones.densenet.densenet_backbone import (
    DenseNetBackbone,
)
from keras_cv.src.tests.test_case import TestCase
from keras_cv.src.utils.train import get_feature_extractor


class DenseNetBackboneTest(TestCase):
    def setUp(self):
        self.input_batch = np.ones(shape=(2, 224, 224, 3))

    def test_valid_call(self):
        model = DenseNetBackbone(
            stackwise_num_repeats=[6, 12, 24, 16],
            include_rescaling=False,
        )
        model(self.input_batch)

    def test_valid_call_applications_model(self):
        model = DenseNet121Backbone()
        model(self.input_batch)

    def test_valid_call_with_rescaling(self):
        model = DenseNetBackbone(
            stackwise_num_repeats=[6, 12, 24, 16],
            include_rescaling=True,
        )
        model(self.input_batch)

    @pytest.mark.large  # Saving is slow, so mark these large.
    def test_saved_model(self):
        model = DenseNetBackbone(
            stackwise_num_repeats=[6, 12, 24, 16],
            include_rescaling=False,
        )
        model_output = model(self.input_batch)
        save_path = os.path.join(self.get_temp_dir(), "densenet_backbone.keras")
        model.save(save_path)
        restored_model = keras.models.load_model(save_path)

        # Check we got the real object back.
        self.assertIsInstance(restored_model, DenseNetBackbone)

        # Check that output matches.
        restored_output = restored_model(self.input_batch)
        self.assertAllClose(
            ops.convert_to_numpy(model_output),
            ops.convert_to_numpy(restored_output),
        )

    @pytest.mark.large  # Saving is slow, so mark these large.
    def test_saved_alias_model(self):
        model = DenseNet121Backbone()
        model_output = model(self.input_batch)
        save_path = os.path.join(
            self.get_temp_dir(), "densenet_alias_backbone.keras"
        )
        model.save(save_path)
        restored_model = keras.models.load_model(save_path)

        # Check we got the real object back.
        # Note that these aliases serialized as the base class
        self.assertIsInstance(restored_model, DenseNetBackbone)

        # Check that output matches.
        restored_output = restored_model(self.input_batch)
        self.assertAllClose(
            ops.convert_to_numpy(model_output),
            ops.convert_to_numpy(restored_output),
        )

    def test_feature_pyramid_inputs(self):
        model = DenseNet121Backbone()
        backbone_model = get_feature_extractor(
            model,
            model.pyramid_level_inputs.values(),
            model.pyramid_level_inputs.keys(),
        )
        input_size = 256
        inputs = keras.Input(shape=[input_size, input_size, 3])
        outputs = backbone_model(inputs)
        levels = ["P2", "P3", "P4", "P5"]
        self.assertEqual(list(outputs.keys()), levels)
        self.assertEqual(
            outputs["P2"].shape,
            (None, input_size // 2**2, input_size // 2**2, 256),
        )
        self.assertEqual(
            outputs["P3"].shape,
            (None, input_size // 2**3, input_size // 2**3, 512),
        )
        self.assertEqual(
            outputs["P4"].shape,
            (None, input_size // 2**4, input_size // 2**4, 1024),
        )
        self.assertEqual(
            outputs["P5"].shape,
            (None, input_size // 2**5, input_size // 2**5, 1024),
        )

    @parameterized.named_parameters(
        ("one_channel", 1),
        ("four_channels", 4),
    )
    def test_application_variable_input_channels(self, num_channels):
        model = DenseNetBackbone(
            stackwise_num_repeats=[6, 12, 24, 16],
            input_shape=(None, None, num_channels),
            include_rescaling=False,
        )
        self.assertEqual(model.output_shape, (None, None, None, 1024))
