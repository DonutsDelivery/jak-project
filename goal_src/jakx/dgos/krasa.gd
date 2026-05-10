;; Jak X KRA.DGO — Kras City master art DGO (krasa-vis level data).
;; This DGO bundles the geometry/art shared by the kras-* level family
;; (krastrn, krasw, krastbox, krastt). Without it, krastrn/krasw load
;; only their per-level actor scaffolding and the BSP exposes a single
;; drawable-tree-actor — no TIE/tfrag/shrub trees → empty TIE buckets
;; → black-screen-with-actors symptom.
;;
;; Code objects (kras-effects, kras-obs, kras-ocean, kras-part) are
;; deferred until ported to OpenGOAL; only geometry + tpages + art groups
;; here. krasa-vis.go is the visibility binary the loader matches against
;; visname 'krasa-vis from the krasa level-load-info.
;; Output filename is KRASA.DGO (not the PS2-original KRA.DGO) so the level
;; loader's name-based DGO lookup `(format "~S.DGO" name)` for the 'krasa
;; level finds it. Atoll precedent: vis?=#f boot path uses name.DGO, not
;; nickname.DGO, so the file must match the level name verbatim.
("KRASA.DGO"
 ("tpage-296.go"
  "tpage-582.go"
  "tpage-406.go"
  "tpage-583.go"
  "kras-rusty-sign-ag.go"
  "kras-windsock-ag.go"
  "kras-fishtank-lo-ag.go"
  "kras-fireworks-ship-a-ag.go"
  "krasa-vis.go"
  ))
