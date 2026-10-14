#!/usr/bin/env python3
"""Inspect the FORM/EMC2 level resource container."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pakinfo import parse_pak


@dataclass(frozen=True)
class Chunk:
    tag: str
    data: bytes


@dataclass(frozen=True)
class BytecodeInfo:
    data_words: int
    order_slots: int
    valid_functions: int
    sentinel_functions: int
    entry_opcodes: Counter[int]
    reachable_instructions: int
    branch_targets: int
    system_calls: Counter[int]
    call_cleanup_arities: Counter[tuple[int, int]]
    call_stack_depths: Counter[tuple[int, int]]


OPCODE_NAMES = (
    "jmp", "setRetValue", "pushRetOrPos", "push", "push", "pushReg",
    "pushBPNeg", "pushBPAdd", "popRetOrPos", "popReg", "popBPNeg",
    "popBPAdd", "addSP", "subSP", "sysCall", "ifNotJmp", "negate",
    "eval", "setRetAndJmp",
)

# Cross-reference names for the LoL-specific dispatch table. The numeric order
# is the order used by ScummVM's LoLEngine::setupOpcodeTable(); the local DOS
# corpus still needs native call-site confirmation before these names become
# Falcon implementation contracts.
SYSTEM_CALL_NAMES = (
    "setWallType", "getWallType", "drawScene", "rollDice",
    "moveParty", "unimplemented_05", "delay", "setGameFlag",
    "testGameFlag", "loadLevelGraphics", "loadBlockProperties", "loadMonsterShapes",
    "deleteHandItem", "allocItemPropertiesBuffer", "setItemProperty", "makeItem",
    "placeMoveLevelItem", "createLevelItem", "getItemPara", "getCharacterStat",
    "setCharacterStat", "loadLevelShapes", "closeLevelShapeFile", "unimplemented_17",
    "loadDoorShapes", "initAnimStruct", "playAnimationPart", "freeAnimStruct",
    "getDirection", "characterSurpriseFeedback", "setMusicTrack", "setSequenceButtons",
    "setDefaultButtonState", "checkRectForMousePointer", "clearDialogueField", "setupBackgroundAnimationPart",
    "startBackgroundAnimation", "hideMouse", "showMouse", "fadeToBlack",
    "fadePalette", "loadBitmap", "stopBackgroundAnimation", "unimplemented_2B",
    "unimplemented_2C", "getGlobalScriptVar", "setGlobalScriptVar", "getGlobalVar",
    "setGlobalVar", "triggerDoorSwitch", "checkEquippedItemScriptFlags", "setDoorState",
    "updateBlockAnimations", "assignLevelDecorationShape", "resetBlockShapeAssignment", "copyRegion",
    "initMonster", "fadeClearSceneWindow", "fadeSequencePalette", "redrawPlayfield",
    "loadNewLevel", "getNearestMonsterFromCharacter", "dummy_3E", "loadMonsterProperties",
    "battleHitSkillTest", "inflictDamage", "unimplemented_42", "unimplemented_43",
    "moveMonster", "setupDialogueButtons", "giveTakeMoney", "checkMoney",
    "setScriptTimer", "createHandItem", "playAttackSound", "addRemoveCharacter",
    "giveItem", "unimplemented_4D", "loadTimScript", "runTimScript",
    "releaseTimScript", "initSceneWindowDialogue", "restoreAfterSceneWindowDialogue", "getItemInHand",
    "checkMagic", "giveItemToMonster", "loadLangFile", "playSoundEffect",
    "processDialogue", "stopTimScript", "getWallFlags", "changeMonsterStat",
    "getMonsterStat", "releaseMonsterShapes", "playCharacterScriptChat", "update",
    "playEnvironmentalSfx", "healCharacter", "drawExitButton", "loadSoundFile",
    "playMusicTrack", "deleteMonstersFromBlock", "countBlockItems", "characterSkillTest",
    "countAllMonsters", "playEndSequence", "stopPortraitSpeechAnim", "setPaletteBrightness",
    "calcInflictableDamage", "getInflictedDamage", "checkForCertainPartyMember", "printMessage",
    "deleteLevelItem", "calcInflictableDamagePerItem", "distanceAttack", "removeCharacterEffects",
    "checkInventoryFull", "moveBlockObjects", "unimplemented_76", "unimplemented_77",
    "addSpellToScroll", "playDialogueText", "playDialogueTalkText", "checkMonsterTypeHostility",
    "setNextFunc", "dummy_7D", "unimplemented_7E", "suspendMonster",
    "setScriptTextParameter", "triggerEventOnMouseButtonClick", "printWindowText", "countSpecificMonsters",
    "updateBlockAnimations2", "checkPartyForItemType", "blockDoor", "resetTimDialogueState",
    "getItemOnPos", "removeLevelItem", "savePage5", "restorePage5",
    "initDialogueSequence", "restoreAfterDialogueSequence", "setSpecialSceneButtons", "restoreButtonsAfterSpecialScene",
    "unimplemented_90", "unimplemented_91", "prepareSpecialScene", "restoreAfterSpecialScene",
    "assignCustomSfx", "unimplemented_95", "findAssignedMonster", "checkBlockForMonster",
    "crossFadeRegion", "calcCoordinatesAddDirectionOffset", "resetPortraitsAndDisableSysTimer", "enableSysTimer",
    "checkNeedSceneRestore", "getNextActiveCharacter", "paralyzePoisonCharacter", "drawCharPortrait",
    "removeInventoryItem", "unimplemented_A1", "unimplemented_A2", "getAnimationLastPart",
    "assignSpecialGuiShape", "findInventoryItem", "restoreFadePalette", "calcNewBlockPosition",
    "getSelectedCharacter", "setHandItem", "drinkBezelCup", "changeItemTypeOrFlag",
    "placeInventoryItemInHand", "castSpell", "pitDrop", "increaseSkill",
    "paletteFlash", "restoreMagicShroud", "dummy_B2", "disableControls",
    "enableControls", "shakeScene", "gasExplosion", "calcNewBlockPosition",
    "crossFadeScene", "updateDrawPage2", "setMouseCursor", "characterSays",
    "queueSpeech", "getItemPrice", "getLanguage", "dummy_BF",
)


def parse_text_table(data: bytes) -> list[str]:
    """Parse the big-endian offset table used by EMC2 TEXT chunks."""
    if len(data) < 2:
        raise ValueError("EMC2 TEXT chunk is too small")
    first_offset = struct.unpack_from(">H", data)[0]
    if first_offset == 0 or first_offset & 1:
        raise ValueError("invalid EMC2 TEXT first offset")
    slot_count = first_offset // 2
    if slot_count * 2 > len(data):
        raise ValueError("EMC2 TEXT offset table does not fit")
    offsets = list(struct.unpack_from(f">{slot_count}H", data))
    if offsets[0] != slot_count * 2:
        raise ValueError("EMC2 TEXT first offset is not the table size")
    if any(offset < first_offset or offset >= len(data) for offset in offsets):
        raise ValueError("EMC2 TEXT offset is outside its chunk")
    if any(left >= right for left, right in zip(offsets, offsets[1:])):
        raise ValueError("EMC2 TEXT offsets are not strictly increasing")
    strings: list[str] = []
    for offset in offsets:
        end = data.find(b"\0", offset)
        if end < 0:
            raise ValueError("EMC2 TEXT string is not NUL-terminated")
        strings.append(data[offset:end].decode("cp437", "replace"))
    if data[-1] != 0:
        raise ValueError("EMC2 TEXT does not end with a NUL")
    return strings


def decode_instruction(data: tuple[int, ...], ip: int) -> tuple[int, int, int]:
    """Decode one EMC instruction as (opcode, parameter, word_length)."""
    if ip < 0 or ip >= len(data):
        raise ValueError(f"EMC2 instruction offset 0x{ip:X} is outside DATA")
    code = data[ip]
    opcode = (code >> 8) & 0x1F
    if code & 0x8000:
        opcode = 0
        parameter = code & 0x7FFF
        length = 1
    elif code & 0x4000:
        parameter = code & 0xFF
        if parameter & 0x80:
            parameter -= 0x100
        length = 1
    elif code & 0x2000:
        if ip + 1 >= len(data):
            raise ValueError("EMC2 extended instruction parameter is truncated")
        parameter = data[ip + 1]
        length = 2
    else:
        parameter = 0
        length = 1
    return opcode, parameter, length


def walk_bytecode(
    data: tuple[int, ...], entries: list[int]
) -> tuple[
    set[int],
    set[int],
    Counter[int],
    Counter[tuple[int, int]],
    Counter[tuple[int, int]],
]:
    """Walk statically resolvable paths and track relative stack depth.

    The depth is relative to each ORDR entry.  Values already present on the
    caller's stack are intentionally not guessed; this keeps the witness
    about script-local pushes/pops while preserving the native interpreter's
    dynamic call/return boundary.
    """
    pending = [(entry, 0) for entry in entries]
    seen_states: set[tuple[int, int]] = set()
    visited: set[int] = set()
    branch_targets: set[int] = set()
    system_calls: Counter[int] = Counter()
    call_cleanup_arities: Counter[tuple[int, int]] = Counter()
    call_stack_depths: Counter[tuple[int, int]] = Counter()
    while pending:
        ip, stack_depth = pending.pop()
        state = (ip, stack_depth)
        if state in seen_states:
            continue
        seen_states.add(state)
        opcode, parameter, length = decode_instruction(data, ip)
        if opcode >= len(OPCODE_NAMES):
            raise ValueError(f"EMC2 opcode {opcode} is outside the core interpreter")
        if opcode in (2, 8) and parameter not in (0, 1):
            raise ValueError(f"EMC2 opcode {opcode} has invalid parameter {parameter}")
        if opcode == 16 and parameter not in (0, 1, 2):
            raise ValueError(f"EMC2 negate has invalid parameter {parameter}")
        if opcode == 17 and not 0 <= parameter <= 17:
            raise ValueError(f"EMC2 eval has invalid parameter {parameter}")
        new_instruction = ip not in visited
        visited.add(ip)

        if opcode == 14:
            # The interpreter casts its signed parameter to uint8 for dispatch.
            call_id = parameter & 0xFF
            # Preserve the original instruction-level corpus counts even when
            # a control-flow join reaches one call site with multiple abstract
            # stack depths.
            if new_instruction:
                system_calls[call_id] += 1
            call_stack_depths[(call_id, stack_depth)] += 1
            if new_instruction:
                next_ip = ip + length
                if next_ip < len(data):
                    next_opcode, next_parameter, _ = decode_instruction(data, next_ip)
                    if next_opcode == 12:
                        call_cleanup_arities[(call_id, next_parameter)] += 1

        # Stack effects mirror the 19 interpreter operations.  A dynamic
        # return/tail-call has no statically known successor, so it is handled
        # below before its stack effect would need to be modelled.
        if opcode == 2:
            if parameter == 0:
                stack_delta = 1
            elif parameter == 1:
                stack_delta = 2
            else:
                continue
        elif opcode in (3, 4, 5, 6, 7):
            stack_delta = 1
        elif opcode == 8:
            if parameter == 1:
                # Return address and base pointer are dynamic stack values.
                continue
            stack_delta = -1
        elif opcode in (9, 10, 11):
            stack_delta = -1
        elif opcode == 12:
            stack_delta = -parameter
        elif opcode == 13:
            stack_delta = parameter
        elif opcode == 15:
            stack_delta = -1
        elif opcode == 17:
            stack_delta = -1
        elif opcode == 18:
            # The target is also a dynamic stack value.
            continue
        else:
            stack_delta = 0
        next_stack_depth = stack_depth + stack_delta

        if opcode == 0:
            target = parameter
            branch_targets.add(target)
            pending.append((target, next_stack_depth))
        elif opcode == 15:
            target = parameter & 0x7FFF
            branch_targets.add(target)
            pending.extend(((target, next_stack_depth), (ip + length, next_stack_depth)))
        else:
            pending.append((ip + length, next_stack_depth))
    return (
        visited,
        branch_targets,
        system_calls,
        call_cleanup_arities,
        call_stack_depths,
    )


def parse_bytecode(ordr_data: bytes, data_chunk: bytes) -> BytecodeInfo:
    """Validate LoL EMC word arrays, entries and static control-flow paths."""
    if len(ordr_data) % 2 or len(data_chunk) % 2:
        raise ValueError("EMC2 ORDR/DATA chunks must contain whole words")
    order_slots = len(ordr_data) // 2
    data_words = len(data_chunk) // 2
    order = struct.unpack(f">{order_slots}H", ordr_data)
    data = struct.unpack(f">{data_words}H", data_chunk)
    valid = [offset for offset in order if offset != 0xFFFF]
    if any(offset + 1 >= data_words for offset in valid):
        raise ValueError("EMC2 ORDR function offset is outside DATA")

    entry_opcodes: Counter[int] = Counter()
    for offset in valid:
        opcode, _, _ = decode_instruction(data, offset + 1)
        if opcode >= len(OPCODE_NAMES):
            raise ValueError(f"EMC2 opcode {opcode} is outside the core interpreter")
        entry_opcodes[opcode] += 1
    (
        visited,
        branch_targets,
        system_calls,
        call_cleanup_arities,
        call_stack_depths,
    ) = walk_bytecode(
        data, [offset + 1 for offset in valid]
    )
    return BytecodeInfo(
        data_words,
        order_slots,
        len(valid),
        order_slots - len(valid),
        entry_opcodes,
        len(visited),
        len(branch_targets),
        system_calls,
        call_cleanup_arities,
        call_stack_depths,
    )


def parse_emc2(data: bytes) -> tuple[int, list[Chunk]]:
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] != b"EMC2":
        raise ValueError("not a FORM/EMC2 resource")
    declared_size = struct.unpack_from(">I", data, 4)[0]
    if declared_size != len(data):
        raise ValueError(f"FORM size 0x{declared_size:X} != file size 0x{len(data):X}")

    chunks: list[Chunk] = []
    pos = 12
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("EMC2 chunk header is truncated")
        tag = data[pos:pos + 4].decode("ascii")
        size = struct.unpack_from(">I", data, pos + 4)[0]
        start = pos + 8
        end = start + size
        if end > len(data):
            raise ValueError(f"EMC2 {tag} chunk extends past the file")
        chunks.append(Chunk(tag, data[start:end]))
        pos = end + (size & 1)
        if pos > len(data) or (size & 1 and data[end] != 0):
            raise ValueError(f"EMC2 {tag} chunk has invalid padding")
    if pos != len(data) or [chunk.tag for chunk in chunks] not in (["ORDR", "TEXT", "DATA"], ["ORDR", "DATA"]):
        raise ValueError("unexpected EMC2 chunk sequence")
    if len(chunks) == 3:
        parse_text_table(chunks[1].data)
    return declared_size, chunks


def select_payload(path: Path, entry_name: str | None) -> tuple[bytes, str]:
    data = path.read_bytes()
    try:
        entries, _ = parse_pak(data)
    except (ValueError, struct.error):
        if entry_name:
            raise ValueError("--entry requires a PAK input")
        return data, path.name
    if not entry_name:
        raise ValueError("PAK input requires --entry")
    match = next((entry for entry in entries if entry.name.upper() == entry_name.upper()), None)
    if match is None:
        raise ValueError(f"PAK entry not found: {entry_name}")
    return data[match.offset:match.offset + match.size], match.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--entry", help="PAK member to inspect")
    parser.add_argument("--calls", action="store_true", help="show observed addSP syscall cleanup arities")
    parser.add_argument(
        "--stack",
        action="store_true",
        help="show script-local stack depths at syscall call sites",
    )
    args = parser.parse_args()
    try:
        data, label = select_payload(args.path, args.entry)
        _, chunks = parse_emc2(data)
        bytecode = parse_bytecode(chunks[0].data, chunks[-1].data)
        text_count = len(parse_text_table(chunks[1].data)) if len(chunks) == 3 else 0
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
    chunk_names = ",".join(chunk.tag for chunk in chunks)
    entry_names = ", ".join(f"{OPCODE_NAMES[opcode]}={count}" for opcode, count in sorted(bytecode.entry_opcodes.items()))
    system_call_names = ", ".join(
        f"0x{call:02X}/{SYSTEM_CALL_NAMES[call]}={count}"
        for call, count in sorted(bytecode.system_calls.items())
    )
    print(f"{label}: {len(data)} bytes; FORM/EMC2=PASS; chunks={chunk_names}; TEXT slots={text_count}")
    print(f"  DATA words={bytecode.data_words}; ORDR slots={bytecode.order_slots}; functions={bytecode.valid_functions}; sentinels={bytecode.sentinel_functions}; entry opcodes={entry_names}")
    print(f"  reachable instructions={bytecode.reachable_instructions}; branch targets={bytecode.branch_targets}; system calls={system_call_names}")
    if args.calls:
        grouped: dict[int, Counter[int]] = {}
        for (call, arity), count in bytecode.call_cleanup_arities.items():
            grouped.setdefault(call, Counter())[arity] += count
        print("  observed syscall cleanup arities:")
        for call in sorted(grouped):
            arities = ", ".join(
                f"{arity} ({count})" for arity, count in sorted(grouped[call].items())
            )
            print(f"    0x{call:02X}/{SYSTEM_CALL_NAMES[call]}: addSP {arities}")
    if args.stack:
        grouped: dict[int, Counter[int]] = {}
        for (call, depth), count in bytecode.call_stack_depths.items():
            grouped.setdefault(call, Counter())[depth] += count
        print("  observed syscall stack depths (relative to ORDR entry):")
        for call in sorted(grouped):
            depths = ", ".join(
                f"{depth} ({count})" for depth, count in sorted(grouped[call].items())
            )
            print(f"    0x{call:02X}/{SYSTEM_CALL_NAMES[call]}: {depths}")
    for chunk in chunks:
        print(f"  {chunk.tag}: {len(chunk.data)} bytes")


if __name__ == "__main__":
    main()
