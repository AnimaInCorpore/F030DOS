SHELL := /bin/bash

ROOT := $(abspath .)
SRC_DIR := src
OBJ_DIR := obj
RELEASE_DIR := release
FALCON_DATA_DIR := $(RELEASE_DIR)/WC1CACHE

VASM ?= $(ROOT)/../F030Arcade/third_party/vasm/vasmm68k_mot
VLINK ?= $(ROOT)/../F030Arcade/third_party/vlink/vlink
M68K_CC ?= m68k-elf-gcc
HOST_CC ?= cc
HATARI ?= hatari
TOS ?= $(ROOT)/../F030Arcade/third_party/tos/tos404.img
MEMSIZE ?= 14

GAME := $(RELEASE_DIR)/wc1.tos
GAME_DEBUG := $(RELEASE_DIR)/wc1_debug.tos
DSP_WIRE_SMOKE := $(RELEASE_DIR)/dspwire.tos
RESOURCE_SMOKE := $(OBJ_DIR)/resource_loader_smoke
C2P_SMOKE := $(OBJ_DIR)/c2p_smoke

ASM_SOURCES := start vbl main input front game object render hud mission resource_io c2p_fast
C_SOURCES := resources
OBJECTS := $(ASM_SOURCES:%=$(OBJ_DIR)/%.o) $(C_SOURCES:%=$(OBJ_DIR)/%.o)
INCLUDES := $(wildcard $(SRC_DIR)/inc/*.s) $(wildcard $(SRC_DIR)/dsp/*.inc) include/wc1_data.h
ASMFLAGS := -quiet -Felf -m68030
CFLAGS := -m68030 -msoft-float -O2 -ffreestanding -fno-builtin -fno-common \
	-fomit-frame-pointer -fno-pic -Wall -Wextra -Werror
LFLAGS := -b ataritos -tos-flags 1

.PHONY: all build test fixture data falcon-data falcon-data-smoke resource-smoke truecolor-smoke c2p-smoke dsp-c2p dsp-wire-smoke smoke run clean tools

all: build

build: $(GAME) $(GAME_DEBUG)

tools:
	@test -x "$(VASM)" || { echo "vasm not found: $(VASM)" >&2; exit 1; }
	@test -x "$(VLINK)" || { echo "vlink not found: $(VLINK)" >&2; exit 1; }
	@command -v "$(M68K_CC)" >/dev/null || { echo "m68k C compiler not found: $(M68K_CC)" >&2; exit 1; }

$(OBJ_DIR):
	mkdir -p $@

$(RELEASE_DIR):
	mkdir -p $@

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.s $(INCLUDES) Makefile | $(OBJ_DIR) tools
	$(VASM) $(ASMFLAGS) -o $@ -L $(OBJ_DIR)/$*.lst $<

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c Makefile | $(OBJ_DIR) tools
	$(M68K_CC) $(CFLAGS) -c -o $@ $<

$(RESOURCE_SMOKE): tools/resource_loader_smoke.c $(SRC_DIR)/resources.c | $(OBJ_DIR)
	$(HOST_CC) -std=c99 -fno-common -Wall -Wextra -Werror -o $@ tools/resource_loader_smoke.c $(SRC_DIR)/resources.c

$(C2P_SMOKE): tools/c2p_smoke.c $(SRC_DIR)/c2p.c include/wc1_c2p.h | $(OBJ_DIR)
	$(HOST_CC) -std=c99 -fno-common -Wall -Wextra -Werror -o $@ tools/c2p_smoke.c $(SRC_DIR)/c2p.c

$(GAME): $(OBJECTS) | $(RELEASE_DIR) tools
	$(VLINK) $(OBJECTS) $(LFLAGS) -e _main -s -o $@

$(GAME_DEBUG): $(OBJECTS) | $(RELEASE_DIR) tools
	$(VLINK) $(OBJECTS) $(LFLAGS) -e _main -o $@

$(OBJ_DIR)/dsp_wire_smoke.o: tools/dsp_wire_smoke.s $(SRC_DIR)/dsp_c2p_host.s $(INCLUDES) Makefile | $(OBJ_DIR) tools
	$(VASM) $(ASMFLAGS) -o $@ -L $(OBJ_DIR)/dsp_wire_smoke.lst $<

$(DSP_WIRE_SMOKE): dsp-c2p $(OBJ_DIR)/dsp_wire_smoke.o $(OBJ_DIR)/dsp_c2p_host.o | $(RELEASE_DIR) tools
	$(VLINK) $(OBJ_DIR)/dsp_wire_smoke.o $(OBJ_DIR)/dsp_c2p_host.o $(LFLAGS) -e _main -s -o $@

test:
	python3 tools/check_contracts.py

fixture:
	@test ! -e "$(RELEASE_DIR)/WC1DATA/MODULE.000" || { \
		echo "refusing to overwrite staged DOS data; run make clean first" >&2; exit 1; }
	python3 tools/make_mission_fixture.py $(RELEASE_DIR)/WC1DATA

# Install the user's own original three-disk ZIPs for local Falcon testing.
# These files are ignored under release/WC1DATA and are never source assets.
data:
	@for disk in WC_Disk1.zip WC_Disk2.zip WC_Disk3.zip; do \
		test -f "$$disk" || { echo "missing original DOS disk: $$disk" >&2; exit 1; }; \
		unzip -oq "$$disk" -d "$(RELEASE_DIR)/WC1DATA"; \
	done

# Convert only record layouts that are fully understood.  The executable uses
# this native-endian cache first, then falls back to the original DOS packet.
falcon-data:
	@test -f "$(RELEASE_DIR)/WC1DATA/INSTALL.DAT" || { echo "stage original DOS data first: make data" >&2; exit 1; }
	python3 tools/convert_data.py $(RELEASE_DIR)/WC1DATA $(FALCON_DATA_DIR)

falcon-data-smoke: falcon-data
	python3 tools/check_falcon_cache.py $(FALCON_DATA_DIR)/MISSION.BIN --source $(RELEASE_DIR)/WC1DATA

resource-smoke: $(RESOURCE_SMOKE)
	@test -f "$(RELEASE_DIR)/WC1DATA/GAME.PAL" || { echo "stage original DOS data first: make data" >&2; exit 1; }
	cd $(RELEASE_DIR) && ../$(RESOURCE_SMOKE)

truecolor-smoke: $(C2P_SMOKE)
	@# Indexed-to-RGB565 presentation contract smoke test.
	$(C2P_SMOKE)

c2p-smoke: truecolor-smoke

dsp-c2p:
	bash tools/build-dsp-c2p.sh

dsp-wire-smoke: $(DSP_WIRE_SMOKE)
	@test -f "$(TOS)" || { echo "TOS image not found: $(TOS)" >&2; exit 1; }
	rm -f $(RELEASE_DIR)/DSPWIRE.BIN
	cd $(RELEASE_DIR) && $(HATARI) --memsize 4 --tos "$(TOS)" \
		--fast-boot true --cpu-exact true --compatible true --patch-tos true \
		--machine falcon --confirm-quit off --mmu true --sound off --conout 2 \
		--benchmark --run-vbls 1000 dspwire.tos
	@test -s "$(RELEASE_DIR)/DSPWIRE.BIN" || { echo "DSP wire test did not report a status" >&2; exit 1; }
	@result=$$(od -An -N2 -tx2 "$(RELEASE_DIR)/DSPWIRE.BIN" | tr -d '[:space:]'); \
		test "$$result" = "0000" || { echo "DSP worker self-test failed (status/index/actual/expected):" >&2; od -An -tx2 "$(RELEASE_DIR)/DSPWIRE.BIN" >&2; exit 1; }
	@echo "WC1 DSP C2P wire: PASS"

smoke: build
	@test -f "$(TOS)" || { echo "TOS image not found: $(TOS)" >&2; exit 1; }
	cd $(RELEASE_DIR) && $(HATARI) --memsize $(MEMSIZE) --tos "$(TOS)" \
		--fast-boot true --cpu-exact true --compatible true --patch-tos true \
		--frameskips 0 --monitor rgb --machine falcon --confirm-quit off --mmu true \
		--benchmark --run-vbls 600 --sound off --disable-video on wc1.tos

run: build
	@test -f "$(TOS)" || { echo "TOS image not found: $(TOS)" >&2; exit 1; }
	cd $(RELEASE_DIR) && $(HATARI) --memsize $(MEMSIZE) --tos "$(TOS)" \
		--fast-boot true --cpu-exact true --compatible true --patch-tos true \
		--frameskips 0 --monitor rgb --machine falcon --mmu true wc1.tos

clean:
	rm -rf $(OBJ_DIR) $(RELEASE_DIR)
