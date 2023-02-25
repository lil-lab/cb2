"""Various utilities dealing with hex coordinates mapping onto tensors representing the environment.

See: https://arxiv.org/pdf/1803.02108.pdf

Authors: Alane Suhr and Noriyuki Kojima.
"""

import copy
import math
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import torch
from torch import nn

from follower_bots.constants import TORCH_DEVICE
from follower_bots.models.pose import Pose
from follower_bots.models.rotation import ROTATIONS


def _compute_rotation_matrices() -> Dict[int, np.ndarray]:
    rotation_matrices = dict()
    rot_matrix = np.zeros((3, 3))

    # Counter-clockwise.
    rot_matrix[0, 2] = -1
    rot_matrix[1, 0] = -1
    rot_matrix[2, 1] = -1

    for i, r in enumerate(ROTATIONS):
        num_iters = r.to_radians() // math.radians(60)
        num_iters = int(num_iters)
        num_iters = num_iters % 6

        matrix = np.eye(3)
        for _ in range(num_iters):
            matrix = np.matmul(matrix, rot_matrix)
        rotation_matrices[num_iters] = matrix

    return rotation_matrices


# PRECOMPUTATION: Rotation matrices for the six possible rotations.
# Clockwise 1.047 radians (60') rotation. x is -y, y is -z and z is -x
ROTATION_MATRICES: Dict[int, np.ndarray] = _compute_rotation_matrices()


@dataclass
class AxialMapBounds:
    """Stores bounds where a neutrally-translated map was stored after translated in a global axial map."""

    u_min: torch.Tensor
    u_max: torch.Tensor
    v_min: torch.Tensor
    v_max: torch.Tensor


def _get_batch_index_tensor(batch_size: int, env_height: int, env_width: int):
    index_array = torch.tensor([i for i in range(batch_size)], device=TORCH_DEVICE)
    index_tensor = index_array.repeat(env_height, env_width, 1)
    return index_tensor.permute(2, 0, 1).long()


def _get_offset_index_tensor(env_height: int, env_width: int) -> torch.Tensor:
    # Create a H x W x 2 matrix
    q_col_indices = torch.linspace(0, env_width - 1, env_width, device=TORCH_DEVICE)
    r_row_indices = torch.linspace(0, env_height - 1, env_height, device=TORCH_DEVICE)
    q_cols, r_rows = torch.meshgrid([q_col_indices, r_row_indices])
    return torch.stack((q_cols, r_rows)).permute(1, 2, 0).long()


def _get_batched_offset_index_tensor(
    batch_size: int, env_height: int, env_width: int
) -> torch.Tensor:
    # Batch size could include the channel dimension.

    index_tensor = _get_offset_index_tensor(env_height, env_width)

    # Stack it
    return index_tensor.unsqueeze(0).repeat(batch_size, 1, 1, 1)


def _get_axial_index_tensor(
    offset_index_tensor: torch.Tensor, add_u: int = 0, add_v: int = 0
) -> torch.Tensor:
    # The offset index tensor is assumed to be of size B x H x W x 2, where B is the batch size (or batch size x
    # channel dimension).
    if offset_index_tensor.size(3) != 2:
        raise ValueError(
            "Offset index tensor should have size B x H x W x 2: %s"
            % offset_index_tensor.size()
        )

    # v is just the same as r.
    v = offset_index_tensor[:, :, :, 1]

    # u is the axis index. It is q - r // 2.
    u = offset_index_tensor[:, :, :, 0] - v // 2

    # Add the offsets.
    u += add_u
    v += add_v

    if (u < 0).any():
        print(u)
        raise ValueError(
            "Axial index tensor has u negative values. Perhaps you need to add u."
        )
    if (v < 0).any():
        print(v)
        raise ValueError(
            "Axial index tensor has v negative values. Perhaps you need to add v."
        )

    return torch.stack((u, v)).permute(1, 2, 3, 0).long()


def _get_cube_index_tensor(axial_index_tensor: torch.Tensor) -> torch.Tensor:
    # The offset index tensor is assumed to be of size B x H x W x 2, where B is the batch size (or batch size x
    # channel dimension).
    if axial_index_tensor.size(3) != 2:
        raise ValueError(
            "Axial index tensor should have size B x H x W x 2: %s"
            % axial_index_tensor.size()
        )

    u = axial_index_tensor[:, :, :, 0]
    v = axial_index_tensor[:, :, :, 1]

    # x is just the same as v.
    x = v

    # y is -(u + v).
    y = -(u + v)

    # z is just the same as u.
    z = u

    return torch.stack((x, y, z)).permute(1, 2, 3, 0).long()


def _get_offset_axial_indices(
    batch_size: int, height: int, width: int, additional_size: int
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    offset_index_tensor = _get_batched_offset_index_tensor(batch_size, height, width)
    axial_index_tensor = _get_axial_index_tensor(
        offset_index_tensor, add_u=additional_size
    )

    qs = offset_index_tensor[:, :, :, 0].flatten()
    rs = offset_index_tensor[:, :, :, 1].flatten()
    us = axial_index_tensor[:, :, :, 0].flatten()
    vs = axial_index_tensor[:, :, :, 1].flatten()
    return qs, rs, us, vs


def _get_axial_cube_index_tensors(
    batch_size: int, height: int, width: int, additional_size: int
) -> Tuple[torch.Tensor, torch.Tensor]:

    # axial coordinate is the pixel coordinate on the tensor - center
    axial_index_tensor = _get_batched_offset_index_tensor(batch_size, height, width)
    axial_index_tensor -= additional_size
    cube_index_tensor = _get_cube_index_tensor(axial_index_tensor)

    return axial_index_tensor, cube_index_tensor


def _get_cube_rotation_matrix(rots):
    assert (
        len(rots.size()) == 1
    ), f"Rotation must be a one-dimensional tensor: {rots.size()}"

    cube_rot_matrix = torch.zeros((rots.size(0), 3, 3), device=TORCH_DEVICE)

    for i, r in enumerate(rots):
        num_iters = r // math.radians(60)
        num_iters = num_iters.long()
        num_iters = num_iters % 6

        cube_rot_matrix[i, :, :] = torch.tensor(
            ROTATION_MATRICES[int(num_iters.detach().item())]
        )

    return cube_rot_matrix


def _rotate_cube_indices(cube_index_tensor: torch.Tensor, rots: torch.Tensor):
    batch_size, height, width, channels = cube_index_tensor.size()
    assert channels == 3, "Tensor does not have 3 channels: %s" % channels

    # Calculate rotation matrices for each batch
    cube_rotation_matrix = _get_cube_rotation_matrix(rots)
    cube_index_tensor = cube_index_tensor.permute(0, 3, 1, 2)
    cube_index_tensor = cube_index_tensor.view(batch_size, channels, height * width)
    cube_index_tensor = cube_index_tensor.float()

    cube_index_tensor_rot = torch.bmm(cube_rotation_matrix, cube_index_tensor)
    cube_index_tensor_rot = cube_index_tensor_rot.view(
        batch_size, channels, height, width
    )
    cube_index_tensor_rot = cube_index_tensor_rot.permute(0, 2, 3, 1)
    cube_index_tensor_rot = cube_index_tensor_rot.long()
    return cube_index_tensor_rot


class OffsetToAxialConverter(nn.Module):
    def __init__(self, env_edge_size: int):
        super(OffsetToAxialConverter, self).__init__()
        self._edge_size = env_edge_size
        additional_size = (env_edge_size - 1) // 2
        self._axial_size = env_edge_size + additional_size
        qs, rs, us, vs = _get_offset_axial_indices(
            1, env_edge_size, env_edge_size, additional_size
        )
        self._unbatched_qs = nn.Parameter(qs, requires_grad=False)
        self._unbatched_rs = nn.Parameter(rs, requires_grad=False)
        self._unbatched_us = nn.Parameter(us, requires_grad=False)
        self._unbatched_vs = nn.Parameter(vs, requires_grad=False)

    def forward(self, input_tensor: torch.Tensor):
        batch_size, num_channels, env_height, env_width = input_tensor.size()
        assert env_width == env_height, "Tensor is not square: %s x %s" % (
            env_width,
            env_height,
        )

        axial_tensor = torch.zeros(
            (batch_size * num_channels, self._axial_size, env_width),
            device=TORCH_DEVICE,
        )

        # Need to batch the indices
        batched_qs = self._unbatched_qs.detach().repeat(
            batch_size * num_channels, 1, 1, 1
        )
        batched_us = self._unbatched_us.detach().repeat(
            batch_size * num_channels, 1, 1, 1
        )
        batched_rs = self._unbatched_rs.detach().repeat(
            batch_size * num_channels, 1, 1, 1
        )
        batched_vs = self._unbatched_vs.detach().repeat(
            batch_size * num_channels, 1, 1, 1
        )
        batched_bs = (
            _get_batch_index_tensor(batch_size * num_channels, batched_qs.shape[-1], 1)
            .squeeze(-1)
            .unsqueeze(1)
            .unsqueeze(1)
        )

        indexed_input = input_tensor.view(
            batch_size * num_channels, env_height, env_width
        )[batched_bs, batched_qs, batched_rs]

        axial_tensor[batched_bs, batched_us, batched_vs] = indexed_input

        return axial_tensor.view(batch_size, num_channels, self._axial_size, env_width)


class AxialTranslatorRotator(nn.Module):
    def __init__(self, env_edge_size: int, translate: bool = True):
        super(AxialTranslatorRotator, self).__init__()
        self._edge_size = env_edge_size
        self._additional_size = (env_edge_size - 1) // 2
        self._axial_size = env_edge_size + self._additional_size
        self._translate = translate

        # Create a H x W x 2 matrix
        u_indices = torch.linspace(0, env_edge_size - 1, env_edge_size)
        v_indices = torch.linspace(0, self._axial_size - 1, self._axial_size)
        us, vs = torch.meshgrid([u_indices, v_indices])
        unit_items = torch.ones(us.size())
        self._axial_indices = nn.Parameter(
            torch.stack((vs, us, unit_items)).permute(1, 2, 0).long(),
            requires_grad=False,
        )

        self._pos_mask_cache = dict()

    def resulting_width(self) -> int:
        return self._axial_size * 2 + 1

    def translate(
        self, axial_tensor: torch.Tensor, offset: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, AxialMapBounds]:
        """Pads an input axial tensor to a square such that the position (0, 0) is in the center of the new square
        tensor."""
        batch_size, num_channels, axial_height, axial_width = axial_tensor.size()

        if self._translate:
            placeholder = torch.zeros(
                (num_channels, self._axial_size * 2 + 1, self._axial_size * 2 + 1),
                device=TORCH_DEVICE,
            )

            placeholder = placeholder.repeat(batch_size, 1, 1)
        else:
            placeholder = torch.zeros(
                (batch_size, num_channels, axial_height * 2 + 1, axial_height * 2 + 1),
                device=TORCH_DEVICE,
            )

        pose_batch_size, pose_coord_size = offset.size()
        if pose_batch_size != batch_size:
            raise ValueError(
                "Batch size of pose and input tensor are not the same: %s vs. %s"
                % (pose_batch_size, batch_size)
            )
        if pose_coord_size != 2:
            raise ValueError("Pose must have 2 coordinates; has %s" % pose_coord_size)

        # Transformation matrix. Size: B x 3 x 3.
        additional_size = axial_height - axial_width
        qs = offset[:, 0]
        rs = offset[:, 1]
        us = qs - rs // 2

        if self._translate:
            direction_vector = torch.stack((us, rs)).permute(1, 0).contiguous()

            transform_matrix = np.eye(3)
            batched_transform_matrix = np.tile(transform_matrix, [batch_size, 1, 1])
            batched_transform_matrix[:, 0:2, 2] = (
                -direction_vector[:, 0:2].detach().cpu()
            )

            # (Repeated) indices of the input tensor. Size: B x E x E' x 3.
            expanded_indices = self._axial_indices.unsqueeze(0).repeat(
                batch_size, 1, 1, 1
            )

            # Flatten the indices across locations.
            flattened_indices = (
                expanded_indices.view(batch_size, -1, 3).permute(0, 2, 1).contiguous()
            )

            # The transformed indices are size B x EE' x 2, and represent the target indices of the transform.
            # However, this will include negative values. So values must be added to the u and v to represent the center
            # position. The final dimension is discarded.
            transformed_indices = (
                torch.matmul(
                    torch.tensor(batched_transform_matrix, device=TORCH_DEVICE).float(),
                    flattened_indices.float(),
                )
                .permute(0, 2, 1)
                .contiguous()[:, :, :-1]
                .long()
            )
            # B x EE'
            assigned_us = (
                transformed_indices[:, :, 0] + axial_height - self._additional_size
            )
            assigned_vs = transformed_indices[:, :, 1] + axial_height

            # Expand the tensors to include the channels: these should be size BC x EE'.
            assigned_us = (
                assigned_us.unsqueeze(1)
                .repeat(1, num_channels, 1)
                .view(batch_size * num_channels, -1)
            )
            assigned_vs = (
                assigned_vs.unsqueeze(1)
                .repeat(1, num_channels, 1)
                .view(batch_size * num_channels, -1)
            )
            assigned_bs = _get_batch_index_tensor(
                batch_size * num_channels, assigned_us.shape[1], 1
            ).squeeze(2)

            # Perform the assignment
            original_indices = expanded_indices[:, :, :, :-1].view(batch_size, -1, 2)
            original_indices = (
                original_indices.unsqueeze(1)
                .repeat(1, num_channels, 1, 1)
                .view(batch_size * num_channels, -1, 2)
            )

            original_us = original_indices[:, :, 0]
            original_vs = original_indices[:, :, 1]
            original_bs = _get_batch_index_tensor(
                batch_size * num_channels, original_indices.shape[1], 1
            ).squeeze(2)

            indexed_input = axial_tensor.view(
                batch_size * num_channels, axial_height, axial_width
            )[original_bs, original_us, original_vs]
            placeholder[assigned_bs, assigned_us, assigned_vs] = indexed_input
            placeholder = placeholder.view(
                batch_size, num_channels, axial_height * 2 + 1, axial_height * 2 + 1
            )

        # Need to get the us, vs for the offset. Offset is in offset coordinates, not axial coordinates.
        # Pose has 0th index of q, and 1th index of r.

        u_min = (axial_height - additional_size - us).long()
        v_min = (axial_height - rs).long()
        u_max = u_min + axial_height
        v_max = v_min + axial_width

        if not self._translate:
            for b in range(batch_size):
                placeholder[
                    b, :, u_min[b] : u_max[b], v_min[b] : v_max[b]
                ] = axial_tensor[b, :, :, :]

        # Create a mask for the non-padded region of axil tensor and move the mask to the coordinates of the placeholder
        # If you don't create a mask, some of pixels will be outside of the placeholder after rotation
        mask = torch.zeros(
            (batch_size, axial_height * 2 + 1, axial_height * 2 + 1)
        ).bool()

        if self._translate:
            _, _, us, vs = _get_offset_axial_indices(
                batch_size, axial_width, axial_width, additional_size
            )
            for b in range(batch_size):
                # Caches mask for this offset index.
                pos = tuple(offset[b].tolist())
                if pos in self._pos_mask_cache:
                    mask[b] = torch.tensor(
                        copy.copy(self._pos_mask_cache[pos]), device=TORCH_DEVICE
                    )
                else:
                    m_us, m_vs = us + u_min[b], vs + v_min[b]
                    mask[b, m_us, m_vs] = 1

                    self._pos_mask_cache[pos] = mask[b].numpy()

                mask = mask.bool()

        return placeholder, mask, AxialMapBounds(u_min, u_max, v_min, v_max)

    def forward(
        self, axial_tensor: torch.Tensor, target_poses: Pose
    ) -> Tuple[torch.Tensor, AxialMapBounds]:
        # Input should be an axial tensor (not square)
        # B x C x H x W
        # Should return a square tensor
        # Should return B x C x H' x W' where H' = W' = some function of W
        translated_tensor, mask, axial_map_bounds = self.translate(
            axial_tensor, offset=target_poses.position
        )

        if not self._translate:
            center = translated_tensor.shape[-1] // 2
            slack = axial_tensor.shape[-1] // 2
            offset = center - slack
            end = center + slack + 1
            mask[:, offset:end, offset:end] = True

        placeholder = torch.zeros(translated_tensor.shape, device=TORCH_DEVICE)

        center = translated_tensor.size(2) // 2
        batch_size, _, height, width = translated_tensor.shape

        axial_index_tensor, cube_index_tensor = _get_axial_cube_index_tensors(
            batch_size, height, width, additional_size=center
        )

        # Rotate tensors clockwise by angles specified by target_poses.orientation
        cube_index_tensor_rot = _rotate_cube_indices(
            cube_index_tensor, rots=target_poses.orientation
        )

        bs = _get_batch_index_tensor(batch_size, height, width)
        us, vs = (
            axial_index_tensor[:, :, :, 0] + center,
            axial_index_tensor[:, :, :, 1] + center,
        )
        us_rot, vs_rot = (
            cube_index_tensor_rot[:, :, :, 2] + center,
            cube_index_tensor_rot[:, :, :, 0] + center,
        )

        bs, us, vs, us_rot, vs_rot = (
            bs[mask],
            us[mask],
            vs[mask],
            us_rot[mask],
            vs_rot[mask],
        )
        indexed_padded = translated_tensor[bs, :, us, vs]
        placeholder[bs, :, us_rot, vs_rot] = indexed_padded

        return placeholder, axial_map_bounds
