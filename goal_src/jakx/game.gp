;;-*-Lisp-*-

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Jak X Project File
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

;;;;;;;;;;;;;;;;;;;;;;;
;; Inputs from ISO
;;;;;;;;;;;;;;;;;;;;;;;

(cond
  ;; extractor can override everything by providing *use-iso-data-path*
  (*use-iso-data-path*
   (map-path! "$ISO" (string-append *iso-data* "/")))
  ;; if the user's repl-config has a game version folder, use that
  ((> (string-length (get-game-version-folder)) 0)
   (map-path! "$ISO" (string-append "iso_data/" (get-game-version-folder) "/")))
  ;; otherwise, default to jakx
  (#t
   (map-path! "$ISO" "iso_data/jakx/")))

;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Inputs from decompiler
;;;;;;;;;;;;;;;;;;;;;;;;;;

(cond
  ;; if the user's repl-config has a game version folder, use that
  ((> (string-length (get-game-version-folder)) 0)
   (map-path! "$DECOMP" (string-append "decompiler_out/" (get-game-version-folder) "/")))
  ;; otherwise, default to jakx
  (#t
   (map-path! "$DECOMP" "decompiler_out/jakx/")))

;;;;;;;;;;;;;;;;;;;;;;;
;; Output
;;;;;;;;;;;;;;;;;;;;;;;

;; NOTE: the game itself will load from out/jakx/iso and out/jakx/fr3.
(map-path! "$OUT" "out/jakx/")

;; tell the compiler to put its outputs in out/jakx/
(set-output-prefix "jakx/")

;; use defmacro to define goos macros.
(define defmacro defsmacro)
(define defun desfun)

;;;;;;;;;;;;;;;;;;;;;;;
;; Build Groups
;;;;;;;;;;;;;;;;;;;;;;;

(define *all-cgos* '())
(define *all-str* '())
(define *all-vis* '())
(define *all-mus* '())
(define *all-sbk* '())
(define *all-vag* '())
(define *all-gc* '())

(define *file-entry-map* (make-string-hash-table))

;; Load required macros
(load-file "goal_src/jakx/lib/project-lib.gp")
(set-gsrc-folder! "goal_src/jakx")

;;;;;;;;;;;;;;;;;
;; GOAL Kernel
;;;;;;;;;;;;;;;;;

(cgo-file "kernel.gd" '())

;;;;;;;;;;;;;;;;;;;;;
;; DGOs
;;;;;;;;;;;;;;;;;;;;;

(defstep :in "$DECOMP/textures/tpage-dir.txt"
  :tool 'tpage-dir
  :out '("$OUT/obj/dir-tpages.go")
  )
(hash-table-set! *file-entry-map* "dir-tpages.go" #f)

(cgo-file "game.gd" '("$OUT/obj/gcommon.o" "$OUT/obj/gstate.o" "$OUT/obj/gstring.o" "$OUT/obj/gkernel.o"))

;; minimal TITLE.DGO so play can satisfy its load of the 'title level during early boot
(cgo-file "title.gd" '())

;; first race-level DGO — atoll. Code objects not yet ported; only geometry/art/textures.
;; Named ATL.DGO to match level info nickname 'atl (loader requests ATL.DGO).
(cgo-file "atoll.gd" '())

;; tutorial level — krastrn (Kras City training arena). Code objects (net-training)
;; not yet ported; only level data/visibility.
(cgo-file "krastrn.gd" '())

;; first wide tutorial level — krasw (Kras City open hub). KRASW.DGO unblocked
;; via no_type_analysis on kras-pump-break methods 43-45 (Lane C #2). Code
;; objects (kras-effects, kras-part, kras-obs, kras-ocean, construction-obs)
;; not yet ported; only tpages, art groups, and krasw level binary.
(cgo-file "krasw.gd" '())

;; first vehicle art DGO — bobcl (Bobcat car, tutorial vehicle). 1 chassis +
;; 25 bodywork variants + 22 wheel variants + bobcl.go level binary.
;; Code objects (wcar-bobcat.o) not yet ported — only art groups + level binary.
(cgo-file "bobcl.gd" '())

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Groups
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(group-list "all-code" *all-gc*)
(group-list "engine" *all-cgos*)
