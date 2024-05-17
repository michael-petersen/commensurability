"""
This module defines abstract base classes for commensurability analysis
of a galactic potential's phase space. The "dimensionality" associated
with the class corresponds with the dimensionality of the relevant orbits.

This module also defines user-facing analysis classes for 2D and 3D
commensurability analysis using the tessellation subpackage.
"""

from __future__ import annotations

import inspect
import warnings
from abc import abstractmethod
from math import prod
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union

import astropy.coordinates as c
import astropy.units as u
import h5py
import numpy as np
import pidgey
from more_itertools import chunked
from pidgey import AgamaBackend, GalaBackend, GalpyBackend, get_backend_from
from pidgey.base import Backend
from tqdm import tqdm

from .evaluation import Evaluation
from .interactive import InteractivePlot2D, InteractivePlot3D, InteractivePlotBase
from .utils import collapse_coords, make_quantity


class AnalysisBase:
    """
    Base class for analyzing commensurate orbits within galactic potentials.

    This class provides methods for evaluating orbits, constructing images of
    phase space slices, and saving/loading analysis data.
    """

    @staticmethod
    @abstractmethod
    def evaluate(orbit: c.SkyCoord) -> Evaluation:
        """
        Evaluate an orbit and return an evaluation object.

        Args:
            orbit (c.SkyCoord): Integrated orbit coordinates.

        Returns:
            Evaluation: Evaluation object containing analysis results.
        """
        pass

    def __init__(
        self,
        ic_function: Callable[..., c.SkyCoord],
        values: Mapping[str, Sequence[float]],
        /,
        potential_function: Callable[[], Any],
        dt: Union[float, np.ndarray, u.Quantity],
        steps: Union[int, np.ndarray],
        *,
        pattern_speed: Union[float, u.Quantity] = 0.0,
        backend: Optional[Union[str, Backend]] = None,
        chunksize: int = 1,
        progressbar: bool = True,
        _blank_image: bool = False,
    ) -> None:
        """
        Initialize AnalysisBase instance.

        Args:
            ic_function (Callable[..., c.SkyCoord]): Function to generate initial conditions for orbits.
            values (Mapping[str, Sequence[float]]): Values to pass into ic_function.
            potential_function (Callable[[], Any]): Function to generate the potential for orbit integration.
            dt (Union[float, np.ndarray, u.Quantity]): Time step for orbit integration.
            steps (Union[int, np.ndarray]): Number of integration steps.
            pattern_speed (Union[float, u.Quantity], optional): Pattern speed for orbit integration (default 0.0).
            backend (Optional[Union[str, Backend]], optional): Backend for orbit computation.
            chunksize (int, optional): Chunk size for image construction (default 1).
            progressbar (bool, optional): Whether to show progress bar during image construction (default True).
        """
        self.ic_function = ic_function
        argspec = inspect.getfullargspec(ic_function)
        self.axis_names = argspec.args
        self.values = values
        if len(self.values) != len(self.axis_names) or not all(
            name in self.axis_names for name in self.values
        ):
            raise ValueError("values and ic_function signature do not correspond")
        self.shape = tuple(len(self.values[name]) for name in self.axis_names)
        self.size = prod(self.shape)

        self.potential_function = potential_function
        self.potential = potential_function()
        self.dt = make_quantity(dt, u.Gyr)
        if self.dt.value <= 0:
            raise ValueError("dt must be greater than 0")
        self.steps = steps
        if self.steps <= 0:
            raise ValueError("steps must be greater than 0")

        self.pattern_speed = make_quantity(pattern_speed, u.km / u.s / u.kpc)
        if isinstance(backend, str):
            if backend == "agama":
                backend = AgamaBackend()
            elif backend == "gala":
                backend = GalaBackend()
            elif backend == "galpy":
                backend = GalpyBackend()
            else:
                raise ValueError(f"Unrecognized backend: {backend}")
        self.backend = backend or get_backend_from(self.potential)
        if not self.backend:
            raise TypeError(f"Unrecognized potential: {self.potential}")

        if chunksize <= 0:
            raise ValueError("chunksize must be greater than 0")
        if chunksize >= self.size:
            raise ValueError("chunksize must be less than total number of starting coordinates")

        self.image = np.zeros(self.shape)
        if not _blank_image:
            self._construct_image(chunksize, progressbar)

    def _construct_image(self, chunksize: int = 1, progressbar: bool = True):
        """
        Construct an image of a slice of phase space by integrating orbits and evaluating them.

        Args:
            chunksize (int, optional): Chunk size for batching evaluation calls (default 1).
            progressbar (bool, optional): Whether to show progress bar during construction (default True).
        """
        for pixels in tqdm(
            chunked(np.ndindex(self.shape), chunksize),
            desc=f"with {chunksize=}",
            total=self.size // chunksize,
            disable=not progressbar,
        ):
            coords = []
            for pixel in pixels:
                params = [self.values[ax][i] for i, ax in zip(pixel, self.axis_names)]
                coord = self.ic_function(*params)
                coords.append(coord)
            coords = collapse_coords(coords)

            orbits = self.backend.compute_orbit(
                coords,
                self.potential,
                self.dt,
                self.steps,
                pattern_speed=self.pattern_speed,
            )
            for pixel, orbit in tqdm(
                zip(pixels, orbits),
                desc="commensurability evaluation",
                total=chunksize,
                disable=not progressbar,
                leave=False,
            ):
                self.image[pixel] = self.evaluate(orbit).measure

    def save(self, path: Any):
        """
        Save the analysis data to an HDF5 file.

        Args:
            path: Path to the HDF5 file.
        """
        path = Path(path)
        if not path.parent.exists():
            print("Parent directory does not exist; creating directory.")
            path.parent.mkdir(parents=True)

        # store image mapping function source
        icsource = inspect.getsource(self.ic_function)
        icsource = icsource.replace(self.ic_function.__name__, "ic_function", 1)

        # store potential function source
        potsource = inspect.getsource(self.potential_function)
        potsource = potsource.replace(self.potential_function.__name__, "potential_function", 1)

        attrs = dict(
            icfunc=np.void(icsource.encode("utf8")),
            potfunc=np.void(potsource.encode("utf8")),
            dt=self.dt,
            steps=self.steps,
            pattern_speed=self.pattern_speed,
            backend=np.void(self.backend.__class__.__name__.encode("utf8")),
        )
        with h5py.File(path, "w") as f:
            dset = f.create_dataset(self.__class__.__name__, data=self.image)
            for attr, value in attrs.items():
                dset.attrs[attr] = value
            for attr, value in self.values.items():
                dset.attrs[attr] = value

    @classmethod
    def read_from_hdf5(cls, path: Any) -> AnalysisBase:
        """
        Read analysis data from an HDF5 file.

        Args:
            path: Path to the HDF5 file.

        Returns:
            AnalysisBase: Instance of AnalysisBase class with loaded data.
        """
        with h5py.File(path, "r") as f:
            dset = f[cls.__name__]

            if "icfunc" in dset.attrs:
                icsource = dset.attrs["icfunc"].tobytes().decode("utf8")
                namespace: dict[str, Any] = {}
                exec(icsource, {"u": u, "c": c}, namespace)
                ic_function = namespace["ic_function"]
            else:
                warnings.warn("No potential function defined.")

                def ic_function() -> None:
                    pass

            axis_names = inspect.getfullargspec(ic_function).args
            values = {name: dset.attrs[name] for name in axis_names}

            if "potfunc" in dset.attrs:
                potsource = dset.attrs["potfunc"].tobytes().decode("utf8")
                namespace = {}
                exec(potsource, {"u": u, "c": c}, namespace)
                potential_function = namespace["potential_function"]
            else:
                warnings.warn("No potential function defined.")

                def potential_function() -> None:
                    pass

            backend_cls = getattr(pidgey, dset.attrs["backend"].tobytes().decode("utf8"))
            analysis = cls(
                ic_function,
                values,
                potential_function=potential_function,
                dt=dset.attrs["dt"],
                steps=dset.attrs["steps"],
                pattern_speed=dset.attrs["pattern_speed"],
                backend=backend_cls(),
                _blank_image=True,
            )
            analysis.image = dset[()]
        return analysis


class AnalysisBase2D(AnalysisBase):
    """
    Base class for commensurability analysis on 2D orbits.

    This class extends AnalysisBase and provides additional methods for launching interactive plots.
    """

    def launch_interactive_plot(self, x_axis: str, y_axis: str, var_axis: Optional[str] = None):
        """
        Launch an interactive plot for 2D orbits.

        Args:
            x_axis (str): Name of the x-axis parameter.
            y_axis (str): Name of the y-axis parameter.
            var_axis (Optional[str]): Name of the axis varied by scrolling (optional).
        """
        iplot: InteractivePlotBase = InteractivePlot2D(self, x_axis, y_axis, var_axis)
        iplot.show()


class AnalysisBase3D(AnalysisBase):
    """
    Base class for commensurability analysis on 3D orbits.

    This class extends AnalysisBase and provides additional methods for launching interactive plots.
    """

    def launch_interactive_plot(self, x_axis: str, y_axis: str, var_axis: Optional[str] = None):
        """
        Launch an interactive plot for 3D orbits.

        Args:
            x_axis (str): Name of the x-axis parameter.
            y_axis (str): Name of the y-axis parameter.
            var_axis (Optional[str]): Name of the variable axis (optional).
        """
        iplot: InteractivePlotBase = InteractivePlot3D(self, x_axis, y_axis, var_axis)
        iplot.show()


# define user-facing analysis classes
from .tessellation import Tessellation
from .tessellation.base import TessellationBase


class TessellationAnalysis(AnalysisBase3D):
    """
    Analysis class for tessellation analysis on 3D orbits.

    This class extends AnalysisBase3D and implements the evaluate method for tessellation analysis.
    """

    @staticmethod
    def evaluate(orbit: c.SkyCoord) -> TessellationBase:
        """
        Evaluate an orbit using the tessellation and trimming algorithm.

        Args:
            orbit (c.SkyCoord): Integrated orbit coordinates.

        Returns:
            TessellationBase: Tessellation object containing tessellation results.
        """
        return Tessellation(orbit)


class TessellationAnalysis2D(AnalysisBase2D):
    """
    Analysis class for tessellation analysis on 2D orbits.

    This class extends AnalysisBase2D and implements the evaluate method for tessellation analysis.
    """

    @staticmethod
    def evaluate(orbit) -> TessellationBase:
        """
        Evaluate an orbit using the tessellation and trimming algorithm.

        Args:
            orbit (c.SkyCoord): Integrated orbit coordinates.

        Returns:
            TessellationBase: Tessellation object containing tessellation results.
        """
        return Tessellation(orbit.xyz[:2].T)
