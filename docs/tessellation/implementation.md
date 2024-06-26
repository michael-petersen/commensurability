# Implementation

The algorithm computes a normalized volume (between 0 and 1), and is roughly split into 4 steps:

1. [Compute a tessellation](implementation.md#compute-a-tessellation)
2. [Compute side-length values](implementation.md#compute-side-length-values)
3. [Trim simplices](implementation.md#trim-simplices)
3. [Compute the normalization](implementation.md#compute-the-normalization)

## Compute a Tessellation

After integrating an orbit, the raw point-array of its position over time is passed into a tessellation algorithm. For this specific implementation, [SciPy's Delaunay Tessellation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Delaunay.html) routine is used, which itself calls out to [Qhull](http://www.qhull.org/) under-the-hood.

## Compute Side-Length Values

The important values to compute here are the smallest side-lengths and longest side-lengths of the simplices in our tessellation.
These are what will be used in our trimming condition.

## Trim Simplices

The median of the smallest simplex side-lengths probes the length-scale of "related" parts of an orbit.
If the longest side of a simplex is significantly larger than this value, it likely connects unrelated parts of the orbit and should be trimmed.

This threshold is referred to as the **axis ratio**, and is set to `10` by default.
The trimming condition can be written out as so:

$$ \frac{\text{longest side}}{\text{median(all shortest sides)}} > \text{axis ratio} $$

=== "0"
    ![Axis ratio of 0](ar0.png){ width=50% align=left }

    100×100 example image of a slice of phase space.
    All simplices with an axis ratio above 0 are removed.
    Commensurability is calculated from the remaining simplices.

    !!! note "No Total Measure"
        By setting the axis ratio threshold to 0, all simplices are removed.

=== "5"
    ![Axis ratio of 5](ar5.png){ width=50% align=left }

    100×100 example image of a slice of phase space.
    All simplices with an axis ratio above 5 are removed.
    Commensurability is calculated from the remaining simplices.

=== "10"
    ![Axis ratio of 10](ar10.png){ width=50% align=left }

    100×100 example image of a slice of phase space.
    All simplices with an axis ratio above 10 are removed.
    Commensurability is calculated from the remaining simplices.

    !!! note "This is the default."

=== "15"
    ![Axis ratio of 15](ar15.png){ width=50% align=left }

    100×100 example image of a slice of phase space.
    All simplices with an axis ratio above 15 are removed.
    Commensurability is calculated from the remaining simplices.

=== "20"
    ![Axis ratio of 20](ar20.png){ width=50% align=left }

    100×100 example image of a slice of phase space.
    All simplices with an axis ratio above 20 are removed.
    Commensurability is calculated from the remaining simplices.


## Compute the Normalization

There is some delicacy in choosing an appropriate normalization.
The canonical choice is a [hypersphere](https://en.wikipedia.org/wiki/N-sphere) that encapsulates the whole orbit, but orbits rarely fill a whole hypersphere, resulting in poor dynamic range.

In 2D, the default normalization a circle that encapsulates the orbit (routine name is `circle`).
This is the only normalization routine available.

In 3D, the default normalization takes 4 rotated copies of the point array and computes its convex hull (routine name is `convexhull_rot4`).

### Normalization Routines in 3D

=== "Sphere"
    ![Phase space commensurability diagram with "sphere" normalization routine](sphere.png){ width=50% align=left }

    100×100 example image of a slice of phase space generated with `sphere` normalization.
    Normalizing shape is the smallest enclosing sphere centered at the origin.

=== "Cylinder"
    ![Phase space commensurability diagram with "cylinder" normalization routine](cylinder.png){ width=50% align=left }

    100×100 example image of a slice of phase space generated with `cylinder` normalization.
    Normalizing shape is the smallest enclosing cylinder centered at the origin.

=== "Convex Hull"
    ![Phase space commensurability diagram with "convexhull" normalization routine](convexhull.png){ width=50% align=left }

    100×100 example image of a slice of phase space generated with `convexhull` normalization.
    Normalizing shape is the convex hull of the points.

    !!! note "Co-rotation Tracks"
        Co-rotation resonance tracks are difficult to detect with this normalization routine.

=== "Convex Hull in $R$ vs $z$"
    ![Phase space commensurability diagram with "Rz_convexhull" normalization routine](Rz_convexhull.png){ width=50% align=left }

    100×100 example image of a slice of phase space generated with `Rz_convexhull` normalization.
    Normalizing shape is the convex hull in the $R$ vs $z$ plane rotated about the $z$-axis.

=== "4 Rotated Convex Hulls"
    ![Phase space commensurability diagram with "convexhull_rot4" normalization routine](convexhull_rot4.png){ width=50% align=left }

    100×100 example image of a slice of phase space generated with `convexhull_rot4` normalization.
    Normalizing shape is the convex hull of 4 rotated copies of the points about the $z$-axis.

    !!! note "This is the default."
