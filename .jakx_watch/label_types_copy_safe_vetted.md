# label_types_copy_safe — vetted against binary type-tags

_Audited: 112 entries. Likely safe: 0, Conflicts: 37, Unclear: 75_

## TYPE_TAG_CONFLICT (exclude from batch-apply)

- **debug/L283**: proposed `(inline-array vector)` but binary is `string`
- **debug/L286**: proposed `(inline-array vector)` but binary is `string`
- **debug/L287**: proposed `(inline-array vector)` but binary is `string`
- **default-menu/L6786**: proposed `attack-info` but binary is `string`
- **default-menu/L6792**: proposed `attack-info` but binary is `string`
- **editable/L680**: proposed `vector` but binary is `string`
- **editable/L722**: proposed `uint64` but binary is `string`
- **editable/L723**: proposed `rgba` but binary is `string`
- **editable/L724**: proposed `rgba` but binary is `string`
- **editable/L725**: proposed `rgba` but binary is `string`
- **editable/L726**: proposed `rgba` but binary is `string`
- **editable/L727**: proposed `rgba` but binary is `string`
- **editable/L728**: proposed `rgba` but binary is `string`
- **editable/L729**: proposed `rgba` but binary is `string`
- **editable/L730**: proposed `rgba` but binary is `string`
- **editable-player/L1499**: proposed `uint64` but binary is `state`
- **foreground/L214**: proposed `vector` but binary is `string`
- **generic-obs/L790**: proposed `uint64` but binary is `string`
- **generic-obs/L791**: proposed `uint64` but binary is `string`
- **generic-obs/L792**: proposed `uint64` but binary is `string`
- **generic-obs/L793**: proposed `uint64` but binary is `string`
- **level/L1003**: proposed `uint64` but binary is `string`
- **level/L1004**: proposed `uint64` but binary is `string`
- **mood/L267**: proposed `vector` but binary is `string`
- **nav-mesh-editor/L504**: proposed `(inline-array triangulation-vert)` but binary is `string`
- **nav-mesh-editor/L505**: proposed `(inline-array triangulation-vert)` but binary is `string`
- **nav-mesh-editor/L555**: proposed `(pointer int32)` but binary is `string`
- **nav-mesh-editor/L556**: proposed `(inline-array vector)` but binary is `string`
- **nav-mesh-editor/L557**: proposed `uint64` but binary is `string`
- **nav-mesh-editor/L560**: proposed `uint64` but binary is `string`
- **process-drawable/L462**: proposed `vector` but binary is `string`
- **process-drawable/L463**: proposed `vector` but binary is `string`
- **profile/L2**: proposed `(pointer uint64)` but binary is `array`
- **texture-anim/L197**: proposed `(pointer uint16)` but binary is `string`
- **texture-anim/L198**: proposed `(pointer uint8)` but binary is `string`
- **water-anim/L62**: proposed `attack-info` but binary is `string`
- **water-anim/L63**: proposed `attack-info` but binary is `state`

## UNCLEAR (75 entries, require investigation)

- **anim-tester/L698**: proposed `uint64` (no binary type found)
- **anim-tester/L700**: proposed `uint64` (no binary type found)
- **anim-tester/L701**: proposed `uint64` (no binary type found)
- **anim-tester/L702**: proposed `uint64` (no binary type found)
- **cam-states-dbg/L59**: proposed `vector` (no binary type found)
- **cam-states-dbg/L60**: proposed `vector` (no binary type found)
- **capture/L4**: proposed `gs-store-image-packet` (no binary type found)
- **collide-cache/L184**: proposed `vector` (no binary type found)
- **debug/L265**: proposed `(inline-array vector)` (no binary type found)
- **editable-player/L1431**: proposed `(inline-array vector4w)` (no binary type found)
- **font-data/L1**: proposed `(inline-array vector)` (no binary type found)
- **font-data/L2**: proposed `(inline-array vector)` (no binary type found)
- **generic-merc/L175**: proposed `(inline-array invinitdata)` (no binary type found)
- **generic-obs/L721**: proposed `attack-info` (no binary type found)
- **generic-obs/L722**: proposed `sphere` (no binary type found)
- **generic-obs/L725**: proposed `attack-info` (no binary type found)
- **intro-scenes/L7337**: proposed `uint64` (no binary type found)
- **intro-scenes/L7338**: proposed `uint64` (no binary type found)
- **intro-scenes/L7339**: proposed `uint64` (no binary type found)
- **intro-scenes/L7340**: proposed `uint64` (no binary type found)

... and 55 more unclear entries
