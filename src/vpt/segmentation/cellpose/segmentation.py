import warnings
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from vpt.run_segmentation_on_tile.image import ImageSet
from vpt.segmentation.entity import Entity
from vpt.segmentation.utils.polygon_utils import generate_polygons_from_mask
from vpt.segmentation.utils.seg_result import SegmentationResult


@dataclass(frozen=True)
class CellposeSegProperties:
    model: str
    model_dimensions: str
    version: str
    custom_weights: Optional[str] = None


@dataclass(frozen=True)
class CellposeSegParameters:
    nuclear_channel: str
    entity_fill_channel: str
    diameter: int
    flow_threshold: float
    mask_threshold: float
    dilation: float
    minimum_mask_size: int
    sharpen_radius: float
    take_max: bool


def cellpose_polygons_masks(images: ImageSet, segmentation_properties: Dict,
                            segmentation_parameters: Dict) -> np.ndarray:
    warnings.filterwarnings('ignore', message='.*the `scipy.ndimage.filters` namespace is deprecated.*')
    from cellpose import models

    properties = CellposeSegProperties(**segmentation_properties)
    parameters = CellposeSegParameters(**segmentation_parameters)

    is_valid_channels = parameters.nuclear_channel and parameters.entity_fill_channel
    image = images.as_stack([parameters.nuclear_channel, parameters.entity_fill_channel]) \
        if is_valid_channels else images.as_stack()

    empty_z_levels = set()
    for z_i, z_plane in enumerate(image):
        for channel_i in range(z_plane.shape[-1]):
            if z_plane[..., channel_i].std() < 0.1:
                empty_z_levels.add(z_i)
    if len(empty_z_levels) == image.shape[0]:
        return np.zeros((image.shape[0],) + image.shape[1:-1])

    if properties.custom_weights:
        model = models.CellposeModel(gpu=False, pretrained_model=properties.custom_weights, net_avg=False)
    else:
        model = models.Cellpose(gpu=False, model_type=properties.model, net_avg=False)

    to_segment_z = list(set(range(image.shape[0])).difference(empty_z_levels))
    if parameters.take_max:
        image_seg = image[to_segment_z,...].max(axis=0)
    else:
        image_seg = image[to_segment_z,...]
    mask = model.eval(
        image_seg,
        z_axis=0 if not parameters.take_max else None,
        channel_axis=len(image_seg.shape) - 1,
        diameter=parameters.diameter,
        flow_threshold=parameters.flow_threshold,
        cellprob_threshold=parameters.mask_threshold,
        normalize={"normalize":True, 
                   "sharpen_radius":parameters.sharpen_radius},
        resample=False,
        min_size=parameters.minimum_mask_size,
        tile=True,
        do_3D=(properties.model_dimensions == '3D')
    )[0]
    if parameters.dilation > 0.:
        from cellpose.utils import dilate_masks
        mask = dilate_masks(mask.astype(int), int(parameters.dilation))
    if not parameters.take_max:
        mask = mask.reshape((len(to_segment_z),) + image.shape[1:-1])
        for i in empty_z_levels:
            mask = np.insert(mask, i, np.zeros(image.shape[1:-1]), axis=0)
    else:
        mask = np.repeat(mask[np.newaxis,...], image.shape[0], axis=0)
    return mask


def run_segmentation(images: ImageSet, segmentation_properties: Dict, segmentation_parameters: Dict,
                     polygon_parameters: Dict, result: Entity) -> SegmentationResult:

    masks = cellpose_polygons_masks(images, segmentation_properties, segmentation_parameters)
    CellposeSegProperties(**segmentation_properties)
    # todo: different entity
    return generate_polygons_from_mask(masks, polygon_parameters)