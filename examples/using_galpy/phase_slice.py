import numpy as np
import astropy.units as u
import galpy.potential as p

from commensurability.analysis import Analysis

# rotating bar potential
omega = 30 * u.km/u.s/u.kpc
halo = p.NFWPotential(conc=10, mvir=1)
disc = p.MiyamotoNagaiPotential(amp=5e10 * u.solMass, a=3 * u.kpc, b=0.1 * u.kpc)
bar = p.SoftenedNeedleBarPotential(amp=1e9 * u.solMass, a=1.5 * u.kpc, b=0 * u.kpc, c=0.5 * u.kpc, omegab=omega)
pot = [halo, disc, bar]


SIZE = 10
coords = dict(
    R   = np.linspace(0, 10, SIZE + 1)[1:]  * u.kpc,
    vR  = np.linspace(0, 0, 1)  * u.km/u.s,
    vT  = np.linspace(0, 300, SIZE + 1)[1:]  * u.km/u.s,
    z   = np.linspace(1, 1, 1)  * u.kpc,
    vz  = np.linspace(0, 0, 1)  * u.km/u.s,
    phi = np.linspace(0, 0, 1)  * u.deg,
)
ts = np.linspace(0, 1, 501) * u.Gyr
canal = Analysis(pot, ts, pattern_speed=omega, **coords)
canal.construct_image()
canal.save_image('test.hdf5')
canal.display_image()