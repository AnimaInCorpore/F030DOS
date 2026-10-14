# Build the x86trace QEMU TCG plugin.
#
# QEMU's plugin header includes glib, and the plugin resolves qemu_plugin_*
# symbols against the QEMU binary at load time -- hence the undefined-symbol
# allowance on macOS and the import-library link on Windows. Override
# QEMU_INCLUDE if qemu-plugin.h lives elsewhere.
#
#   macOS:   make                                  (Homebrew QEMU headers)
#   Linux:   make QEMU_INCLUDE=/usr/include
#   MSYS2:   make QEMU_INCLUDE=/mingw64/include \
#                 QEMU_IMPLIB=/mingw64/lib/libqemu_plugin_api.a
#
# Windows notes: the output is x86trace.dll (run_trace.py picks that name on
# win32); QEMU only loads plugins if it was built with plugin support, and a
# DLL cannot leave symbols undefined, so it must link against the plugin-API
# import stub QEMU ships as libqemu_plugin_api.a -- point QEMU_IMPLIB at it.

UNAME := $(shell uname -s 2>/dev/null)
ifneq (,$(findstring MINGW,$(UNAME))$(findstring MSYS,$(UNAME))$(findstring CYGWIN,$(UNAME)))
PLUGIN       ?= x86trace.dll
QEMU_INCLUDE ?= /mingw64/include
QEMU_IMPLIB  ?=
LDFLAGS      := -shared $(QEMU_IMPLIB)
else ifeq ($(UNAME),Darwin)
PLUGIN       ?= x86trace.so
QEMU_INCLUDE ?= /opt/homebrew/include
LDFLAGS      := -shared -undefined dynamic_lookup
else
PLUGIN       ?= x86trace.so
QEMU_INCLUDE ?= /usr/include
LDFLAGS      := -shared
endif

CFLAGS ?= -O2 -Wall -Wextra -fPIC
GLIB   := $(shell pkg-config --cflags glib-2.0 2>/dev/null)

all: $(PLUGIN)

$(PLUGIN): x86trace.c
# $(shell ...) swallows a pkg-config failure, which used to surface later as
# a baffling `glib.h: No such file` -- fail with the real cause instead.
# (These are recipe lines, so `make clean` never trips them.)
ifeq ($(strip $(GLIB)),)
	$(error pkg-config could not find glib-2.0: install the glib headers (brew install glib / apt install libglib2.0-dev / pacman -S mingw-w64-x86_64-glib2) or pass GLIB='-I<dir>')
endif
	@test -f $(QEMU_INCLUDE)/qemu-plugin.h || { \
	    echo "qemu-plugin.h not found in $(QEMU_INCLUDE) -- set QEMU_INCLUDE=<dir>"; \
	    exit 1; }
	$(CC) $(CFLAGS) -I$(QEMU_INCLUDE) $(GLIB) $(LDFLAGS) -o $@ $<

clean:
	rm -f x86trace.so x86trace.dll

.PHONY: all clean
