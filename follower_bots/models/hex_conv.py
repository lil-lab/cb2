"""Utilities for hex convolutions.

Based on HexaConv (Hoogeboom et al. 2018, https://arxiv.org/pdf/1803.02108.pdf)
Authors: Alane Suhr and Noriyuki Kojima
"""
import math
from typing import Tuple

import numpy as np
import torch
from torch import nn
from torch.nn import functional

from follower_bots.constants import EDGE_WIDTH, FOG_END, FOV, UNITY_COORDS_SCALE


def _get_hex_conv_mask(kernel_size: int) -> torch.Tensor:
    # This is a mask on the filter which zeros out the corners of the convolution.
    # See https://arxiv.org/pdf/1803.02108.pdf, Figure 4a.
    mask = torch.ones((kernel_size, kernel_size))
    cutoff_amount = (kernel_size - 1) // 2
    for i in range(cutoff_amount):
        for j in range(cutoff_amount - i):
            mask[i][j] = 0.0
            mask[kernel_size - 1 - i][kernel_size - 1 - j] = 0.0
    return mask


def _get_crop_mask(kernel_size: int, fov: float):
    # This is a mask that filters out: (1) values not within a distance of
    # xxx from the center and (2) values not within the
    # agent's FOV. The crop mask must be square with odd edges.

    mask = torch.ones((kernel_size, kernel_size))
    special_cases = [
        ((kernel_size - 1) // 2 + 1, (kernel_size - 1) // 2 - 1),  # -60 degrees
        ((kernel_size - 1) // 2, (kernel_size - 1) // 2 + 1),
    ]  # 60 degrees
    center_coord = ((kernel_size - 1) // 2, (kernel_size - 1) // 2)

    for u in range(kernel_size):
        for v in range(kernel_size):
            visible = coordinate_is_visible(u, v, special_cases, center_coord, fov)
            mask[u, v] = 1.0 if visible else 0.0

    return mask


def coordinate_is_visible(u, v, special_cases, center_coord, fov):
    # Treat the tiles immediately beside the agent as special cases
    if (u, v) in special_cases or (u, v) == center_coord:
        return True

    # First filter based on (cartesian) distance
    view_depth = FOG_END / UNITY_COORDS_SCALE + 0.5
    if get_distance((u, v), center_coord) > view_depth:
        return False

    degrees_to = get_degrees(center_coord, (u, v))
    left = (-fov / 2) % 360
    right = (fov / 2) % 360
    if left < right:
        return left <= degrees_to <= right
    else:
        return left <= degrees_to or degrees_to <= right


def get_cartesian(coords):
    basis_matrix = np.array([[1, 0.5], [0, np.sqrt(3) / 2]])
    return np.matmul(basis_matrix, np.array(coords))


def get_distance(target, center):
    diff = get_cartesian(center) - get_cartesian(target)
    distance = np.sqrt(np.sum(diff**2))
    return distance


def get_degrees(center, target):
    center = get_cartesian(center)
    target = get_cartesian(target)
    diff = target - center
    return math.degrees(math.atan2(diff[1], diff[0])) % 360


class HexConv(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        bias: bool = True,
    ):
        super(HexConv, self).__init__()

        if kernel_size % 2 != 1:
            raise ValueError("Kernel size must be odd for Hex Conv: %s" % kernel_size)

        self.register_parameter(
            name="_weight",
            param=torch.nn.Parameter(
                torch.zeros(out_channels, in_channels, kernel_size, kernel_size),
                requires_grad=True,
            ),
        )
        nn.init.kaiming_normal_(self._weight)
        if bias:
            self.register_parameter(
                name="_bias",
                param=torch.nn.Parameter(torch.zeros(out_channels), requires_grad=True),
            )

            nn.init.constant_(self._bias, 0)
        else:
            self._bias = None

        self._stride = stride
        self._kernel_size = kernel_size
        self._in_channels = in_channels
        self._out_channels = out_channels
        self._padding = padding
        self._mask = nn.Parameter(_get_hex_conv_mask(kernel_size), requires_grad=False)

    def extra_repr(self):
        return "input_channels={}, output_channels={}, kernel_size={}, stride={}, padding={}, bias={}".format(
            self._in_channels,
            self._out_channels,
            self._kernel_size,
            self._stride,
            self._padding,
            self._bias is not None,
        )

    def forward(self, input_tensor: torch.Tensor):
        """Input must be in axial coordinates."""
        masked_filter = self._weight * self._mask.detach()
        return functional.conv2d(
            input_tensor,
            masked_filter,
            bias=self._bias,
            stride=self._stride,
            padding=self._padding,
        )


class HexCrop(nn.Module):
    def __init__(self, crop_size: int, env_size: int = EDGE_WIDTH, fov: float = FOV):
        """Crops an N x N region around the center of a tensor, where N = crop size."""
        super(HexCrop, self).__init__()
        if crop_size % 2 != 1:
            raise ValueError("Crop size must be odd for Hex Crop: %s" % crop_size)
        self._crop_mask = nn.Parameter(
            _get_crop_mask(crop_size, fov), requires_grad=False
        )
        self._crop_size = crop_size
        self._environment_size = env_size

    def forward(
        self, input_tensor: torch.Tensor, center_positions: torch.Tensor, mask: bool
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Crops a square portion around the center of the input tensor, masking out values not in the neighborhood
        of the crop value. Input and center positions must be in axial coordinates."""
        batch_size, num_channels, height, width = input_tensor.size()

        crop_center = (self._crop_size - 1) // 2  # Need to pad the input
        padded_state = torch.nn.functional.pad(
            input_tensor, [crop_center, crop_center, crop_center, crop_center]
        )  # Convert the position to axial coordinates

        u_pos = center_positions[:, 0]
        v_pos = center_positions[:, 1]

        us = [u_pos + (slack - crop_center) for slack in range(self._crop_size)]
        us = torch.stack(us, 0).unsqueeze(1)
        us = us.repeat(1, self._crop_size, 1).long()
        us += crop_center  # Because of padding
        vs = [v_pos + (slack - crop_center) for slack in range(self._crop_size)]
        vs = torch.stack(vs, 0).unsqueeze(0)
        vs = vs.repeat(self._crop_size, 1, 1).long()
        vs += crop_center  # Because of padding

        batch_indices = (
            torch.tensor([i for i in range(batch_size)])
            .long()
            .unsqueeze(0)
            .unsqueeze(0)
        )
        batch_indices = batch_indices.repeat(self._crop_size, self._crop_size, 1)
        cropped_square = padded_state[batch_indices, :, us, vs]
        cropped_square = cropped_square.permute(2, 3, 0, 1)

        # Mask
        if mask:
            cropped_square *= self._crop_mask.detach()
        return cropped_square, self._crop_mask.detach()
