SHELL := /bin/sh

ROOT := $(abspath .)
VASM ?= $(ROOT)/../F030Arcade/third_party/vasm/vasmm68k_mot
VLINK ?= $(ROOT)/../F030Arcade/third_party/vlink/vlink
VASM_MAC ?= $(ROOT)/../F030Arcade/third_party/chorensha/tools/vasmm68k_mot_mac
VLINK_MAC ?= $(ROOT)/../F030Arcade/third_party/chorensha/tools/vlink_mac
TOS ?= $(ROOT)/../F030Arcade/third_party/tos/tos404.img

BUILD_DIR := build/falcon
TARGET_CPU ?= -m68030
ASMFLAGS := -quiet -Felf
LFLAGS := -b ataritos -tos-flags 1 -e _main

PRESENT_OBJ := $(BUILD_DIR)/present.o
SMOKE_OBJ := $(BUILD_DIR)/smoke.o
SMOKE_TOS := $(BUILD_DIR)/uw2-falcon-smoke.tos
SMOKE_MAP := $(BUILD_DIR)/uw2-falcon-smoke.map

.PHONY: all assemble smoke check hatari-smoke clean tools

all: check

tools:
	@test -x "$(VASM)" || test -x "$(VASM_MAC)" || { echo "vasm not found" >&2; exit 1; }
	@test -x "$(VLINK)" || test -x "$(VLINK_MAC)" || { echo "vlink not found" >&2; exit 1; }

$(BUILD_DIR):
	mkdir -p $@

$(PRESENT_OBJ): src/target/falcon/present.s src/target/falcon/inc/falcon.s src/common/inc/uw2.s Makefile | $(BUILD_DIR) tools
	@asm="$(VASM)"; test -x "$$asm" || asm="$(VASM_MAC)"; \
	"$$asm" $(ASMFLAGS) $(TARGET_CPU) -I src/target/falcon -o $@ -L $(BUILD_DIR)/present.lst $<

$(SMOKE_OBJ): src/target/falcon/smoke.s src/target/falcon/inc/falcon.s src/common/inc/uw2.s Makefile | $(BUILD_DIR) tools
	@asm="$(VASM)"; test -x "$$asm" || asm="$(VASM_MAC)"; \
	"$$asm" $(ASMFLAGS) $(TARGET_CPU) -I src/target/falcon -o $@ -L $(BUILD_DIR)/smoke.lst $<

$(SMOKE_TOS): $(SMOKE_OBJ) $(PRESENT_OBJ) | tools
	@link="$(VLINK)"; test -x "$$link" || link="$(VLINK_MAC)"; \
	"$$link" $(SMOKE_OBJ) $(PRESENT_OBJ) $(LFLAGS) -M > $(SMOKE_MAP) -o $@

assemble: $(PRESENT_OBJ) $(SMOKE_OBJ)

smoke: $(SMOKE_TOS)
	@test -f "$(TOS)" || { echo "TOS image not found: $(TOS)" >&2; exit 1; }
	@echo "assembled Falcon smoke harness: $(SMOKE_TOS)"
	@echo "run Hatari with --machine falcon --tos $(TOS) and inspect exported smoke symbols"

hatari-smoke: $(SMOKE_TOS)
	python3 work/run_falcon_smoke.py --build-dir $(BUILD_DIR) --hatari "$${HATARI:-/opt/homebrew/bin/hatari}" --tos "$${TOS:-$(TOS)}"

check: $(SMOKE_TOS)
	python3 work/check_falcon_present.py --listing build/falcon/present.lst --map build/falcon/uw2-falcon-smoke.map

clean:
	rm -rf build/falcon
