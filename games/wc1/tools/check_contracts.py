#!/usr/bin/env python3
"""Static checks for the first DOS-to-Falcon port seam."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def const(text: str, name: str) -> int:
    match = re.search(rf"^\s*{name}\s*=\s*(\$?[0-9a-fA-F]+)", text, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing assembler constant {name}")
    value = match.group(1)
    return int(value[1:], 16) if value.startswith("$") else int(value)


def main() -> None:
    asm = (ROOT / "src/inc/wc1.s").read_text()
    assert const(asm, "GAME_WIDTH") == 320
    assert const(asm, "GAME_HEIGHT") == 200
    assert const(asm, "FRAME_WIDTH") == 320
    assert const(asm, "FRAME_HEIGHT") == 200
    assert "CHUNKY_BYTES" in asm and "FRAME_LINE_WORDS" in asm and \
        "FRAME_STRIDE    = FRAME_WIDTH*2" in asm, \
        "Falcon presentation must retain indexed and RGB565 layouts"
    assert const(asm, "FIX_SHIFT") == 8, \
        "WC1 world vectors use the DOS 24.8 fixed-point representation"
    assert const(asm, "MISSION_ARCHIVE_LOGICAL") == 16
    assert const(asm, "ORIGIN_LZW_MAX_CODES") == 0x1000
    assert const(asm, "FALCON_CACHE_HEADER_BYTES") == 0x40
    assert const(asm, "FALCON_MISSION_NAV_BYTES") == 0x4E
    assert const(asm, "FALCON_MISSION_SHIP_BYTES") == 0x2C
    assert const(asm, "INPUT_ACCEPT") == 5
    assert const(asm, "MOUSE_BUTTON_LEFT") == 0

    input_source = (ROOT / "src/input.s").read_text()
    for seam in (
        "input_init", "input_shutdown", "input_mouse_handler",
        "input_mouse_dx", "input_mouse_dy",
        "input_mouse_buttons", "input_mouse_x", "input_mouse_y",
        "input_mouse_pending_dx", "input_mouse_pending_dy",
        "input_saved_mouse_vector", "Initmouse", "Kbdvbase",
    ):
        assert seam in input_source, f"missing Falcon IKBD mouse seam: {seam}"

    game_input = (ROOT / "src/game.s").read_text()
    for seam in ("input_mouse_dx", "input_mouse_dy", "object_yaw"):
        assert seam in game_input, f"missing mouse flight control seam: {seam}"

    data = (ROOT / "include/wc1_data.h").read_text()
    assert "int32_t x;" in data and "int32_t y;" in data and "int32_t z;" in data, \
        "mission vectors must retain the DOS 32-bit fixed-point fields"
    for name in (
        "MissionHeaderDisk_size_must_be_0x18",
        "MissionNavPointDisk_size_must_be_0x4d",
        "MissionObjectiveDisk_size_must_be_0x40",
        "MissionShipDisk_size_must_be_0x2a",
    ):
        assert name in data, f"missing DOS record assertion {name}"

    for source in ("main.c", "cmpgn.c", "nav.c", "brains.c", "logic.c", "ship.c", "disk.c"):
        assert (ROOT.parent / "wc1-re/src" / source).exists(), f"missing wc1-re reference: {source}"

    mission = (ROOT / "src/mission.s").read_text()
    for symbol in (
        "mission_load_cache",
        "mission_read_cache",
        "mission_decode_header_be",
        "mission_decode_nav_be",
        "mission_decode_objectives_be",
        "mission_decode_ships_be",
        "WC1CACHE\\MISSION.BIN",
        "mission_read_lzw",
        "mission_lzw_decode",
        "mission_lzw_read_code",
        "mission_lzw_expand_code",
    ):
        assert symbol in mission, f"missing Origin LZW decoder seam: {symbol}"

    objects = (ROOT / "src/object.s").read_text()
    for seam in (
        "objects_spawn_nav",
        "objects_set_action_sphere",
        "objects_apply_nav_triggers",
        "mission_nav_ships",
        "mission_nav_triggers",
        "set_up_action_sphere",
        "object_pitch",
        "object_yaw",
        "object_roll",
        "resource_flight_combat_reset",
        "resource_flight_combat_spawn",
    ):
        assert seam in objects, f"missing nav-object seam: {seam}"

    game = (ROOT / "src/game.s").read_text()
    for seam in (
        "game_update_action_sphere",
        "game_service_resources",
        "game_resource_nav_pending",
        "game_current_nav",
        "game_target_object",
        "game_update_target",
        "resource_flight_combat_tick",
        "resource_flight_combat_housekeep",
        "resource_flight_background_reset",
        "resource_flight_background_tick",
        "mission_nav_radius",
        "ReleaseStaleNavTarget()",
    ):
        assert seam in game, f"missing nav-transition seam: {seam}"

    for seam in ("mission_nav_triggers", "mission_nav_preload_types"):
        assert seam in mission, f"missing decoded nav field: {seam}"
    for seam in ("mission_ship_pitch", "mission_ship_yaw", "mission_ship_roll"):
        assert seam in mission, f"missing decoded mission orientation field: {seam}"

    vbl = (ROOT / "src/vbl.s").read_text()
    for seam in (
        "saved_vbl_registers",
        "saved_vbl_return",
        ".after_tos_vbl",
        "movec   vbr,d0",
        "vbl_vector_base",
        ".after_tos_vbl",
        ".publish_pending",
        "FalconVblPresentation.md",
    ):
        assert seam in vbl, f"missing VBL foreground-preservation seam: {seam}"
    assert (ROOT / "analysis/functions/FalconVblPresentation.md").exists(), \
        "missing Falcon VBL platform-boundary record"

    grab = (ROOT / "tools/grab-frame.sh").read_text()
    for seam in (
        "HATARI_INPUT_EVENTS",
        "HATARI_KEY_EVENTS",
        "--cmd-fifo",
        "hatari-debug evaluate VBL",
        "hatari-event $event_action",
        "leftdown|leftup",
        "hatari-event mousemove",
        "info basepage",
    ):
        assert seam in grab, f"missing emulated-VBL flight capture seam: {seam}"

    main = (ROOT / "src/main.s").read_text()
    for seam in (
        "game_service_resources", "resource_load_title", "front_run",
        "render_screen", "wc1_indexed_to_rgb565", "resource_palette_rgb565",
    ):
        assert seam in main, f"missing title-to-flight seam: {seam}"
    assert "game_service_resources" in main, \
        "nav resource service must run outside the masked frame update"

    front = (ROOT / "src/front.s").read_text()
    for seam in (
        "front_run", "resource_draw_intro_frame", "resource_draw_title_screen",
        "FRONT_PHASE_OPENING", "FRONT_PHASE_LOGO", "FRONT_PHASE_CREDIT",
        "FRONT_PHASE_MENU", "INPUT_ACCEPT", "flip_pages", "render_screen",
        "wc1_indexed_to_rgb565", "resource_palette_rgb565",
        "front_catch_up", "front_advance_elapsed",
    ):
        assert seam in front, f"missing Falcon title-menu seam: {seam}"

    fixture = (ROOT / "tools/make_mission_fixture.py").read_text()
    assert "bytes((1, 2, 16))" in fixture, \
        "fixture must use MODULE.000's on-disk INSTALL.DAT record id"

    converter = (ROOT / "tools/convert_data.py").read_text()
    for seam in ("WCF1", "decode_origin_lzw", "convert_nav", "convert_ship"):
        assert seam in converter, f"missing Falcon cache conversion seam: {seam}"
    makefile = (ROOT / "Makefile").read_text()
    assert "falcon-data-smoke" in makefile and "WC1CACHE" in makefile, \
        "missing native-endian Falcon cache build target"
    assert "truecolor-smoke" in makefile and "RGB565" in makefile, \
        "missing indexed-to-RGB565 conversion build target"
    assert "c2p_fast" in makefile and "C_SOURCES := resources" in makefile, \
        "Falcon target must use the native 68030 RGB565 presentation seam"
    assert "dsp-wire-smoke" in makefile and "DSP_WIRE_SMOKE" in makefile, \
        "missing real DSP host-port verification target"

    c2p_header = (ROOT / "include/wc1_c2p.h").read_text()
    resources = (ROOT / "src/resources.c").read_text()
    for seam in (
        "WC1_TRUECOLOUR_BYTES",
        "WC1_RGB565_PALETTE_ENTRIES",
        "wc1_indexed_to_rgb565",
    ):
        assert seam in c2p_header, f"missing RGB565 presentation seam: {seam}"
    c2p = (ROOT / "src/c2p.c").read_text()
    assert "write_be16" in c2p and "palette[indexed[pixel]]" in c2p, \
        "true-colour reference must define big-endian RGB565 expansion"
    c2p_fast = (ROOT / "src/c2p_fast.s").read_text()
    for seam in (
        "c2p_present_rgb565", "move.w  d0,(a1)+", "(a2,d0.w*2)",
        "(CHUNKY_BYTES/8)-1", "N/A - platform replacement",
    ):
        assert seam in c2p_fast, \
            f"missing native 68030 RGB565 presentation optimization: {seam}"
    assert (ROOT / "analysis/functions/c2p-present.md").exists(), \
        "missing target presentation function record"
    for seam in (
        "build_transform_axis_maps", "draw_transform_axis_pixels",
        "draw_shape_frame_axis_aligned", "resource_intro_rendering",
    ):
        assert seam in resources, \
            f"missing cache-contained zero-angle renderer seam: {seam}"
    assert (ROOT / "analysis/functions/ShapeTransformAxis.md").exists(), \
        "missing transformed-shape optimization record"

    dsp_proto = (ROOT / "src/dsp/c2pproto.inc").read_text()
    for seam in (
        "C2P_PROTOCOL_VERSION", "C2P_CMD_PING", "C2P_CMD_LOOPBACK", "C2P_CMD_SCANLINE",
        "C2P_REPLY_HELLO", "C2P_REPLY_SCANLINE", "C2P_SCANLINE_WORDS      EQU     107",
    ):
        assert seam in dsp_proto, f"missing DSP C2P protocol seam: {seam}"
    dsp_worker = (ROOT / "src/dsp/wc1c2p.asm").read_text()
    for seam in ("c2p_ping", "c2p_loopback", "c2p_scanline", "c2p_convert_cells", "C2P_REPLY_SCANLINE"):
        assert seam in dsp_worker, f"missing DSP C2P worker seam: {seam}"
    dsp_host = (ROOT / "src/dsp_c2p_host.s").read_text()
    for seam in (
        "dsp_c2p_init", "dsp_c2p_convert", "dsp_c2p_loopback", "dsp_c2p_vector_test", "dsp_c2p_full_vector_test", "dsp_c2p_vector_actual", "Dsp_Available", "Dsp_Reserve",
        "Dsp_LoadProgram", "DSP_C2P_ERR_LOOPBACK", "DSP_C2P_TIMEOUT",
    ):
        assert seam in dsp_host, f"missing bounded DSP C2P host seam: {seam}"
    dsp_vector = (ROOT / "src/dsp/c2p_test_vector.inc").read_text()
    for seam in ("dsp_c2p_full_source", "dsp_c2p_full_expected", "$1d66af", "$aaaa66"):
        assert seam in dsp_vector, f"missing DSP C2P full-row golden vector: {seam}"
    for seam in ("wc1_indexed_to_rgb565", "present_flight_frame"):
        assert seam in main, f"missing RGB565 presentation seam: {seam}"
    assert "dsp_c2p_init" not in main and "dsp_c2p_convert" not in main, \
        "game main loop must not depend on the legacy DSP C2P path"
    dsp_smoke = (ROOT / "tools/dsp_wire_smoke.s").read_text()
    for seam in ("dsp_c2p_init", "dsp_c2p_convert", "frame_chunky", "WC1 DSP C2P wire: PASS"):
        assert seam in dsp_smoke, f"missing DSP C2P hardware smoke seam: {seam}"

    for seam in (
        "resource_load_packet",
        "WC1_PACKET_ABSENT 0xffU",
        "decode_origin_lzw",
        "load_game_palette",
        "resource_draw_target_lock",
        "resource_draw_cockpit",
        "resource_draw_cockpit_indicators",
        "resource_load_cockpit",
        "resource_load_object_shape",
        "resource_load_capital_view",
        "resolve_install_logical_file",
        "resource_draw_object",
        "resource_draw_object_transformed",
        "resource_draw_flight_object",
        "resource_flight_velocity",
        "resource_flight_service_capital",
        "resource_flight_target_visible",
        "resource_load_flight_weapons",
        "resource_flight_fire",
        "resource_flight_ai_tick",
        "resource_flight_enemy_tick",
        "resource_flight_player_damage",
        "resource_draw_flight_projectiles",
        "resource_draw_flight_explosions",
        "resource_draw_flight_background",
        "resource_draw_flight_scene",
        "WC1_FLIGHT_SCENE_MAX",
        "FlightSceneEntry",
        "FlightSceneDepthMerge.md",
        "resource_flight_combat_reset",
        "resource_flight_combat_spawn",
        "resource_flight_combat_tick",
        "resource_flight_combat_housekeep",
        "resource_flight_hit_spark_data",
        "flight_combat_profiles",
        "WC1_FLIGHT_PROJECTILE_COUNT 40U",
        "WC1_FLIGHT_EXPLOSION_COUNT 8U",
        "resource_load_title",
        "resource_draw_intro_frame",
        "resource_advance_intro_scene",
        "resource_reset_intro_scene",
        "resource_draw_title_screen",
        "resource_draw_mouse_cursor",
        "resource_load_object_shape(10U)",
        "resource_load_object_shape(0U)",
        "canned mission records 32..35",
        "WC1_TITLE_FONT_BUFFER_MAX",
        "WC1_CONSTELLATION_BUFFER_MAX",
        "WC1_TITLE_EXPLOSION_BUFFER_MAX",
        "WC1_TITLE_DEBRIS_BUFFER_MAX",
        "WC1_TITLE_COMMON_DEBRIS_BUFFER_MAX",
        "WC1_TITLE_LASER_BUFFER_MAX",
        "WC1_TITLE_ROCK_BUFFER_MAX",
        "WC1_TITLE_ASTEROID_BUFFER_MAX",
        "WC1_INTRO_STAR_COUNT 7U",
        "WC1_FLIGHT_DUST_COUNT 8U",
        "WC1_FLIGHT_STAR_COUNT 7U",
        "flight_background_project",
        "resource_flight_background_reset",
        "resource_flight_background_tick",
        "WC1_INTRO_EXPLOSION_COUNT 1U",
        "WC1_INTRO_LASER_COUNT 12U",
        "WC1_INTRO_DEBRIS_COUNT 7U",
        "WC1_INTRO_DEBRIS_DUST_COUNT 8U",
        "WC1_INTRO_ASTEROID_COUNT 20U",
        "WC1_TRANSFORM_SCRATCH_MAX",
        "resource_intro_opening_text",
        "resource_intro_credit_text",
        "load_intro_strings",
        "load_wc_exe_data",
        "load_shape_tables",
        "WC_EXE_SHAPE_FRAME_ROWS 0x40C6U",
        "WC_EXE_SHAPE_FLIP_ROWS 0x4180U",
        "WC_EXE_SHAPE_ROW_BYTES 0x3EU",
        "WC_EXE_CAPITAL_SHAPE_ROW 2U",
        "WC_EXE_DEBRIS_SETS 0x0D04U",
        "WC_EXE_OPENING_POINTER 0x264EU",
        "WC_EXE_CREDIT_TABLE 0x2767U",
        "draw_intro_title_logo",
        "draw_intro_constellation",
        "draw_intro_fighters",
        "draw_intro_explosions",
        "draw_intro_lasers",
        "draw_intro_debris",
        "draw_intro_debris_dust",
        "draw_intro_credit_asteroids",
        "intro_explosion1_animation",
        "intro_spawn_explosion",
        "intro_spawn_explosion_debris",
        "intro_fire_laser_pair",
        "intro_hornet_laser_hardpoints",
        "intro_spawn_credit_asteroid",
        "begin_intro_credit_scene",
        "intro_canned_sequence_32",
        "IntroFixedVector",
        "intro_rotate_about_i",
        "intro_rotate_about_j",
        "intro_select_mobile_shape",
        "flight_mobile_shape_profile",
        "intro_camera_axes",
        "resource_intro_camera_pitch",
        "15000L << 8",
        "draw_shape_frame_scaled",
        "PLANETS.VGA",
        "OBJECTS.VGA",
        "TITLE.VGA",
        "COCKPIT.VGA",
        "mode + 17U",
        "DecodeShapeFrame()",
        "resource_palette_rgb565",
        "RESOURCE_STATUS_COCKPIT_DAMAGE",
        "g_aaCockpitBars_0046dd88",
        "flight_cockpit_light_on",
    ):
        assert seam in resources, f"missing resource/shape seam: {seam}"
    assert "WC1_PACKET_BUFFER_MAX 0x20000UL" in resources, \
        "resource packet storage must remain bounded for stock Falcon RAM"
    assert "WC1_OBJECT_SHAPE_BUFFER_MAX 0x12000UL" in resources and \
        "RESOURCE_OBJECT_SLOT_COUNT 3U" in resources, \
        "stock Falcon object-shape cache must preserve the DOS three-slot policy"

    resource_smoke = (ROOT / "tools/resource_loader_smoke.c").read_text()
    for seam in (
        "resource_load_packet(\"PCSHIP.V04\", 1U)",
        "absent packet slot was not accepted as empty",
        "resource_draw_intro_frame", "resource_reset_intro_scene",
        "opening subtitle decode failed", "title-logo zoom decode failed",
        "title 3Space constellation/fighter decode failed",
        "3Space projected stars did not follow title camera",
        "title fighter shape retention failed",
        "rotated Dralthi transform failed",
        "forward 3Space Dralthi projection failed",
        "eye-frame-relative 3Space Dralthi projection failed",
        "mission-frame velocity transform failed",
        "check_target visibility range failed",
        "player projectile packet load failed",
        "Hornet fixed-projectile fire failed",
        "flight projectile projection failed",
        "source collision/shield/spark state failed",
        "capital internal damage/explosion failed",
        "capital per-view packet load failed",
        "flight star/dust field produced too few pixels",
        "enemy projectile/player damage failed",
        "3Space scene merge depth order failed",
        "3Space scene merge omitted a represented class",
        "title Explosion1/laser/debris actions failed",
        "title credit asteroid field failed",
        "cockpit indicator frame path failed",
    ):
        assert seam in resource_smoke, \
            "missing asset-backed intro resource validation seam"

    scene_record = ROOT / "analysis/functions/FlightSceneDepthMerge.md"
    assert scene_record.exists(), "missing flight scene depth-merge record"
    scene_record_text = scene_record.read_text()
    for seam in (
        "Status: **Unproven diagnostic slice.**",
        "Canonical 1990 DOS function symbol and range: **TBD**",
        "resource_draw_flight_scene()",
        "resource_flight_scene_order[]",
        "Difference ledger against DOS",
    ):
        assert seam in scene_record_text, \
            "missing required unproven flight-scene record detail"

    print("WC1 Falcon contracts: OK")


if __name__ == "__main__":
    main()
