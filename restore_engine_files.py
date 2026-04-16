#!/usr/bin/env python3
"""Copy pure engine/math/rendering .gc files from jak3 to jakx."""

import os
import shutil
from pathlib import Path

BASE = Path("/home/user/Programs/Jak-X/jak-project")
JAK3_DIR = BASE / "goal_src" / "jak3"
JAKX_DIR = BASE / "goal_src" / "jakx"

EXCLUDE_DIRS = {"kernel", "pc", "lib"}

FILES = """matrix-h matrix matrix-compose quaternion quaternion-h euler euler-h
transform transform-h trigonometry trigonometry-h transformq transformq-h
bounding-box bounding-box-h geometry geometry-h vector math-camera-h math-camera
trajectory trajectory-h smush-control-h curves dma-h dma dma-buffer dma-bucket
dma-disasm vif-h gs display-h display video-h profile-h profile vu1-user-h
font-h font-data decomp-h decomp texture-h texture-anim-h texture lights-h lights
blit-displays-h blit-displays sky-h sky-data sky-tng ocean-h shadow-cpu-h
shadow-vu1-h shadow-cpu warp merc-h generic-merc-h generic-tie-h generic-vu1-h
generic-work-h generic-h foreground-h sprite-h simple-sprite-h eye-h prim-h
shrubbery-h tie-h tfrag-h background-h subdivide-h draw-node-h drawable-h
drawable-group-h drawable-inline-array-h drawable-tree-h drawable-actor-h mspace-h
prototype-h cloth-art-h art-h merc emerc foreground bones bones-h joint-h joint
joint-mod-h joint-mod ripple draw-node shrubbery shrub-work tfrag tfrag-near
tfrag-methods tfrag-work tie etie-vu1 etie-near-vu1 tie-near tie-work tie-methods
merc-vu1 emerc-vu1 merc-blend-shape merc-death generic-vu0 generic-vu1
generic-effect generic-merc generic-tie debug-foreground debug-sphere debug prim
background ocean ocean-mid ocean-transition ocean-near ocean-trans-tables font
texture-anim texture-anim-funcs texture-anim-tables texture-upload texture-finish
eye collide-func-h collide-mesh-h collide-shape-h collide-touch-h collide-frag-h
collide-hash-h collide-cache-h collide-h collide-func collide-hash collide-probe
collide-frag collide-touch collide-shape-rider collide collide-planes collide-cache
collide-debug spatial-hash-h spatial-hash actor-hash-h actor-hash find-nearest-h
find-nearest pat-h main-collide connect engines res-h res file-io loader-h
load-dgo ramdisk timer-h timer capture-h capture memory-usage-h memory-usage rpc-h
history text-h text gsound-h gsound speech-h speech wind-h wind-work wind
lightning-h lightning light-trails-h lightning-new-h lightning-new light-trails
particle-curves sparticle-launcher-h sparticle-h sparticle-launcher sparticle
entity-table entity-h mood-h mood-tables mood-tables2 mood mood-funcs mood-funcs2
weather-part time-of-day-h time-of-day level-h level-info level bsp-h bsp subdivide
sprite sprite-distort sprite-glow load-state loader region-h region path-h path
nav-mesh-h nav-control-h nav-engine nav-mesh nav-control dynamics-h
process-drawable-h process-drawable generic-obs-h actor-link-h camera-h
cam-interface-h cam-debug-h cam-update-h camera cam-interface cam-master
cam-combiner cam-update cam-layout cam-debug cam-start cam-states cam-states-dbg
vol-h vol ambient-h ambient relocate effect-control-h effect-control debris
joint-exploder water-info-h water-h water water-part water-flow ragdoll-h
ragdoll-test cloth-h cloth rigid-body-h rigid-body rigid-body-queue video main
main-h shadow-vu1""".split()

def build_index(root, exclude_dirs=None):
    """Build name -> path index for all .gc files under root."""
    idx = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if exclude_dirs:
            rel = os.path.relpath(dirpath, root)
            top = rel.split(os.sep)[0]
            if top in exclude_dirs:
                continue
        for f in filenames:
            if f.endswith(".gc"):
                name = f[:-3]  # strip .gc
                idx[name] = os.path.join(dirpath, f)
    return idx

def main():
    jak3_idx = build_index(JAK3_DIR)
    jakx_idx = build_index(JAKX_DIR, exclude_dirs=EXCLUDE_DIRS)

    copied = 0
    not_in_jak3 = []
    not_in_jakx = []

    for name in FILES:
        if name not in jak3_idx:
            not_in_jak3.append(name)
        elif name not in jakx_idx:
            not_in_jakx.append(name)
        else:
            src = jak3_idx[name]
            dst = jakx_idx[name]
            shutil.copy2(src, dst)
            copied += 1

    print(f"Copied: {copied}")
    print(f"Not found in jak3: {len(not_in_jak3)}")
    if not_in_jak3:
        for n in not_in_jak3:
            print(f"  - {n}")
    print(f"Not found in jakx: {len(not_in_jakx)}")
    if not_in_jakx:
        for n in not_in_jakx:
            print(f"  - {n}")
    print(f"Total requested: {len(FILES)}")

if __name__ == "__main__":
    main()
