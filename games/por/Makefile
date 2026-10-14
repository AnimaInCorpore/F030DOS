SHELL := /bin/bash

ROOT := $(abspath .)
# Which back end to build. Nothing outside src/target/$(TARGET)/ may assume it.
TARGET ?= falcon
SRC_DIR := src
COMMON_DIR := $(SRC_DIR)/common
TARGET_DIR := $(SRC_DIR)/target/$(TARGET)
OBJ_DIR := obj/$(TARGET)
RELEASE_DIR := release
CACHE_DIR := $(RELEASE_DIR)/PORCACHE
EXPANDED := work/expanded

VASM ?= $(ROOT)/../F030Arcade/third_party/vasm/vasmm68k_mot
VLINK ?= $(ROOT)/../F030Arcade/third_party/vlink/vlink
HATARI ?= hatari
TOS ?= $(ROOT)/../F030Arcade/third_party/tos/tos404.img
MEMSIZE ?= 14
VBL ?= 600
OUT ?= build/title.png

GAME := $(RELEASE_DIR)/por.tos
GAME_DEBUG := $(RELEASE_DIR)/por_debug.tos

COMMON_SOURCES := $(wildcard $(COMMON_DIR)/*.s)
# start.s must be linked FIRST: a TOS executable begins at the first byte of
# TEXT, so link order picks the entry point and vlink's -e does not override it.
TARGET_SOURCES := $(TARGET_DIR)/start.s \
                  $(filter-out $(TARGET_DIR)/start.s,$(wildcard $(TARGET_DIR)/*.s))
OBJECTS := $(TARGET_SOURCES:$(TARGET_DIR)/%.s=$(OBJ_DIR)/target_%.o) \
           $(COMMON_SOURCES:$(COMMON_DIR)/%.s=$(OBJ_DIR)/common_%.o)
INCLUDES := $(wildcard $(COMMON_DIR)/inc/*.s) $(wildcard $(TARGET_DIR)/inc/*.s)
# src/common/ must stay 68000-clean so a plain ST back end can reuse it; only
# the target directory may raise the CPU.
COMMON_CPU ?= -m68000
TARGET_CPU ?= -m68030
ASMFLAGS := -quiet -Felf
LFLAGS := -b ataritos -tos-flags 1

.PHONY: all build test data falcon-data title-smoke reasm decompile oracle-stage oracle run grab clean tools

all: build

build: $(GAME) $(GAME_DEBUG)

tools:
	@test -x "$(VASM)" || { echo "vasm not found: $(VASM)" >&2; exit 1; }
	@test -x "$(VLINK)" || { echo "vlink not found: $(VLINK)" >&2; exit 1; }

$(OBJ_DIR) $(RELEASE_DIR):
	mkdir -p $@

$(OBJ_DIR)/common_%.o: $(COMMON_DIR)/%.s $(INCLUDES) Makefile | $(OBJ_DIR) tools
	$(VASM) $(ASMFLAGS) $(COMMON_CPU) -I $(COMMON_DIR) -o $@ -L $(OBJ_DIR)/common_$*.lst $<

$(OBJ_DIR)/target_%.o: $(TARGET_DIR)/%.s $(INCLUDES) Makefile | $(OBJ_DIR) tools
	$(VASM) $(ASMFLAGS) $(TARGET_CPU) -I $(TARGET_DIR) -o $@ -L $(OBJ_DIR)/target_$*.lst $<

$(GAME): $(OBJECTS) | $(RELEASE_DIR) tools
	$(VLINK) $(OBJECTS) $(LFLAGS) -e _main -s -o $@

$(GAME_DEBUG): $(OBJECTS) | $(RELEASE_DIR) tools
	$(VLINK) $(OBJECTS) $(LFLAGS) -e _main -o $@

# Stage the original DOS data. Derived, never committed.
data:
	sh work/stage.sh

# Convert only the formats that are fully resolved. An unrecognised block is
# skipped and counted, never emitted with invented geometry.
falcon-data:
	@test -f "$(EXPANDED)/TITLE.DAX" || { echo "stage the DOS data first: make data" >&2; exit 1; }
	python3 tools/convert_data.py $(EXPANDED) $(CACHE_DIR) TITLE.DAX ICON.DAX

test:
	python3 tools/check_contracts.py

# Disassembly proof: reassemble every overlay unit and START.EXE, then rebuild
# both original files and require them to be byte-identical. Byte-exactness is
# an invariant; the instruction/data ratio it reports is the score.
# Decompile every overlay unit with Ghidra in one headless run. Units are
# imported individually at their own base; PORSeed.java resolves each one's
# entry-thunk list by program name. Needs JAVA_HOME (openjdk@21 is keg-only).
GHIDRA_HEADLESS ?= /opt/homebrew/Cellar/ghidra/12.1.3/libexec/support/analyzeHeadless
JAVA_HOME ?= /opt/homebrew/opt/openjdk@21

decompile:
	@test -x "$(GHIDRA_HEADLESS)" || { echo "Ghidra not found: $(GHIDRA_HEADLESS) (brew install ghidra)" >&2; exit 1; }
	@test -f "$(EXPANDED)/GAME.OVR" || { echo "stage the DOS data first: make data" >&2; exit 1; }
	python3 work/overlay.py work/overlay_map.json
	python3 work/extract_units.py
	rm -rf work/ghidra/POR16.rep work/ghidra/POR16.gpr work/ghidra_export
	JAVA_HOME=$(JAVA_HOME) "$(GHIDRA_HEADLESS)" "$(ROOT)/work/ghidra" POR16 \
		-import "$(ROOT)/work/ghidra/units" \
		-processor "x86:LE:16:Real Mode" \
		-scriptPath "$(ROOT)/work/ghidra_scripts" \
		-preScript  PORSeed.java   "$(ROOT)/work/ghidra/entries" \
		-postScript PORExport.java "$(ROOT)/work/ghidra_export" \
		| grep -E "PORSeed|PORExport|ERROR" || true
	python3 work/funcmap.py

# DOS dynamic oracle. See analysis/dos-oracle.md — the harness works, but the
# palette question is not settled yet: START.EXE stops before it touches video
# hardware because no POOL.CFG exists.
ORACLE_DIR := img/oracle

oracle-stage:
	@test -f "$(EXPANDED)/START.EXE" || { echo "stage the DOS data first: make data" >&2; exit 1; }
	mkdir -p $(ORACLE_DIR)/GAME $(ORACLE_DIR)/DISK1 $(ORACLE_DIR)/DISK2 $(ORACLE_DIR)/HD
	cp $(EXPANDED)/* $(ORACLE_DIR)/GAME/
	cp game/POR/Disk1/* $(ORACLE_DIR)/DISK1/
	cp game/POR/Disk2/* $(ORACLE_DIR)/DISK2/
	chmod -R u+w $(ORACLE_DIR)

oracle-hd-stage:
	@test -f img/por.hdd || { echo "build the QEMU image first: python3 work/build_dos_hdd.py" >&2; exit 1; }
	@mkdir -p $(ORACLE_DIR)/HD
	@rm -rf $(ORACLE_DIR)/HD/POOLRAD
	MTOOLS_SKIP_CHECK=1 mcopy -s -o -i img/por.hdd@@$$(python3 -c "import json;print(json.load(open('img/por.hdd.geom.json'))['part_offset'])") ::/POOLRAD $(ORACLE_DIR)/HD/
	@chmod -R u+w $(ORACLE_DIR)/HD

# The palette capture that item 8 was blocked on: run the installed game, with
# its own POOL.CFG, and log what it does to the EGA hardware.
oracle-hd: oracle-hd-stage
	@command -v dosbox-x >/dev/null || { echo "dosbox-x not found (brew install dosbox-x)" >&2; exit 1; }
	cd $(ORACLE_DIR) && rm -f hd.log && \
		timeout -k 5 60 env SDL_VIDEODRIVER=dummy \
		dosbox-x -conf hd.conf -nogui -fastlaunch -silent >/dev/null 2>&1 || true
	@echo "--- INT 10h and video-port activity ---"
	@grep -icE "int10|3c[0-9a-f]" $(ORACLE_DIR)/hd.log | xargs -I{} echo "matching lines: {}"

oracle: oracle-stage
	@command -v dosbox-x >/dev/null || { echo "dosbox-x not found (brew install dosbox-x)" >&2; exit 1; }
	cd $(ORACLE_DIR) && rm -f io.log && \
		timeout -k 5 45 env SDL_VIDEODRIVER=dummy \
		dosbox-x -conf io.conf -nogui -fastlaunch -silent >/dev/null 2>&1 || true
	@echo "--- INT 10h and video-port activity ---"
	@grep -icE "int10|3c[0-9a-f]" $(ORACLE_DIR)/io.log | xargs -I{} echo "matching lines: {}"
	@grep -iE "int10|3c[0-9a-f]" $(ORACLE_DIR)/io.log || echo "(none)"

reasm:
	@command -v nasm >/dev/null || { echo "nasm not found (brew install nasm)" >&2; exit 1; }
	@test -f "$(EXPANDED)/GAME.OVR" || { echo "stage the DOS data first: make data" >&2; exit 1; }
	python3 work/overlay.py work/overlay_map.json
	@for s in $$(python3 -c "import json;print(' '.join('%X'%u['seg'] for u in json.load(open('work/overlay_map.json'))))"); do \
		python3 work/reasm.py unit $$s || exit 1; \
	done
	python3 work/reasm.py start
	python3 work/rebuild.py

grab: build falcon-data
	bash tools/grab-frame.sh $(VBL) $(OUT)

# End-to-end: boot the Falcon, capture the published page, and require it to
# equal the host expansion of the same DOS source bytes. Not a similarity
# score — the two are produced from one converter and must be identical.
title-smoke: build falcon-data
	bash tools/grab-frame.sh $(VBL) $(OUT)
	python3 tools/check_frame.py $(RELEASE_DIR)/frame.bin $(EXPANDED)/TITLE.DAX 0
	@status=$$(od -An -N2 -tx2 "$(RELEASE_DIR)/PORSTAT.BIN" | tr -d '[:space:]'); \
		test "$$status" = "0000" || { echo "resource self-check reported $$status" >&2; exit 1; }
	@echo "resource self-check: STATUS_OK"

run: build falcon-data
	@test -f "$(TOS)" || { echo "TOS image not found: $(TOS)" >&2; exit 1; }
	cd $(RELEASE_DIR) && $(HATARI) --memsize $(MEMSIZE) --tos "$(TOS)" \
		--machine falcon --monitor rgb --mmu true --cpu-exact true \
		--compatible true --patch-tos true --sound off \
		--confirm-quit off por.tos

clean:
	rm -rf obj $(GAME) $(GAME_DEBUG) $(CACHE_DIR) build/*.png build/*.ppm \
		work/reasm work/rebuilt
