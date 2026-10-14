/* Host-side validation for the same freestanding resource service linked into
 * WC1.TOS.  Run from release/ so the DOS-style WC1DATA\\ prefix resolves to
 * the staged original files.  This deliberately supplies only the GEMDOS
 * calls that resources.c uses; no Falcon code or libc enters the target. */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define FRAME_BYTES (320U * 200U)

extern void resource_init(void);
extern int resource_load_title(void);
extern const char *resource_intro_opening_text;
extern const char *resource_intro_credit_text[11];
extern void resource_reset_intro_scene(void);
extern void resource_draw_intro_frame(uint8_t *target, uint16_t stage,
                                      uint16_t index);
extern void resource_draw_title_screen(uint8_t *target, uint16_t selection);
extern void resource_draw_cockpit(void);
extern void resource_draw_cockpit_indicators(uint16_t fuel_percent,
                                             uint16_t weapon_percent);
extern int resource_draw_object(int32_t anchor_x, int32_t anchor_y,
                                uint16_t object_type, uint16_t frame);
extern int resource_draw_object_transformed(int32_t anchor_x,
                                            int32_t anchor_y,
                                            uint16_t object_type,
                                            uint16_t frame, int16_t angle,
                                            uint16_t scale, uint16_t flip);
extern int resource_draw_flight_object(int32_t direction_x,
                                       int32_t direction_y,
                                       int32_t direction_z,
                                       uint16_t object_type,
                                       int16_t object_pitch,
                                       int16_t object_yaw,
                                       int16_t object_roll,
                                       int16_t camera_pitch,
                                       int16_t camera_yaw,
                                       int16_t camera_roll);
extern void resource_draw_target_lock(void);
extern int resource_load_cockpit(uint16_t mode);
extern int resource_load_packet(const char *name, uint16_t section);
extern int resource_load_object_shape(uint16_t object_type);
extern int resource_load_flight_weapons(uint16_t player_type);
extern int resource_load_capital_view(uint16_t object_type, uint16_t frame);
extern void resource_flight_service_capital(void);
extern void resource_flight_weapons_reset(void);
extern void resource_flight_weapons_tick(void);
extern void resource_flight_background_reset(void);
extern void resource_flight_background_tick(void);
extern void resource_draw_flight_background(void);
extern void resource_draw_flight_scene(void);
extern void resource_flight_combat_reset(void);
extern void resource_flight_combat_spawn(uint16_t slot, uint16_t type);
extern void resource_flight_combat_tick(void);
extern void resource_flight_enemy_tick(void);
extern int resource_flight_fire(int32_t player_x, int32_t player_y,
                                int32_t player_z, int16_t player_pitch,
                                int16_t player_yaw, int16_t player_roll,
                                int16_t player_speed, uint16_t player_type);
extern void resource_draw_flight_projectiles(int32_t camera_x,
                                             int32_t camera_y,
                                             int32_t camera_z,
                                             int16_t camera_pitch,
                                             int16_t camera_yaw,
                                             int16_t camera_roll);
extern void resource_flight_velocity(int16_t object_pitch,
                                     int16_t object_yaw,
                                     int16_t object_roll, int16_t speed);
extern int resource_flight_target_visible(int32_t direction_x,
                                          int32_t direction_y,
                                          int32_t direction_z,
                                          int16_t camera_pitch,
                                          int16_t camera_yaw,
                                          int16_t camera_roll);
extern uint16_t resource_status;
extern uint16_t resource_palette_count;
extern uint16_t resource_palette_rgb565[256];
extern uint16_t resource_packet_compression;
extern uint16_t resource_cockpit_sections;
extern uint32_t resource_packet_size;
extern uint16_t resource_cockpit_mode;
extern uint16_t resource_object_type;
extern void resource_draw_mouse_cursor(uint8_t *target, int16_t x,
                                       int16_t y);
extern uint16_t resource_intro_explosion_count;
extern uint16_t resource_intro_laser_count;
extern uint16_t resource_intro_debris_count;
extern uint16_t resource_intro_debris_dust_count;
extern uint16_t resource_intro_asteroid_count;
extern uint16_t resource_flight_projectile_count;
extern uint16_t resource_flight_hit_count;
extern uint16_t resource_flight_spark_count;
extern uint16_t resource_flight_explosion_count;
extern uint16_t resource_flight_player_damage;
extern uint16_t resource_flight_scene_order_count;
extern uint16_t resource_flight_scene_order[71];
extern uint16_t resource_flight_scene_depth[71];
extern int16_t resource_flight_ship_shields[9][2];
extern int16_t resource_flight_ship_armor[9][4];
extern int32_t resource_flight_velocity_x;
extern int32_t resource_flight_velocity_y;
extern int32_t resource_flight_velocity_z;
extern int32_t resource_flight_target_distance;
extern uint8_t *render_target;

static FILE *open_files[4];
static uint8_t smoke_frame[FRAME_BYTES];
uint8_t *render_target = smoke_frame;
/* resources.c reads the same compact object.s state in the Falcon build.
 * The host smoke supplies a real native-endian roster for collision checks. */
uint16_t object_count;
uint16_t object_types[9];
uint16_t object_sides[9];
uint8_t object_active[9];
int32_t object_x[9];
int32_t object_y[9];
int32_t object_z[9];
int16_t object_pitch[9];
int16_t object_yaw[9];
int16_t object_roll[9];
int16_t object_speeds[9];

static uint32_t frame_checksum(const uint8_t *frame)
{
    uint32_t index;
    uint32_t checksum;

    checksum = 2166136261UL;
    for (index = 0; index < FRAME_BYTES; index++)
        checksum = (checksum ^ frame[index]) * 16777619UL;
    return checksum;
}

static FILE *lookup_file(int32_t handle)
{
    if (handle <= 0 || handle > (int32_t)(sizeof(open_files) /
                                           sizeof(open_files[0])))
        return 0;
    return open_files[handle - 1];
}

int32_t wc_fopen(const char *path, int32_t mode)
{
    char host_path[64];
    uint32_t index;

    if (mode != 0)
        return -1;
    for (index = 0; index + 1U < sizeof(host_path) && path[index] != '\0';
         index++) {
        host_path[index] = path[index] == '\\' ? '/' : path[index];
    }
    if (path[index] != '\0')
        return -1;
    host_path[index] = '\0';
    for (index = 0; index < sizeof(open_files) / sizeof(open_files[0]);
         index++) {
        if (open_files[index] == 0) {
            open_files[index] = fopen(host_path, "rb");
            return open_files[index] == 0 ? -1 : (int32_t)index + 1;
        }
    }
    return -1;
}

int32_t wc_fclose(int32_t handle)
{
    FILE *file;

    file = lookup_file(handle);
    if (file == 0)
        return -1;
    open_files[handle - 1] = 0;
    return fclose(file) == 0 ? 0 : -1;
}

int32_t wc_fread(int32_t handle, uint32_t count, void *destination)
{
    FILE *file;
    size_t read_count;

    file = lookup_file(handle);
    if (file == 0)
        return -1;
    read_count = fread(destination, 1, count, file);
    if (ferror(file))
        return -1;
    return (int32_t)read_count;
}

int32_t wc_fseek(int32_t offset, int32_t handle, int32_t whence)
{
    FILE *file;
    int origin;

    file = lookup_file(handle);
    if (file == 0)
        return -1;
    if (whence == 0)
        origin = SEEK_SET;
    else if (whence == 1)
        origin = SEEK_CUR;
    else if (whence == 2)
        origin = SEEK_END;
    else
        return -1;
    if (fseek(file, offset, origin) != 0)
        return -1;
    return (int32_t)ftell(file);
}

int main(void)
{
    uint32_t index;
    uint32_t changed;
    uint32_t min_x;
    uint32_t max_x;
    uint32_t min_y;
    uint32_t max_y;
    uint32_t transformed_checksum;
    uint32_t cockpit_base_checksum;

    resource_init();
    if (!resource_load_packet("PCSHIP.V04", 1U) ||
        resource_packet_compression != 0x00ffU || resource_packet_size != 0U) {
        fprintf(stderr, "absent packet slot was not accepted as empty\n");
        return 1;
    }
    memset(smoke_frame, 0x55, sizeof(smoke_frame));
    resource_draw_mouse_cursor(smoke_frame, 160, 100);
    if (smoke_frame[100U * 320U + 160U] != 0U ||
        smoke_frame[102U * 320U + 161U] != 0x0fU ||
        smoke_frame[100U * 320U + 161U] != 0x55U) {
        fprintf(stderr, "mouse cursor raster failed\n");
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if ((resource_status & 0x0003U) != 0x0003U ||
        resource_palette_count == 0U || resource_cockpit_sections != 9U) {
        fprintf(stderr, "resource load failed: status=%04x palette=%u sections=%u size=%lu\n",
                resource_status, resource_palette_count,
                resource_cockpit_sections, (unsigned long)resource_packet_size);
        return 1;
    }
    if (!resource_load_cockpit(0U) ||
        (resource_status & 0x0007U) != 0x0007U ||
        resource_cockpit_mode != 0U || resource_packet_size != 18730U) {
        fprintf(stderr, "Hornet cockpit load failed: status=%04x mode=%u size=%lu\n",
                resource_status, resource_cockpit_mode,
                (unsigned long)resource_packet_size);
        return 1;
    }
    if (!resource_load_cockpit(1U) || resource_cockpit_mode != 1U ||
        resource_packet_size == 0U) {
        fprintf(stderr, "Rapier cockpit lookup failed: status=%04x mode=%u size=%lu\n",
                resource_status, resource_cockpit_mode,
                (unsigned long)resource_packet_size);
        return 1;
    }
    /* Restore the Hornet packet so the draw verification below is stable. */
    if (!resource_load_cockpit(0U))
        return 1;
    object_types[0] = 0U;
    resource_flight_combat_reset();
    resource_flight_combat_spawn(0U, object_types[0]);
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_cockpit();
    cockpit_base_checksum = frame_checksum(smoke_frame);
    resource_draw_cockpit_indicators(100U, 100U);
    if (frame_checksum(smoke_frame) == cockpit_base_checksum) {
        fprintf(stderr, "cockpit indicator frame path failed\n");
        return 1;
    }
    resource_draw_target_lock();
    if (!resource_load_object_shape(0U) ||
        (resource_status & 0x000fU) != 0x000fU ||
        resource_object_type != 0U || resource_packet_size != 60913U) {
        fprintf(stderr, "Hornet shape load failed: status=%04x type=%u size=%lu\n",
                resource_status, resource_object_type,
                (unsigned long)resource_packet_size);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_object(160, 120, 0U, 0U)) {
        fprintf(stderr, "Hornet shape draw failed\n");
        return 1;
    }
    if (resource_palette_rgb565[185U] != 0U ||
        resource_palette_rgb565[190U] != 0U ||
        resource_palette_rgb565[191U] != 0x0004U) {
        fprintf(stderr, "cockpit palette reset failed: %04x,%04x,%04x\n",
                resource_palette_rgb565[185U],
                resource_palette_rgb565[190U],
                resource_palette_rgb565[191U]);
        return 1;
    }
    if (!resource_load_object_shape(1U) || resource_object_type != 1U ||
        resource_packet_size != 71590U ||
        !resource_draw_object(120, 120, 0U, 0U) ||
        !resource_draw_object(200, 120, 1U, 0U)) {
        fprintf(stderr, "three-slot ship-shape cache failed: status=%04x type=%u size=%lu\n",
                resource_status, resource_object_type,
                (unsigned long)resource_packet_size);
        return 1;
    }
    /* Dralthi is the largest supplied mobile-ship shape set (72,860 bytes).
     * Its load completes the DOS player-plus-two-preload cache policy. */
    if (!resource_load_object_shape(10U) || resource_object_type != 10U ||
        resource_packet_size != 72860U ||
        !resource_draw_object(120, 120, 0U, 0U) ||
        !resource_draw_object(160, 120, 1U, 0U) ||
        !resource_draw_object(200, 120, 10U, 0U)) {
        fprintf(stderr, "three-slot retention failed: status=%04x type=%u size=%lu\n",
                resource_status, resource_object_type,
                (unsigned long)resource_packet_size);
        return 1;
    }
    /* A fourth normal fighter still replaces the oldest retained packet,
     * which validates bounded replacement once the DOS-sized cache is full. */
    if (!resource_load_object_shape(9U) || resource_object_type != 9U ||
        resource_draw_object(120, 120, 0U, 0U) ||
        !resource_draw_object(160, 120, 1U, 0U) ||
        !resource_draw_object(200, 120, 10U, 0U) ||
        !resource_draw_object(240, 120, 9U, 0U)) {
        fprintf(stderr, "three-slot replacement failed: status=%04x type=%u size=%lu\n",
                resource_status, resource_object_type,
                (unsigned long)resource_packet_size);
        return 1;
    }
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed < 1000U) {
        fprintf(stderr, "shape decode produced too few pixels: %lu\n",
                (unsigned long)changed);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    /* Title_Sequence() has its own bounded resource lifetime. Start the
     * title load with empty fighter slots so this test proves it retains the
     * three-Dralthi/one-Hornet action-sphere art rather than reusing the
     * earlier generic shape-cache exercise. */
    resource_init();
    if (!resource_load_title() || (resource_status & 0x0010U) == 0U) {
        fprintf(stderr, "title packet load failed: status=%04x\n",
                resource_status);
        return 1;
    }
    /* nav.c:Title_Sequence() text comes from WC.EXE's DS:264E / DS:2767
     * pointers (resources.c load_intro_strings).  The expected FNV-1a over
     * the twelve NUL-terminated strings and their line counts were taken
     * from the 1990 WC.EXE at those pointers; the text itself stays out of
     * the repository. */
    {
        static const unsigned expected_lines[12] = {
            2U, 3U, 7U, 6U, 7U, 3U, 6U, 5U, 2U, 1U, 2U, 2U
        };
        uint32_t hash = 0x811C9DC5UL;
        unsigned string_index;

        for (string_index = 0; string_index < 12U; string_index++) {
            const char *text = string_index == 0U ?
                resource_intro_opening_text :
                resource_intro_credit_text[string_index - 1U];
            unsigned lines = 1U;
            size_t offset;

            if (text == NULL) {
                fprintf(stderr, "title string %u not loaded\n", string_index);
                return 1;
            }
            for (offset = 0;; offset++) {
                hash = (hash ^ (uint8_t)text[offset]) * 0x01000193UL;
                if (text[offset] == '\0')
                    break;
                if (text[offset] == '\n')
                    lines++;
            }
            if (lines != expected_lines[string_index]) {
                fprintf(stderr, "title string %u: %u lines, expected %u\n",
                        string_index, lines, expected_lines[string_index]);
                return 1;
            }
        }
        if (hash != 0x20116327UL) {
            fprintf(stderr, "title strings hash %08lx, expected 20116327\n",
                    (unsigned long)hash);
            return 1;
        }
    }
    if (resource_packet_size != 60913U ||
        !resource_draw_object(120, 120, 10U, 0U) ||
        !resource_draw_object(200, 120, 0U, 0U)) {
        fprintf(stderr,
                "title fighter shape retention failed: status=%04x size=%lu\n",
                resource_status, (unsigned long)resource_packet_size);
        return 1;
    }
    /* generate_stars() retains eight dust records and seven far stars after
     * the eye frame exists. Verify the same retained PLANETS.VGA frames feed
     * the flight renderer, rather than the old synthetic dot fallback. */
    memset(object_x, 0, sizeof(object_x));
    memset(object_y, 0, sizeof(object_y));
    memset(object_z, 0, sizeof(object_z));
    memset(object_pitch, 0, sizeof(object_pitch));
    memset(object_yaw, 0, sizeof(object_yaw));
    memset(object_roll, 0, sizeof(object_roll));
    object_count = 1U;
    object_active[0] = 1U;
    resource_flight_background_reset();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_flight_background();
    changed = 0;
    for (index = 0U; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed < 20U) {
        fprintf(stderr, "flight star/dust field produced too few pixels: %lu\n",
                (unsigned long)changed);
        return 1;
    }
    resource_flight_background_tick();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_object_transformed(160, 110, 10U, 0U, 45, 0x180U,
                                          0U)) {
        fprintf(stderr, "rotated Dralthi transform failed\n");
        return 1;
    }
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    transformed_checksum = frame_checksum(smoke_frame);
    if (changed < 100U) {
        fprintf(stderr, "rotated Dralthi produced too few pixels: %lu\n",
                (unsigned long)changed);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_object_transformed(160, 110, 10U, 0U, 45, 0x180U,
                                          0x10U) ||
        frame_checksum(smoke_frame) == transformed_checksum) {
        fprintf(stderr, "Dralthi horizontal-flip transform failed\n");
        return 1;
    }
    /* The active-flight path uses geom.c's eye-frame projection and fighter
     * view lattice rather than the old contact marker. Exercise both a
     * forward object and the equivalent one after a quarter turn. */
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_flight_object(0, 0, 0x00080000L, 10U,
                                     0, 0, 0, 0, 0, 0)) {
        fprintf(stderr, "forward 3Space Dralthi projection failed\n");
        return 1;
    }
    transformed_checksum = frame_checksum(smoke_frame);
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_flight_object(0x00080000L, 0, 0, 10U,
                                     0, 0, 0, 90, 0, 0) ||
        frame_checksum(smoke_frame) == transformed_checksum) {
        fprintf(stderr, "eye-frame-relative 3Space Dralthi projection failed\n");
        return 1;
    }
    resource_flight_velocity(90, 0, 0, 6);
    if (resource_flight_velocity_x != 1536L ||
        resource_flight_velocity_y != 0L ||
        resource_flight_velocity_z != 0L) {
        fprintf(stderr, "mission-frame velocity transform failed: %ld,%ld,%ld\n",
                (long)resource_flight_velocity_x,
                (long)resource_flight_velocity_y,
                (long)resource_flight_velocity_z);
        return 1;
    }
    if (!resource_flight_target_visible(0, 0, 2000L << 8, 0, 0, 0) ||
        resource_flight_target_distance != (2000L << 8) ||
        resource_flight_target_visible(0, 0, 12000L << 8, 0, 0, 0)) {
        fprintf(stderr, "check_target visibility range failed\n");
        return 1;
    }
    if (!resource_load_flight_weapons(1U) ||
        !resource_load_flight_weapons(2U) ||
        !resource_load_flight_weapons(3U)) {
        fprintf(stderr, "player projectile packet load failed\n");
        return 1;
    }
    /* The flight weapon path mirrors fire_fixed_projectile_weapon(): the
     * Hornet fires its two enabled laser hardpoints together, then its bolts
     * move through the source 24.8 forward vector before being projected. */
    if (!resource_load_flight_weapons(0U)) {
        fprintf(stderr, "Hornet projectile packet load failed\n");
        return 1;
    }
    if (!resource_load_capital_view(6U, 0U) ||
        !resource_load_capital_view(6U, 16U)) {
        fprintf(stderr, "capital per-view packet load failed\n");
        return 1;
    }
    memset(object_types, 0, sizeof(object_types));
    memset(object_x, 0, sizeof(object_x));
    memset(object_y, 0, sizeof(object_y));
    memset(object_z, 0, sizeof(object_z));
    memset(object_pitch, 0, sizeof(object_pitch));
    memset(object_yaw, 0, sizeof(object_yaw));
    memset(object_roll, 0, sizeof(object_roll));
    memset(object_active, 0, sizeof(object_active));
    object_count = 2U;
    object_types[1] = 6U;
    object_active[1] = 1U;
    object_z[1] = 2000L << 8;
    resource_flight_service_capital();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    if (!resource_draw_flight_object(0, 0, 2000L << 8, 6U, 0, 0, 0,
                                     0, 0, 0)) {
        fprintf(stderr, "capital 3Space projection failed\n");
        return 1;
    }
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed == 0U) {
        fprintf(stderr, "capital 3Space decode produced no pixels\n");
        return 1;
    }
    resource_flight_weapons_reset();
    if (resource_flight_fire(0, 0, 0, 0, 0, 0, 6, 0U) != 2 ||
        resource_flight_projectile_count != 2U) {
        fprintf(stderr, "Hornet fixed-projectile fire failed: count=%u\n",
                resource_flight_projectile_count);
        return 1;
    }
    /* A 160-unit laser reaches the visible 100-unit near plane in one DOS
     * update. This catches confusion between ObjectTypeData.damageCapacity
     * (25) and maximumVelocity (160). */
    for (index = 0U; index < 1U; index++)
        resource_flight_weapons_tick();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_flight_projectiles(0, 0, 0, 0, 0, 0);
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed == 0U) {
        fprintf(stderr, "flight projectile projection failed\n");
        return 1;
    }
    /* check_for_collision() walks dynamic cannon shots against the compact
     * ship roster before movement. Two Hornet lasers at their source mounts
     * hit this close Dralthi: 25 - 30 / 2 gives ten damage each, reducing
     * its source 50-point fore shield to 30 and creating two LASER_SPARKs. */
    memset(object_types, 0, sizeof(object_types));
    memset(object_x, 0, sizeof(object_x));
    memset(object_y, 0, sizeof(object_y));
    memset(object_z, 0, sizeof(object_z));
    memset(object_pitch, 0, sizeof(object_pitch));
    memset(object_yaw, 0, sizeof(object_yaw));
    memset(object_roll, 0, sizeof(object_roll));
    memset(object_speeds, 0, sizeof(object_speeds));
    object_count = 2U;
    object_types[0] = 0U;
    object_types[1] = 10U;
    object_z[1] = 20L << 8;
    resource_flight_combat_reset();
    resource_flight_combat_spawn(0U, object_types[0]);
    resource_flight_combat_spawn(1U, object_types[1]);
    resource_flight_weapons_reset();
    if (resource_flight_fire(0, 0, 0, 0, 0, 0, 6, 0U) != 2 ||
        resource_flight_projectile_count != 2U) {
        fprintf(stderr, "collision fixture projectile fire failed\n");
        return 1;
    }
    resource_flight_combat_tick();
    if (resource_flight_hit_count != 2U ||
        resource_flight_projectile_count != 0U ||
        resource_flight_spark_count != 2U ||
        resource_flight_ship_shields[1][0] != 30) {
        fprintf(stderr,
                "source collision/shield/spark state failed: hits=%u bolts=%u sparks=%u fore=%d\n",
                resource_flight_hit_count, resource_flight_projectile_count,
                resource_flight_spark_count,
                resource_flight_ship_shields[1][0]);
        return 1;
    }
    /* Capital damage follows internal_damage()'s Kilrathi/Confederate
     * accumulation branch rather than the fighter system-event branch.  A
     * Venture takes seven ten-point post-armor hits per test loop here; after
     * 70 events it leaves the active roster and retains an EXPLOSION1 object. */
    object_types[1] = 4U;
    object_sides[1] = 0U;
    object_z[1] = 20L << 8;
    resource_flight_combat_reset();
    resource_flight_combat_spawn(0U, object_types[0]);
    resource_flight_combat_spawn(1U, object_types[1]);
    resource_flight_ship_shields[1][0] = 0;
    resource_flight_ship_shields[1][1] = 0;
    resource_flight_ship_armor[1][0] = 0;
    resource_flight_ship_armor[1][1] = 0;
    resource_flight_ship_armor[1][2] = 0;
    resource_flight_ship_armor[1][3] = 0;
    resource_flight_weapons_reset();
    for (index = 0U; index < 35U; index++) {
        resource_flight_weapons_reset();
        if (resource_flight_fire(0, 0, 0, 0, 0, 0, 6, 0U) != 2)
            break;
        resource_flight_combat_tick();
        if (object_active[1] == 0U)
            break;
    }
    if (object_active[1] != 0U || resource_flight_explosion_count != 1U) {
        fprintf(stderr, "capital internal damage/explosion failed: active=%u explosions=%u\n",
                object_active[1], resource_flight_explosion_count);
        return 1;
    }
    /* Draw_3Space_Frame() transforms every represented world class before
     * selecting its far-to-near list.  The Falcon keeps its compact classes
     * in separate fixed arrays, so exercise the shared bounded merger with a
     * retained star field, ship, cannon bolts, and the EXPLOSION1 created
     * above. The exported trace is the target fixture for the DOS-sized
     * distance >> 8 sort key: 1=background, 2=ship, 3=projectile,
     * 4=explosion in the high byte. */
    memset(object_types, 0, sizeof(object_types));
    memset(object_x, 0, sizeof(object_x));
    memset(object_y, 0, sizeof(object_y));
    memset(object_z, 0, sizeof(object_z));
    memset(object_pitch, 0, sizeof(object_pitch));
    memset(object_yaw, 0, sizeof(object_yaw));
    memset(object_roll, 0, sizeof(object_roll));
    memset(object_active, 0, sizeof(object_active));
    object_count = 2U;
    object_types[0] = 0U;
    object_types[1] = 10U;
    object_active[0] = 1U;
    object_active[1] = 1U;
    object_z[1] = 2000L << 8;
    resource_flight_weapons_reset();
    if (resource_flight_fire(0, 0, 0, 0, 0, 0, 6, 0U) != 2) {
        fprintf(stderr, "scene merge projectile setup failed\n");
        return 1;
    }
    resource_flight_background_reset();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_flight_scene();
    {
        uint16_t kinds;

        kinds = 0U;
        if (resource_flight_scene_order_count == 0U) {
            fprintf(stderr, "3Space scene merge produced no entries\n");
            return 1;
        }
        for (index = 0U; index < resource_flight_scene_order_count; index++) {
            uint16_t kind;

            if (index != 0U &&
                resource_flight_scene_depth[index - 1U] <
                    resource_flight_scene_depth[index]) {
                fprintf(stderr, "3Space scene merge depth order failed\n");
                return 1;
            }
            kind = resource_flight_scene_order[index] >> 8;
            if (kind >= 1U && kind <= 4U)
                kinds |= (uint16_t)(1U << kind);
        }
        if ((kinds & 0x1eU) != 0x1eU) {
            fprintf(stderr, "3Space scene merge omitted a represented class: %04x\n",
                    kinds);
            return 1;
        }
    }
    /* fire() uses the enemy's forward cone and lifetime/range test. Put a
     * Dralthi one hundred units behind the player, with its native +Z frame
     * aimed through the player, then let its two source laser mounts reach the
     * player before collision. Shields and armor are cleared to exercise the
     * source your_internal_damage() path as well as ownership filtering. */
    memset(object_sides, 0, sizeof(object_sides));
    memset(object_types, 0, sizeof(object_types));
    memset(object_x, 0, sizeof(object_x));
    memset(object_y, 0, sizeof(object_y));
    memset(object_z, 0, sizeof(object_z));
    memset(object_pitch, 0, sizeof(object_pitch));
    memset(object_yaw, 0, sizeof(object_yaw));
    memset(object_roll, 0, sizeof(object_roll));
    memset(object_speeds, 0, sizeof(object_speeds));
    object_count = 2U;
    object_types[0] = 10U;
    object_types[1] = 10U;
    object_sides[1] = 1U;
    object_z[1] = -(20L << 8);
    resource_flight_combat_reset();
    resource_flight_combat_spawn(0U, object_types[0]);
    resource_flight_combat_spawn(1U, object_types[1]);
    resource_flight_ship_shields[0][0] = 0;
    resource_flight_ship_shields[0][1] = 0;
    resource_flight_ship_armor[0][0] = 0;
    resource_flight_ship_armor[0][1] = 0;
    resource_flight_ship_armor[0][2] = 0;
    resource_flight_ship_armor[0][3] = 0;
    resource_flight_weapons_reset();
    resource_flight_enemy_tick();
    if (resource_flight_projectile_count != 2U) {
        fprintf(stderr, "enemy fire cone/loadout failed: bolts=%u\n",
                resource_flight_projectile_count);
        return 1;
    }
    resource_flight_combat_tick();
    if (resource_flight_hit_count != 2U ||
        resource_flight_player_damage == 0U ||
        resource_flight_projectile_count != 0U) {
        fprintf(stderr,
                "enemy projectile/player damage failed: hits=%u damage=%u bolts=%u active=%u/%u sides=%u/%u\n",
                resource_flight_hit_count, resource_flight_player_damage,
                resource_flight_projectile_count, object_active[0],
                object_active[1], object_sides[0], object_sides[1]);
        return 1;
    }
    resource_flight_weapons_reset();
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_title_screen(smoke_frame, 0U);
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed < 4000U) {
        fprintf(stderr, "title shape decode produced too few pixels: %lu\n",
                (unsigned long)changed);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_reset_intro_scene();
    resource_draw_intro_frame(smoke_frame, 1U, 0U);
    changed = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed < 100U) {
        fprintf(stderr,
                "title 3Space constellation/fighter decode failed: pixels=%lu\n",
                (unsigned long)changed);
        return 1;
    }
    {
        uint32_t first_stars;
        uint32_t later_stars;
        uint16_t frame;

        first_stars = frame_checksum(smoke_frame);
        for (frame = 0; frame < 30U; frame++) {
            memset(smoke_frame, 0, sizeof(smoke_frame));
            resource_draw_intro_frame(smoke_frame, 1U, 0U);
        }
        later_stars = frame_checksum(smoke_frame);
        if (first_stars == later_stars) {
            fprintf(stderr,
                    "3Space projected stars did not follow title camera\n");
            return 1;
        }
    }
    /* The first action sphere's record 32 reaches its canonical command-two
     * explosion during the opening/space/logo timeline.  This verifies the
     * retained OBJECTS.VGA section two reaches its real title simulation;
     * unlike the old approximation, the Dralthi is not simply removed. */
    resource_reset_intro_scene();
    for (index = 0U; index < 235U; index++) {
        memset(smoke_frame, 0, sizeof(smoke_frame));
        resource_draw_intro_frame(smoke_frame, 1U, 0U);
    }
    if (resource_intro_explosion_count != 1U ||
        resource_intro_laser_count != 14U ||
        resource_intro_debris_count != 7U ||
        resource_intro_debris_dust_count != 8U) {
        fprintf(stderr,
                "title Explosion1/laser/debris actions failed: explosions=%u lasers=%u debris=%u dust=%u\n",
                resource_intro_explosion_count, resource_intro_laser_count,
                resource_intro_debris_count, resource_intro_debris_dust_count);
        return 1;
    }
    /* Action sphere 17 is the credit asteroid field. Its source
     * start_hazard_field() immediately creates slots one through three, then
     * normal update_hazards() continues to populate the remaining slots. */
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_draw_intro_frame(smoke_frame, 3U, 0U);
    if (resource_intro_asteroid_count < 3U) {
        fprintf(stderr, "title credit asteroid field failed: asteroids=%u\n",
                resource_intro_asteroid_count);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_reset_intro_scene();
    resource_draw_intro_frame(smoke_frame, 0U, 0U);
    changed = 0;
    min_x = FRAME_BYTES;
    max_x = 0;
    min_y = FRAME_BYTES;
    max_y = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U) {
            uint32_t x;
            uint32_t y;

            x = index % 320U;
            y = index / 320U;
            if (x < min_x)
                min_x = x;
            if (x > max_x)
                max_x = x;
            if (y < min_y)
                min_y = y;
            if (y > max_y)
                max_y = y;
            changed++;
        }
    }
    if (changed < 200U || min_x >= 120U || max_x <= 200U ||
        min_y >= 70U || max_y <= 70U) {
        fprintf(stderr,
                "opening subtitle decode failed: pixels=%lu bounds=%lu,%lu-%lu,%lu\n",
                (unsigned long)changed, (unsigned long)min_x,
                (unsigned long)min_y, (unsigned long)max_x,
                (unsigned long)max_y);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_reset_intro_scene();
    resource_draw_intro_frame(smoke_frame, 2U, 99U);
    changed = 0;
    min_x = FRAME_BYTES;
    max_x = 0;
    min_y = FRAME_BYTES;
    max_y = 0;
    for (index = 0; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U) {
            uint32_t x;
            uint32_t y;

            x = index % 320U;
            y = index / 320U;
            if (x < min_x)
                min_x = x;
            if (x > max_x)
                max_x = x;
            if (y < min_y)
                min_y = y;
            if (y > max_y)
                max_y = y;
            changed++;
        }
    }
    if (changed < 4000U || min_x > 8U || max_x < 300U ||
        min_y > 55U || max_y < 150U) {
        fprintf(stderr,
                "title-logo zoom decode failed: pixels=%lu bounds=%lu,%lu-%lu,%lu\n",
                (unsigned long)changed, (unsigned long)min_x,
                (unsigned long)min_y, (unsigned long)max_x,
                (unsigned long)max_y);
        return 1;
    }
    memset(smoke_frame, 0, sizeof(smoke_frame));
    resource_reset_intro_scene();
    resource_draw_intro_frame(smoke_frame, 2U, 0U);
    changed = 0;
    for (index = 0U; index < FRAME_BYTES; index++) {
        if (smoke_frame[index] != 0U)
            changed++;
    }
    if (changed != 286U || frame_checksum(smoke_frame) != 0xfb15dc43UL) {
        fprintf(stderr,
                "sub-1x title-logo raster changed: pixels=%lu checksum=%08lx\n",
                (unsigned long)changed,
                (unsigned long)frame_checksum(smoke_frame));
        return 1;
    }
    printf("WC1 resource smoke: status=%04x palette=%u cockpit-sections=%u pixels=%lu\n",
           resource_status, resource_palette_count, resource_cockpit_sections,
           (unsigned long)changed);
    return 0;
}
