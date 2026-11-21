"""The talk's numbers and drawings. narrate.py runs this file before it reads the narration.

Numbers the slides or the voice quote go through values(); a drawing goes through figure(), and its parts are named
with gid: gid="s2-fit" appears with sentence 2 of its slide and gets the id "<figure>-fit" for point= and grow=.
In a real talk, read the project's numbers file here instead of simulating.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from narrate import C, figure, values

# C holds the theme's colours (C.ink, C.muted, C.light, C.accent, C.blue, C.green, C.purple); text, axes and the
# colour cycle already follow it. Give each colour one meaning for the whole talk: here blue is data, accent the reading.

# ---------------------------------------------------------------- data, and the numbers that are spoken or shown
STEPS, WALKERS, D0 = 400, 2000, 0.5  # steps, walkers, diffusion constant of the walk (variance 2 D0 per step)
SHOWN = 200  # steps of the one walker that is drawn
rng = np.random.default_rng(20261121)
path = np.cumsum(rng.normal(0, np.sqrt(2 * D0), (STEPS, WALKERS, 2)), axis=0)
t = np.arange(1, STEPS + 1)
msd = (path**2).sum(axis=2).mean(axis=1)
slope = np.polyfit(t, msd, 1)[0]
D = slope / 4

# fail the build if a quoted number or a qualitative word of the narration no longer follows from the data
assert abs(D - D0) < 0.05 * D0, "the narration says the measured D returns the one put in"
assert 1.8 < msd[399] / msd[199] < 2.2, "'twice the time, twice the area'"
values(D=f"{D:.2f}", D0=D0, walkers=WALKERS, steps=STEPS, shown=SHOWN)

# ---------------------------------------------------------------- drawings
# one walker: the path is drawn while sentence 1 is spoken (grow="#walker-path"), the arrow comes with sentence 2
p = np.vstack([[0, 0], path[:SHOWN, 3]])
fig, ax = plt.subplots(figsize=(4.4, 4.0))
ax.plot(p[:, 0], p[:, 1], color=C.blue, lw=1.6, gid="path")
ax.plot(0, 0, "o", color=C.ink, ms=7)
ax.add_patch(FancyArrowPatch((0, 0), p[-1], arrowstyle="-|>", mutation_scale=20, color=C.accent, lw=2.6, gid="s2-arrow"))
ax.text(*(p[-1] / 2 + [1.2, 1.2]), "Δr(t)", color=C.accent, size=17, gid="s2-label")
ax.set_aspect("equal")
ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)
figure(fig, "walker")

# the measurement: the points are there from the start, the fitted line comes with sentence 2
fig, ax = plt.subplots(figsize=(5.4, 3.9))
ax.plot(t[::8], msd[::8], "o", color=C.blue, ms=5, gid="points")
ax.plot(t, slope * t, color=C.accent, lw=2.4, gid="s2-fit")
ax.text(215, slope * 215 - 170, f"slope 4D, D = {D:.2f}", color=C.accent, size=14, gid="s2-fitlabel")
ax.set_xlabel("time t (steps)")
ax.set_ylabel("⟨Δr²⟩ (step lengths squared)")
ax.set_xlim(0, STEPS)
ax.set_ylim(0, None)
fig.tight_layout()
figure(fig, "msd")
