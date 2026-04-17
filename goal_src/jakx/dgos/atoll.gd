;; Jak X ATOLL.DGO — main atoll race track.
;;
;; For initial bringup we omit the jakx level-code objects
;; (atoll-ocean.o, atoll-effects.o, atoll-part.o, atoll-obs.o) because they
;; haven't been ported to OpenGOAL yet. The level still packages the geometry
;; (atoll-vis.go), art groups, and textures — enough to validate the DGO
;; build pipeline and, once wired to level-load-info, the loader path.
("ATOLL.DGO"
 ("tpage-3038.go"
  "tpage-3039.go"
  "tpage-3040.go"
  "tpage-3041.go"
  "tpage-3042.go"
  "atoll-dish-ag.go"
  "atoll-rotor-ag.go"
  "atoll-vis.go"
 ))
