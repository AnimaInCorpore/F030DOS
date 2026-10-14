#!/usr/bin/env python3
"""Emit a symbol table for UW2.EXE: what is actually known, with its evidence.

`ghidra.md` section 6 carries "semantic pass 1 (UW1-style renames)" as an open
box. This is the seed for it. Two tiers, kept apart on purpose:

  TIER 1 -- names derived from reading the code and verified against data or
            the oracle. Each carries the evidence that produced it. These are
            safe to apply as Ghidra symbols.
  TIER 2 -- functions annotated only by the DGROUP strings they reference.
            A reference is a fact; the *name* it suggests is not. These are
            emitted as comments, not names, and are for a human to promote.

Addresses are FILE OFFSETS into UW2.EXE. To convert:
    image block   Ghidra seg:off  -> file = seg*16 + off - 0xD200
    CODE_TAIL     Ghidra CODE_TAIL::xxxxxx -> file = xxxxxx  (already an offset)

Usage:
  python work/symbols.py                 # summary
  python work/symbols.py --emit          # write ghidra_export/symbols.txt
"""
import argparse
import bisect
import collections
import re
import struct
from pathlib import Path

EXE = Path("work/extracted/D3/UW2.EXE")
FUNCS = Path("work/ghidra_export/functions.txt")
OUT = Path("work/ghidra_export/symbols.txt")
DGROUP = 0x68E80
SKEW = 0xD200

# (file offset, name, kind, evidence)
TIER1 = [
    # --- conversation VM variable marshalling (ghidra.md S36)
    (0x07DFA0, "conv_publish_vars",     "code", "publishes game state into the VM by name: <compute value>; push count; push &value; push name_ptr; lcall 0x2f8:0x98 = conv_import_write_by_name. ~30 variables, DGROUP 0xefa..0x102e"),
    (0x07E42F, "conv_readback_vars",    "code", "counterpart reading VM variables back into game state via lcall 0x2f8:0x10b = conv_import_read_by_name"),
    # --- barter/trade implementation, overlay 97 (V=0x0308) -- ghidra.md S34
    (0x079888, "barter_collect_player_offer","code", "loops slots 0..5 skipping unflagged [si+0x472f], reads object indices from [bx+0x479c], returns the count"),
    (0x0798EB, "barter_npc_inv_add_merge","code", "merges two is_quantity objects whose summed +6 counts pass cmp ax,0x3e7, else obj_link_from_word into the NPC container"),
    (0x079A26, "conv_give_obj_to_npc",  "code", "barter_npc_inv_add_merge then clears the matching player slot [bx+0x479c] and its flag"),
    (0x079725, "barter_obj_value",      "code", "word 0 of the 11-byte property record at [bx+0x6b68] x quantity x quality>>6, then srand(object index) so a price is stable"),
    (0x079F2E, "barter_like_dislike",   "code", "-1 for a zero property word or an item on the dislike list, +1 on the like list, same add ax,0x3e8 category encoding"),
    (0x02C3AC, "obj_ptr_from_index",    "code", "cmp si,0x100 then mov dx,0x1b -- 27-byte mobile records"),
    (0x02C5A6, "obj_container_search",  "code", "recursive container walk matching item id &0x1c0 / &0x30 / &0xf"),
    # --- rest/sleep + advancement, overlay 154 (V=0x04d0)
    (0x09BC2A, "sleep_begin",           "code", "refuses on [bx+0x306]&0x1b or hostiles nearby; add ax,0x15 picks the sleeping-bag/bed message; advances the clock by (rand%5+2)*0xE10 seconds"),
    (0x09B193, "player_recalc_max_hp_mana","code", "max HP = level*rec[5]/5+30 into [0x827c]+4; max mana = (player[0x28]+1)*rec[7]>>3 into +0x38; +0x4c = rec[5]*13+300"),
    (0x09C12F, "player_food_add",       "code", "player+0x39 += arg, refusing overflow past 0xff; converts player+0x3b (/6, capped 8) into HP on a positive delta"),
    (0x09B373, "skill_advance_one",     "code", "raises player[0x21+skill], capped at 0x1e and at 2x the class factor; skill 8 additionally writes player+0x310+[0x8282]"),
    (0x09B4BB, "skill_advance_group",   "code", "-3/-2/-1 select (base 10, span 10, 4 picks) / (7,3,2) / (0,7,3); non-negative means one specific skill"),
    (0x09C957, "trap_disarm_attempt",   "code", "finds the linked class-6 subclass-3 trigger, rolls a 4-tier check against 8+(level-1)/8, prints the disarm or set-off message"),
    (0x09C8C0, "trap_probe_linked_trigger","code", "same chain walk, rolls against 10+2*(level-1)/8 and returns the tier; gates trap_disarm_attempt"),
    (0x09C55D, "dream_wake_and_return", "code", "clears player+0x63 bit 1, arms the deferred callback at [0x12b8]/[0x12ba], teleports to (0x3f,0x3f) on level player[0x2ff]>>8, prints string 25"),
    (0x09C224, "run_pending_scene_request","code", "reads player[0xf5]; value-1 == 2 takes a special branch, anything else calls cutscene_play(value-1); clears the byte either way"),
    # --- NPC social / placement, overlay 107 (V=0x0358) -- the crime-witness system
    (0x07F770, "crime_alert_owner_race","code", "takes the owner code from arg or from obj+6 bits 0-5 (gated by COMOBJ byte 7 bit 7), sweeps a 16x16 tile square of CRITTERS via objects_in_rect_foreach, then erases the owner code from the object and its container tree"),
    (0x07F52B, "crime_witness_react_cb","code", "race filter [si+9] vs [0x103d]&0x1f, range test against critter_props[+0x1e]>>4, line of sight via 0x17357, then drops obj+0xd bits 14-15 by one and prints block-1 string 240/241/242"),
    (0x07F743, "clear_owner_field_cb",  "code", "container-tree twin of crime_alert_owner_race's tail: and byte ptr es:[bx+6], 0xc0"),
    (0x07E680, "npc_set_goal",          "code", "saves/restores [0x2246]/[0x2248] around 0x1BA8F, which writes obj+0xb bits 0-3 = goal, bits 4-11 = target"),
    (0x07E73B, "tile_type_subpos",      "code", "jmp word ptr cs:[bx+0x109] on tile type 0..5; type 0 returns 0, default (4,4)"),
    (0x07E795, "critter_level_entry_reset","code", "heals to (hp+maxhp)/2, clears 6 bits of obj+0x19, tallies [si+9] into the caller's 64-byte race array, relinks to the home tile"),
    (0x07EAA7, "nonmobile_level_entry_reset","code", "publishes the tile in [0x2266], re-creates and relinks the object"),
    (0x07EBEF, "level_entry_attitude_pass","code", "zeroes a 64-byte local, splits critters (and ax,0x1c0 == 0x40) from the rest, then adds delta[race] into obj+0xd bits 14-15 clamped 0..3"),
    (0x07EDBB, "any_engaged_npc_within_r2","code", "clears [0x1038], area_effect_around_obj radius 2 with callback 0x358:0x6b, returns [0x1038]"),
    (0x07F43B, "try_close_in_hostile_npc","code", "clears [0x553e], area_effect_around_obj radius 8 limit 1 with callback 0x358:0x43"),
    (0x07F23A, "npc_move_to_tile",      "code", "unlinks, writes obj+0x16 (bits 10-15 x, 4-9 y) and the obj+2 sub-position, relinks"),
    (0x07F466, "vendetta_state_load",   "code", "player+0x308 -> [0xc5]/[0xc6]/[0x2274..0x2279]; called from savegame_restore"),
    (0x07F49A, "vendetta_state_save",   "code", "exact mirror writing player+0x308; called from savegame_save"),
    (0x07F518, "reset_vendetta_state",  "code", "[0xc5]=0, [0xc6]=0xff then clear_witness_flags_all; called on level switch"),
    (0x07F4DE, "clear_witness_flags_all","code", "loops objects 2..0xff clearing bit 7 of obj+0x15, then [0xb4]=0xffff"),
    (0x07F82A, "reposition_all_controlled","code", "loops the 5 slots at player+0x360 through reposition_when_unseen"),
    (0x07F857, "reposition_when_unseen","code", "gated by the in-player-view test 0x895EF; octant_ccw_from_delta then builds a destination tile"),
    (0x07F97D, "controlled_creature_lost","code", "inc byte ptr [bx+0xe7] with a high-water mark at player+0x37b, sets goal 6, release_owned_object_slot"),
    (0x07F9BF, "npc_apply_schedule",    "code", "npc_schedule_destination then stores the destination tile and goal 1; skipped when the player can see the NPC"),
    (0x07FA89, "npc_schedule_destination","code", "hour = clock/0xE1000 % 24 then jmp word ptr cs:[bx+0x1635], 12 half-hourly slots and 4 room rectangles"),
    # --- conversation intrinsics, named by the binary's own registration table at 0x7C38C (ghidra.md S34)
    (0X07C86A, "cnv_babl_menu",             "code", "conversation intrinsic \"babl_menu\", registered at 0x7C38C as 0x0338:0x0089"),
    (0X07CA49, "cnv_babl_fmenu",            "code", "conversation intrinsic \"babl_fmenu\", registered at 0x7C38C as 0x0338:0x009d"),
    (0X07CD5C, "cnv_say",                   "code", "conversation intrinsic \"say\", registered at 0x7C38C as 0x0338:0x003e"),
    (0X07CDC3, "cnv_respond",               "code", "conversation intrinsic \"respond\", registered at 0x7C38C as 0x0338:0x00a2"),
    (0X077722, "cnv_get_quest",             "code", "conversation intrinsic \"get_quest\", registered at 0x7C38C as 0x0300:0x007a"),
    (0X07767F, "cnv_set_quest",             "code", "conversation intrinsic \"set_quest\", registered at 0x7C38C as 0x0300:0x007f"),
    (0X077837, "cnv_sex",                   "code", "conversation intrinsic \"sex\", registered at 0x7C38C as 0x0300:0x0057"),
    (0X07CF6E, "cnv_babl_ask",              "code", "conversation intrinsic \"babl_ask\", registered at 0x7C38C as 0x0338:0x0034"),
    (0X07CE7D, "cnv_print",                 "code", "conversation intrinsic \"print\", registered at 0x7C38C as 0x0338:0x004d"),
    (0X07CFFC, "cnv_show_inv",              "code", "conversation intrinsic \"show_inv\", registered at 0x7C38C as 0x0338:0x007f"),
    (0X07D27C, "cnv_give_to_npc",           "code", "conversation intrinsic \"give_to_npc\", registered at 0x7C38C as 0x0338:0x006b"),
    (0X07D514, "cnv_find_inv",              "code", "conversation intrinsic \"find_inv\", registered at 0x7C38C as 0x0338:0x0070"),
    (0X07D53F, "cnv_take_from_npc",         "code", "conversation intrinsic \"take_from_npc\", registered at 0x7C38C as 0x0338:0x0075"),
    (0X07D55A, "cnv_take_id_from_npc",      "code", "conversation intrinsic \"take_id_from_npc\", registered at 0x7C38C as 0x0338:0x008e"),
    (0X07D590, "cnv_identify_inv",          "code", "conversation intrinsic \"identify_inv\", registered at 0x7C38C as 0x0338:0x0066"),
    (0X079102, "cnv_do_offer",              "code", "conversation intrinsic \"do_offer\", registered at 0x7C38C as 0x0308:0x0043"),
    (0X07953E, "cnv_do_decline",            "code", "conversation intrinsic \"do_decline\", registered at 0x7C38C as 0x0308:0x005c"),
    (0X07954B, "cnv_do_judgement",          "code", "conversation intrinsic \"do_judgement\", registered at 0x7C38C as 0x0308:0x0061"),
    (0X0782D3, "cnv_end_barter",            "code", "conversation intrinsic \"end_barter\", registered at 0x7C38C as 0x0308:0x0025"),
    (0X077EF0, "cnv_setup_to_barter",       "code", "conversation intrinsic \"setup_to_barter\", registered at 0x7C38C as 0x0308:0x003e"),
    (0X07CF34, "cnv_pause",                 "code", "conversation intrinsic \"pause\", registered at 0x7C38C as 0x0338:0x00a7"),
    (0X079EFC, "cnv_set_likes_dislikes",    "code", "conversation intrinsic \"set_likes_dislikes\", registered at 0x7C38C as 0x0308:0x002a"),
    (0X07D575, "cnv_do_inv_create",         "code", "conversation intrinsic \"do_inv_create\", registered at 0x7C38C as 0x0338:0x0093"),
    (0X07D4F9, "cnv_do_inv_delete",         "code", "conversation intrinsic \"do_inv_delete\", registered at 0x7C38C as 0x0338:0x0098"),
    (0X07D7DE, "cnv_check_inv_quality",     "code", "conversation intrinsic \"check_inv_quality\", registered at 0x7C38C as 0x0338:0x0020"),
    (0X07D814, "cnv_set_inv_quality",       "code", "conversation intrinsic \"set_inv_quality\", registered at 0x7C38C as 0x0338:0x002a"),
    (0X07D782, "cnv_count_inv",             "code", "conversation intrinsic \"count_inv\", registered at 0x7C38C as 0x0338:0x0039"),
    (0X0769C8, "cnv_babl_hack",             "code", "conversation intrinsic \"babl_hack\", registered at 0x7C38C as 0x0300:0x0070"),
    (0X07A038, "cnv_give_all_stuff",        "code", "conversation intrinsic \"give_all_stuff\", registered at 0x7C38C as 0x0308:0x002f"),
    (0X07785C, "cnv_gronk_door",            "code", "conversation intrinsic \"gronk_door\", registered at 0x7C38C as 0x0300:0x002f"),
    (0X076F44, "cnv_set_sequence",          "code", "conversation intrinsic \"set_sequence\", registered at 0x7C38C as 0x0300:0x0089"),
    (0X0770D9, "cnv_set_attitude",          "code", "conversation intrinsic \"set_attitude\", registered at 0x7C38C as 0x0300:0x008e"),
    (0X077114, "cnv_set_race_attitude",     "code", "conversation intrinsic \"set_race_attitude\", registered at 0x7C38C as 0x0300:0x0043"),
    (0X077547, "cnv_take_from_npc_inv",     "code", "conversation intrinsic \"take_from_npc_inv\", registered at 0x7C38C as 0x0300:0x004d"),
    (0X0775AF, "cnv_add_to_npc_inv",        "code", "conversation intrinsic \"add_to_npc_inv\", registered at 0x7C38C as 0x0300:0x0084"),
    (0X077364, "cnv_place_object",          "code", "conversation intrinsic \"place_object\", registered at 0x7C38C as 0x0300:0x006b"),
    (0X0775E3, "cnv_transform_talker",      "code", "conversation intrinsic \"transform_talker\", registered at 0x7C38C as 0x0300:0x0066"),
    (0X077634, "cnv_remove_talker",         "code", "conversation intrinsic \"remove_talker\", registered at 0x7C38C as 0x0300:0x00a2"),
    (0X07728B, "cnv_x_skills",              "code", "conversation intrinsic \"x_skills\", registered at 0x7C38C as 0x0300:0x0048"),
    (0X07731D, "cnv_x_traps",               "code", "conversation intrinsic \"x_traps\", registered at 0x7C38C as 0x0300:0x003e"),
    (0X07795E, "cnv_x_obj_stuff",           "code", "conversation intrinsic \"x_obj_stuff\", registered at 0x7C38C as 0x0300:0x005c"),
    (0X077C11, "cnv_x_obj_pos",             "code", "conversation intrinsic \"x_obj_pos\", registered at 0x7C38C as 0x0300:0x0052"),
    (0X07D083, "cnv_find_barter",           "code", "conversation intrinsic \"find_barter\", registered at 0x7C38C as 0x0338:0x00b1"),
    (0X07D131, "cnv_find_barter_total",     "code", "conversation intrinsic \"find_barter_total\", registered at 0x7C38C as 0x0338:0x0025"),
    (0X07D369, "cnv_give_ptr_npc",          "code", "conversation intrinsic \"give_ptr_npc\", registered at 0x7C38C as 0x0338:0x00bb"),
    (0X0777A2, "cnv_x_clock",               "code", "conversation intrinsic \"x_clock\", registered at 0x7C38C as 0x0300:0x0020"),
    (0X076FA0, "cnv_x_exp",                 "code", "conversation intrinsic \"x_exp\", registered at 0x7C38C as 0x0300:0x0039"),
    (0X076FD5, "cnv_teleport_player",       "code", "conversation intrinsic \"teleport_player\", registered at 0x7C38C as 0x0300:0x0025"),
    (0X077022, "cnv_teleport_talker",       "code", "conversation intrinsic \"teleport_talker\", registered at 0x7C38C as 0x0300:0x002a"),
    (0X07D85F, "cnv_switch_pic",            "code", "conversation intrinsic \"switch_pic\", registered at 0x7C38C as 0x0338:0x0043"),
    # --- save/restore + level persistence, overlay 149 (V=0x04a8) -- ghidra.md S33
    (0x099940, "savedir_prepare_and_check_space","code", "mkdir the working dir, dir_delete_all_files, then getdfree (INT21 AH=36h); returns avail*bsec*sclus >= 0x4b0"),
    (0x0999D2, "level_load",            "code", "mov word ptr [0x8282], ax makes the arg the current level, then level_ambient_light_load and the reader trio 0x92836/0x96E5F/0x72E8E, ark_close(1)"),
    (0x099A73, "level_save",            "code", "and ax,0xfe3f clears the player object's id bits 6..8, then the writer trio 0x92927/0x96F2C/0x72E39 mirroring level_load"),
    (0x099B26, "savegame_scan_slot_descriptions","code", "loops slots 1..4 patching the digit with add al,0x31, reads each <slot>\\desc via fgets, substitutes \"<not used yet>\" (DGROUP 0x1a3f) when absent"),
    (0x099C02, "savegame_print_slot_list","code", "copies the 4-entry label pointer table at DGROUP 0x1a30 (\"I- \",\"II- \",\"III- \",\"IV- \"), textwin_clear, then print_wrapped per slot"),
    (0x099C98, "savegame_menu_action",  "code", "mode != 0 -> savegame_restore, mode == 0 -> savegame_save; callers set [0x8168] = 0 for Save and 1 for Restore"),
    (0x099D5B, "savegame_restore",      "code", "wipes the working dir, dir_copy_all_files(slot -> working), reads player.dat via 0x8D76D, level_load, then level_transition_hook(level, 3)"),
    (0x099E24, "savegame_save",         "code", "textwin_read_line (max 0x1e, ESC -> 2), write_whole_file of the description to <slot>\\desc, mkdir and wipe the slot, level_save, dir_copy_all_files(working -> slot)"),
    (0x09A13F, "dir_copy_all_files",    "code", "strcat \"*.*\", findfirst/findnext, file_copy per DTA filename"),
    (0x09A1AE, "level_change",          "code", "level_transition_hook(from,1), level_save, level_load, level_transition_hook(to,0), mana_restore, then 0x9AA96(1)"),
    (0x09A2C2, "level_transition_hook", "code", "jmp word ptr cs:[bx+0xb25], 8-entry table at file 0x9A465 indexed by ((lvl-1)/8)-1; phase 0 = entered, 1 = leaving, 3 = after restore"),
    (0x09AA96, "npc_schedule_update",   "code", "opens ark handle 5 = scd.ark, loops i = 0..0x0f over the 16 bytes at player+0x36D against the per-level last-applied values at +0x106 + level*4"),
    (0x0885FB, "plotflag_9a_bit2_set_and_reschedule","code", "stock plot-flag idiom: 1-bit write of bit 2 into the dword at player+0x9A (and dx,0xfffb / add dx,4 / adc ax,0) then inc byte [bx+0x37c], i.e. schedule counter 15. NOT a death sequence -- see ghidra.md S33"),
    (0x08D25C, "player_dat_write",      "code", "strcat \"player.dat\" (DGROUP 0x15c8) then player_record_save"),
    (0x08D76D, "player_dat_read",       "code", "counterpart reader of player_dat_write"),
    (0x013058, "getdfree",              "code", "mov ah, 0x36 / int 21h"),
    (0x013303, "mkdir",                 "code", "mov ah, 0x39 / int 21h"),
    (0x012D43, "findfirst",             "code", "mov ah, 0x4e / int 21h"),
    (0x012D76, "findnext",              "code", "mov ah, 0x4f / int 21h"),
    (0x013195, "lseek",                 "code", "mov ah, 0x42 / int 21h"),
    (0x01255F, "strrchr",               "code", "strlen then a backward walk -- NOT strchr"),
    (0x011769, "access",                "code", "standard C/DOS wrapper; exact full contract not yet isolated"),
    (0x011AF5, "fgets",                 "code", "standard C/DOS wrapper; exact full contract not yet isolated"),
    (0x071ECA, "ark_build_filename",    "code", "kind 1=lev.ark 2=cnv.ark 3=test.ark 4=byt.ark 5=scd.ark"),
    (0x0892A8, "save0_seed_from_data",  "code", "file_copy(\"DATA\\\\\", <savedir 0x5d0e>, \"lev.ark\") and the same for \"scd.ark\", via lcall 0x4a8:0x2a = file_copy 0x9A02E; main_init step 41. NOTE cdecl order: last push is arg1"),
    (0x09A02E, "file_copy",              "code", "builds arg1+arg3 and arg2+arg3 by strcpy/strcat, opens both and copies src to dst in 0xF000-byte chunks"),
    (0x099FAB, "dir_delete_all_files",   "code", "strcat(dir, \"*.*\"), findfirst/findnext, unlink each with the name spliced at dir+strlen(dir); called from main_shutdown to wipe SAVE0"),
    (0x088AFF, "main_shutdown",          "code", "9 far calls: video/BIOS/DOS state restore, chdir to the startup cwd, free the record arrays, EMS release, sound teardown, strings.pak close, then wipe <UWHOME>\\SAVE0\\"),
    (0x088B57, "startup_paths_and_hotkeys_init","code", "if argc==2 strcpy(0x5de2, strupr(argv[1])); strcpy(0x5d5a, \"DATA\\\\\"); getcurdir(0, 0x5d9e); [0x5d9c]=0x7fff, [0x5d56]=-1; main_init step 36"),
    (0x088FA1, "int0_divide_by_zero_handler","code", "copies DGROUP 0x12e8 \"Underworld exiting, divide by zero.\\r\\n$\", calls main_shutdown, then chains the saved vector at [0x5d52]"),
    (0x088FF0, "level_transition_apply", "code", "guarded on [0x5df6] > 0; fatal_error(0x300c) when [0x8282] == [0x5dfa]; ends shl ax,6 / add [0x5df6] = y*64 + x tile index"),
    (0x088C1F, "ui_mode_set_index",      "code", "[[0xe4]+8] = [0x5d50] = arg; maps 2 -> [0x5d56]=1, 4 -> 2, else 0"),
    (0x088C5A, "ui_mode_switch",         "code", "lcall [bx+0x1226] leave hook, then ui_mode_set_index, then lcall [bx+0x11ea] enter hook, bx = [0x5d56] << 6"),
    # --- palettes, fonts, screen transitions, GR banks -- overlay 118 (V=0x03b0)
    (0x08AC7B, "font_load_by_index",    "code", "truncates DGROUP 0x14bb \"font????.sys\" to \"font\", indexes the 5-byte-stride name table at 0x14c8 (4x5p/5x6p/char/big/5x6i/butn), strcats \".sys\" from 0x14e6"),
    (0x08AC14, "font_load_file",        "code", "open, read a 0xc-byte header into far [0x21bc], then (hdr[2]+hdr[0])<<7 bytes into far [0x21c0], close"),
    (0x08ACC2, "gfx_reset_clip_fullscreen","code", "gfx_set_clip_rect(0, 0xc7, 0x13f, 0) then gfx_select_bitmap(0); also normalises min/max into [0x415a]/[0x415c] via 0x6a73"),
    (0x08ACF1, "palette_read_pals_dat", "code", "opens \"pals.dat\" (DGROUP 0x14eb), lseek idx*0x300, reads 0x300 bytes; returns 1 only on a full 768-byte read"),
    (0x08AD51, "palette_load_and_activate","code", "palette_read_pals_dat into the global buffer far [0x219c], then vga_set_dac_range(0x100, 0)"),
    (0x08AD7F, "palette_set_all",       "code", "far-copies 0x300 bytes into [0x219c] then vga_set_dac_range(0x100, 0)"),
    (0x08ADAA, "palette_set_range",     "code", "same but length count*3 with both offsets biased by first*3, then vga_set_dac_range(count, first)"),
    (0x08ADF3, "palette_fade_out",      "code", "accumulator preloaded with src[i]*(steps*8); each frame subtracts and divides, strictly descending to 0; paced by the 32-bit counter at far [0x2148]"),
    (0x08AF10, "palette_fade_in",       "code", "mirror of palette_fade_out, accumulator from 0 and ascending"),
    (0x08B00F, "screen_remap_transition_fwd","code", "loops i=0..count calling the far callback then presenting; afterwards fills the bitmap with fill_color via 0xb8:0xc84"),
    (0x08B052, "screen_remap_transition_rev","code", "mirror: saves 0x6800 bytes of the bitmap and restores them each frame, looping count..1"),
    (0x08B142, "screen_fill_and_present","code", "bitmap fill via 0xb8:0xc84, present, then or word [0x5d9c], 2"),
    (0x08B4F2, "gr_bank_reserve",       "code", "cmp ax,0x4000 (the 16 KB window); on overflow [0x1504]=0 and [0x1506]++, switches bank when [0x1506] != [0x1500]; returns (seg[0xe4d2] + [0x1504] + 0x800):0"),
    (0x08B546, "gr_bank_seek_current",  "code", "reads [0x2184][[0x1502]], switches to packed>>12, sets [0x1504] = packed & 0xfff"),
    (0x08B587, "gr_post_far_no_handle", "code", "post_far variant: writes ([0x1506]<<12)|[0x1504] into [0x2184][[0x1502]+index] but allocates no handle and never touches [0x2188]"),
    (0x08B636, "gr_post_far_biased",    "code", "post_far variant indexing [0x2188] at [0x151f]+index"),
    (0x08B6C2, "gr_post_far_planar",    "code", "planar-VGA variant: allocates via lcall 8:0x4a(w, h+1), decodes raw/compressed, stores the RAW value in [0x2184] -- the representation shape_draw handles on its >= [0x14fa] branch"),
    (0x08B73F, "gr_post_far_planar_reload","code", "as gr_post_far_planar but reuses the existing [0x2184] entry instead of allocating"),
    (0x08B86D, "gr_archive_load_wrapper","code", "calls gr_archive_load then add word [0x1502], [0x6730] -- advances the handle cursor by the archive's record count"),
    # --- character creation entry slice -- analysis/functions/character-creation.md
    (0x07BB2D, "character_create_entry", "code", "wrapper: character UI setup 0x7a280(1), character_create_run 0x7b8a4, then UI cleanup 0x2344; live oracle reaches the sex-choice screen"),
    (0x07B8A4, "character_create_run", "code", "allocates character-choice state, loads chrbtns, DATA\\skills.dat and DATA\\chrgen.dat, builds eight entries, then calls character_choice_screen 0x7b2f8"),
    (0x07B2F8, "character_choice_screen", "code", "renders and samples one mouse-driven character choice; the browser record covers the first main-menu/Create/Male/Female boundary only"),
    # --- .ARK container layer, overlay 93 (V=0x02e8); cutscene player, overlay 108 (V=0x0360) -- ghidra.md S31
    (0x071C10, "ark_read_index_tables", "code", "lseek 0, reads u16 N and a u32, then four dos_read of N*4 bytes into the far pointers at [0x994]/[0x998]/[0x99c]/[0x9a0]; restores position"),
    (0x071D38, "ark_write_index_tables","code", "mirror: push 6 to seek past the header, then four lcall 0x538:0x8e writes of N*4 bytes"),
    (0x071E2C, "file_read_u32_at",      "code", "tell, lseek(off), read 4 bytes, lseek back, return DX:AX"),
    (0x071E7E, "file_write_u32_at",     "code", "same shape writing via lcall 0x30:0x1458 from lea ax,[bp+0xa]"),
    (0x071F49, "file_copy_bytes",       "code", "100-byte bounce buffer (cmp di,0x64) read/write loop"),
    (0x071FB6, "ark_open",              "code", "opens with 0x8004 (O_RDWR|O_BINARY), reads u16 N into es:[2] and a u32 into es:[4]/es:[6]; the open archive struct lives at V=0x258"),
    (0x07208F, "ark_close",             "code", "close(es:[0]) on the V=0x258 struct; its one argument is never referenced"),
    (0x0720C1, "ark_write_slot",        "code", "flags bit0 drives compress-to-_mem.tmp via lcall 0x4c8:0x25 and sets bit1; bit2 marks growable-in-place with pad = (15*len)/100; otherwise streams the archive through _arc.tmp in 0x2000 chunks and rewrites the index"),
    (0x072843, "ark_read_slot",         "code", "rejects slot >= es:[2]; off = u32 at 6+4*slot, size at 6+8N+4*slot, flags at 6+4N+4*slot; flags bit1 -> lcall 0x4c8:0x2a (LZSS) else dos_read"),
    (0x072958, "ark_slot_is_used",      "code", "opens read-only, reads N, then file_read_u32_at(6 + 4*slot); 1 if non-zero, 0 if zero, 0xffff if the open failed"),
    (0x0729D1, "ark_read_slot_count",   "code", "open read-only, read the u16, close, return it (0 on failure)"),
    (0x07FD70, "voc_stream_open",       "code", "builds \"SOUND\\\" + \"BSP\" + itoa(id) + \".VOC\", opens it, fstat for the size, preloads EMS banks of 0x4000 bytes"),
    (0x08009F, "voc_stream_refill",     "code", "per slot 0..1, takes up to 0x800 bytes of the remainder, pages in the EMS bank, builds a {ptr,len} descriptor at si*12 + 0x23dc and submits it"),
    (0x080367, "voc_stream_reset",      "code", "zeroes [0x556a]/[0x556c] then lcall 0xc0:0xc09"),
    (0x080383, "ems_banks_reset",       "code", "invalidates the GR bank cache then sets [0x5902] = 3; returns 3"),
    (0x080393, "ems_bank_ptr",          "code", "rejects bank >= [0x5902]; maps 4 EMS pages via lcall 0x70:0xdb (INT 67h AX=5000h) and returns [0x22be]:0000, the EMS page frame"),
    (0x0803D7, "gr_bank_cache_invalidate","code", "nothing but lcall 0x160:0x134"),
    (0x08113D, "voc_stream_refill_thunk","code", "body is exactly call 0x8009F; all four call sites are in the sound driver overlay"),
    (0x0811FC, "cutscene_chunk_filename","code", "\"CUTS\\csXXX.nXX\" with the cutscene number as 3 OCTAL digits at [7..9] and the chunk as 2 at [0xc..0xd]"),
    (0x0828E3, "cutscene_run",          "code", "opens the chunk, reads a 0x400-byte header, copies 0x300 of it to the DAC palette buffer [0x219c], requires >= 3 EMS banks"),
    (0x082B35, "cutscene_play",         "code", "[0x5ce4] = id; region (0,0xc7,0x140,0xc8) for id < 0x100 else (0x10,0xb6,0xd0,0x7f); called with ids 0,1,2,9; this is game_loop's exit call"),
    (0x083150, "cutscene_load_lback",   "code", "\"CUTS\\lbackNNN.byt\" (NNN octal), 64000-byte full-screen load; brackets a narrowed clip rect with [0xdc4]=1 and clears it for the full-screen blit"),
    (0x008111, "gfx_set_clip_rect",     "code", "stores its 4 args at [0x503e..0x5044] and calls 0x8934 -> 0x6837, which does mov di,0x3df4 + four movsw; [0xdc4] switches whether the blitter honours it"),
    (0x006837, "gfx_clip_rect_store",   "code", "mov di,0x3df4 then four movsw -- writes the clip window the blitter clamps against"),
    (0x008AB7, "blit_span_modex_transparent","code", "byte-for-byte identical to blit_span_modex_opaque 0x89C2 except the pixel loop: xor ah,ah then lodsb/cmp al,ah/je/stosb -- skips colour 0"),
    (0x0089C2, "blit_span_modex_opaque", "code", "Mode X span loop, movsb + add si,3; the [0xdc5]==0 half of the pair with 0x8AB7"),
    (0x003D79, "blit_span_linear_transparent","code", "linear span loop with lodsb/or al,al/je/stosb -- the transparent half of the pair with blit_span_linear 0x3D48"),
    # --- magic/spell module, overlay 156 (V=0x04e0); traps+variable store, overlay 166 (V=0x0530) -- ghidra.md S29
    (0X09CE00, "mana_spend",                "code", "subtracts [bp+6] from player[0x37] with a floor at 0; called at 0x9D429 with the cost byte [0x1b02]"),
    (0X09CE29, "tile_magic_blocked",        "code", "grid64_cell_ptr then bit 6 of cell byte 1; spell_effect_dispatch aborts when set"),
    (0X09CE4C, "spell_apply_by_id",         "code", "spell-def lookup at V=0x270 (file 0x66880), 4-byte stride, 69 contiguous entries 0x00-0x44; type = rec[0]>>3, param = rec[3]; ids with 0xc0 set become types 12..14"),
    (0X09CEC9, "spell_effect_dispatch",     "code", "15-way jmp word ptr cs:[bx+0x321] (table at file 0x9D121), bounded by cmp bx,0xe"),
    (0X09D13F, "mana_restore",              "code", "player[0x37] += (amt + rand&3)*player[0x38]>>4 + 1 for amt>0, clamped against player[0x38]"),
    (0X09D1ED, "player_hp_restore",         "code", "same shape on obj+8 of [0x827e], clamped by the critter record's +4 (max HP)"),
    (0X09D285, "obj_hp_add_capped",         "code", "any critter: obj[8] += delta capped at crit_props[item_id&0x3f]+4; redraws only for the player"),
    (0X09D2F7, "spell_heal_dice",           "code", "critter check (and ax,0x1c0), amount 0xff when param==0xf else roll_dice(param,8), then obj_hp_add_capped"),
    (0X09D33E, "spell_damage_floor3",       "code", "roll_dice(param,8) subtracted from obj+8 but never below 3; which spell school was NOT determined"),
    (0X09D3CC, "spell_add_timed_effect",    "code", "indexes the 6-byte table at DGROUP+0x1b03 by the 1-based param, calls 0x299FD, spends [0x1b02] mana on success"),
    (0X09D43C, "spell_create_obj",          "code", "obj_create then writes a randomised 7-bit field into the new object's word at +2"),
    (0X09DEF6, "objects_in_rect_foreach",   "code", "clips a tile rect to 64x64 with four symmetric clamps, walks tiles via grid64_cell_ptr, calls the far callback at [bp+0xa]"),
    (0X09E1AF, "area_effect_around_obj",    "code", "obj_index_from_ptr; heading from obj[2] bits 7-9 and obj+0x18 low 5 bits; add_polar_offset then objects_in_rect_foreach over a (2r+1)^2 square"),
    (0X09E286, "npc_foreach_by_id1a",       "code", "walks the u8 index list at [0x2586]:[0x2588] for [0x257c] entries, matches byte obj+0x1a and calls the far callback; obj+0x1a's meaning NOT determined (callers pass conv variables and 0x8b-0x8f/0xa8)"),
    (0X09E2F3, "spell_area_effect_indexed", "code", "copies a 7-byte record from DGROUP+0x1b02 + 7*(param&0x3f) whose first two words are a far callback, then area_effect_around_obj"),
    (0X09E3E0, "spell_begin_target_select", "code", "player-only; parks a far callback in [0x24d8]/[0x24da] into this overlay, sets mode [0x24f6]=2, pushes cursor 0x1076"),
    (0X0A18F8, "var_apply_op",              "code", "8-way ALU on (a,b): add, sub, assign, and, or, xor, shl, equality; jmp word ptr cs:[bx+0x2dd] bounded by cmp bx,7"),
    (0X0A194D, "game_var_write",            "code", "index<0x100 -> player[0xf9+2i] = var_apply_op(...) & 0x3ff; 0x100-0x17F -> bit i&3 of the dword at player+0x66+4*(i>>2); the conversation VM calls it with op=2 from 0x7731D"),
    (0X0A1B9E, "game_var_read",             "code", "mirror of game_var_write; also player[0xe6+k] for 0x180-0x18F and player[0x36d+k] for 0x190-0x19F"),
    (0X0A31BE, "trigger_unlink_refs",       "code", "walks an object chain clearing links equal to [0x862c] and decrementing [0x862e]; subtype 0xa gets an extra call to 0x38AAD"),
    (0X0A32CF, "obj_detach_triggers",       "code", "seeds [0x862e] from word0 bits 9-12, sweeps all 4096 tile records at [0x188c] stride 4 invoking trigger_unlink_refs, then obj_find_in_container_chain"),
    (0X0A3D0C, "player_range_gate8",        "code", "returns 1 if the flag arg is 0, else only when |player_coord - arg| >= 8 on either axis"),
    (0X0A3D60, "traps_run_all_linked",      "code", "enumerates level objects via 0x2C70F mode 6, filters word0 bits 9-12 == 0, marks bit 8 of the linked object's +0xd, gates on player_range_gate8, runs trap_dispatch"),
    (0X0A3C85, "trigger_probe_callback",    "code", "raises [0x1bae] for any object with bit 8 of +0xd set that is neither the probe centre [0x8630] nor the player"),
    (0X0A3CD6, "any_marked_obj_within_4",   "code", "stores the centre in [0x8630], calls the area walker with radius 4 and callback 0x530:0x89; returns [0x1bae]"),
    (0X0A3F02, "player_total_weight",       "code", "player[0x4a] plus obj_get_weight of the object in [0x6afc]/[0x6afe]"),
    # --- trap dispatcher (overlay 166) + world-mutation workers (overlay 110), ghidra.md S28
    (0x0A1C36, "trap_dispatch",         "code", "bx = obj.word0 & 0x3f (trap id - 0x180); cmp bx,0x18; jmp word ptr cs:[bx+0x1b2c] -- a 25-entry table at file 0xA318C"),
    (0x084A0B, "trap_damage_or_poison", "code", "dispatcher case 0 = item 0x180 = STRINGS block4[384] \"a_damage trap\"; negative amount rewrites player+0x60 bits1-4, positive calls 0x28092 with damage type 4"),
    (0x083FB2, "request_teleport_to_level","code", "case 1 = 0x181 = block4[385] \"a_teleport trap\"; writes [0x5df6]=x [0x5df8]=y [0x5dfa]=level then lcall 0x68:0xb5 with 0x20"),
    (0x084E43, "special_effect_apply",  "code", "case 4 = 0x184 = block4[388] \"a_special effects trap\"; jmp word ptr cs:[bx+0x18ab], 7 entries at file 0x84E9B"),
    (0x084527, "set_tile_region",       "code", "case 5 = 0x185 = block4[389] \"a_change terrain trap\"; bounds type at [bp+0x10] <= 0xa, writes the 6-bit wall texture, per-tile via grid64_cell_ptr; re-settles objects on a height change"),
    (0x084ACB, "spelltrap_cast_at_tile","code", "case 6 = 0x186 = block4[390] \"a_spelltrap\"; stores tile x,y at [0x8628]/[0x8629] then lcall 0x4e0:0x48 or 0x4e0:0x66"),
    (0x087210, "fire_triggers_in_tile", "code", "grid64_cell_ptr(x,y)+2 then 0x2C5A6 walks the tile's object chain for class 6; dispatches on word0 bit 5"),
    (0x084EF0, "release_owned_object_slot","code", "scans the 5-byte table at player+0x360, clears the matching slot; clears player+0x63 bit 2 when fewer than 2 slots were occupied"),
    (0x086E6A, "convert_object_to_item_0xc3","code", "or ax,0xc3 rewrites word0's item id to 0xc3 (block4[195] \"a_skull\") keeping bits 9-15; callers gate on id == 0x13 (block4[19] \"a_skull\", the missile form)"),
    (0x084CC4, "area_effect_at_object_tile","code", "temporarily overwrites [0x24e8]/[0x24ea] with the object's +0x16 tile, calls the 15x15 sweep at 0x7F770, then restores them"),
    (0x0835F0, "find_placeable_tile_near","code", "BFS over a 10x10 window clamped to 1..0x3e with two 20-entry frontier queues; grid64_cell_ptr per tile then the placement test 0x2B58C; 6-entry jump table at cs:0x93d on tile type"),
    # --- player derived state + PLAYER.DAT, overlay 142 (V=0x0470)
    (0x0977E2, "player_recalc_derived_state","code", "31 callers; clears armour[0..3] at [0x827c], walks paperdoll slots via inv_slot_obj_ptr accumulating obj_armour_value, sets the weapon anim class, tracks the brightest light into player+0x64, ends at lcall 0x4c0:0x25"),
    (0x09778B, "obj_armour_value",      "code", "0 for id<0x20; else [0x69e6 + (id&0x1ff - 0x20)*4] * (obj[+4] & 0x3f) >> 6, +1"),
    (0x0972B0, "effect_state_reset",    "code", "mov byte ptr [0x70e1],0; [0x19a8]=13-(player+0x2e)/3, [0x19a9]=15-(player+0x2e)/5; zeroes [0x37e..0x383]; [0x386]=0x90"),
    (0x0973DD, "effect_apply_one",      "code", "13-way jmp word ptr cs:[bx+0x577]; sets [0x37e..0x386], ORs [0xd2] and [0x1900], raises player+0x64, adds protection into [0x827c] and [0x24ba]"),
    (0x0976C5, "effect_totals_apply",   "code", "consumes the accumulator: low bits reduce [0x19a8]/[0x19a9], nibble (w>>4)&0xf adds to all four armour bytes, then builds icons via active_spell_icons_build"),
    (0x097641, "active_spell_icons_build","code", "memset(buf,0x1e,3); buf[i] = [0x19bb + (player[0x3e+2i] & 0xf)] + ((player[0x3e+2i] & 0xf0)>>4)"),
    (0x09732F, "random_screen_effect_set","code", "picks rand()%3 into [0x19b0] when none active, dispatches on/off to 0x110:0x96 / 0x3b0:0x2f / 0x4c0:0x2f; which effect it is was NOT determined"),
    (0x0970B5, "player_record_save",    "code", "key = player[0] ^ 0xaa; writes the 0x37d-byte record at [0x827a] via lcall 0x538:0x39; caller 0x8D2D6 strcats \"player.dat\" (DGROUP 0x15c8)"),
    (0x0971B2, "player_record_load",    "code", "mirror of player_record_save via lcall 0x538:0x20, push 0x37d; restores [0x25cc/0x25ce/0x25d0], [0x8282], [0x8284], [0x25f1], [0x38a/0x38c]"),
    (0x097BA2, "level_ambient_light_load","code", "opens \"dl.dat\" (DGROUP 0x19cb; DATA/DL.DAT is 80 bytes), seeks to [0x8282]-1, reads one byte into [0x19ab]/[0x19ad]/[0x19ae]"),
    # --- text-window UI, overlay 139 (V=0x0458); [0x34a0] = the current window record
    (0x096460, "textwin_reset_main",    "code", "mov word ptr [0x34a0],0x92e; [0x974]=0; lcall 0x168:0x621 with the rect window 0x92e is statically initialised to at file 0x697AE"),
    (0x096489, "wait_ticks_or_key",     "code", "snapshots the 32-bit counter behind far [0x2148], polls until start+ticks, aborts early when the input source changes; brackets with cursor hide/show"),
    (0x09651D, "textwin_more_prompt",   "code", "draws \"[MORE]\" (DGROUP 0x1972) forcing colour 0x12, waits, erases with gfx_clipped_rect, sets [0x976] = window[+0x11]-1"),
    (0x0965B1, "textwin_select",        "code", "picks window 0x958 when [[0xe4]+8]==4, else window 0x92e"),
    (0x0965CC, "textwin_print_number",  "code", "itoa(value, buf, 10) via lcall 0x30:0x1d1b (push 0xa), erases the line, prints via print_wrapped"),
    (0x096643, "textwin_print_yesno",   "code", "prints \"Yes\" (DGROUP 0x1979) or \"No\" (0x197d) into the answer area"),
    (0x0966B1, "textwin_read_line",     "code", "maxlen clamped to 0x32; key loop with a blinking caret, backspace 8, arrows 0x8c/0x8f/0x91/0x92/0xa8; ESC restores the initial text and prints \"-\""),
    (0x096BA7, "textwin_prompt_yesno",  "code", "accepts Y/y/N/n (cmp ax,0x79), echoes via textwin_print_yesno, exits on 0x0d/0x1b/1/2/3; ESC returns -1"),
    (0x096C9C, "textwin_clear",         "code", "16 callers; gfx_select_bitmap(0x71) then gfx_clipped_rect over the window rect, resets cursor +8/+0xa from home +0xc/+0xe, zeroes +0x10/+0x11"),
    # --- main and the game loop (ghidra.md S27)
    (0x088940, "main",                  "code", "reached from c0_startup's lcall 0x64de:0x48 -> stub 0x67C28; calls init(argc,argv) at 0x88976, game_loop 0x88B3F, shutdown 0x88AFF, returns 0"),
    (0x088976, "main_init",             "code", "45 calls in order (ghidra.md S32): env/filesystem checks, level buffer, graphics, input, player record, conversation globals, clip window, palette. Init callees return a fatal_error code in AX, 0 = success"),
    (0x088B3F, "game_loop",             "code", "do { ax = event_pump(0) } while (ax > 3); then lcall 0x360:0xf2 (= 0x82B35) with argument 9"),
    (0x01EC8B, "event_pump",            "code", "thin wrapper passing 0 to event_pump_alternating"),
    (0x01EC3E, "event_pump_alternating","code", "round-robins two event sources via the [0x291] toggle, falling back to the other when the preferred returns negative"),
    (0x01EADD, "event_source_queued",   "code", "one-slot pushback at [0x26f] (sentinel 0xFFFF); fetches via lcall 0x1b90:0xf0c, consumes the pushback when that yields 0, flags it in [0x277], records the event in [0x278]"),
    (0x003D48, "blit_span_linear",     "code", "span-list walker, linear target: rows via ss:[bx+0x95c], target seg ss:[0x958] (= 0x3d14); {u16 row, x0, x1, src_off} terminated by row bit 15"),
    (0x008F17, "blit_span_linear_alt",  "code", "same algorithm as blit_span_linear on the other target: ss:[0x39d0] / ss:[0x39d2]"),
    (0x008D33, "blit_span_modex_masked","code", "the only Mode X loop with a per-pixel 'or al, al' (at 0x8D8C) -- transparency handling"),
    # --- .GR decode chain (ghidra.md S25)
    (0x01D4D7, "shape_handle_to_ptr",   "code", "handle -> far ptr via [0x2184]: bank = packed>>12, paragraph = packed & 0x3ff, address = [0x4fce:0xe4d2] + para + 0x800; banks switched via lcall 0x1b50:0xbe"),
    (0x01D543, "shape_draw",            "code", "reads the record header (+0 format, +1 w, +2 h, +3 aux palette), format 4 raw, else lcall 0x2133:0xf83; blits via gfx_blit_8arg"),
    (0x0250B3, "gr_decode_thunk",       "code", "stack-switching thunk: saves SS:SP at cs:0xc24/0xc26, DS/ES/SS = 0x60d8, sp = 0x510, lcall 0x65c:0x7f0c"),
    (0x0112CC, "gr_decode_dispatch",    "code", "call word ptr cs:[bx + 0x6d30] with bx = the UNSCALED format byte; 7-word table, even formats only"),
    (0x009499, "gr_decode_type8",       "code", "4-bit unpack (high nibble first, count u16 at the front) into scratch 0x43bf:0, then RLE stage 0x954D; returns es+0x540"),
    (0x0094DC, "gr_decode_type6",       "code", "identical to gr_decode_type8 but passes cx=2 to the setup at 0x9423"),
    (0x00954D, "gr_rle_xlat",           "code", "RLE with xlatb: control byte, run of one translated byte, then a literal run, repeating until si reaches si+cx"),
    (0x022B0E, "vga_set_dac_range",     "code", "waits on in al,0x3da & 8, out 0x3c8 first, lds si,[0x219c] + first*3, rep outsb count*3 bytes to 0x3c9"),
    (0x013319, "far_block_copy",        "code", "NOTE non-standard argument order: (src_seg, src_off, dst_seg, dst_off, len) -- segment BEFORE offset; rep movsw"),
    # --- Borland RTL, identified via overlay 167's call sites (ghidra.md S26)
    (0x0130BD, "intdosx",               "code", "int 0x21 at 0x130E2; and word ptr [si+0xc],1 at 0x13101 stores the carry flag into outregs.cflag"),
    (0x013366, "open",                  "code", "test si,0xc000 (O_TEXT/O_BINARY vs _fmode), test si,0x100 (O_CREAT), test si,0x400 (O_EXCL) -> errno 0x50 EEXIST"),
    (0x01181E, "close",                 "code", "cmp si,0x14; mov word ptr [bx+0x1e3c],0xffff releases the FILE slot"),
    (0x0140E0, "unlink",                "code", "mov ah,0x41 / int 0x21 (DOS delete file)"),
    (0x013C78, "stat",                  "code", "INT 21h AH=1Ah set-DTA then AH=4Eh findfirst attr 0x16; ORs si,0x4040 for the DOS directory bit; st_mode stored at struct +4"),
    (0x012C05, "stackavail",            "code", "mov ax,sp / sub ax,[0x9e] / sub ax,0x220 / and al,0xf0"),
    (0x011A1D, "farcoreleft",           "code", "32-bit result assembled from [0xa4..0xaa]"),
    # --- file I/O + startup checks, overlay V=0x538, code file 0xA4740 (ghidra.md S26)
    (0x0A4D1A, "dos_read",              "code", "REGS at [bp-0x18] with AX=0x3F00 (INT 21h AH=3Fh) then intdosx; on cflag stores DOS error in errno [0x96] and returns -1"),
    (0x0A4D67, "dos_write",             "code", "same shape as dos_read with AX=0x4000 (INT 21h AH=40h)"),
    (0x0A4FC1, "open_prefixed_file",    "code", "strcpy(buf, arg2 ? DGROUP 0x1be4 \"DATA\\\\\" : 0x5d0e the UWHOME path), strcat(arg1), open with flags from the cs:0x8e6 jump table (0x8001/0x8302/0x8304/0x8004)"),
    (0x0A4CC7, "read_whole_file",       "code", "open(name,0x8001), dos_read, compares the count, close; returns char 0/1"),
    (0x0A4C71, "write_whole_file",      "code", "open(name,0x8302,0x80), dos_write, compare, close; NOTE buffer-first argument order, unlike read_whole_file"),
    (0x0A4BA3, "have_free_stack_and_heap","code", "stackavail() >= 0x898 && farcoreleft() >= 0x5dc"),
    (0x0A4BC9, "check_8_file_handles",  "code", "opens \"a.tmp\"..\"h.tmp\" (seed DGROUP 0x1bb4, first letter incremented from 'a'), then closes and unlinks each; failure exits with code 6"),
    (0x0A4B36, "is_directory",          "code", "stat(path) then test word ptr [bp-0x1a],0x4000 (S_IFDIR)"),
    (0x0A4B61, "check_data_dirs",       "code", "is_directory(\"data\") & (\"crit\") & (\"cuts\") from DGROUP 0x1bd5/0x1bda/0x1bdf; fatal_error(0x3001) on failure"),
    (0x0A4B01, "print_error_two_strings","code", "four print_wrapped calls: DGROUP 0x1bcd \"Error: \", arg1, 0x1bbe, arg2"),
    (0x0A47BC, "dir8_from_delta_abs",   "code", "8-way direction from two signed bytes using abs(a)/2 vs abs(b); same octant numbering as dir8_from_delta 0x17F29 but different tie-breaking"),
    (0x0A48B7, "dir8_between_points",   "code", "dir8_from_delta_abs(x1-x0, y1-y0)"),
    (0x0A4841, "octant_ccw_from_delta", "code", "45-degree sectors counter-clockwise from +x; DISTINCT numbering from dir8_from_delta_abs, do not conflate"),
    # --- inventory mechanics, overlay 124; panel UI, overlay 125 (ghidra.md S26)
    (0x08E020, "ui_redraw_inv_slot",    "code", "maps the slot through the slot->element table at DGROUP+0x175e, then ui_redraw_element"),
    (0x08E035, "inv_slot_obj_ptr",      "code", "forms &inv_slots[arg] as 0x6a88 + arg*2 and passes it to obj_ptr_from_word; returns DX:AX"),
    (0x08E04C, "inv_find_empty_slot",   "code", "scans slots 5..0x12 of [0x6a88] for a zero link, else 0xFFFF"),
    (0x08E077, "inv_put_object_in_slot","code", "or word ptr [bx+0x6a88],ax writes the object index into the slot; add word ptr [0x82de],si adds its weight"),
    (0x08E16A, "inv_find_slot_of_obj",  "code", "obj_index_from_ptr then a 20-iteration scan via the element->slot table at DGROUP+0x177a; negates the slot when found nested via 0x2C3ED"),
    (0x08E5F0, "inv_remove_object",     "code", "2-arg thunk pushing count=1 into inv_remove_object_n"),
    (0x08E605, "inv_remove_object_n",   "code", "worker: sub word ptr [0x82de],di (weight); refresh_container/container_arrows for slots >= 0x13, ui_redraw_element below that; arg2 is a count checked against the object's quantity field"),
    (0x08E8FF, "inv_slot_take_object",  "code", "removes from a slot and returns the object's far pointer; sub [0x82de],di and or word ptr [bx+0x6a88],ax"),
    (0x08EEA9, "inv_weight_fits",       "code", "obj_get_weight + [0x82de] compared against [0x82e0]; returns 1 iff <="),
    (0x08F1A2, "inv_panel_click",       "code", "ui_hittest_panel_element on the cursor, maps the element through DGROUP+0x177a to a slot, branches on the cursor object [0x6afc]/[0x6afe]; its word argument is an unidentified action code"),
    (0x090690, "ui_redraw_inv_panel",   "code", "checks the suppression flag [0x79e] then ui_redraw_element_range(6, 0x16)"),
    (0x0906D6, "ui_redraw_element_range","code", "loops ui_redraw_element from [bp+6] while si < [bp+8]"),
    (0x09091A, "ui_hittest_panel_element","code", "walks the 14-byte-stride rect table at DGROUP+0x161c; returns the element index, with 0x17/0x18 for two hard-coded rects"),
    (0x02C3ED, "obj_find_in_container_chain","code", "recursive container chain search used by inv_find_slot_of_obj"),
        (0x00617C, "gfx_build_row_table",   "code", "row[y] = ax + y*[0x36a8]; [0x36a8] is 0x50 (80) in the file; writes [bx+0x36ac] descending"),
    (0x006194, "gfx_build_plane_masks", "code", "expands seed [0x2d2c]='0f 0e 0c 08' into [0x3b64] and [0x2d31]='01 03 07 0f' into [0x3ca8], 0x50 x 4 bytes = 320 entries"),
    (0x0058E6, "gfx_clip_and_dispatch", "code", "shared tail of the 6 widest graphics entries: reads source origin [0xdc6]/[0xdc8], clips against [0x3df4]/[0x3df6]/[0x3df8], ends jmp word ptr [0xdc2]"),
    # --- overlay pool, reachable since ghidra.md S20
    (0x08A1F1, "fatal_error",           "code", "strcpy(buf, DGROUP+0x1432 = \"Underworld can no longer run.  Error code XXXX.\\r\\n$\"), patches offset 0x2a with 'A'+(code>>12) then octal(code&0x1ff); 26 call sites via lcall 0x390:0x25"),
    # --- conversation VM runtime, overlay V=0x2f8, code file 0x745A0..0x7683B (ghidra.md S25)
    (0x0765A7, "conv_mem_get_word",     "code", "returns far [0x4704][i]; 87 callers, the most-called routine in the pool; [0x4704] is the VM's word memory, heap_alloc(([0x471c]+0x800)*2) at 0x74EF1"),
    (0x076592, "conv_mem_far_ptr",      "code", "returns AX=[0x4704]+i*2, DX=[0x4706] -- a far pointer to VM memory word i"),
    (0x0765BA, "conv_mem_set_word",     "code", "[0x4704][i] = arg; les bx,[0x4704] at 0x765C2, mov es:[bx],ax at 0x765CB"),
    (0x0765D0, "conv_stack_get_word",   "code", "returns [0x46fc][[0x4726]+i]; reads the VM eval stack at frame base [0x4726]"),
    (0x0765E6, "conv_bind_builtin",     "code", "strcmp-walks the 0x20-byte import table at [0x4700] (lcall 0x98:0x1f5 at 0x76611), stores a far pointer at [0x470e]+entry[+0x1a]*4"),
    (0x07664D, "conv_import_write_by_name","code", "(name, src, n): finds the import by name, copies min(n, entry[+0x18]) words into [0x4704] at entry[+0x1a]; call sites pass \"npc_attitude\", \"npc_hp\", \"npc_hunger\""),
    (0x0766EA, "conv_import_read_by_name","code", "mirror of conv_import_write_by_name, copying [0x4704] -> the caller's buffer; mov [bx],ax at 0x7673B"),
    (0x07675F, "conv_imports_reset_vars","code", "walks the import table, skips entry[+0x1e]==0x111, switches on entry[+0x1c]-0x126 via jmp cs:[bx+0x228a] at 0x76799"),
    (0x07624A, "conv_op_fetchm",        "code", "stack[sp] = mem[stack[sp]]; les bx,[0x46fc] then les bx,[0x4704]"),
    (0x0762B1, "conv_op_sto",           "code", "mem[stack[sp-1]] = stack[sp]; sub word ptr [0x46fa],2 at 0x762DD"),
    (0x076277, "conv_op_offset",        "code", "stack[sp-1] = stack[sp]+stack[sp-1]-1 (1-based indexing); dec [0x46fa] at 0x7629C"),
    (0x0762E4, "conv_op_calli",         "code", "loads the far pointer at [0x470e]+code[pc+1]*4, records the intrinsic id in [0x4722] at 0x7631F"),
    (0x074CE4, "conv_globals_load",     "code", "opens \"bglobals.dat\" (DGROUP+0xb94), scans {u16 slot, u16 count} records, loads the record whose slot == [0xc66]"),
    (0x074D81, "conv_globals_save",     "code", "mirror of conv_globals_load, writing the buffer back into the matching record"),
    (0x075A74, "conv_globals_save_current","code", "calls conv_globals_save([0x4704], [0x4706], [0x471c])"),
    (0x075863, "conv_header_parse",     "code", "builds the 0x20-byte import table: +0x1a slot id, +0x18 count/live, +0x1c data type, +0x1e import kind (cmp 0x111 at 0x759C6)"),
    # --- graphics module, segment 0x0085 (base 0x3650), ghidra.md S18
    (0x0067E5, "gfx_select_bitmap_impl","code", "body behind gfx_select_bitmap: thunk 0x7F44 -> jmp table 0x8907 -> here"),
    (0x0088C8, "gfx_jumptable",         "code", "40 x 3-byte near jmp at cs:0x5278..0x52EA; second-level dispatch for 20 of the 50 public thunks"),
    (0x005824, "gfx_blit_8arg",         "code", "widest public entry: thunk 0x8612 passes 8 word args on the 0x372c stack"),
    # --- timer service, segment 0x223b (hand-written asm module), ghidra.md S17
    (0x0255BA, "timer_isr",             "code", "INT 8 handler at cs:0x40A; installer writes 0x40a to IVT 0:0x20; reentrancy guard cs:[2], private stack, 17-slot scan, EOI out 0x20"),
    (0x0256D4, "timer_install_int8",    "code", "saves the old INT 8 vector from 0:0x20/0:0x22 into cs:0x118/0x11a; pre-wires slot 16 via mov cs:[0x44],0x51d; mov dx,0x40a and writes es:[0x20]/[0x22]"),
    (0x025720, "timer_uninstall_int8",  "code", "sets cs:[0x11c]=0xFFFF and restores the saved original vector from cs:0x118/0x11a into 0:0x20/0:0x22"),
    (0x025750, "timer_set_divisor",     "code", "cli; out 0x43,0x36 (PIT ch0 mode 3); caches [bp+6] at cs:0x122; out 0x40 lo then hi"),
    (0x02556A, "svc_resolve",           "code", "cmp bx,0x10; les bx,cs:[bx*4+0x124]; scans {u16 code,u16 off} for AX, terminator 0xFFFF; returns es:off or 0:0"),
    (0x0255A2, "svc_call",              "code", "bx = ss:[sp+4]; calls svc_resolve; tail-jumps via push dx/push ax/retf leaving args in place"),
    (0x025C78, "svc_call_code_0x64",    "code", "C wrapper: pushes far ptr 0x223b:0x09fc + arg via the 8086 push-imm16 idiom, AX=0x64, near-calls svc_call"),
    # --- Borland runtime
    (0x011F27, "fseek",                 "code", "flushes via lcall 0xe72:0x54f (=0x11A6F); whence==1 adjusts by the buffered count; clears FILE flags &0xfe5f, count, ptr; lseek; 0 / -1"),
    (0x0131BE, "ltoa",                  "code", "radix bounds cmp bx,0x24 / cmp bl,2; buffer at [bp+0xa]; 32-bit value at [bp+0xc]/[bp+0xe]; emits '-' for negatives"),
    # --- input/event polling
    (0x01F60C, "event_poll_buttons",    "code", "if far [0x2144] nonzero calls 0x2133:0x9f0; else builds a mask from bytes +0x52/+0x53 of far [0x2128], OR 1 and 0x1002"),
    (0x01EBA5, "event_poll_mods",       "code", "lcall 0x2133:0x971 (or 0x1eb29 when arg!=0); 0xFFFF if low byte 0; copies the word pair at far [0x2148] to [0x28d]/[0x28f]; ORs 0x400/0x200/0x100 from three byte flags"),
    (0x011520, "c0_startup",            "code", "Borland C0.ASM entry; MZ e_cs:e_ip resolves here (AGENTS.md)"),
    (0x012307, "rand",                  "code", "LCG: seed32 at [0x1e6a] * 0x015A4E35 + 1, returns (high word & 0x7FFF); 50 callers"),
    (0x033BFA, "grid64_cell_ptr",       "code", "if x,y < 64 returns far [0x188c] + (y*64 + x)*4, else NULL; 37 callers"),
    (0x02BA41, "level_buf_layout",     "code", "masks every grid cell's word1 to &0x3F, then derives the 5 region pointers at +0x4000/+0x5B00/+0x7300/+0x74FA"),
    (0x02C2F9, "obj_ptr_from_word",    "code", "id=(word>>6)&0x3FF; id<0x100 -> [0x2578]+id*27 (imul 0x1b), else [0x25a6]+(id-0x100)*8"),
    (0x02C362, "obj_index_from_ptr",   "code", "inverse of obj_ptr_from_word: (ptr-[0x2578])/27 for the 27-byte array, /8 for the 8-byte one; 30 callers"),
    (0x02C3AC, "obj_ptr_from_index",   "code", "idx<0x100 -> [0x2578]+idx*27 (mov dx,0x1b/imul), else the 8-byte array; 28 callers"),
    (0x01E3BE, "ems_map_page",        "code", "INT 67h AH=44h: AL=physical page, BX=logical page, DX=EMS handle from [0x22c0]; returns 1/0"),
    (0x01E76B, "cursor_redraw",       "code", "blits via segment 0x85 and rebuilds a box from position [0x268]/[0x26a] + extents [0x2300]/[0x2302]/[0x2384]/[0x238e] -- all four written by the cursor-bitmap setter 0x1EE3C, which is what upgraded this from overlay_* to cursor_*"),
    (0x01E7B7, "cursor_hide",         "code", "nested: inc the depth at [0x26c]; on 0->1 calls 0x1b90:0xc67; 12 callers"),
    (0x01E7CD, "cursor_show",         "code", "nested: dec [0x26c]; at 0 calls cursor_redraw, clears [0x26e], blits 0x85:0x48f4(1); 12 callers"),
    (0x02BFC7, "obj_link_from_word",   "code", "(word>>6)&0x3FF off a far pointer -- the 10-bit object link; 11 callers"),
    (0x0765A7, "conv_mem_read",        "code", "u16 from the conversation VM memory array [0x4704] at index*2"),
    (0x0765D0, "conv_stack_read",      "code", "u16 from the VM stack [0x46fc] at ([0x4726]+arg)*2 -- frame-relative"),
    (0x017FB1, "npc_set_goal_tile",  "code", "les bx,[0x2246] at 0x17FB4; writes goal x/y into word +0x0f bits 0-5 / 6-11 and height into +0x0d"),
    (0x018068, "npc_goto_tile",      "code", "call 0x17FB1 at 0x18084, then branches on whether the goal tile equals the object's own tile"),
    (0x01D6F7, "gfx_id_to_shape_slot","code", "cmp di,0x2000 at 0x1D6FF; ids >=0x2000 offset from [0x14fa], 0x1000-0x1fff from [0x14f6], else the table at [0x2188]"),
    (0x01E3DB, "ems_map_pages",      "code", "mov ax,0x5000 at 0x1E41C -- EMS 50h, map up to 4 (logical,physical) pairs on handle [0x22c0]"),
    (0x01EEA2, "cursor_for_region",  "code", "cmp byte ptr [0x282],0 at 0x1EEA6; walks [0x280] hotspot rects and applies the matching cursor id via cursor_set_bitmap"),
    (0x02239A, "music_request_track","code", "cmp byte ptr [0x242d],6 at 0x2239D; stores the pending track in [0x242e] unless track 6 is playing"),
    (0x025A4E, "timer_stop",         "code", "cmp word ptr cs:[bx+0x6a],1 at 0x25A5B then sets it to 2 -- the driver's CS-resident timer slot table"),
    (0x0353F2, "skill_check_roll",   "code", "sub ax,[bp+8] at 0x353F9 then rand()%31; buckets to 2/1/0/-1 at thresholds 28/15/2"),
    (0x036EE7, "add_polar_offset",   "code", "mov ax,0x140 at 0x36EF1 normalises an 8-bit heading; scales the trig pair by distance and adds into two caller variables"),
    (0x036FB8, "roll_dice",          "code", "lcall 0xe72:0xde7 at 0x36FD4 (= rand, file 0x12307) summed [bp+6] times scaled by [bp+8]/32768"),
    (0x0731C7, "plot_pixel_shaded",  "code", "mov ax,0x7fff at 0x731CF then div by the range; reads a pixel, adds base + rand offset, writes it back"),
    (0x08124F, "poll_input_low_code","code", "cmp ax,3 at 0x8126A drains events until a code <= 3; ESC (0x1b) sets the abort bit in [si+0x5b]"),
    (0x084527, "set_tile_region",    "code", "cmp [bp+0x10],0xa at 0x8461E bounds the tile type; writes type/height/floor tex/wall tex over a rectangle"),
    (0x08C418, "refresh_container",  "code", "mov si,0x14 at 0x8C41F; repopulates 8 display slots at DGROUP+0x6AB0 from the container chain at +0x6AAE"),
    (0x09D944, "apply_hit_critter",  "code", "and ax,0x1c0 at 0x9D962 requires the target's item id to be in the critter class before applying damage"),
    (0x0A169B, "fire_obj_trigger",   "code", "and ax,0x30 at 0xA16AC checks the trigger subtype against the event code, then runs the link through the 25-way dispatcher; refined 2026-08-23: matches the subtype against the 16-byte table at DGROUP+0x863c and recurses through link objects"),
    (0x07AC03, "menu_redraw_pair",   "code", "cmp si,2 at 0x7AE18 bounds a two-cell loop; repaints the newly and previously highlighted menu cells"),
    (0x08C364, "container_arrows",    "code", "and ax,0x4000 at 0x8C3B3 walks the container chain; sets [0x1793]/[0x1794], the bytes ui_redraw_element tests"),
    (0x08EE12, "obj_get_weight",      "code", "and ax,0x1ff at 0x8EE1E takes the item id, then *0xb + 0x6b64 for the 11-byte property record; mass is bits 4..15 of word+1"),
    (0x08F864, "ui_redraw_element",   "code", "cmp byte ptr [0x79e],0 at 0x8F86F suppresses the whole routine; dispatches by element index into three ranges"),
    (0x093AC0, "list_row_rect",       "code", "shl ax,4 at 0x93ACE; paints a 0x4f x 0x10 rect at x=0xec, y=0xc2-16*row-2 through ui_draw_rect"),
    (0x093D47, "ui_draw_rect",        "code", "lcall 0x18:0x48f4 at 0x93D86; 7 args, draws a w x h rect then optionally re-clips"),
    (0x002EA6, "sprite_set_pos_size", "code", "cmp ax,0x40 at 0x2EB8 bounds the slot; writes x +2, y +4, w +5, h +7 then calls sprite_mark_dirty"),
    (0x007D36, "vga_flip_row_table",  "code", "call 0x88E9 at 0x7D59; rewrites the per-row VRAM offset table at 0x36ac in descending order, inverting the row mapping"),
    (0x008111, "vga_set_clip_window", "code", "mov [0x5040],bx at 0x8140; = far entry 0x85:0x4ac1; copies 4 words into [0x3df4..0x3dfa]"),
    (0x008612, "vga_blit_bitmap",     "code", "mov sp,0x4fa8 at 0x8656; = far entry 0x85:0x4fc2; 8 words (x,y,src off/seg,h,w,sx,sy), clipped span-list blit"),
    (0x0132EA, "memset",              "code", "call 0x132c2 at 0x132F8 after re-ordering args; the callee does rep stosw + stosb"),
    (0x013DD5, "strlen",              "code", "repne scasb at 0x13DE6 with al=0, then not ax / dec ax"),
    (0x0A18AC, "dispatch_ctx_guard",  "code", "mov ax,[0x8634] at 0xA18B0; publishes a context far pointer only if null, calls the 25-case dispatcher 0xA1C36, then nulls it again; refined 2026-08-23: stashes TWO far pointers, [0x8634] and [0x8638] -- the trap and its actor"),
    (0x002EEB, "sprite_set_shape",    "code", "or word ptr [bx],2 at 0x2F0E sets the changed flag after writing the shape at +0x0b of a 16-byte slot in segment 0x5f1c"),
    (0x008342, "gfx_clipped_rect",    "code", "thunk at cs:0x4cf2, same 0x372c private stack; calls body 0x6A6E direct (not via the jumptable); 4 word args; clips against [0x3df4..0x3dfa] then emits"),
    (0x014864, "farmalloc",           "code", "add ax,0x13 at 0x1487A then >>4: rounds a dword byte count up to paragraphs including a 4-byte header"),
    (0x01BA8F, "npc_set_goal",        "code", "mov word ptr es:[bx+0xb],ax at 0x1BADD writes goal into bits 0-3 and target into bits 4-11"),
    (0x01E2F5, "event_set_pending",   "code", "or word ptr [0x5d9c],ax at 0x1E2FB -- the bitmask the dispatcher at 0x1E272 scans bit by bit"),
    (0x0214D3, "play_positional_snd", "code", "mov word ptr [bp-0xa],0x40 at 0x21505 (centre pan); derives pan/volume from listener position, reaches ems_map_page via 0x1F955"),
    (0x078D73, "ui_redraw_slot_mark", "code", "cmp byte ptr [bx+0x4729],0 at 0x78DBC picks the marker colour for a (side, slot) pair"),
    (0x089507, "obj_dispatch_by_mode","code", "jmp word ptr cs:[bx+0x187] at 0x8952E dispatches 4 modes; mode 2 lcalls the caller's far callback"),
    # --- from the parallel reading pass, every cited instruction re-verified
    #     locally with work/verify_claim.py before being accepted here
    (0x003029, "sprite_mark_dirty",    "code", "mov word ptr cs:[0],1 at 0x3029; adds the record to its layer list and marks overlapping sprites"),
    (0x003130, "sprite_flush_lists",   "code", "mov ax,0x5f1c at 0x314E; walks the deferred draw lists and re-blits, bracketed by cursor_hide/show"),
    (0x007F44, "gfx_select_bitmap",    "code", "thunk at 0x85:0x48f4 (base 0x3650 confirmed: 0x2E00+0x850+0x48f4 = 0x7F44); switches DS/ES/SS to 0x372c, sp=0x4fa8, calls jumptable 0x8907 -> body 0x67E5; 1 arg"),
    (0x011D1C, "fopen",                "code", "call 0x11cfa at 0x11D20 scans the 20-entry FILE table at DGROUP+0x1cfc"),
    (0x01199D, "fclose",               "code", "mov byte ptr [si+4],0xff at 0x119F8 after flushing and closing the handle"),
    (0x013147, "dos_error_to_errno",   "code", "mov word ptr [0x1e88],si / mov al,[si+0x1e8a] / mov word ptr [0x96],si; 16 of its 24 call sites have an INT 21h within 20 bytes"),
    (0x013D13, "strcat",               "code", "lea si,[di-1] at 0x13D27 captures the destination NUL after repne scasb"),
    (0x013DB1, "strcpy",               "code", "repne scasb at 0x13DC5 then rep movsb"),
    (0x014C00, "near_free",            "code", "sub bx,4 at 0x14C07 converts a user pointer to its 4-byte block header"),
    (0x01477E, "farfree",              "code", "mov dx,[bp+8] at 0x14788 takes only the segment of a far pointer"),
    (0x017F29, "dir8_from_delta",      "code", "neg ax at 0x17F49; nested signed compares of dx,dy against 2x the other, returning 0..7"),
    (0x018954, "npc_set_anim_state",   "code", "and ax,0x3f at 0x18961 on the object's byte +0x15; resets or advances the frame nibble"),
    (0x0189D9, "npc_set_heading_dir8", "code", "shl al,5 at 0x189E3 writes dir*32 as the coarse angle at object +9"),
    (0x01E9A0, "input_wait_release",   "code", "cmp word ptr [0x278],1 at 0x1E9AB; spins on the input queue until the held button changes"),
    (0x01EDA6, "cursor_stack_pop",     "code", "mov byte ptr [0x282],al at 0x1EDB9; pops the 4-deep cursor-id stack at [0x23be]"),
    (0x01EE3C, "cursor_set_bitmap",    "code", "writes [0x238e],[0x2384],[0x2300],[0x2302] at 0x1EE69..0x1EE88 -- the extents cursor_redraw reads"),
    (0x02506F, "isqrt32",              "code", "mov sp,0x510 at 0x25094 (the same 0x60d8 private stack as vm2_enter); Newton iteration on a 32-bit input"),
    (0x021635, "play_sound_effect",    "code", "shl ax,3 at 0x2166A indexes an 8-byte descriptor table; falls through to the MIDI voice allocator"),
    (0x02B443, "sort_obj_by_height",   "code", "mov al,[bx+0x2510] at 0x2B47A; two bubble passes over 6-byte records by top then bottom height"),
    (0x033C2F, "obj_create",           "code", "and ax,0xfe00 at 0x33C73 writes the type into item_id bits 0-8 of a freshly allocated record"),
    (0x034023, "ui_slot_set",          "code", "jmp word ptr cs:[bx+0x402] at 0x34037 dispatches 9 slots; sets a redraw bit per slot"),
    (0x035AED, "msg_print_string_id",  "code", "or ax,0x200 at 0x35AF6 forces string block 1, then resolves and prints"),
    (0x037459, "print_wrapped",        "code", "cmp di,0x31 at 0x37536 breaks the text into <=49-char lines at the last space"),
    (0x078981, "ui_draw_obj_slot",     "code", "and ax,0x1ff at 0x789C8 takes the item id; draws a 16x16 icon and the quantity"),
    (0x093C29, "list_row_highlight",   "code", "cmp ax,[bp+6] at 0x93C30 against [0x122]; repaints old and new rows of a 7-row list"),
    (0x0927C0, "level_buf_alloc",      "code", "the ONLY writer of [0x188c]: malloc(0x7E08 = 32,264) = exactly a LEV.ARK level record's decompressed size"),
    (0x0927F7, "level_grid_copy_in",   "code", "copies 0x1000 four-byte cells into [0x188c], then sets [0x1890]=1"),
    (0x0392D9, "ovl_int3f_handler",   "code", "the INT 3Fh vector points here at runtime (3bd4:04e9); reads the 2 bytes after CD 3F, backs the return address up by 2, calls ovl_load"),
    (0x039389, "ovl_load",             "code", "Borland overlay loader; works through a per-overlay descriptor in ES (+0x10,+0x18,+0x1a,+0x1b,+0x1c) and manager globals [0x118]/[0x11c]/[0x12c]"),
    (0x074626, "heap_alloc",            "code", "rounds the 32-bit size up to a multiple of 4, adds 12 B of overhead, walks a free list at [0x46f6] -- a private heap, not INT 21h"),
    (0x0747BE, "heap_free",             "code", "validates the far pointer via 0x745d1, then steps back 8 B to the block header"),
    # --- conversation subsystem (analysis/data-formats.md, ghidra.md section 11)
    (0x074E15, "conv_load",             "code", "mallocs 0x5000, reads archive 2 record [0xc66], calls conv_parse"),
    (0x075863, "conv_parse",            "code", "decodes the record header field-by-field; IS the record layout"),
    (0x075A95, "conv_vm_run",           "code", "42-opcode stack VM; refuses to run unless code[0]==0x22"),
    (0x075E1B, "conv_vm_table",         "data", "42 jump-table slots = segment base 0x745A0 + 0x187B"),
    (0x0765E6, "conv_register_builtin", "code", "walks the 32-byte import table, strcmp, stores far ptr at [0x470e]+idx*4"),
    (0x07C38C, "conv_init",             "code", "opens DATA\\cnv.ark then the 51 registration sites at 0x7C39B"),
    (0x0754F6, "conv_expand_at",        "code", "strchr(s,'@') substitution expander used by say/respond/streq"),
    # --- the threaded engine, segment 0x065C (ghidra.md sections 10b-10f)
    (0x0093C0, "vm2_code_base",         "data", "segment 0x065C:0000; unique best fit for the dispatch table, 63/111"),
    (0x054FD4, "vm2_dispatch_table",    "data", "111 slots at 0x4FCE:0x24F4; byte-identical in guest RAM (section 10f)"),
    (0x0250B3, "vm2_enter",             "code", "sets SI=arg3, DS=arg4, private stack 0x60D8:0x510, lcall 0x065C:0x7F0C"),
    (0x0112CC, "vm2_decode_trampoline", "code", "call word ptr cs:[bx+0x6d30] / retf -- 6-entry decode API"),
    (0x0100F0, "vm2_decode_table",      "data", "the 6 doors indexed by BX (2 stubs, 4 decoder variants)"),
    (0x0093F9, "vm2_expand_4bpp",       "code", "lodsb / and 0xF0 / shr 4 / xlatb / stosb over both nibbles"),
    (0x009423, "vm2_load_xlat_table",   "code", "rep movsb of cx<<4 bytes from DS:SI to 0x065C:0000 (the xlat table)"),
    # --- misc, each read from its own code
    (0x075A12, "conv_init_fnptr_array", "code", "mallocs [0x4718]*4 and pre-fills every slot with the default stub 0x2f8:0x00ed"),
    (0x07DD53, "conv_publish_vars",     "code", "publishes 30 of the 31 CNV variable imports by name via lcall 0x2f8:0x98"),
    (0x0792AD, "conv_publish_attitude",  "code", "publishes npc_attitude through the same call, twice"),
    (0x08BC38, "gfx_init",             "code", "reads data/allpals.dat's first 0x200 B to DGROUP:0x6732, then loads the .GR archives by name"),
    (0x08B798, "gr_archive_load",      "code", "walks a .GR offset table at [0x672c], sizing each record and reading it"),
    (0x08B435, "gr_record_read",       "code", "seeks and reads one .GR record RAW -- no decode happens at load time"),
    (0x0811FC, "cuts_build_filename",   "code", "strcpy CUTS\\csXXX.nXX then 3-bit digit groups -- octal filenames"),
    (0x089179, "uwhome_env_lookup_and_savedir",     "code", "walks environ at [0x2042] comparing 6 bytes against \"UWHOME\", then scans for '='"),
]


def strings(d):
    out, i = {}, DGROUP
    while i < len(d) - 1:
        if 32 <= d[i] < 127:
            j = i
            while j < len(d) and 32 <= d[j] < 127:
                j += 1
            if j < len(d) and d[j] == 0 and j - i >= 3:
                out[i - DGROUP] = d[i:j].decode("latin1")
            i = j + 1
        else:
            i += 1
    return out


def functions():
    out = []
    for line in FUNCS.read_text().splitlines():
        m = re.match(r"([0-9a-f]{4}):([0-9a-f]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)", line)
        if m:
            out.append((int(m.group(1), 16) * 16 + int(m.group(2), 16) - SKEW,
                        m.group(5), int(m.group(4))))
            continue
        m = re.match(r"CODE_TAIL::([0-9a-f]+)\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)", line)
        if m:
            out.append((int(m.group(1), 16), m.group(4), int(m.group(3))))
    out.sort()
    return out


def xrefs(d, strs, funcs):
    """Attribute every PUSH/MOV of a DGROUP string offset to the nearest
    preceding function start.  Nearest-preceding is an approximation --
    functions.txt gives instruction counts, not byte extents."""
    starts = [f[0] for f in funcs]
    hits = collections.defaultdict(set)
    for op in [0x68] + list(range(0xB8, 0xC0)):
        for m in re.finditer(re.escape(bytes([op])), d):
            o = m.start()
            if o + 3 > len(d):
                continue
            imm = struct.unpack_from("<H", d, o + 1)[0]
            if imm in strs:
                k = bisect.bisect_right(starts, o) - 1
                if k >= 0:
                    hits[k].add(imm)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    a = ap.parse_args()
    d = EXE.read_bytes()
    strs = strings(d)
    funcs = functions()
    hits = xrefs(d, strs, funcs)
    print(f"{EXE}: {len(funcs)} functions, {len(strs)} DGROUP strings")
    print(f"  TIER 1 verified names        : {len(TIER1)}")
    print(f"  TIER 2 string-annotated fns  : {len(hits)} "
          f"({100 * len(hits) // len(funcs)}%), "
          f"{sum(len(v) for v in hits.values())} (function, string) pairs")
    if not a.emit:
        return
    with OUT.open("w") as fh:
        fh.write("# UW2.EXE symbols. Addresses are FILE OFFSETS.\n")
        fh.write("# TIER 1: read from the code and verified. Safe to apply.\n\n")
        for off, name, kind, why in sorted(TIER1):
            fh.write(f"{off:06X}  {kind:4s}  {name:22s}  # {why}\n")
        fh.write("\n# TIER 2: DGROUP strings a function references. The reference\n"
                 "# is a fact; any name it suggests is NOT. Promote by hand.\n\n")
        for k in sorted(hits, key=lambda k: funcs[k][0]):
            off, fname, inref = funcs[k]
            names = ", ".join(sorted(strs[s] for s in hits[k])[:6])
            fh.write(f"{off:06X}  xref  {fname:28s}  inrefs={inref:<4d} {names}\n")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
