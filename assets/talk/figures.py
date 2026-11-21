"""The talk's numbers and drawings. narrate.py runs this file before it reads the narration.

Numbers the slides or the voice quote go through values(); a drawing goes through figure(), and its parts are named
with gid: gid="s2-fit" appears with sentence 2 of its slide and gets the id "<figure>-fit" for point= and grow=.
In a real talk, read the project's numbers file here instead of simulating.

A figure is drawn at the size of the box it fills, at 100 px per inch of the 1920 x 1080 frame, so that text sizes
are the videos' points: FIG is the `.fig` box of a `.beside` slide (with PLOT, the place of its axes), ART the picture
box of a title card. Text, axes and the colour cycle follow the theme; draw with C.blue, C.accent, ... and not with
typed-in colours, so that the figure follows a change of theme. Blue is data here, the accent what the talk points at.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from narrate import ART, FIG, PLOT, C, figure, values

# ---------------------------------------------------------------- data, and the numbers that are spoken or shown
STEPS, WALKERS, D0 = 400, 2000, 0.5  # steps, walkers, diffusion constant of the walk (variance 2 D0 per step)
SHOWN = 200  # steps of the one walker that is drawn
rng = np.random.default_rng(20261120)
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
# the title's picture: walkers leaving the origin
fig, ax = plt.subplots(figsize=ART)
for j in range(40):
    p = path[90:151, j]
    ax.plot(p[:, 0], p[:, 1], color=C.blue, lw=1.2, alpha=0.35)
    ax.plot(*p[-1], "o", color=C.blue, ms=7)
ax.plot(0, 0, "+", color=C.ink, ms=18, mew=2)
ax.set(xlim=(-45, 45), ylim=(-45, 45), aspect="equal")
ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)
figure(fig, "walkers")

# one walker: the path is drawn while sentence 1 is spoken (grow="#walker-path"), the arrow comes with sentence 2
p = np.vstack([[0, 0], path[:SHOWN, 3]])
c, h = (p.min(0) + p.max(0)) / 2, 0.62 * np.ptp(p, axis=0).max()
fig, ax = plt.subplots(figsize=(8.06, 7.13))  # the box it is pinned in on the slide: 42 % x 66 % of the frame
ax.plot(p[:, 0], p[:, 1], color=C.blue, lw=2, gid="path")
ax.plot(0, 0, "o", color=C.ink, ms=11)
ax.add_patch(FancyArrowPatch((0, 0), p[-1], arrowstyle="-|>", mutation_scale=20, shrinkA=0, shrinkB=0, color=C.accent,
                             lw=4, gid="s2-arrow"))
ax.plot(*p[-1], "o", color=C.accent, ms=11, gid="s2-end")
ax.text(*(p[-1] / 2 + [1.5, 1.5]), "Δr(t)", color=C.accent, size=30, weight="semibold", gid="s2-label")
ax.set(xlim=(c[0] - 1.13 * h, c[0] + 1.13 * h), ylim=(c[1] - h, c[1] + h), aspect="equal")
ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)
figure(fig, "walker")

# the measurement: the points are there from the start, the fitted line comes with sentence 2
fig = plt.figure(figsize=FIG)
ax = fig.add_axes(PLOT)
ax.plot(t[::8], msd[::8], "o", color=C.blue, ms=7, gid="points")
ax.plot(t, slope * t, color=C.accent, lw=3, gid="s2-fit")
ax.text(215, slope * 215 - 150, f"slope 4D, D = {D:.2f}", color=C.accent, size=22, gid="s2-fitlabel")
ax.set_xlabel("time t (steps)")
ax.set_ylabel("⟨Δr²⟩ (step lengths squared)")
ax.set_xlim(0, STEPS)
ax.set_ylim(0, None)
figure(fig, "msd")
