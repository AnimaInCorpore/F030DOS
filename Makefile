# F030DOS: build, run and release the DOS ports.  Each port keeps its own build
# entry point in games/<game>/; this file only supplies the toolchain locations,
# so the imported files stay identical to their development repositories.
#
#   make list               the ports, their programs and what they need
#   make <game>             build games/<game> (comanche, f29, por, wc1, uw2)
#   make comanche060        the 68060 image with the music (needs ../F030OPL2)
#   make run-<game>         run it in the patched Hatari
#   make release VERSION=v  release/F030DOS-<v>.zip (tools/release.py)
#   make check              the publication checks (tools/publication.py)
#   make status             imported commit of every port vs. its repository
#
# Override ARCADE= (the F030Arcade checkout) or PYTHON= (a Python 3 with
# capstone, which Comanche's build needs) when they live elsewhere, and OPL2= (the
# F030OPL2 checkout, GPL-3.0, linked into comanche060).

ARCADE ?= $(abspath ../F030Arcade)
PYTHON ?= python3
HATARI ?= $(ARCADE)/third_party/hatari/build/src/hatari
VASM ?= $(ARCADE)/third_party/vasm/vasmm68k_mot
VLINK ?= $(ARCADE)/third_party/vlink/vlink
TOS402 ?= $(ARCADE)/third_party/tos/tos402.img
TOS404 ?= $(ARCADE)/third_party/tos/tos404.img
OPL2 ?= $(abspath ../F030OPL2)

# The ports' scripts call `python`; a pyenv shim that points nowhere makes
# Comanche's build fail without relinking.  build/pybin puts PYTHON first.
# PYTHON is looked up in the PATH before that, or pybin would link to itself.
PYBIN := $(CURDIR)/build/pybin
OUTER_PATH := $(PATH)
export PATH := $(PYBIN):$(PATH)

.PHONY: list pybin check status release comanche comanche060 f29 por wc1 uw2 \
	run-comanche run-f29 run-por run-wc1 run-uw2

list:
	@echo "comanche  make comanche   -> games/comanche/release/comanche.tos  (needs your install in games/comanche/assets/)"
	@echo "comanche  make comanche060 -> games/comanche/release/68060/comanche.tos + OPLDATA.BIN (68060, music; needs ../F030OPL2)"
	@echo "f29       make f29        -> games/f29/release/f29.tos + 3d.lod"
	@echo "por       make por        -> games/por/release/por.tos            (PORCACHE: make -C games/por data falcon-data)"
	@echo "wc1       make wc1        -> games/wc1/release/wc1.tos            (WC1DATA: make -C games/wc1 data)"
	@echo "uw2       make uw2        -> games/uw2/build/falcon/uw2-falcon-smoke.tos (presenter smoke harness)"
	@echo "pg uw tie falcon3 links386 lol magiccarpet icr: analysis and tools; no Falcon program yet"

pybin:
	@mkdir -p $(PYBIN)
	@p=$$(PATH='$(OUTER_PATH)'; command -v $(PYTHON)) || { echo "$(PYTHON) not found" >&2; exit 1; }; \
		ln -sfn "$$p" $(PYBIN)/python; ln -sfn "$$p" $(PYBIN)/python3

comanche: pybin
	cd games/comanche && F030ARCADE_ROOT=$(ARCADE) bash tools/build-run.sh
run-comanche: comanche
	cd games/comanche && HATARI=$(HATARI) TOS=$(TOS402) bash tools/run.sh
comanche060: pybin
	cd games/comanche && F030ARCADE_ROOT=$(ARCADE) TARGET_CPU=68060 OPL2=1 OPL2_ROOT=$(OPL2) bash tools/build-run.sh

f29: pybin
	cd games/f29 && F29_ROOTS=$(abspath $(ARCADE)/..) bash tools/build-run.sh
	cd games/f29 && F29_ROOTS=$(abspath $(ARCADE)/..) bash tools/build-dsp.sh
run-f29: f29
	cd games/f29 && F29_ROOTS=$(abspath $(ARCADE)/..) HATARI=$(HATARI) TOS=$(TOS402) bash tools/run.sh

por: pybin
	$(MAKE) -C games/por build VASM=$(VASM) VLINK=$(VLINK)
run-por: pybin
	$(MAKE) -C games/por run VASM=$(VASM) VLINK=$(VLINK) HATARI=$(HATARI) TOS=$(TOS404)

wc1: pybin
	$(MAKE) -C games/wc1 build VASM=$(VASM) VLINK=$(VLINK)
run-wc1: pybin
	$(MAKE) -C games/wc1 run VASM=$(VASM) VLINK=$(VLINK) HATARI=$(HATARI) TOS=$(TOS404)

uw2: pybin
	$(MAKE) -C games/uw2 check VASM=$(VASM) VLINK=$(VLINK) TOS=$(TOS404)
run-uw2: pybin
	$(MAKE) -C games/uw2 hatari-smoke VASM=$(VASM) VLINK=$(VLINK) TOS=$(TOS404) HATARI=$(HATARI)

check:
	python3 tools/publication.py check

status:
	python3 tools/publication.py status

release: pybin
	@test -n "$(VERSION)" || { echo "usage: make release VERSION=<version>"; exit 1; }
	python3 tools/release.py $(VERSION)
