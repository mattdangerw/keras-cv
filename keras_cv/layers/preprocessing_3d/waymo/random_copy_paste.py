# Copyright 2022 Waymo LLC.
#
# Licensed under the terms in https://github.com/keras-team/keras-cv/blob/master/keras_cv/layers/preprocessing_3d/waymo/LICENSE  # noqa: E501

import tensorflow as tf

from keras_cv.api_export import keras_cv_export
from keras_cv.backend import random
from keras_cv.bounding_box_3d import CENTER_XYZ_DXDYDZ_PHI
from keras_cv.layers.preprocessing_3d import base_augmentation_layer_3d
from keras_cv.ops import iou_3d
from keras_cv.point_cloud import is_within_any_box3d

POINT_CLOUDS = base_augmentation_layer_3d.POINT_CLOUDS
BOUNDING_BOXES = base_augmentation_layer_3d.BOUNDING_BOXES
OBJECT_POINT_CLOUDS = base_augmentation_layer_3d.OBJECT_POINT_CLOUDS
OBJECT_BOUNDING_BOXES = base_augmentation_layer_3d.OBJECT_BOUNDING_BOXES


@keras_cv_export("keras_cv.layers.RandomCopyPaste")
class RandomCopyPaste(base_augmentation_layer_3d.BaseAugmentationLayer3D):
    """A preprocessing layer which randomly pastes object point clouds and
    bounding boxes during training.

    This layer will randomly paste object point clouds and bounding boxes.
    OBJECT_POINT_CLOUDS and OBJECT_BOUNDING_BOXES are generated by running
    group_points_by_bounding_boxes function on additional input frames. We use
    the first frame to check overlap between existing bounding boxes and pasted
    bounding boxes.
    If a to-be-pasted bounding box overlaps with an existing bounding box and
    object point clouds, we do not paste the additional bounding box. We load 5
    times max_paste_bounding_boxes to check overlap.
    If a to-be-pasted bounding box overlaps with existing background point
    clouds, we paste the additional bounding box and replace the background
    point clouds with object point clouds.

    Input shape:
      point_clouds: 3D (multi frames) float32 Tensor with shape
        [num of frames, num of points, num of point features].
        The first 5 features are [x, y, z, class, range].
      bounding_boxes: 3D (multi frames) float32 Tensor with shape
        [num of frames, num of boxes, num of box features]. Boxes are expected
        to follow the CENTER_XYZ_DXDYDZ_PHI format. Refer to
        https://github.com/keras-team/keras-cv/blob/master/keras_cv/bounding_box_3d/formats.py

    Output shape:
      A tuple of two Tensors (point_clouds, bounding_boxes) with the same shape
      as input Tensors.

    Arguments:
      label_index: An optional int scalar sets the target object index.
        Bounding boxes and corresponding point clouds with box class ==
        label_index will be saved as OBJECT_BOUNDING_BOXES and
        OBJECT_POINT_CLOUDS. If label index is None, all valid bounding boxes
        (box class !=0) are used.
      min_paste_bounding_boxes: A int scalar sets the min number of pasted
        bounding boxes.
      max_paste_bounding_boxes: A int scalar sets the max number of pasted
        bounding boxes.

    """

    def __init__(
        self,
        label_index=None,
        min_paste_bounding_boxes=0,
        max_paste_bounding_boxes=10,
        **kwargs
    ):
        super().__init__(**kwargs)
        if label_index and label_index < 0:
            raise ValueError("label_index must be >=0.")
        if min_paste_bounding_boxes < 0:
            raise ValueError("min_paste_bounding_boxes must be >=0.")
        if max_paste_bounding_boxes < 0:
            raise ValueError("max_paste_bounding_boxes must be >=0.")
        if max_paste_bounding_boxes < min_paste_bounding_boxes:
            raise ValueError(
                "max_paste_bounding_boxes must be >= min_paste_bounding_boxes."
            )

        self._label_index = label_index
        self._min_paste_bounding_boxes = min_paste_bounding_boxes
        self._max_paste_bounding_boxes = max_paste_bounding_boxes

    def get_config(self):
        return {
            "label_index": self._label_index,
            "min_paste_bounding_boxes": self._min_paste_bounding_boxes,
            "max_paste_bounding_boxes": self._max_paste_bounding_boxes,
        }

    def get_random_transformation(
        self,
        point_clouds,
        bounding_boxes,
        object_point_clouds,
        object_bounding_boxes,
        **kwargs
    ):
        del point_clouds
        num_paste_bounding_boxes = random.uniform(
            (),
            minval=self._min_paste_bounding_boxes,
            maxval=self._max_paste_bounding_boxes,
            seed=self._random_generator,
        )
        num_paste_bounding_boxes = tf.cast(
            num_paste_bounding_boxes, dtype=tf.int32
        )
        num_existing_bounding_boxes = tf.shape(bounding_boxes)[1]
        if self._label_index:
            object_mask = (
                object_bounding_boxes[0, :, CENTER_XYZ_DXDYDZ_PHI.CLASS]
                == self._label_index
            )
            object_point_clouds = tf.boolean_mask(
                object_point_clouds, object_mask, axis=1
            )
            object_bounding_boxes = tf.boolean_mask(
                object_bounding_boxes, object_mask, axis=1
            )
        shuffle_index = tf.range(tf.shape(object_point_clouds)[1])
        shuffle_index = tf.random.shuffle(shuffle_index)
        object_point_clouds = tf.gather(
            object_point_clouds, shuffle_index, axis=1
        )
        object_bounding_boxes = tf.gather(
            object_bounding_boxes, shuffle_index, axis=1
        )

        # Load at most 5 times num_paste_bounding_boxes to check overlaps.
        num_compare_bounding_boxes = tf.math.minimum(
            num_paste_bounding_boxes * 5,
            tf.shape(object_point_clouds)[1],
        )

        object_point_clouds = object_point_clouds[
            :, :num_compare_bounding_boxes, :
        ]
        object_bounding_boxes = object_bounding_boxes[
            :, :num_compare_bounding_boxes, :
        ]
        # Use the current frame to check overlap between existing bounding boxes
        # and pasted bounding boxes
        all_bounding_boxes = tf.concat(
            [bounding_boxes, object_bounding_boxes], axis=1
        )[0, :, :7]
        iou = iou_3d(all_bounding_boxes, all_bounding_boxes)
        iou = tf.linalg.band_part(iou, -1, 0)
        iou_sum = tf.reduce_sum(iou[num_existing_bounding_boxes:], axis=1)
        # A non overlapping bounding box has a 1.0 IoU with itself.
        non_overlapping_mask = tf.reshape(iou_sum <= 1, [-1])
        object_point_clouds = tf.boolean_mask(
            object_point_clouds, non_overlapping_mask, axis=1
        )
        object_bounding_boxes = tf.boolean_mask(
            object_bounding_boxes, non_overlapping_mask, axis=1
        )
        object_point_clouds = object_point_clouds[
            :, :num_paste_bounding_boxes, :
        ]
        object_bounding_boxes = object_bounding_boxes[
            :, :num_paste_bounding_boxes, :
        ]
        return {
            OBJECT_POINT_CLOUDS: object_point_clouds,
            OBJECT_BOUNDING_BOXES: object_bounding_boxes,
        }

    def augment_point_clouds_bounding_boxes(
        self, point_clouds, bounding_boxes, transformation, **kwargs
    ):
        additional_object_point_clouds = transformation[OBJECT_POINT_CLOUDS]
        additional_object_bounding_boxes = transformation[OBJECT_BOUNDING_BOXES]
        original_point_clouds_shape = point_clouds.get_shape().as_list()
        original_object_bounding_boxes = bounding_boxes.get_shape().as_list()
        points_in_paste_bounding_boxes = is_within_any_box3d(
            point_clouds[..., :3], additional_object_bounding_boxes[..., :7]
        )
        num_frames = point_clouds.get_shape().as_list()[0]
        point_clouds_list = []
        bounding_boxes_list = []
        for frame_index in range(num_frames):
            # Remove background point clouds that are in object_bounding_boxes.
            existing_point_clouds_mask = ~points_in_paste_bounding_boxes[
                frame_index, :
            ] & tf.math.greater(point_clouds[frame_index, :, 3], 0.0)
            existing_point_clouds = tf.boolean_mask(
                point_clouds[frame_index], existing_point_clouds_mask, axis=0
            )
            paste_point_clouds = tf.boolean_mask(
                additional_object_point_clouds[frame_index],
                tf.math.greater(
                    additional_object_point_clouds[frame_index, :, :, 3], 0.0
                ),
                axis=0,
            )
            point_clouds_list += [
                tf.concat([paste_point_clouds, existing_point_clouds], axis=0)
            ]

            existing_bounding_boxes = tf.boolean_mask(
                bounding_boxes[frame_index],
                tf.math.greater(
                    bounding_boxes[frame_index, :, CENTER_XYZ_DXDYDZ_PHI.CLASS],
                    0.0,
                ),
            )
            paste_bounding_boxes = tf.boolean_mask(
                additional_object_bounding_boxes[frame_index],
                tf.math.greater(
                    additional_object_bounding_boxes[
                        frame_index, :, CENTER_XYZ_DXDYDZ_PHI.CLASS
                    ],
                    0.0,
                ),
                axis=0,
            )
            bounding_boxes_list += [
                tf.concat(
                    [paste_bounding_boxes, existing_bounding_boxes], axis=0
                )
            ]

        point_clouds = tf.ragged.stack(point_clouds_list)
        bounding_boxes = tf.ragged.stack(bounding_boxes_list)

        return (
            point_clouds.to_tensor(shape=original_point_clouds_shape),
            bounding_boxes.to_tensor(shape=original_object_bounding_boxes),
        )

    def _augment(self, inputs):
        result = inputs
        point_clouds = inputs.get(POINT_CLOUDS, None)
        bounding_boxes = inputs.get(BOUNDING_BOXES, None)
        object_point_clouds = inputs.get(OBJECT_POINT_CLOUDS, None)
        object_bounding_boxes = inputs.get(OBJECT_BOUNDING_BOXES, None)
        transformation = self.get_random_transformation(
            point_clouds=point_clouds,
            bounding_boxes=bounding_boxes,
            object_point_clouds=object_point_clouds,
            object_bounding_boxes=object_bounding_boxes,
        )
        point_clouds, bounding_boxes = self.augment_point_clouds_bounding_boxes(
            point_clouds,
            bounding_boxes=bounding_boxes,
            transformation=transformation,
        )
        result.update(
            {POINT_CLOUDS: point_clouds, BOUNDING_BOXES: bounding_boxes}
        )
        return result

    def call(self, inputs):
        # TODO(ianstenbit): Support the model input format.
        point_clouds = inputs[POINT_CLOUDS]
        bounding_boxes = inputs[BOUNDING_BOXES]
        if point_clouds.shape.rank == 3 and bounding_boxes.shape.rank == 3:
            return self._augment(inputs)
        elif point_clouds.shape.rank == 4 and bounding_boxes.shape.rank == 4:
            batch = point_clouds.get_shape().as_list()[0]
            point_clouds_list = []
            bounding_boxes_list = []
            for i in range(batch):
                no_batch_inputs = {
                    POINT_CLOUDS: inputs[POINT_CLOUDS][i],
                    BOUNDING_BOXES: inputs[BOUNDING_BOXES][i],
                    OBJECT_POINT_CLOUDS: inputs[OBJECT_POINT_CLOUDS][i],
                    OBJECT_BOUNDING_BOXES: inputs[OBJECT_BOUNDING_BOXES][i],
                }
                no_batch_result = self._augment(no_batch_inputs)
                point_clouds_list += [
                    no_batch_result[POINT_CLOUDS][tf.newaxis, ...]
                ]
                bounding_boxes_list += [
                    no_batch_result[BOUNDING_BOXES][tf.newaxis, ...]
                ]

            inputs[POINT_CLOUDS] = tf.concat(point_clouds_list, axis=0)
            inputs[BOUNDING_BOXES] = tf.concat(bounding_boxes_list, axis=0)
            return inputs
        else:
            raise ValueError(
                "Point clouds augmentation layers are expecting inputs "
                "point clouds and bounding boxes to be rank 3D (Frame, "
                "Point, Feature) or 4D (Batch, Frame, Point, Feature) "
                "tensors. Got shape: {} and {}".format(
                    point_clouds.shape, bounding_boxes.shape
                )
            )
