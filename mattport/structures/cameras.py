"""
Camera Models
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

import torch
from torch.nn.functional import normalize
from torchtyping import TensorType

from mattport.structures.rays import CameraRayBundle, RayBundle


@dataclass
class Rays:
    """Camera rays. Can be arbitrary dimension"""

    origin: TensorType[..., 3]
    direction: TensorType[..., 3]


class Camera:
    """Base Camera. Intended to be subclassed"""

    def __init__(self, camera_to_world: Optional[TensorType[3, 4]] = torch.eye(4)[:3]) -> None:
        self.camera_to_world = camera_to_world

    @abstractmethod
    def get_num_intrinsics_params(self) -> int:
        """_summary_

        Returns:
            int: _description_
        """
        return

    @abstractmethod
    def get_intrinsics(self) -> torch.Tensor:
        """_summary_

        Returns:
            torch.Tensor: _description_
        """
        return

    def get_camera_to_world(self) -> TensorType[3, 4]:
        """_summary_

        Returns:
            TensorType[3, 4]: _description_
        """
        return self.camera_to_world

    @abstractmethod
    def get_image_height(self):
        """_summary_"""
        return

    @abstractmethod
    def get_image_width(self):
        """_summary_"""
        return

    def get_image_coords(self, pixel_offset: float = 0.5) -> TensorType["image_height", "image_width", 2]:
        """_summary_

        Returns:
            _type_: _description_
        """
        image_height = self.get_image_height()
        image_width = self.get_image_width()
        image_coords = torch.meshgrid(torch.arange(image_height), torch.arange(image_width), indexing="ij")
        image_coords = torch.stack(image_coords, dim=-1) + pixel_offset  # stored as (y, x) coordinates
        return image_coords

    @classmethod
    @abstractmethod
    def generate_rays(
        cls,
        intrinsics: TensorType["num_rays", "num_intrinsics_params"],
        camera_to_world: TensorType["num_rays", 3, 4],
        coords: TensorType["image_height", "image_width", 2],
    ) -> RayBundle:
        """_summary_

        Args:
            intrinsics (TensorType[&quot;num_rays&quot;, &quot;num_intrinsics_params&quot;]): _description_
            camera_to_world (TensorType[&quot;num_rays&quot;, 3, 4]): _description_
            coords (TensorType[&quot;image_height&quot;, &quot;image_width&quot;, 2]): _description_

        Returns:
            RayBundle: _description_
        """
        return

    def generate_camera_rays(self) -> CameraRayBundle:
        """Generate rays for the camera.

        Returns:
            Rays: Camera rays of shape [height, width]
        """
        image_height = self.get_image_height()
        image_width = self.get_image_width()
        num_rays = image_height * image_width
        intrinsics = self.get_intrinsics().unsqueeze(0).repeat(num_rays, 1)  # (num_rays, num_intrinsics_params)
        camera_to_world = self.camera_to_world.unsqueeze(0).repeat(num_rays, 1, 1)  # (num_rays, 3, 4)
        coords = self.get_image_coords().view(num_rays, 2)  # (num_rays, 2)
        ray_bundle = self.generate_rays(intrinsics, camera_to_world, coords)
        camera_ray_bundle = ray_bundle.to_camera_ray_bundle(image_height, image_width)
        return camera_ray_bundle


class PinholeCamera(Camera):
    """Pinhole camera model."""

    def __init__(
        self, cx: float, cy: float, fx: float, fy: float, camera_to_world: Optional[TensorType[3, 4]] = torch.eye(4)[:3]
    ):
        super().__init__(camera_to_world)
        self.cx = cx
        self.cy = cy
        self.fx = fx
        self.fy = fy

    def get_num_intrinsics_params(self):
        return 4

    def get_image_width(self):
        return int(self.cx * 2.0)

    def get_image_height(self):
        return int(self.cy * 2.0)

    def get_intrinsics_matrix(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        K = torch.tensor(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0, 0, 1.0]],
            dtype=torch.float32,
        )
        return K

    def get_intrinsics(self) -> torch.Tensor:
        return torch.tensor([self.cx, self.cy, self.fx, self.fy])

    @classmethod
    def fx_index(cls):
        """TODO(ethan): redo this in a better way.
        Ideally we can dynamically grab the focal length parameters depending on
        Simple vs. not Simple Pinhole Model.

        Returns:
            _type_: _description_
        """
        return 2

    @classmethod
    def fy_index(cls):
        """_summary_

        Returns:
            _type_: _description_
        """
        return 3

    @classmethod
    def generate_rays(
        cls,
        intrinsics: TensorType["num_rays", "num_intrinsics_params"],
        camera_to_world: TensorType["num_rays", 3, 4],
        coords: TensorType["num_rays", 2],
    ) -> RayBundle:

        cx = intrinsics[:, 0:1]
        cy = intrinsics[:, 1:2]
        fx = intrinsics[:, cls.fx_index() : cls.fx_index() + 1]
        fy = intrinsics[:, cls.fy_index() : cls.fy_index() + 1]
        y = coords[:, 0:1]  # (num_rays, 1)
        x = coords[:, 1:2]  # (num_rays, 1)
        original_directions = torch.cat([(x - cx) / fx, -(y - cy) / fy, -torch.ones_like(x)], -1)  # (num_rays, 3)
        rotation = camera_to_world[:, :3, :3]  # (num_rays, 3, 3)
        directions = torch.sum(
            original_directions[:, None, :] * rotation, dim=-1
        )  # (num_rays, 1, 3) * (num_rays, 3, 3) -> (num_rays, 3)
        directions = normalize(directions, dim=-1)
        origins = camera_to_world[:, :3, 3]  # (num_rays, 3)
        return RayBundle(origins=origins, directions=directions)


class SimplePinholeCamera(PinholeCamera):
    """Simple Pinhole Camera model."""

    def __init__(self, cx: float, cy: float, f: float, camera_to_world: Optional[TensorType[3, 4]] = torch.eye(4)[:3]):
        super().__init__(cx, cy, f, f, camera_to_world)

    @classmethod
    def fx_index(cls):
        return 2

    @classmethod
    def fy_index(cls):
        return 2


def get_camera_model(num_intrinsics_params):
    """Returns the camera model given the specified number of intrinsics parameters.

    Args:
        num_intrinsics_params (_type_): _description_

    Returns:
        _type_: _description_
    """
    if num_intrinsics_params == 3:
        return SimplePinholeCamera
    if num_intrinsics_params == 4:
        return PinholeCamera
    raise NotImplementedError
