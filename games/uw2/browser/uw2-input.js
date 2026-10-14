/*
 * UW2 BIOS keyboard boundary.
 *
 * A browser key is only converted to the PC BIOS AX word and queued. The
 * recovered DOS keyboard routine is the only reader of that queue.
 */
(function (global) {
  "use strict";

  var SCAN_CODES = {
    Escape: 0x01,
    Minus: 0x0c,
    Equal: 0x0d,
    Backspace: 0x0e,
    Tab: 0x0f,
    BracketLeft: 0x1a,
    BracketRight: 0x1b,
    Enter: 0x1c,
    ControlLeft: 0x1d,
    Semicolon: 0x27,
    Quote: 0x28,
    Backquote: 0x29,
    ShiftLeft: 0x2a,
    Backslash: 0x2b,
    ShiftRight: 0x36,
    NumpadMultiply: 0x37,
    AltLeft: 0x38,
    Space: 0x39,
    CapsLock: 0x3a,
    F1: 0x3b,
    F2: 0x3c,
    F3: 0x3d,
    F4: 0x3e,
    F5: 0x3f,
    F6: 0x40,
    F7: 0x41,
    F8: 0x42,
    F9: 0x43,
    F10: 0x44,
    NumLock: 0x45,
    ScrollLock: 0x46,
    Numpad7: 0x47,
    Numpad8: 0x48,
    Numpad9: 0x49,
    NumpadSubtract: 0x4a,
    Numpad4: 0x4b,
    Numpad5: 0x4c,
    Numpad6: 0x4d,
    NumpadAdd: 0x4e,
    Numpad1: 0x4f,
    Numpad2: 0x50,
    Numpad3: 0x51,
    Numpad0: 0x52,
    NumpadDecimal: 0x53,
    F11: 0x57,
    F12: 0x58
  };

  var EXTENDED_WORDS = {
    Home: 0x4700,
    ArrowUp: 0x4800,
    PageUp: 0x4900,
    ArrowLeft: 0x4b00,
    ArrowRight: 0x4d00,
    End: 0x4f00,
    ArrowDown: 0x5000,
    PageDown: 0x5100,
    Insert: 0x5200,
    Delete: 0x5300
  };

  function addScanCodes(names, first) {
    for (var i = 0; i < names.length; i += 1) {
      SCAN_CODES[names[i]] = first + i;
    }
  }

  addScanCodes(["Digit1", "Digit2", "Digit3", "Digit4", "Digit5",
    "Digit6", "Digit7", "Digit8", "Digit9", "Digit0"], 0x02);
  addScanCodes(["KeyQ", "KeyW", "KeyE", "KeyR", "KeyT", "KeyY",
    "KeyU", "KeyI", "KeyO", "KeyP"], 0x10);
  addScanCodes(["KeyA", "KeyS", "KeyD", "KeyF", "KeyG", "KeyH",
    "KeyJ", "KeyK", "KeyL"], 0x1e);
  addScanCodes(["KeyZ", "KeyX", "KeyC", "KeyV", "KeyB", "KeyN",
    "KeyM"], 0x2c);

  function controlCharacter(event) {
    if (!event.ctrlKey || event.key.length !== 1) {
      return null;
    }
    var upper = event.key.toUpperCase();
    return upper >= "A" && upper <= "Z" ? upper.charCodeAt(0) - 64 : null;
  }

  function browserKeyWord(event) {
    var extended = EXTENDED_WORDS[event.key];
    if (extended !== undefined) {
      return extended;
    }
    var scan = SCAN_CODES[event.code];
    if (scan === undefined) {
      return null;
    }
    var ascii = controlCharacter(event);
    if (ascii === null) {
      if (event.key === "Enter") {
        ascii = 0x0d;
      } else if (event.key === "Escape") {
        ascii = 0x1b;
      } else if (event.key === "Backspace") {
        ascii = 0x08;
      } else if (event.key === "Tab") {
        ascii = 0x09;
      } else if (event.key === " ") {
        ascii = 0x20;
      } else if (event.key.length === 1 && event.key.charCodeAt(0) < 0x80) {
        ascii = event.key.charCodeAt(0);
      } else {
        ascii = 0;
      }
    }
    return ((scan & 0xff) << 8) | (ascii & 0xff);
  }

  function DosInputDriver() {
    this.keyboard = [];
  }

  DosInputDriver.prototype.queueDosKeyWord = function (word) {
    this.keyboard.push(word & 0xffff);
  };

  DosInputDriver.prototype.queueKeyboardEvent = function (event) {
    var word = browserKeyWord(event);
    if (word !== null) {
      this.queueDosKeyWord(word);
    }
    return word;
  };

  /* DOS: BIOS INT 16h AH=1/AH=0; record: uw2_input_keyboard_driver. */
  DosInputDriver.prototype.bios16 = function (ah) {
    if (ah === 1) {
      return {
        available: this.keyboard.length !== 0,
        ax: this.keyboard.length ? this.keyboard[0] : 0
      };
    }
    if (ah === 0) {
      return {
        available: this.keyboard.length !== 0,
        ax: this.keyboard.length ? this.keyboard.shift() : 0
      };
    }
  };

  /* DOS: fn_24358 at 0x24358; record: uw2_input_keyboard_driver. */
  DosInputDriver.prototype.keyboardRoutine24358 = function () {
    var checked = this.bios16(1);
    return checked.available ? this.bios16(0).ax : 0;
  };

  global.UW2Input = {
    driver: new DosInputDriver()
  };
}(window));
