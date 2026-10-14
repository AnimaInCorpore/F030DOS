/*
 * Bounded DOS-data resource service for the Falcon port.
 *
 * This is deliberately freestanding C: it emits plain m68k ELF objects that
 * VLINK combines with the TOS assembly bootstrap.  No MiNT runtime, libc, or
 * dynamic allocation is involved.  The packet/LZW rules mirror
 * wc1-re/src/sdl/resources.c; only the backing storage policy is Falcon
 * specific and fixed-size for a stock 4 MB machine.
 */

#include <stdint.h>

#define WC1_PACKET_OFFSET_MASK 0x00ffffffUL
#define WC1_PACKET_ABSENT 0xffU
#define WC1_LZW_CLEAR_CODE 0x100U
#define WC1_LZW_STOP_CODE 0x101U
#define WC1_LZW_FIRST_CODE 0x102U
#define WC1_LZW_MAX_CODES 0x1000U

#define WC1_FILE_BUFFER_MAX 0x1000UL
#define WC1_PACKET_BUFFER_MAX 0x20000UL
#define WC1_PACKET_COMPRESSED_MAX 0x20000UL
#define WC1_TARGET_LOCK_BUFFER_MAX 0x1000UL
#define WC1_PRIMARY_COCKPIT_BUFFER_MAX 0x8000UL
#define WC1_COCKPIT_DAMAGE_BUFFER_MAX 0x4000UL
#define WC1_TITLE_LOGO_BUFFER_MAX 0x6000UL
#define WC1_TITLE_FONT_BUFFER_MAX 0x4000UL
#define WC1_TITLE_MENU_BUFFER_MAX 0x4000UL
#define WC1_CONSTELLATION_BUFFER_MAX 0x1000UL
/* Title_Sequence() explicitly retains these two OBJECTS.VGA sections before
 * creating canned action sphere 16.  Their observed decoded sizes are
 * 24,911 and 24,077 bytes respectively, so the fixed caps retain the exact
 * source streams without taking an object-cache slot away from the Hornet or
 * Dralthi. */
#define WC1_TITLE_EXPLOSION_BUFFER_MAX 0x6200UL
#define WC1_TITLE_DEBRIS_BUFFER_MAX 0x6000UL
/* OBJECTS.VGA section four supplies the pipe/O-ring/girder/tubing/glass
 * variants. Section five, retained above, supplies metal-sheet and wing. */
#define WC1_TITLE_COMMON_DEBRIS_BUFFER_MAX 0x1400UL
/* OBJECTS.VGA section six is the common 3Space laser-cannon shape set. Its
 * decoded title packet is 341 bytes. */
#define WC1_TITLE_LASER_BUFFER_MAX 0x200UL
/* load_ship(OBJECT_TYPE_ASTEROID_FIELD) retains the rock fragment packet and
 * the stock-memory asteroid set.  The original only loads the alternate
 * section 17 set on its expanded-memory configuration, so the Falcon's
 * bounded path intentionally uses sections 13 and 16 only. */
#define WC1_TITLE_ROCK_BUFFER_MAX 0x400UL
#define WC1_TITLE_ASTEROID_BUFFER_MAX 0x4600UL
/* The DOS dynamic-object allocator has forty slots (10..49).  Projectiles
 * use that same ceiling here, while ships remain in the separate nine-entry
 * mission roster owned by object.s. */
#define WC1_FLIGHT_PROJECTILE_COUNT 40U
#define WC1_FLIGHT_OBJECT_COUNT 9U
/* OBJECTS.VGA section nine is the six-frame LASER_SPARK set selected by
 * object_collision() whenever a cannon bolt strikes an object. */
#define WC1_FLIGHT_HIT_SPARK_COUNT WC1_FLIGHT_PROJECTILE_COUNT
/* OBJECTS.VGA sections 6, 7, and 8 are the laser, mass-driver, and neutron
 * bolt shape sets.  They are tiny sparse packets, but each gets a bounded
 * independent copy so the generic packet workspace can still service nav
 * shape replacements outside the render interval. */
#define WC1_FLIGHT_PROJECTILE_BUFFER_MAX 0x400UL
#define WC1_INTRO_STAR_COUNT 7U
#define WC1_FLIGHT_DUST_COUNT 8U
#define WC1_FLIGHT_STAR_COUNT 7U
#define WC1_FLIGHT_BACKGROUND_COUNT \
    (WC1_FLIGHT_DUST_COUNT + WC1_FLIGHT_STAR_COUNT)
#define WC1_FLIGHT_DUST_MAX_DISTANCE 1400U
#define WC1_FLIGHT_STAR_DISTANCE 15000L
#define WC1_FLIGHT_EYE_RADIUS 100L
#define WC1_INTRO_FIGHTER_COUNT 4U
#define WC1_INTRO_EXPLOSION_COUNT 1U
#define WC1_FLIGHT_EXPLOSION_COUNT 8U
/* The diagnostic flight roster has eight non-eye ships, forty dynamic cannon
 * objects, and the fifteen star-field records.  Keep the merge storage
 * bounded rather than recreating the DOS 64-slot object arena on Falcon. */
#define WC1_FLIGHT_SCENE_MAX \
    ((WC1_FLIGHT_OBJECT_COUNT - 1U) + WC1_FLIGHT_PROJECTILE_COUNT + \
     WC1_FLIGHT_BACKGROUND_COUNT + WC1_FLIGHT_EXPLOSION_COUNT)
#define INTRO_EXPLOSION1_ANIMATION_COUNT 20U
/* The Hornet fires a seven-pair burst every seven updates. A laser lasts 30
 * updates, so twelve slots cover the source burst with headroom while still
 * making the stock-Falcon title allocation fixed and visible. */
#define WC1_INTRO_LASER_COUNT 12U
/* Create_explosion_debris() emits exactly seven sprite debris objects before
 * making its separate eight-dust-particle pass. */
#define WC1_INTRO_DEBRIS_COUNT 7U
#define WC1_INTRO_DEBRIS_DUST_COUNT 8U
/* update_hazards() owns twenty title hazard slots. Keep that source limit,
 * rather than turning the credit backdrop into a fixed small sprite list. */
#define WC1_INTRO_ASTEROID_COUNT 20U
/* RotateRLEImage() allows a decoded source frame up to 0xfa00 bytes.  Keep
 * one bounded source workspace rather than materialising every rotated
 * shape, which is the difference between the original visual path fitting
 * beside two Falcon Videl pages and requiring expansion RAM. */
#define WC1_TRANSFORM_SCRATCH_MAX 0xfa00UL
/* The supplied WC1 ship shape sets peak at 72,860 bytes (Dralthi). Three
 * 72 KiB slots reproduce WC1's player-plus-two-nav-preload policy and still
 * leave a stock 4 MiB Falcon more than enough ST-RAM beside its three 64 KiB
 * frame surfaces. */
#define WC1_OBJECT_SHAPE_BUFFER_MAX 0x12000UL
#define RESOURCE_OBJECT_SLOT_COUNT 3U

#define RESOURCE_STATUS_PALETTE 0x0001U
#define RESOURCE_STATUS_COCKPIT_PACKET 0x0002U
#define RESOURCE_STATUS_PRIMARY_COCKPIT 0x0004U
#define RESOURCE_STATUS_OBJECT_SHAPE 0x0008U
#define RESOURCE_STATUS_TITLE 0x0010U
#define RESOURCE_STATUS_FLIGHT_WEAPONS 0x0020U
#define RESOURCE_STATUS_CAPITAL_VIEW 0x0040U
#define RESOURCE_STATUS_COCKPIT_DAMAGE 0x0080U
#define RESOURCE_STATUS_ERROR 0x8000U

/* initialize() resets the six cockpit fade slots and uses entry $bf as the
 * dark-blue space/cockpit background.  The source GAME.PAL contains black at
 * $bf; that runtime override must remain visible in true colour too. */
#define WC1_COCKPIT_FADE_FIRST 185U
#define WC1_COCKPIT_FADE_COUNT 6U
#define WC1_COCKPIT_BACKGROUND_INDEX 0xbfU

#define FALCON_FRAME_WIDTH 320
#define FALCON_FRAME_HEIGHT 200
#define TARGET_LOCK_X 160
#define TARGET_LOCK_Y 150

extern int32_t wc_fopen(const char *path, int32_t mode);
extern int32_t wc_fclose(int32_t handle);
extern int32_t wc_fread(int32_t handle, uint32_t count, void *destination);
extern int32_t wc_fseek(int32_t offset, int32_t handle, int32_t whence);
extern uint8_t *render_target;
/* object.s owns this compact, native-endian active roster.  Reading it
 * directly avoids a second DOS-endian collision copy or a per-tick marshal. */
extern uint16_t object_count;
extern uint16_t object_types[WC1_FLIGHT_OBJECT_COUNT];
extern uint16_t object_sides[WC1_FLIGHT_OBJECT_COUNT];
extern int32_t object_x[WC1_FLIGHT_OBJECT_COUNT];
extern int32_t object_y[WC1_FLIGHT_OBJECT_COUNT];
extern int32_t object_z[WC1_FLIGHT_OBJECT_COUNT];
extern int16_t object_pitch[WC1_FLIGHT_OBJECT_COUNT];
extern int16_t object_yaw[WC1_FLIGHT_OBJECT_COUNT];
extern int16_t object_roll[WC1_FLIGHT_OBJECT_COUNT];
extern int16_t object_speeds[WC1_FLIGHT_OBJECT_COUNT];
extern uint8_t object_active[WC1_FLIGHT_OBJECT_COUNT];

uint16_t resource_status;
uint16_t resource_palette_count;
uint16_t resource_cockpit_sections;
uint16_t resource_packet_compression;
uint32_t resource_packet_size;
uint16_t resource_object_type;
uint16_t resource_cockpit_mode;
/* Palette entries expanded once to the Falcon's native RGB565 words. */
uint16_t resource_palette_rgb565[256];
uint8_t resource_packet_data[WC1_PACKET_BUFFER_MAX];

static uint8_t resource_file_data[WC1_FILE_BUFFER_MAX];
static uint8_t resource_compressed_data[WC1_PACKET_COMPRESSED_MAX];
static uint8_t resource_target_lock_data[WC1_TARGET_LOCK_BUFFER_MAX];
static uint32_t resource_target_lock_size;
static uint8_t resource_primary_cockpit_data[WC1_PRIMARY_COCKPIT_BUFFER_MAX];
static uint32_t resource_primary_cockpit_size;
static uint8_t resource_cockpit_damage_data[WC1_COCKPIT_DAMAGE_BUFFER_MAX];
static uint32_t resource_cockpit_damage_size;
static uint8_t resource_title_logo_data[WC1_TITLE_LOGO_BUFFER_MAX];
static uint32_t resource_title_logo_size;
static uint8_t resource_title_font_data[WC1_TITLE_FONT_BUFFER_MAX];
static uint32_t resource_title_font_size;
static uint8_t resource_title_menu_data[WC1_TITLE_MENU_BUFFER_MAX];
static uint32_t resource_title_menu_size;
static uint8_t resource_constellation_data[WC1_CONSTELLATION_BUFFER_MAX];
static uint32_t resource_constellation_size;
static uint8_t resource_title_explosion_data[WC1_TITLE_EXPLOSION_BUFFER_MAX];
static uint32_t resource_title_explosion_size;
static uint8_t resource_title_debris_data[WC1_TITLE_DEBRIS_BUFFER_MAX];
static uint32_t resource_title_debris_size;
static uint8_t resource_title_common_debris_data
    [WC1_TITLE_COMMON_DEBRIS_BUFFER_MAX];
static uint32_t resource_title_common_debris_size;
static uint8_t resource_title_laser_data[WC1_TITLE_LASER_BUFFER_MAX];
static uint32_t resource_title_laser_size;
static uint8_t resource_title_rock_data[WC1_TITLE_ROCK_BUFFER_MAX];
static uint32_t resource_title_rock_size;
static uint8_t resource_title_asteroid_data[WC1_TITLE_ASTEROID_BUFFER_MAX];
static uint32_t resource_title_asteroid_size;
static uint8_t resource_flight_neutron_data[WC1_FLIGHT_PROJECTILE_BUFFER_MAX];
static uint32_t resource_flight_neutron_size;
static uint8_t resource_flight_mass_driver_data
    [WC1_FLIGHT_PROJECTILE_BUFFER_MAX];
static uint32_t resource_flight_mass_driver_size;
static uint8_t resource_flight_hit_spark_data
    [WC1_FLIGHT_PROJECTILE_BUFFER_MAX];
static uint32_t resource_flight_hit_spark_size;
static uint8_t resource_transform_scratch[WC1_TRANSFORM_SCRATCH_MAX];
/* Zero-angle scaled sprites have separable source coordinates. Keep the
 * bounded maps in BSS so the hot destination loop does not spend its time on
 * two signed 32-bit divisions and a scratch-row multiply per pixel. */
static int32_t resource_transform_x_map[FALCON_FRAME_WIDTH];
static int32_t resource_transform_y_map[FALCON_FRAME_HEIGHT];
/* Keep the accepted title callback cadence independent of renderer speed.
 * resource_draw_intro_frame() sets this while the attract artwork is drawn;
 * the zero-angle optimization is consequently reserved for the flight path. */
static uint8_t resource_intro_rendering;
static uint8_t resource_capital_shape_data[0x7000UL];
static uint32_t resource_capital_shape_size;
static uint16_t resource_capital_shape_type;
static uint16_t resource_capital_shape_frame;
static uint16_t resource_intro_star_frame[WC1_INTRO_STAR_COUNT];
static uint32_t resource_intro_star_seed;
/* WC1's FixedVector is 24.8. Unit axes therefore use 0x100 and the star
 * positions generated by the original are 15000 << 8 units away. */
typedef struct IntroFixedVector {
    int32_t x;
    int32_t y;
    int32_t z;
} IntroFixedVector;

/* generate_stars() owns eight moving dust records followed by seven far star
 * records. Keep that source order and the source frame lattice here instead
 * of folding the background into the nine mission-object slots. */
typedef struct FlightBackgroundObject {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t frame;
    uint16_t screen_angle;
    uint8_t star;
    uint8_t offscreen;
} FlightBackgroundObject;
static FlightBackgroundObject resource_flight_background
    [WC1_FLIGHT_BACKGROUND_COUNT];
static uint32_t resource_flight_background_seed;
static uint16_t resource_flight_background_frame;
static uint8_t resource_flight_background_initialized;

/* The first flight weapon slice keeps projectiles independent from the
 * mission roster: DOS reserves object slots 10..49 for dynamic objects,
 * while this port's object.s owns slots 0..8 for player/mission ships. */
typedef struct FlightProjectile {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t owner;
    uint16_t type;
    uint16_t ticks;
    uint16_t frame;
    uint8_t spark;
    uint8_t fresh;
    uint8_t active;
} FlightProjectile;
static FlightProjectile resource_flight_projectiles
    [WC1_FLIGHT_PROJECTILE_COUNT];
typedef struct FlightExplosion {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t type;
    uint16_t frame;
    uint16_t animation_index;
    uint16_t active;
    int32_t scale;
} FlightExplosion;
static FlightExplosion resource_flight_explosions
    [WC1_FLIGHT_EXPLOSION_COUNT];
typedef enum FlightSceneKind {
    FLIGHT_SCENE_BACKGROUND = 1,
    FLIGHT_SCENE_SHIP = 2,
    FLIGHT_SCENE_PROJECTILE = 3,
    FLIGHT_SCENE_EXPLOSION = 4
} FlightSceneKind;
typedef struct FlightSceneEntry {
    uint16_t depth;
    uint16_t kind;
    uint16_t index;
} FlightSceneEntry;
static FlightSceneEntry resource_flight_scene[WC1_FLIGHT_SCENE_MAX];
/* The host fixture reads this last sorted sequence.  Encoding is
 * (FlightSceneKind << 8) | local index, and depth is the DOS-sized
 * distance >> 8 used as the sort key. */
uint16_t resource_flight_scene_order_count;
uint16_t resource_flight_scene_order[WC1_FLIGHT_SCENE_MAX];
uint16_t resource_flight_scene_depth[WC1_FLIGHT_SCENE_MAX];
static int16_t resource_flight_gun_refire;
static uint16_t resource_flight_enemy_refire[WC1_FLIGHT_OBJECT_COUNT];
uint16_t resource_flight_projectile_count;
uint16_t resource_flight_hit_count;
uint16_t resource_flight_spark_count;
uint16_t resource_flight_explosion_count;
uint16_t resource_flight_player_damage;
/* These are the source g_aasShipShield/g_aasShipArmor values for the
 * nine-slot Falcon roster.  m68k-native shorts are already big-endian. */
int16_t resource_flight_ship_shields[WC1_FLIGHT_OBJECT_COUNT][2];
int16_t resource_flight_ship_armor[WC1_FLIGHT_OBJECT_COUNT][4];
uint16_t resource_flight_ship_damage[WC1_FLIGHT_OBJECT_COUNT];
static int16_t resource_flight_ship_max_shields
    [WC1_FLIGHT_OBJECT_COUNT][2];
static uint16_t resource_flight_ship_types[WC1_FLIGHT_OBJECT_COUNT];
static uint8_t resource_flight_ship_initialized[WC1_FLIGHT_OBJECT_COUNT];
static uint16_t resource_flight_ship_accumulated
    [WC1_FLIGHT_OBJECT_COUNT];
static uint16_t resource_flight_ship_component_damage
    [WC1_FLIGHT_OBJECT_COUNT];
static uint8_t resource_flight_ship_pilot[WC1_FLIGHT_OBJECT_COUNT];
static uint32_t resource_flight_combat_frame;
/* resource_flight_velocity() returns its exact 24.8 source-style result in
 * these ABI-simple globals for the small assembly state owners. */
int32_t resource_flight_velocity_x;
int32_t resource_flight_velocity_y;
int32_t resource_flight_velocity_z;
/* check_target() considers the object-screen list only out to 12,000 units.
 * The assembly target owner reads this 24.8 result after a visible test. */
int32_t resource_flight_target_distance;

static IntroFixedVector resource_intro_star_position[WC1_INTRO_STAR_COUNT];
static IntroFixedVector resource_intro_camera_right;
static IntroFixedVector resource_intro_camera_up;
static IntroFixedVector resource_intro_camera_forward;
static IntroFixedVector resource_intro_camera_position;
static IntroFixedVector resource_intro_camera_velocity;
static int16_t resource_intro_camera_pitch;
typedef struct IntroTitleShip {
    uint16_t type;
    uint16_t collision_radius;
    int16_t pitch_rate;
    int16_t yaw_rate;
    int16_t roll_rate;
    int16_t acceleration;
    IntroFixedVector position;
    IntroFixedVector velocity;
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    const int16_t *sequence;
    uint16_t sequence_offset;
    int16_t command;
    int16_t action_count;
    int16_t yaw_goal;
    int16_t pitch_goal;
    int16_t roll_goal;
    int16_t yaw_rotation;
    int16_t pitch_rotation;
    int16_t roll_rotation;
    int32_t speed;
    uint16_t destruction_ticks;
    uint8_t destroying;
    uint8_t active;
} IntroTitleShip;
static IntroTitleShip resource_intro_fighters[WC1_INTRO_FIGHTER_COUNT];
/* ShipExplosion() moves a destroyed fighter's position/velocity into a new
 * OBJECT_TYPE_EXPLOSION1 object.  The original action sphere has only one
 * such event, so one bounded effect slot is sufficient for the exact title
 * sequence and keeps the stock-Falcon allocation explicit. */
typedef struct IntroTitleExplosion {
    IntroFixedVector position;
    IntroFixedVector velocity;
    int32_t scale;
    uint16_t frame;
    uint16_t animation_index;
    uint8_t active;
} IntroTitleExplosion;
static IntroTitleExplosion
    resource_intro_explosions[WC1_INTRO_EXPLOSION_COUNT];
uint16_t resource_intro_explosion_count;
typedef struct IntroTitleLaser {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t ticks;
    uint8_t active;
} IntroTitleLaser;
static IntroTitleLaser resource_intro_lasers[WC1_INTRO_LASER_COUNT];
uint16_t resource_intro_laser_count;
typedef struct IntroTitleDebris {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t type;
    uint16_t frame;
    uint16_t flip;
    uint16_t animation_index;
    uint16_t animation_delay;
    uint16_t ticks;
    uint8_t active;
} IntroTitleDebris;
static IntroTitleDebris resource_intro_debris[WC1_INTRO_DEBRIS_COUNT];
/* Public only for the asset smoke test. The full title explosion creates
 * seven sparse debris sprites; its separate dust particles are still a
 * subsequent renderer slice. */
uint16_t resource_intro_debris_count;
static uint32_t resource_intro_debris_seed;
typedef struct IntroTitleDust {
    IntroFixedVector position;
    IntroFixedVector velocity;
    uint16_t screen_angle;
    uint16_t ticks;
    uint8_t active;
} IntroTitleDust;
static IntroTitleDust resource_intro_debris_dust[WC1_INTRO_DEBRIS_DUST_COUNT];
uint16_t resource_intro_debris_dust_count;
static uint16_t resource_intro_space_frame;
/* These are deliberately a direct small representation of the original
 * asteroid hazard objects. ASTEROID1..6 share section 16 on a stock machine;
 * the retained axes are required for the source hazard velocity even though
 * their pre-rotated animation frames need no additional sprite transform. */
typedef struct IntroTitleAsteroid {
    IntroFixedVector position;
    IntroFixedVector velocity;
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    uint16_t type;
    uint16_t frame;
    uint16_t animation_index;
    uint16_t animation_delay;
    uint8_t active;
} IntroTitleAsteroid;
static IntroTitleAsteroid resource_intro_asteroids[WC1_INTRO_ASTEROID_COUNT];
/* Public only for the asset smoke test; it is the active hazard count, not a
 * gameplay score or an artificial title timer. */
uint16_t resource_intro_asteroid_count;
static uint32_t resource_intro_credit_seed;
static uint16_t resource_intro_credit_frame;
static uint8_t resource_intro_credit_scene_active;
static uint8_t resource_object_data[RESOURCE_OBJECT_SLOT_COUNT]
    [WC1_OBJECT_SHAPE_BUFFER_MAX];
static uint32_t resource_object_sizes[RESOURCE_OBJECT_SLOT_COUNT];
static uint16_t resource_object_types[RESOURCE_OBJECT_SLOT_COUNT];
static uint16_t resource_next_object_slot;
static uint8_t resource_clip_enabled;
static int16_t resource_clip_left;
static int16_t resource_clip_top;
static int16_t resource_clip_right;
static int16_t resource_clip_bottom;
static uint16_t resource_lzw_prefix[WC1_LZW_MAX_CODES];
static uint8_t resource_lzw_value[WC1_LZW_MAX_CODES];
static uint8_t resource_lzw_stack[WC1_LZW_MAX_CODES];
static char resource_path[32];

static void reset_intro_scene_state(void);
static void intro_spawn_explosion(IntroTitleShip *ship);
static void intro_fire_laser_pair(const IntroTitleShip *ship);
static int flight_player_uses_projectile(uint16_t player_type,
                                          uint16_t projectile_type);
void resource_flight_weapons_reset(void);
void resource_flight_combat_reset(void);
static void intro_spawn_explosion_debris(const IntroTitleShip *ship);
static void begin_intro_credit_scene(void);
static int load_intro_strings(void);
static void update_intro_credit_scene(void);
static void draw_intro_credit_asteroids(void);
static const uint16_t intro_explosion1_animation[];
int resource_load_object_shape(uint16_t object_type);
int resource_draw_flight_object(int32_t direction_x, int32_t direction_y,
                                int32_t direction_z, uint16_t object_type,
                                int16_t object_pitch, int16_t object_yaw,
                                int16_t object_roll,
                                int16_t camera_pitch, int16_t camera_yaw,
                                int16_t camera_roll);
int32_t resource_flight_distance(int32_t direction_x, int32_t direction_y,
                                 int32_t direction_z);

static uint32_t read_le32(const uint8_t *bytes)
{
    return (uint32_t)bytes[0] |
        ((uint32_t)bytes[1] << 8) |
        ((uint32_t)bytes[2] << 16) |
        ((uint32_t)bytes[3] << 24);
}

static uint16_t read_le16(const uint8_t *bytes)
{
    return (uint16_t)((uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8));
}

static uint32_t read_be32(const uint8_t *bytes)
{
    return ((uint32_t)bytes[0] << 24) |
        ((uint32_t)bytes[1] << 16) |
        ((uint32_t)bytes[2] << 8) |
        (uint32_t)bytes[3];
}

static int build_data_path(const char *name)
{
    static const char prefix[] = "WC1DATA\\";
    uint32_t source;
    uint32_t target;

    target = 0;
    source = 0;
    while (prefix[source] != '\0') {
        if (target + 1U >= sizeof(resource_path))
            return 0;
        resource_path[target++] = prefix[source++];
    }
    source = 0;
    while (name[source] != '\0') {
        if (target + 1U >= sizeof(resource_path))
            return 0;
        resource_path[target++] = name[source++];
    }
    resource_path[target] = '\0';
    return 1;
}

static int open_data_file(const char *name, int32_t *handle)
{
    int32_t result;

    if (!build_data_path(name))
        return 0;
    result = wc_fopen(resource_path, 0);
    if (result < 0)
        return 0;
    *handle = result;
    return 1;
}

static int read_exact(int32_t handle, uint32_t count, void *destination)
{
    return wc_fread(handle, count, destination) == (int32_t)count;
}

static int read_lzw_code(const uint8_t *source, uint32_t source_size,
                         uint32_t *bit_position, uint16_t width,
                         uint16_t *code)
{
    uint32_t value;
    uint32_t bits_read;

    value = 0;
    bits_read = 0;
    while (bits_read < width) {
        uint32_t byte_position;
        uint32_t shift;
        uint32_t available;
        uint32_t needed;
        uint32_t taken;
        uint32_t mask;

        byte_position = *bit_position >> 3;
        if (byte_position >= source_size)
            return 0;
        shift = *bit_position & 7U;
        available = 8U - shift;
        needed = (uint32_t)width - bits_read;
        taken = available < needed ? available : needed;
        mask = (1UL << taken) - 1UL;
        value |= ((uint32_t)(source[byte_position] >> shift) & mask)
            << bits_read;
        *bit_position += taken;
        bits_read += taken;
    }
    *code = (uint16_t)value;
    return 1;
}

static int write_lzw_code(uint16_t code, uint8_t *destination,
                          uint32_t destination_size,
                          uint32_t *destination_position,
                          uint8_t *first_value)
{
    uint32_t reverse_size;

    reverse_size = 0;
    while (code >= WC1_LZW_FIRST_CODE) {
        if (code >= WC1_LZW_MAX_CODES ||
            reverse_size >= WC1_LZW_MAX_CODES)
            return 0;
        resource_lzw_stack[reverse_size++] = resource_lzw_value[code];
        code = resource_lzw_prefix[code];
    }
    if (code > 0xffU || *destination_position >= destination_size)
        return 0;
    *first_value = (uint8_t)code;
    destination[(*destination_position)++] = *first_value;
    while (reverse_size != 0) {
        if (*destination_position >= destination_size)
            return 0;
        destination[(*destination_position)++] =
            resource_lzw_stack[--reverse_size];
    }
    return 1;
}

static int decode_origin_lzw(const uint8_t *source, uint32_t source_size,
                             uint8_t *destination,
                             uint32_t destination_size)
{
    uint32_t bit_position;
    uint32_t destination_position;
    uint16_t code_width;
    uint16_t code_width_threshold;
    uint16_t dictionary_size;
    uint16_t code;
    uint16_t decoded_code;
    uint16_t previous_code;
    uint8_t first_value;
    int special_code;

    bit_position = 0;
    destination_position = 0;
    code_width = 9;
    if (!read_lzw_code(source, source_size, &bit_position, code_width, &code))
        return 0;
    if (code != WC1_LZW_CLEAR_CODE)
        return 0;

    for (;;) {
        code_width = 9;
        code_width_threshold = 1U << code_width;
        dictionary_size = WC1_LZW_FIRST_CODE;
        previous_code = WC1_LZW_CLEAR_CODE;
        for (;;) {
            if (!read_lzw_code(source, source_size, &bit_position,
                               code_width, &code))
                return 0;
            if (code == WC1_LZW_STOP_CODE)
                return destination_position == destination_size;
            if (code == WC1_LZW_CLEAR_CODE)
                break;
            if (code > dictionary_size)
                return 0;

            special_code = code == dictionary_size;
            decoded_code = special_code ? previous_code : code;
            if (decoded_code == WC1_LZW_CLEAR_CODE ||
                !write_lzw_code(decoded_code, destination, destination_size,
                                &destination_position, &first_value))
                return 0;

            if (previous_code != WC1_LZW_CLEAR_CODE) {
                if (dictionary_size >= WC1_LZW_MAX_CODES)
                    return 0;
                resource_lzw_prefix[dictionary_size] = previous_code;
                resource_lzw_value[dictionary_size] = first_value;
                dictionary_size++;
                if (special_code) {
                    if (destination_position >= destination_size)
                        return 0;
                    destination[destination_position++] = first_value;
                }
                if (dictionary_size == code_width_threshold &&
                    code_width < 12U) {
                    code_width++;
                    code_width_threshold <<= 1;
                }
            }
            previous_code = code;
        }
    }
}

/* DOS: PacketLoad; canonical 1990 DOS entry/range TBD; record:
 * analysis/functions/PacketLoad.md. The DOS identity is not yet proven from
 * the hashed WC.EXE; this target resource seam is kept off new supported
 * paths until that range and its direct fixture are recovered. */
/* Load one Origin packet section into resource_packet_data. It accepts raw,
 * type-1 LZW, and verified type-0xFF empty slots, records section metadata,
 * and never allocates memory or reads outside the fixed resource buffers. */
int resource_load_packet(const char *name, uint16_t section)
{
    uint8_t header[8];
    uint8_t entry_bytes[4];
    uint8_t next_bytes[4];
    int32_t handle;
    uint32_t declared_size;
    uint32_t directory_size;
    uint32_t section_count;
    uint32_t entry;
    uint32_t next_entry;
    uint32_t section_offset;
    uint32_t section_end;
    uint32_t section_size;
    uint32_t output_size;
    int result;

    resource_packet_size = 0;
    resource_packet_compression = 0;
    if (!open_data_file(name, &handle))
        return 0;
    result = 0;
    if (!read_exact(handle, sizeof(header), header))
        goto done;
    declared_size = read_le32(header);
    directory_size = read_le32(header + 4) & WC1_PACKET_OFFSET_MASK;
    if (declared_size < 8U || directory_size < 8U ||
        directory_size > declared_size || (directory_size & 3U) != 0)
        goto done;
    section_count = (directory_size >> 2) - 1U;
    if (section >= section_count)
        goto done;

    if (wc_fseek((int32_t)(4U + (uint32_t)section * 4U), handle, 0) < 0 ||
        !read_exact(handle, sizeof(entry_bytes), entry_bytes))
        goto done;
    entry = read_le32(entry_bytes);
    resource_packet_compression = (uint16_t)(entry >> 24);
    section_offset = entry & WC1_PACKET_OFFSET_MASK;
    if ((uint32_t)section + 1U == section_count) {
        section_end = declared_size;
    } else {
        if (wc_fseek((int32_t)(8U + (uint32_t)section * 4U), handle, 0) < 0 ||
            !read_exact(handle, sizeof(next_bytes), next_bytes))
            goto done;
        next_entry = read_le32(next_bytes);
        section_end = next_entry & WC1_PACKET_OFFSET_MASK;
    }
    if (resource_packet_compression == WC1_PACKET_ABSENT) {
        /* 0xFF is a fixed-index hole, not a compressed payload. The verified
         * files repeat the offset for the next entry, so an empty slot is a
         * successful load with size zero and no data read. */
        if (section_offset < directory_size ||
            section_offset > declared_size || section_end != section_offset)
            goto done;
        result = 1;
        goto done;
    }
    if (section_offset < directory_size || section_end <= section_offset ||
        section_end > declared_size)
        goto done;
    section_size = section_end - section_offset;

    if (resource_packet_compression == 0U) {
        if (section_size > WC1_PACKET_BUFFER_MAX ||
            wc_fseek((int32_t)section_offset, handle, 0) < 0 ||
            !read_exact(handle, section_size, resource_packet_data))
            goto done;
        resource_packet_size = section_size;
        result = 1;
        goto done;
    }
    if (resource_packet_compression != 1U || section_size < 4U ||
        section_size - 4U > WC1_PACKET_COMPRESSED_MAX ||
        wc_fseek((int32_t)section_offset, handle, 0) < 0 ||
        !read_exact(handle, 4U, entry_bytes))
        goto done;
    output_size = read_le32(entry_bytes);
    if (output_size == 0U || output_size > WC1_PACKET_BUFFER_MAX ||
        !read_exact(handle, section_size - 4U, resource_compressed_data) ||
        !decode_origin_lzw(resource_compressed_data, section_size - 4U,
                           resource_packet_data, output_size))
        goto done;
    resource_packet_size = output_size;
    result = 1;
done:
    if (wc_fclose(handle) < 0)
        result = 0;
    return result;
}

static int load_game_palette(void)
{
    int32_t handle;
    int32_t length;
    uint32_t offset;

    if (!open_data_file("GAME.PAL", &handle))
        return 0;
    length = wc_fseek(0, handle, 2);
    if (length < 12 || (uint32_t)length > WC1_FILE_BUFFER_MAX ||
        wc_fseek(0, handle, 0) < 0 ||
        !read_exact(handle, (uint32_t)length, resource_file_data)) {
        wc_fclose(handle);
        return 0;
    }
    if (wc_fclose(handle) < 0)
        return 0;
    if (resource_file_data[0] != 'F' || resource_file_data[1] != 'O' ||
        resource_file_data[2] != 'R' || resource_file_data[3] != 'M' ||
        read_be32(resource_file_data + 4) + 8U != (uint32_t)length ||
        resource_file_data[8] != 'I' || resource_file_data[9] != 'L' ||
        resource_file_data[10] != 'B' || resource_file_data[11] != 'M')
        return 0;

    offset = 12;
    while (offset + 8U <= (uint32_t)length) {
        uint32_t chunk_size;
        uint32_t index;
        uint32_t colour_count;

        chunk_size = read_be32(resource_file_data + offset + 4);
        offset += 8U;
        if (chunk_size > (uint32_t)length - offset)
            return 0;
        if (resource_file_data[offset - 8U] == 'C' &&
            resource_file_data[offset - 7U] == 'M' &&
            resource_file_data[offset - 6U] == 'A' &&
            resource_file_data[offset - 5U] == 'P') {
            colour_count = chunk_size / 3U;
            if (colour_count > 256U)
                colour_count = 256U;
            for (index = 0; index < colour_count; index++) {
                uint8_t red;
                uint8_t green;
                uint8_t blue;

                red = resource_file_data[offset + index * 3U];
                green = resource_file_data[offset + index * 3U + 1U];
                blue = resource_file_data[offset + index * 3U + 2U];
                resource_palette_rgb565[index] =
                    (uint16_t)(((uint16_t)(red >> 3) << 11) |
                               ((uint16_t)(green >> 2) << 5) |
                               (uint16_t)(blue >> 3));
            }
            resource_palette_count = (uint16_t)colour_count;
            return colour_count != 0U;
        }
        offset += chunk_size + (chunk_size & 1U);
    }
    return 0;
}

static void reset_cockpit_palette_entries(void)
{
    uint16_t index;

    for (index = WC1_COCKPIT_FADE_FIRST;
         index < WC1_COCKPIT_FADE_FIRST + WC1_COCKPIT_FADE_COUNT; index++)
        resource_palette_rgb565[index] = 0U;
    /* The original stores (0, 0, 32) in this palette slot. */
    resource_palette_rgb565[WC1_COCKPIT_BACKGROUND_INDEX] = 0x0004U;
}

static int retain_loaded_packet(uint8_t *destination,
                                uint32_t destination_capacity,
                                uint32_t *retained_size)
{
    uint32_t index;

    if (resource_packet_size > destination_capacity)
        return 0;
    for (index = 0; index < resource_packet_size; index++)
        destination[index] = resource_packet_data[index];
    *retained_size = resource_packet_size;
    return 1;
}

/* The DOS executable advances g_pDiskFileRecords by one after it has copied
 * INSTALL.DAT. Callers using its logical file numbers therefore resolve the
 * on-disk record whose id is logical_file + 1. This mirrors load_ship() in
 * wc1-re/src/brains.c without hard-coding individual PCSHIP filenames. */
static int resolve_install_logical_file(uint16_t logical_file, char *name,
                                        uint32_t name_capacity)
{
    int32_t handle;
    int32_t length;
    uint32_t record_offset;
    uint8_t record_id;

    if (logical_file >= 0xfeU || name_capacity < 2U ||
        !open_data_file("INSTALL.DAT", &handle))
        return 0;
    length = wc_fseek(0, handle, 2);
    if (length < 16 || (uint32_t)length > WC1_FILE_BUFFER_MAX ||
        wc_fseek(0, handle, 0) < 0 ||
        !read_exact(handle, (uint32_t)length, resource_file_data)) {
        wc_fclose(handle);
        return 0;
    }
    if (wc_fclose(handle) < 0)
        return 0;
    record_id = (uint8_t)(logical_file + 1U);
    for (record_offset = 0; record_offset + 16U <= (uint32_t)length;
         record_offset += 16U) {
        uint32_t index;

        if (resource_file_data[record_offset] == '\0')
            break;
        if (resource_file_data[record_offset + 15U] != record_id)
            continue;
        for (index = 0; index + 1U < name_capacity && index < 13U;
             index++) {
            uint8_t character;

            character = resource_file_data[record_offset + index];
            name[index] = (char)character;
            if (character == '\0')
                return 1;
        }
        name[index] = '\0';
        return 1;
    }
    return 0;
}

/* The C-owned resource slice retains palette and target-lock packets, leaving
 * the general packet buffer available for the mission-selected cockpit and
 * active object shape. The cockpit itself is selected only after mission.s
 * has recovered the player type, exactly as InitializeCockpitResources(). */
void resource_init(void)
{
    uint16_t palette_index;

    resource_status = 0;
    resource_palette_count = 0;
    resource_cockpit_sections = 0;
    resource_packet_size = 0;
    resource_packet_compression = 0;
    resource_target_lock_size = 0;
    resource_primary_cockpit_size = 0;
    resource_cockpit_damage_size = 0;
    resource_title_logo_size = 0;
    resource_title_font_size = 0;
    resource_title_menu_size = 0;
    resource_constellation_size = 0;
    resource_flight_neutron_size = 0;
    resource_flight_mass_driver_size = 0;
    resource_flight_hit_spark_size = 0;
    resource_capital_shape_size = 0U;
    resource_capital_shape_type = 0xffffU;
    resource_capital_shape_frame = 0xffffU;
    resource_intro_star_seed = 0;
    resource_intro_camera_pitch = 0;
    resource_clip_enabled = 0;
    resource_object_type = 0xffffU;
    resource_cockpit_mode = 0xffffU;
    for (palette_index = 0; palette_index < 256U; palette_index++)
        resource_palette_rgb565[palette_index] = 0U;
    resource_next_object_slot = 0;
    resource_flight_combat_frame = 0U;
    resource_flight_weapons_reset();
    resource_flight_combat_reset();
    {
        uint16_t slot;

        for (slot = 0; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
            resource_object_sizes[slot] = 0;
            resource_object_types[slot] = 0xffffU;
        }
    }
    if (load_game_palette()) {
        reset_cockpit_palette_entries();
        resource_status |= RESOURCE_STATUS_PALETTE;
    }
    if (resource_load_packet("COCKPIT.VGA", 0U)) {
        /* COCKPIT.VGA's directory begins at byte four; the known original
         * file has nine sections. The header is re-read only to expose this
         * contract to the renderer/HUD without retaining a second packet. */
        int32_t handle;
        uint8_t header[8];
        handle = -1;
        if (!retain_loaded_packet(resource_target_lock_data,
                                  WC1_TARGET_LOCK_BUFFER_MAX,
                                  &resource_target_lock_size)) {
            resource_status |= RESOURCE_STATUS_ERROR;
        } else if (open_data_file("COCKPIT.VGA", &handle) &&
            read_exact(handle, sizeof(header), header)) {
            resource_cockpit_sections = (uint16_t)
                ((read_le32(header + 4) & WC1_PACKET_OFFSET_MASK) / 4U - 1U);
            wc_fclose(handle);
            resource_status |= RESOURCE_STATUS_COCKPIT_PACKET;
        } else {
            if (handle >= 0)
                wc_fclose(handle);
            resource_status |= RESOURCE_STATUS_ERROR;
        }
    } else {
        resource_status |= RESOURCE_STATUS_ERROR;
    }
}

/* Title_Sequence() loads TITLE.VGA packet zero for its three-part logo,
 * packet one for the cinematic subtitle/credit font, and packet four for the
 * menu entries.  init_3Space_objects() also loads PLANETS.VGA section zero
 * as its constellation shape set.  Title_Sequence() then retains
 * OBJECTS.VGA sections two (EXPLOSION1), four (common debris), five
 * (metal-sheet/wing debris), and six (laser cannon), before action sphere 16
 * instantiates three Dralthi and one Hornet from canned mission records
 * 32..35. The following credit sphere's record 36 is separate; keeping the
 * canned mission records 32..35 phrase here protects the static source map.
 * load_ship(ASTEROID_FIELD) path retains section 13 (rock chunks) and its
 * stock-memory section 16 asteroid frames; section 17 is expanded-memory
 * only. Keep the two actual SHIPTYPE streams in the bounded three-slot cache.
 * Retain all of these decoded sets before flight starts, leaving the generic
 * packet buffer free for later cockpit/object replacement.
 */
int resource_load_title(void)
{
    resource_status &= (uint16_t)~RESOURCE_STATUS_TITLE;
    resource_title_logo_size = 0;
    resource_title_font_size = 0;
    resource_title_menu_size = 0;
    resource_constellation_size = 0;
    resource_title_explosion_size = 0;
    resource_title_debris_size = 0;
    resource_title_common_debris_size = 0;
    resource_title_laser_size = 0;
    resource_title_rock_size = 0;
    resource_title_asteroid_size = 0;
    if (!load_intro_strings() ||
        !resource_load_packet("TITLE.VGA", 0U) ||
        !retain_loaded_packet(resource_title_logo_data,
                              WC1_TITLE_LOGO_BUFFER_MAX,
                              &resource_title_logo_size) ||
        !resource_load_packet("TITLE.VGA", 1U) ||
        !retain_loaded_packet(resource_title_font_data,
                              WC1_TITLE_FONT_BUFFER_MAX,
                              &resource_title_font_size) ||
        !resource_load_packet("TITLE.VGA", 4U) ||
        !retain_loaded_packet(resource_title_menu_data,
                              WC1_TITLE_MENU_BUFFER_MAX,
                              &resource_title_menu_size) ||
        !resource_load_packet("PLANETS.VGA", 0U) ||
        !retain_loaded_packet(resource_constellation_data,
                              WC1_CONSTELLATION_BUFFER_MAX,
                              &resource_constellation_size) ||
        !resource_load_packet("OBJECTS.VGA", 2U) ||
        !retain_loaded_packet(resource_title_explosion_data,
                              WC1_TITLE_EXPLOSION_BUFFER_MAX,
                              &resource_title_explosion_size) ||
        !resource_load_packet("OBJECTS.VGA", 4U) ||
        !retain_loaded_packet(resource_title_common_debris_data,
                              WC1_TITLE_COMMON_DEBRIS_BUFFER_MAX,
                              &resource_title_common_debris_size) ||
        !resource_load_packet("OBJECTS.VGA", 5U) ||
        !retain_loaded_packet(resource_title_debris_data,
                              WC1_TITLE_DEBRIS_BUFFER_MAX,
                              &resource_title_debris_size) ||
        !resource_load_packet("OBJECTS.VGA", 6U) ||
        !retain_loaded_packet(resource_title_laser_data,
                              WC1_TITLE_LASER_BUFFER_MAX,
                              &resource_title_laser_size) ||
        !resource_load_packet("OBJECTS.VGA", 13U) ||
        !retain_loaded_packet(resource_title_rock_data,
                              WC1_TITLE_ROCK_BUFFER_MAX,
                              &resource_title_rock_size) ||
        !resource_load_packet("OBJECTS.VGA", 16U) ||
        !retain_loaded_packet(resource_title_asteroid_data,
                              WC1_TITLE_ASTEROID_BUFFER_MAX,
                              &resource_title_asteroid_size) ||
        !resource_load_object_shape(10U) ||
        !resource_load_object_shape(0U)) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    reset_intro_scene_state();
    resource_status |= RESOURCE_STATUS_TITLE;
    return 1;
}

/* set_objects_data() copies a ship's packed ObjectTypeData loadout, and
 * fire_fixed_projectile_weapon() then fires every enabled projectile slot.
 * Retain exactly the packet sections those four Terran player hulls can use
 * before entering the flight loop; no disk access is permitted from fire or
 * render.  The title already owns section six, so the laser packet is shared
 * rather than copied a second time. */
int resource_load_flight_weapons(uint16_t player_type)
{
    int result;

    resource_status &= (uint16_t)~RESOURCE_STATUS_FLIGHT_WEAPONS;
    result = 1;
    if (!flight_player_uses_projectile(player_type, 24U) &&
        !flight_player_uses_projectile(player_type, 25U) &&
        !flight_player_uses_projectile(player_type, 26U)) {
        result = 0;
    }
    if (result && flight_player_uses_projectile(player_type, 24U) &&
        resource_title_laser_size == 0U &&
        (!resource_load_packet("OBJECTS.VGA", 6U) ||
         !retain_loaded_packet(resource_title_laser_data,
                               WC1_TITLE_LASER_BUFFER_MAX,
                               &resource_title_laser_size))) {
        result = 0;
    }
    /* Enemy ship records use the same three fixed cannon packets. Retain all
     * of them during mission setup so enemy fire never performs disk I/O from
     * the active frame loop, even when the player hull only carries lasers. */
    if (result && resource_flight_neutron_size == 0U &&
        (!resource_load_packet("OBJECTS.VGA", 8U) ||
         !retain_loaded_packet(resource_flight_neutron_data,
                               WC1_FLIGHT_PROJECTILE_BUFFER_MAX,
                               &resource_flight_neutron_size))) {
        result = 0;
    }
    if (result && resource_flight_mass_driver_size == 0U &&
        (!resource_load_packet("OBJECTS.VGA", 7U) ||
         !retain_loaded_packet(resource_flight_mass_driver_data,
                               WC1_FLIGHT_PROJECTILE_BUFFER_MAX,
                               &resource_flight_mass_driver_size))) {
        result = 0;
    }
    /* object_collision() changes every spent cannon bolt into LASER_SPARK.
     * Retain this common packet during flight setup rather than introducing
     * disk activity in the active render/collision interval. */
    if (result && resource_flight_hit_spark_size == 0U &&
        (!resource_load_packet("OBJECTS.VGA", 9U) ||
         !retain_loaded_packet(resource_flight_hit_spark_data,
                               WC1_FLIGHT_PROJECTILE_BUFFER_MAX,
                               &resource_flight_hit_spark_size))) {
        result = 0;
    }
    if (!result) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    resource_flight_weapons_reset();
    resource_status |= RESOURCE_STATUS_FLIGHT_WEAPONS;
    return 1;
}

/* InitializeCockpitResources(mode) derives logical file mode + 17, then
 * LoadShapeSet() obtains the primary frame from packet section zero. Keep the
 * retained cockpit independent from the generic object-shape buffer so the
 * active mobile-fighter streams can be drawn in the same Falcon frame. */
int resource_load_cockpit(uint16_t mode)
{
    char packet_name[14];
    int primary_loaded;

    resource_status &= (uint16_t)~RESOURCE_STATUS_PRIMARY_COCKPIT;
    resource_status &= (uint16_t)~RESOURCE_STATUS_COCKPIT_DAMAGE;
    resource_primary_cockpit_size = 0;
    resource_cockpit_damage_size = 0;
    resource_cockpit_mode = 0xffffU;
    if (mode > 0xedU ||
        !resolve_install_logical_file((uint16_t)(mode + 17U), packet_name,
                                      sizeof(packet_name)) ||
        !resource_load_packet(packet_name, 0U)) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    primary_loaded = retain_loaded_packet(resource_primary_cockpit_data,
                                          WC1_PRIMARY_COCKPIT_BUFFER_MAX,
                                          &resource_primary_cockpit_size);
    if (!primary_loaded) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    resource_cockpit_mode = mode;
    resource_status |= RESOURCE_STATUS_PRIMARY_COCKPIT;

    /* InitializeCockpitResources() loads the secondary cockpit shape set
     * from the same PCSHIP packet.  Section seven contains the bar/lamp
     * frames used by update_bars() and draw_cockpit_lights(); retain it in a
     * dedicated bounded buffer so the VBL-visible HUD never performs packet
     * I/O.  A missing optional section leaves the backdrop usable. */
    if (resource_load_packet(packet_name, 7U) &&
        retain_loaded_packet(resource_cockpit_damage_data,
                             WC1_COCKPIT_DAMAGE_BUFFER_MAX,
                             &resource_cockpit_damage_size))
        resource_status |= RESOURCE_STATUS_COCKPIT_DAMAGE;
    /* Keep the public packet-size contract describing the primary cockpit;
     * the secondary frame set is an internal retained resource. */
    resource_packet_size = resource_primary_cockpit_size;
    return 1;
}

/* load_ship() resolves a mobile ship type through logical file type + 22,
 * then takes section zero as its shape set (Hornet resolves to SHIPTYPE.V00).
 * The DOS engine has three object-resource slots. The stock 4 MiB Falcon
 * reserves ST-RAM for two Videl pages, so its equivalent bounded cache holds
 * two empirically sufficient 72 KiB shape slots. */
int resource_load_object_shape(uint16_t object_type)
{
    char packet_name[14];
    uint16_t slot;

    for (slot = 0; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == object_type) {
            resource_object_type = object_type;
            resource_packet_size = resource_object_sizes[slot];
            resource_status |= RESOURCE_STATUS_OBJECT_SHAPE;
            return 1;
        }
    }
    if (object_type > 0xd9U ||
        !resolve_install_logical_file((uint16_t)(object_type + 22U),
                                      packet_name, sizeof(packet_name)) ||
        !resource_load_packet(packet_name, 0U)) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    for (slot = 0; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == 0xffffU)
            break;
    }
    if (slot == RESOURCE_OBJECT_SLOT_COUNT) {
        slot = resource_next_object_slot;
        resource_next_object_slot = (uint16_t)((resource_next_object_slot + 1U) %
                                                RESOURCE_OBJECT_SLOT_COUNT);
    }
    if (!retain_loaded_packet(resource_object_data[slot],
                              WC1_OBJECT_SHAPE_BUFFER_MAX,
                              &resource_object_sizes[slot])) {
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    resource_object_types[slot] = object_type;
    resource_object_type = object_type;
    resource_status |= RESOURCE_STATUS_OBJECT_SHAPE;
    return 1;
}

/* Capital ships use one decoded SHIP.Vxx section per view. Keep that view
 * outside the three mobile-shape slots: the source releases/replaces it as
 * the direction frame changes, while the Falcon must never perform this
 * packet I/O from render_frame(). */
int resource_load_capital_view(uint16_t object_type, uint16_t frame)
{
    char packet_name[14];

    if (frame >= 17U)
        return 0;
    if ((resource_status & RESOURCE_STATUS_CAPITAL_VIEW) != 0U &&
        resource_capital_shape_type == object_type &&
        resource_capital_shape_frame == frame)
        return 1;
    if (!resolve_install_logical_file((uint16_t)(object_type + 22U),
                                      packet_name, sizeof(packet_name)) ||
        !resource_load_packet(packet_name, frame) ||
        !retain_loaded_packet(resource_capital_shape_data, 0x7000UL,
                              &resource_capital_shape_size)) {
        resource_status &= (uint16_t)~RESOURCE_STATUS_CAPITAL_VIEW;
        resource_status |= RESOURCE_STATUS_ERROR;
        return 0;
    }
    resource_capital_shape_type = object_type;
    resource_capital_shape_frame = frame;
    resource_status |= RESOURCE_STATUS_CAPITAL_VIEW;
    return 1;
}

/* COCKPIT.VGA section zero is the target-lock marker.  WC1 shape frames are
 * sparse runs rather than rectangular bitmaps: the decoder below writes the
 * original palette index directly to the chunky frame, preserving transparent
 * gaps without a colour conversion or second bitmap buffer. It follows
 * DecodeShapeFrame() in wc1-re/src/killbrd.c, with every packet read bounded
 * by the decoded section size. */
static void draw_shape_run(int32_t x, int32_t y, const uint8_t *colours,
                           uint16_t length, int solid)
{
    uint8_t *destination;
    int32_t run_left;
    int32_t run_right;
    int32_t visible_left;
    int32_t visible_right;
    uint32_t skip;
    uint32_t visible;

    if (render_target == 0 || length == 0U ||
        y < 0 || y >= FALCON_FRAME_HEIGHT ||
        x >= FALCON_FRAME_WIDTH || x + (int32_t)length <= 0)
        return;
    run_left = x;
    run_right = x + (int32_t)length - 1;
    visible_left = run_left < 0 ? 0 : run_left;
    visible_right = run_right >= FALCON_FRAME_WIDTH ?
        FALCON_FRAME_WIDTH - 1 : run_right;
    if (resource_clip_enabled != 0U) {
        if (y < resource_clip_top || y > resource_clip_bottom)
            return;
        if (visible_left < resource_clip_left)
            visible_left = resource_clip_left;
        if (visible_right > resource_clip_right)
            visible_right = resource_clip_right;
    }
    if (visible_left > visible_right)
        return;
    skip = (uint32_t)(visible_left - run_left);
    visible = (uint32_t)(visible_right - visible_left + 1);
    destination = render_target + (uint32_t)y * FALCON_FRAME_WIDTH +
        (uint32_t)visible_left;
    if (solid) {
        while (visible-- != 0U)
            *destination++ = colours[0];
    } else {
        while (visible-- != 0U)
            *destination++ = colours[skip++];
    }
}

static void draw_shape_pixel(int32_t x, int32_t y, uint8_t colour)
{
    if (render_target == 0 || x < 0 || x >= FALCON_FRAME_WIDTH ||
        y < 0 || y >= FALCON_FRAME_HEIGHT)
        return;
    render_target[(uint32_t)y * FALCON_FRAME_WIDTH + (uint32_t)x] = colour;
}

/* The Falcon replaces the TOS desktop mouse with the game-owned indexed page,
 * so the pointer must be composited before the page is expanded to RGB565.
 * X is the dark outline and dots are the visible white fill; spaces preserve
 * the scene below the cursor. */
void resource_draw_mouse_cursor(uint8_t *target, int16_t x, int16_t y)
{
    static const char cursor_shape[14][9] = {
        "X       ",
        "XX      ",
        "X.X     ",
        "X..X    ",
        "X...X   ",
        "X....X  ",
        "X.....X ",
        "X......X",
        "X....XX ",
        "X...X   ",
        "X..XX   ",
        "X.X X   ",
        "XX  XX  ",
        "X    X  "
    };
    uint16_t row;

    if (target == 0)
        return;
    for (row = 0U; row < 14U; row++) {
        uint16_t column;

        for (column = 0U; column < 8U; column++) {
            int32_t destination_x;
            int32_t destination_y;
            char pixel;

            pixel = cursor_shape[row][column];
            if (pixel == ' ')
                continue;
            destination_x = (int32_t)x + (int32_t)column;
            destination_y = (int32_t)y + (int32_t)row;
            if (destination_x < 0 || destination_x >= FALCON_FRAME_WIDTH ||
                destination_y < 0 || destination_y >= FALCON_FRAME_HEIGHT)
                continue;
            target[(uint32_t)destination_y * FALCON_FRAME_WIDTH +
                   (uint32_t)destination_x] = pixel == 'X' ? 0U : 0x0fU;
        }
    }
}

/* Title-logo layout still needs a signed floor in 8.8 space. The actual
 * sprite raster now uses the inverse sampler below, so this helper is only
 * for calculating the logo's three-part placement. */
static int32_t scaled_floor_8_8(int32_t value, uint16_t scale)
{
    int32_t product;

    product = value * (int32_t)scale;
    if (product >= 0)
        return product >> 8;
    return -(((-product) + 0xff) >> 8);
}

static int shape_frame_extents(const uint8_t *shape, uint32_t shape_size,
                               uint16_t frame, int16_t *right,
                               int16_t *left, int16_t *top, int16_t *bottom)
{
    uint32_t directory_size;
    uint32_t frame_offset;
    uint32_t next_frame_offset;
    uint32_t frame_count;

    if (shape == 0 || shape_size < 20U)
        return 0;
    directory_size = read_le16(shape + 4);
    if (directory_size < 8U || (directory_size & 3U) != 0U ||
        directory_size > shape_size || frame >= directory_size / 4U - 1U)
        return 0;
    frame_count = directory_size / 4U - 1U;
    frame_offset = read_le32(shape + 4U + (uint32_t)frame * 4U);
    if (frame_offset < directory_size || frame_offset > shape_size - 8U)
        return 0;
    if ((uint32_t)frame + 1U < frame_count) {
        next_frame_offset = read_le32(shape + 8U + (uint32_t)frame * 4U);
        if (next_frame_offset < frame_offset + 8U ||
            next_frame_offset > shape_size)
            return 0;
    }
    *right = (int16_t)read_le16(shape + frame_offset);
    *left = (int16_t)read_le16(shape + frame_offset + 2U);
    *top = (int16_t)read_le16(shape + frame_offset + 4U);
    *bottom = (int16_t)read_le16(shape + frame_offset + 6U);
    return 1;
}

static int draw_shape_frame(const uint8_t *shape, uint32_t shape_size,
                            uint16_t frame, int32_t anchor_x,
                            int32_t anchor_y)
{
    const uint8_t *packet_end;
    const uint8_t *commands;
    const uint8_t *frame_end;
    uint32_t directory_size;
    uint32_t frame_offset;
    uint32_t next_frame_offset;
    uint16_t row_code;

    if (shape == 0 || shape_size < 20U)
        return 0;
    packet_end = shape + shape_size;
    directory_size = read_le16(shape + 4);
    if (directory_size < 8U || (directory_size & 3U) != 0U ||
        directory_size > shape_size || frame >= directory_size / 4U - 1U)
        return 0;
    frame_offset = read_le32(shape + 4U + (uint32_t)frame * 4U);
    if (frame_offset < directory_size || frame_offset > shape_size - 8U)
        return 0;
    if ((uint32_t)frame + 1U < directory_size / 4U - 1U) {
        next_frame_offset = read_le32(shape + 8U + (uint32_t)frame * 4U);
        if (next_frame_offset < frame_offset + 8U ||
            next_frame_offset > shape_size)
            return 0;
        frame_end = shape + next_frame_offset;
    } else {
        frame_end = packet_end;
    }
    commands = shape + frame_offset + 8U;
    while ((uint32_t)(frame_end - commands) >= 2U) {
        int32_t x;
        int32_t y;

        row_code = read_le16(commands);
        commands += 2;
        if (row_code == 0U)
            return 1;
        if ((uint32_t)(frame_end - commands) < 4U)
            return 0;
        x = anchor_x + (int32_t)(int16_t)read_le16(commands);
        y = anchor_y + (int32_t)(int16_t)read_le16(commands + 2);
        commands += 4;
        if ((row_code & 1U) != 0U) {
            uint16_t remaining;

            remaining = row_code >> 1;
            while (remaining != 0U) {
                uint8_t code;
                uint16_t run_length;

                if (commands >= frame_end)
                    return 0;
                code = *commands++;
                run_length = (uint16_t)code >> 1;
                if (run_length == 0U || run_length > remaining)
                    return 0;
                if ((code & 1U) != 0U) {
                    if (commands >= frame_end)
                        return 0;
                    draw_shape_run(x, y, commands, run_length, 1);
                    commands++;
                } else {
                    if ((uint32_t)(frame_end - commands) < run_length)
                        return 0;
                    draw_shape_run(x, y, commands, run_length, 0);
                    commands += run_length;
                }
                x += run_length;
                remaining = (uint16_t)(remaining - run_length);
            }
        } else {
            uint16_t run_length;

            run_length = row_code >> 1;
            if ((uint32_t)(frame_end - commands) < run_length)
                return 0;
            draw_shape_run(x, y, commands, run_length, 0);
            commands += run_length;
        }
    }
    return 0;
}

static int draw_shape_frame_clipped(const uint8_t *shape, uint32_t shape_size,
                                    uint16_t frame, int32_t anchor_x,
                                    int32_t anchor_y, int16_t left,
                                    int16_t top, int16_t right,
                                    int16_t bottom)
{
    uint8_t previous_enabled;
    int16_t previous_left;
    int16_t previous_top;
    int16_t previous_right;
    int16_t previous_bottom;
    int result;

    previous_enabled = resource_clip_enabled;
    previous_left = resource_clip_left;
    previous_top = resource_clip_top;
    previous_right = resource_clip_right;
    previous_bottom = resource_clip_bottom;
    resource_clip_enabled = 1U;
    resource_clip_left = left;
    resource_clip_top = top;
    resource_clip_right = right;
    resource_clip_bottom = bottom;
    result = draw_shape_frame(shape, shape_size, frame, anchor_x, anchor_y);
    resource_clip_enabled = previous_enabled;
    resource_clip_left = previous_left;
    resource_clip_top = previous_top;
    resource_clip_right = previous_right;
    resource_clip_bottom = previous_bottom;
    return result;
}

/* Keep zero-angle scaling on the same inverse-sampling raster contract as
 * RotateRLEImage().  Forward-expanding each source pixel is not equivalent
 * below 1x: several source pixels can land on one destination pixel and the
 * last one would otherwise win instead of the reference nearest sample. */
static int draw_shape_frame_transformed(const uint8_t *shape,
                                        uint32_t shape_size, uint16_t frame,
                                        int32_t anchor_x, int32_t anchor_y,
                                        int16_t angle, uint16_t scale,
                                        uint16_t flip, int solid,
                                        uint8_t solid_colour);

static int draw_shape_frame_scaled(const uint8_t *shape, uint32_t shape_size,
                                   uint16_t frame, int32_t anchor_x,
                                   int32_t anchor_y, uint16_t scale)
{
    return draw_shape_frame_transformed(shape, shape_size, frame, anchor_x,
                                        anchor_y, 0, scale, 0U, 0, 0U);
}

/* The DOS OriginFX raster path receives angle * 10 but the 3Space shape
 * selector produces whole-degree screen angles. These are the corresponding
 * every-degree samples from the original 16.16 cosine table, not a Falcon
 * floating-point approximation. */
static const int32_t rle_cosine_degrees[91] = {
    65536, 65526, 65496, 65446, 65376, 65287, 65177, 65048, 64898,
    64729, 64540, 64332, 64104, 63856, 63589, 63303, 62997, 62672,
    62328, 61966, 61584, 61183, 60764, 60326, 59870, 59396, 58903,
    58393, 57865, 57319, 56756, 56175, 55578, 54963, 54332, 53684,
    53020, 52339, 51643, 50931, 50203, 49461, 48703, 47930, 47143,
    46341, 45525, 44695, 43852, 42995, 42126, 41243, 40348, 39441,
    38521, 37590, 36647, 35693, 34729, 33754, 32768, 31772, 30767,
    29753, 28729, 27697, 26656, 25607, 24550, 23486, 22415, 21336,
    20252, 19161, 18064, 16962, 15855, 14742, 13626, 12505, 11380,
    10252, 9121, 7987, 6850, 5712, 4572, 3430, 2287, 1144, 0
};

static int32_t rle_cosine(int16_t angle)
{
    int16_t normalized;

    normalized = angle;
    while (normalized < 0)
        normalized = (int16_t)(normalized + 360);
    while (normalized >= 360)
        normalized = (int16_t)(normalized - 360);
    if (normalized <= 90)
        return rle_cosine_degrees[(uint16_t)normalized];
    if (normalized <= 180)
        return -rle_cosine_degrees[(uint16_t)(180 - normalized)];
    if (normalized <= 270)
        return -rle_cosine_degrees[(uint16_t)(normalized - 180)];
    return rle_cosine_degrees[(uint16_t)(360 - normalized)];
}

/* The unprepared ship packet has a compact per-frame directory. This helper
 * follows the same validated directory rules as draw_shape_frame(), but lets
 * the transform renderer perform two safe passes over the source runs. */
static int shape_frame_range(const uint8_t *shape, uint32_t shape_size,
                             uint16_t frame, const uint8_t **commands,
                             const uint8_t **frame_end)
{
    uint32_t directory_size;
    uint32_t frame_offset;
    uint32_t next_frame_offset;

    if (shape == 0 || shape_size < 20U)
        return 0;
    directory_size = read_le16(shape + 4U);
    if (directory_size < 8U || (directory_size & 3U) != 0U ||
        directory_size > shape_size || frame >= directory_size / 4U - 1U)
        return 0;
    frame_offset = read_le32(shape + 4U + (uint32_t)frame * 4U);
    if (frame_offset < directory_size || frame_offset > shape_size - 8U)
        return 0;
    if ((uint32_t)frame + 1U < directory_size / 4U - 1U) {
        next_frame_offset = read_le32(shape + 8U + (uint32_t)frame * 4U);
        if (next_frame_offset < frame_offset + 8U ||
            next_frame_offset > shape_size)
            return 0;
        *frame_end = shape + next_frame_offset;
    } else {
        *frame_end = shape + shape_size;
    }
    *commands = shape + frame_offset + 8U;
    return 1;
}

static void extend_shape_bounds(int32_t x, int32_t y, uint16_t length,
                                int *started, int32_t *left,
                                int32_t *top, int32_t *right,
                                int32_t *bottom)
{
    int32_t run_right;

    if (length == 0U)
        return;
    run_right = x + (int32_t)length - 1;
    if (*started == 0) {
        *left = x;
        *right = run_right;
        *top = y;
        *bottom = y;
        *started = 1;
        return;
    }
    if (x < *left)
        *left = x;
    if (run_right > *right)
        *right = run_right;
    if (y < *top)
        *top = y;
    if (y > *bottom)
        *bottom = y;
}

/* Decode only the run boundaries for the scratch allocation. This is kept
 * separate from the write pass so malformed data never reaches an unchecked
 * offset in the fixed 0xfa00-byte Falcon workspace. */
static int scan_shape_frame_bounds(const uint8_t *shape, uint32_t shape_size,
                                   uint16_t frame, int32_t *left,
                                   int32_t *top, int32_t *right,
                                   int32_t *bottom)
{
    const uint8_t *commands;
    const uint8_t *frame_end;
    int started;

    if (!shape_frame_range(shape, shape_size, frame, &commands, &frame_end))
        return 0;
    started = 0;
    while ((uint32_t)(frame_end - commands) >= 2U) {
        uint16_t row_code;
        int32_t source_x;
        int32_t source_y;

        row_code = read_le16(commands);
        commands += 2;
        if (row_code == 0U)
            return started;
        if ((uint32_t)(frame_end - commands) < 4U)
            return 0;
        source_x = (int32_t)(int16_t)read_le16(commands);
        source_y = (int32_t)(int16_t)read_le16(commands + 2U);
        commands += 4;
        if ((row_code & 1U) != 0U) {
            uint16_t remaining;

            remaining = row_code >> 1;
            while (remaining != 0U) {
                uint8_t code;
                uint16_t run_length;

                if (commands >= frame_end)
                    return 0;
                code = *commands++;
                run_length = (uint16_t)code >> 1;
                if (run_length == 0U || run_length > remaining)
                    return 0;
                if ((code & 1U) != 0U) {
                    if (commands >= frame_end)
                        return 0;
                    commands++;
                } else {
                    if ((uint32_t)(frame_end - commands) < run_length)
                        return 0;
                    commands += run_length;
                }
                extend_shape_bounds(source_x, source_y, run_length, &started,
                                    left, top, right, bottom);
                source_x += run_length;
                remaining = (uint16_t)(remaining - run_length);
            }
        } else {
            uint16_t run_length;

            run_length = row_code >> 1;
            if (run_length == 0U ||
                (uint32_t)(frame_end - commands) < run_length)
                return 0;
            extend_shape_bounds(source_x, source_y, run_length, &started,
                                left, top, right, bottom);
            commands += run_length;
        }
    }
    return 0;
}

static void write_transform_pixel(int32_t source_x, int32_t source_y,
                                  int32_t left, int32_t top,
                                  int32_t width, int32_t height,
                                  uint8_t colour)
{
    int32_t x;
    int32_t y;

    x = source_x - left;
    y = source_y - top;
    if (x < 0 || x >= width || y < 0 || y >= height)
        return;
    resource_transform_scratch[(uint32_t)y * (uint32_t)width +
                               (uint32_t)x] = colour;
}

static int decode_shape_frame_to_transform_scratch(
    const uint8_t *shape, uint32_t shape_size, uint16_t frame,
    int32_t left, int32_t top, int32_t width, int32_t height)
{
    const uint8_t *commands;
    const uint8_t *frame_end;
    uint32_t scratch_size;
    uint32_t index;

    if (width <= 0 || height <= 0 ||
        (uint32_t)width > WC1_TRANSFORM_SCRATCH_MAX / (uint32_t)height)
        return 0;
    scratch_size = (uint32_t)width * (uint32_t)height;
    for (index = 0; index < scratch_size; index++)
        resource_transform_scratch[index] = 0xffU;
    if (!shape_frame_range(shape, shape_size, frame, &commands, &frame_end))
        return 0;
    while ((uint32_t)(frame_end - commands) >= 2U) {
        uint16_t row_code;
        int32_t source_x;
        int32_t source_y;

        row_code = read_le16(commands);
        commands += 2;
        if (row_code == 0U)
            return 1;
        if ((uint32_t)(frame_end - commands) < 4U)
            return 0;
        source_x = (int32_t)(int16_t)read_le16(commands);
        source_y = (int32_t)(int16_t)read_le16(commands + 2U);
        commands += 4;
        if ((row_code & 1U) != 0U) {
            uint16_t remaining;

            remaining = row_code >> 1;
            while (remaining != 0U) {
                uint8_t code;
                uint16_t run_length;
                uint16_t pixel;

                if (commands >= frame_end)
                    return 0;
                code = *commands++;
                run_length = (uint16_t)code >> 1;
                if (run_length == 0U || run_length > remaining)
                    return 0;
                if ((code & 1U) != 0U) {
                    uint8_t colour;

                    if (commands >= frame_end)
                        return 0;
                    colour = *commands++;
                    for (pixel = 0; pixel < run_length; pixel++)
                        write_transform_pixel(source_x + pixel, source_y,
                                              left, top, width, height,
                                              colour);
                } else {
                    if ((uint32_t)(frame_end - commands) < run_length)
                        return 0;
                    for (pixel = 0; pixel < run_length; pixel++)
                        write_transform_pixel(source_x + pixel, source_y,
                                              left, top, width, height,
                                              commands[pixel]);
                    commands += run_length;
                }
                source_x += run_length;
                remaining = (uint16_t)(remaining - run_length);
            }
        } else {
            uint16_t run_length;
            uint16_t pixel;

            run_length = row_code >> 1;
            if (run_length == 0U ||
                (uint32_t)(frame_end - commands) < run_length)
                return 0;
            for (pixel = 0; pixel < run_length; pixel++)
                write_transform_pixel(source_x + pixel, source_y, left, top,
                                      width, height, commands[pixel]);
            commands += run_length;
        }
    }
    return 0;
}

/* Match the portable RotateRLEImage sample rule: choose the source integer
 * nearest the inverse-transformed destination sample, with half values
 * rounded toward positive infinity. The numerator and denominator remain
 * bounded 32-bit values for the 320x200 Falcon viewport. */
static int32_t rle_round_ratio(int32_t numerator, int32_t denominator)
{
    if (denominator < 0) {
        numerator = -numerator;
        denominator = -denominator;
    }
    numerator += denominator >> 1;
    if (numerator >= 0)
        return numerator / denominator;
    return -(((-numerator) + denominator - 1) / denominator);
}

/* The source raster's bounding transform is only used to restrict the
 * inverse sampler. It intentionally expands each resulting edge by two
 * pixels below, so its safe 32-bit 8.8 intermediate cannot clip a valid
 * sample at high object scales. */
static int32_t rle_forward_component(int32_t coordinate, int32_t scale,
                                     int32_t trig)
{
    int32_t scaled;

    scaled = (coordinate * scale) / 256;
    if (scaled >= 0)
        return (scaled * trig + 0x8000L) / 0x10000L;
    return (scaled * trig - 0x8000L) / 0x10000L;
}

/* Target artefact: raster_zero_angle_fastpath; record:
 * analysis/functions/ShapeTransformAxis.md. N/A - platform replacement.
 * Keep map construction out of the pixel loop and, more importantly, out of
 * draw_shape_frame_transformed()'s 68030 instruction-cache footprint. */
static void build_transform_axis_maps(int32_t anchor_x, int32_t anchor_y,
                                      int32_t minimum_x, int32_t maximum_x,
                                      int32_t minimum_y, int32_t maximum_y,
                                      int32_t scale_x, int32_t scale_y,
                                      int32_t cosine)
{
    int32_t map_x;
    int32_t map_y;

    for (map_x = minimum_x; map_x <= maximum_x; map_x++)
        resource_transform_x_map[(uint32_t)(map_x - minimum_x)] =
            rle_round_ratio((map_x - anchor_x) * cosine,
                            scale_x * 256);
    for (map_y = minimum_y; map_y <= maximum_y; map_y++)
        resource_transform_y_map[(uint32_t)(map_y - minimum_y)] =
            rle_round_ratio((map_y - anchor_y) * cosine,
                            scale_y * 256);
}

/* Target artefact: raster_zero_angle_fastpath; record:
 * analysis/functions/ShapeTransformAxis.md. N/A - platform replacement.
 * This small body is intentionally separate from the setup and map-building
 * code: repeated flight draws then keep their indexed inner loop compact on
 * the 68030's direct-mapped 256-byte instruction cache. */
static void draw_transform_axis_pixels(int32_t source_left,
                                       int32_t source_top,
                                       int32_t source_right,
                                       int32_t source_bottom,
                                       int32_t source_width,
                                       int32_t minimum_x, int32_t minimum_y,
                                       int32_t maximum_x, int32_t maximum_y,
                                       int solid, uint8_t solid_colour)
{
    int32_t map_count;
    int32_t destination_y;

    map_count = maximum_x - minimum_x + 1;
    for (destination_y = minimum_y; destination_y <= maximum_y;
         destination_y++) {
        int32_t source_y;
        const uint8_t *source_row;
        const int32_t *source_x_values;
        uint8_t *destination;
        int32_t map_index;

        source_y = resource_transform_y_map[
            (uint32_t)(destination_y - minimum_y)];
        if (source_y < source_top || source_y > source_bottom)
            continue;
        source_row = resource_transform_scratch +
            (uint32_t)(source_y - source_top) * (uint32_t)source_width;
        source_x_values = resource_transform_x_map;
        destination = render_target +
            (uint32_t)destination_y * FALCON_FRAME_WIDTH +
            (uint32_t)minimum_x;
        for (map_index = 0; map_index < map_count; map_index++) {
            int32_t source_x;
            uint8_t colour;

            source_x = *source_x_values++;
            if (source_x >= source_left && source_x <= source_right) {
                colour = source_row[(uint32_t)(source_x - source_left)];
                if (colour != 0xffU)
                    *destination = solid ? solid_colour : colour;
            }
            destination++;
        }
    }
}

/* Target artefact: raster_zero_angle_fastpath; record:
 * analysis/functions/ShapeTransformAxis.md. N/A - platform replacement.
 * The caller has already validated and decoded the source frame, and has
 * already computed the exact DOS-derived transformed bounds. */
static int draw_shape_frame_axis_aligned(int32_t anchor_x, int32_t anchor_y,
                                         int32_t source_left,
                                         int32_t source_top,
                                         int32_t source_right,
                                         int32_t source_bottom,
                                         int32_t source_width,
                                         int32_t scale_x, int32_t scale_y,
                                         int32_t cosine,
                                         int32_t minimum_x, int32_t minimum_y,
                                         int32_t maximum_x, int32_t maximum_y,
                                         int solid, uint8_t solid_colour)
{
    build_transform_axis_maps(anchor_x, anchor_y, minimum_x, maximum_x,
                              minimum_y, maximum_y, scale_x, scale_y,
                              cosine);
    draw_transform_axis_pixels(source_left, source_top, source_right,
                               source_bottom, source_width, minimum_x,
                               minimum_y, maximum_x, maximum_y, solid,
                               solid_colour);
    return 1;
}

static int draw_shape_frame_transformed(const uint8_t *shape,
                                        uint32_t shape_size, uint16_t frame,
                                        int32_t anchor_x, int32_t anchor_y,
                                        int16_t angle, uint16_t scale,
                                        uint16_t flip, int solid,
                                        uint8_t solid_colour)
{
    int32_t source_left = 0;
    int32_t source_top = 0;
    int32_t source_right = 0;
    int32_t source_bottom = 0;
    int32_t source_width;
    int32_t source_height;
    int32_t scale_x;
    int32_t scale_y;
    int32_t cosine;
    int32_t sine;
    int32_t minimum_x;
    int32_t minimum_y;
    int32_t maximum_x;
    int32_t maximum_y;
    uint16_t corner;
    int32_t destination_y;

    if (render_target == 0 || scale == 0U ||
        (flip != 0U && flip != 0x10U && flip != 0x20U && flip != 0x30U) ||
        !scan_shape_frame_bounds(shape, shape_size, frame, &source_left,
                                 &source_top, &source_right,
                                 &source_bottom))
        return 0;
    source_width = source_right - source_left + 1;
    source_height = source_bottom - source_top + 1;
    if (!decode_shape_frame_to_transform_scratch(shape, shape_size, frame,
                                                 source_left, source_top,
                                                 source_width, source_height))
        return 0;
    scale_x = (int32_t)scale;
    scale_y = (int32_t)scale;
    if (flip == 0x10U || flip == 0x30U)
        scale_x = -scale_x;
    if (flip == 0x20U || flip == 0x30U)
        scale_y = -scale_y;
    cosine = rle_cosine(angle);
    sine = rle_cosine((int16_t)(90 - angle));
    minimum_x = FALCON_FRAME_WIDTH;
    minimum_y = FALCON_FRAME_HEIGHT;
    maximum_x = -1;
    maximum_y = -1;
    for (corner = 0U; corner < 4U; corner++) {
        int32_t source_x;
        int32_t source_y;
        int32_t transformed_x;
        int32_t transformed_y;

        source_x = (corner & 1U) != 0U ? source_right : source_left;
        source_y = (corner & 2U) != 0U ? source_bottom : source_top;
        transformed_x = anchor_x +
            rle_forward_component(source_x, scale_x, cosine) -
            rle_forward_component(source_y, scale_y, sine);
        transformed_y = anchor_y +
            rle_forward_component(source_x, scale_x, sine) +
            rle_forward_component(source_y, scale_y, cosine);
        if (transformed_x < minimum_x)
            minimum_x = transformed_x;
        if (transformed_x > maximum_x)
            maximum_x = transformed_x;
        if (transformed_y < minimum_y)
            minimum_y = transformed_y;
        if (transformed_y > maximum_y)
            maximum_y = transformed_y;
    }
    minimum_x -= 2;
    minimum_y -= 2;
    maximum_x += 2;
    maximum_y += 2;
    if (minimum_x < 0)
        minimum_x = 0;
    if (minimum_y < 0)
        minimum_y = 0;
    if (maximum_x >= FALCON_FRAME_WIDTH)
        maximum_x = FALCON_FRAME_WIDTH - 1;
    if (maximum_y >= FALCON_FRAME_HEIGHT)
        maximum_y = FALCON_FRAME_HEIGHT - 1;

    /* At zero screen angle, rle_round_ratio() is separable. The setup and
     * compact pixel loop live in separate helpers so this large rotated path
     * does not acquire the fast path's code and instruction-cache pressure.
     * The samples remain the exact integer rule above; rotated sprites retain
     * the general reference path. */
    if (angle == 0 && resource_intro_rendering == 0U) {
        return draw_shape_frame_axis_aligned(
            anchor_x, anchor_y, source_left, source_top, source_right,
            source_bottom, source_width, scale_x, scale_y, cosine,
            minimum_x, minimum_y, maximum_x, maximum_y, solid, solid_colour);
    }

    for (destination_y = minimum_y; destination_y <= maximum_y;
         destination_y++) {
        int32_t destination_x;

        for (destination_x = minimum_x; destination_x <= maximum_x;
             destination_x++) {
            int32_t relative_x;
            int32_t relative_y;
            int32_t source_x;
            int32_t source_y;
            uint8_t colour;

            relative_x = destination_x - anchor_x;
            relative_y = destination_y - anchor_y;
            source_x = rle_round_ratio(relative_x * cosine +
                                       relative_y * sine,
                                       scale_x * 256);
            source_y = rle_round_ratio(-relative_x * sine +
                                       relative_y * cosine,
                                       scale_y * 256);
            if (source_x < source_left || source_x > source_right ||
                source_y < source_top || source_y > source_bottom)
                continue;
            colour = resource_transform_scratch[
                (uint32_t)(source_y - source_top) * (uint32_t)source_width +
                (uint32_t)(source_x - source_left)];
            if (colour != 0xffU)
                draw_shape_pixel(destination_x, destination_y,
                                 solid ? solid_colour : colour);
        }
    }
    return 1;
}

void resource_draw_target_lock(void)
{
    if ((resource_status & (RESOURCE_STATUS_PALETTE |
                            RESOURCE_STATUS_COCKPIT_PACKET)) ==
        (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_COCKPIT_PACKET)) {
        draw_shape_frame(resource_target_lock_data, resource_target_lock_size,
                         0U, TARGET_LOCK_X, TARGET_LOCK_Y);
    }
}

void resource_draw_cockpit(void)
{
    if ((resource_status & (RESOURCE_STATUS_PALETTE |
                            RESOURCE_STATUS_PRIMARY_COCKPIT)) ==
        (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_PRIMARY_COCKPIT)) {
        draw_shape_frame(resource_primary_cockpit_data,
                         resource_primary_cockpit_size,
                         0U, 0, 0);
    }
}

int resource_draw_object(int32_t anchor_x, int32_t anchor_y,
                         uint16_t object_type, uint16_t frame)
{
    uint16_t slot;

    if ((resource_status & (RESOURCE_STATUS_PALETTE |
                            RESOURCE_STATUS_OBJECT_SHAPE)) !=
        (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_OBJECT_SHAPE))
        return 0;
    for (slot = 0; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == object_type) {
            return draw_shape_frame(resource_object_data[slot],
                                    resource_object_sizes[slot], frame,
                                    anchor_x, anchor_y);
        }
    }
    return 0;
}

/* Direct Falcon equivalent of DrawSpriteScaled(): the caller supplies the
 * DOS 8.8 scale, whole-degree screen angle, and optional 0x10/0x20 flips.
 * It is deliberately public now because the title action sphere and the
 * eventual mission depth sorter share exactly this source path. */
int resource_draw_object_transformed(int32_t anchor_x, int32_t anchor_y,
                                     uint16_t object_type, uint16_t frame,
                                     int16_t angle, uint16_t scale,
                                     uint16_t flip)
{
    uint16_t slot;

    if ((resource_status & (RESOURCE_STATUS_PALETTE |
                            RESOURCE_STATUS_OBJECT_SHAPE)) !=
        (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_OBJECT_SHAPE))
        return 0;
    for (slot = 0; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == object_type) {
            return draw_shape_frame_transformed(
                resource_object_data[slot], resource_object_sizes[slot],
                frame, anchor_x, anchor_y, angle, scale, flip, 0, 0U);
        }
    }
    return 0;
}

/* These four values are the public resource/assembly contract for the
 * recoverable, asset-backed part of nav.c:Title_Sequence().  The renderer
 * presently covers its constellation, first action-sphere ships, and that
 * sphere's EXPLOSION1 hand-off; the later credit scene remains separate. */
#define RESOURCE_INTRO_STAGE_OPENING 0U
#define RESOURCE_INTRO_STAGE_SPACE 1U
#define RESOURCE_INTRO_STAGE_LOGO 2U
#define RESOURCE_INTRO_STAGE_CREDIT 3U

/* DOS: nav.c:Title_Sequence() opening subtitle and credits; record:
 * analysis/wcexe.md#title-sequence-strings.  The 1990 WC.EXE keeps them in its
 * data segment and the title overlay reaches them through near pointers:
 *   DGROUP   C0 entry at CS:0000 (file 0x1200) is `mov dx,11CCh` /
 *            `mov cs:[023Eh],dx`, so DS:0000 is file 0x12EC0 (DS:0004 is the
 *            Borland copyright, analysis/wcexe.md §4).
 *   DS:264E  near pointer to the opening subtitle, pushed at file 0x3C608
 *            (`push word [264E]`).
 *   DS:2767  eleven near pointers to the credits, read at file 0x3C72E
 *            (`shl bx,1` / `push word [bx+2767]`).
 * The port reads the same bytes from the player's WC.EXE when the title
 * resources load instead of carrying a copy of the text.  They also differ
 * from wc1-re's 1996 reconstruction, which the earlier transcription followed.
 */
#define WC_EXE_SIZE 302384L
#define WC_EXE_OPENING_POINTER 0x264EU
#define WC_EXE_CREDIT_TABLE 0x2767U
#define INTRO_CREDIT_COUNT 11U
#define INTRO_TEXT_POOL_MAX 1024U

static char resource_intro_text_pool[INTRO_TEXT_POOL_MAX];
const char *resource_intro_opening_text;
const char *resource_intro_credit_text[INTRO_CREDIT_COUNT];

static int read_exe_at(int32_t handle, uint32_t offset, uint32_t count,
                       uint8_t *destination)
{
    return wc_fseek((int32_t)offset, handle, 0) == (int32_t)offset &&
           read_exact(handle, count, destination);
}

/* N/A - platform replacement: the DOS program has the strings in its own
 * image; this reads them out of the player's copy of that image.  Only the
 * 1990 WC.EXE (302,384 bytes, analysis/wcexe.md) has these addresses. */
static int load_intro_strings(void)
{
    int32_t handle;
    uint8_t header[0x18];
    uint8_t entry[3];
    uint8_t pointers[INTRO_CREDIT_COUNT * 2U];
    uint16_t offsets[INTRO_CREDIT_COUNT + 1U];
    const char **targets[INTRO_CREDIT_COUNT + 1U];
    uint32_t load_module;
    uint32_t data_segment;
    uint32_t used;
    uint32_t index;
    int ok;

    resource_intro_opening_text = 0;
    for (index = 0; index < INTRO_CREDIT_COUNT; index++)
        resource_intro_credit_text[index] = 0;
    if (!open_data_file("WC.EXE", &handle))
        return 0;
    ok = wc_fseek(0, handle, 2) == WC_EXE_SIZE &&
         read_exe_at(handle, 0, sizeof(header), header) &&
         header[0] == 'M' && header[1] == 'Z';
    if (ok) {
        /* MZ e_cparhdr (+08), e_ip (+14), e_cs (+16): the entry is C0's
         * `mov dx,DGROUP` (BA imm16), the segment DOS's loader relocates. */
        load_module = (uint32_t)read_le16(header + 0x08) * 16U;
        ok = read_exe_at(handle, load_module +
                         (uint32_t)read_le16(header + 0x16) * 16U +
                         read_le16(header + 0x14), sizeof(entry), entry) &&
             entry[0] == 0xBAU;
    }
    if (ok) {
        data_segment = load_module + (uint32_t)read_le16(entry + 1) * 16U;
        ok = read_exe_at(handle, data_segment + WC_EXE_OPENING_POINTER, 2U,
                         pointers);
        if (ok)
            offsets[0] = read_le16(pointers);
        ok = ok && read_exe_at(handle, data_segment + WC_EXE_CREDIT_TABLE,
                               sizeof(pointers), pointers);
    }
    if (ok) {
        targets[0] = &resource_intro_opening_text;
        for (index = 0; index < INTRO_CREDIT_COUNT; index++) {
            offsets[index + 1U] = read_le16(pointers + index * 2U);
            targets[index + 1U] = &resource_intro_credit_text[index];
        }
        used = 0;
        for (index = 0; ok && index <= INTRO_CREDIT_COUNT; index++) {
            uint32_t length;
            int32_t got;

            if (wc_fseek((int32_t)(data_segment + offsets[index]), handle,
                         0) < 0) {
                ok = 0;
                break;
            }
            got = wc_fread(handle, INTRO_TEXT_POOL_MAX - used,
                           resource_intro_text_pool + used);
            for (length = 0; got > 0 && length < (uint32_t)got &&
                 resource_intro_text_pool[used + length] != '\0'; length++)
                ;
            if (got <= 0 || length >= (uint32_t)got) {
                ok = 0;
                break;
            }
            *targets[index] = resource_intro_text_pool + used;
            used += length + 1U;
        }
    }
    if (wc_fclose(handle) < 0)
        ok = 0;
    if (!ok) {
        resource_intro_opening_text = 0;
        for (index = 0; index < INTRO_CREDIT_COUNT; index++)
            resource_intro_credit_text[index] = 0;
    }
    return ok;
}

static void clear_intro_target(uint8_t *target)
{
    uint32_t pixel;

    for (pixel = 0; pixel < (uint32_t)FALCON_FRAME_WIDTH *
         FALCON_FRAME_HEIGHT; pixel++)
        target[pixel] = 0U;
}

static int intro_font_frame(uint8_t character, uint16_t *frame)
{
    if (character >= (uint8_t)'A' && character <= (uint8_t)'z') {
        *frame = (uint16_t)(character - (uint8_t)'A');
        return 1;
    }
    if (character == (uint8_t)'.') {
        *frame = 58U;
        return 1;
    }
    if (character == (uint8_t)',') {
        *frame = 59U;
        return 1;
    }
    return 0;
}

/* GetLineLength() is deliberately repeated from mono.c, including its
 * unusually broad A..z mapping and the two-pixel post-glyph spacing. */
static int32_t intro_line_width(const char *text)
{
    int32_t width;
    uint32_t offset;

    width = 0;
    for (offset = 0; text[offset] != '\0' && text[offset] != '\n'; offset++) {
        uint16_t frame;

        if (intro_font_frame((uint8_t)text[offset], &frame)) {
            int16_t right;
            int16_t left;
            int16_t top;
            int16_t bottom;

            if (shape_frame_extents(resource_title_font_data,
                                    resource_title_font_size, frame, &right,
                                    &left, &top, &bottom))
                width += (int32_t)right + 2;
        } else if (text[offset] == ' ') {
            width += 6;
        }
    }
    return width;
}

static void draw_intro_text(const char *text)
{
    const char *cursor;
    int32_t y;
    uint32_t lines;
    uint32_t offset;

    lines = 1U;
    for (offset = 0; text[offset] != '\0'; offset++) {
        if (text[offset] == '\n')
            lines++;
    }
    y = (128 - (int32_t)lines * 16) / 2;
    cursor = text;
    for (;;) {
        int32_t x;

        x = (FALCON_FRAME_WIDTH - intro_line_width(cursor)) >> 1;
        while (*cursor != '\0' && *cursor != '\n') {
            uint16_t frame;

            if (intro_font_frame((uint8_t)*cursor, &frame)) {
                int16_t right;
                int16_t left;
                int16_t top;
                int16_t bottom;

                (void)draw_shape_frame(resource_title_font_data,
                                       resource_title_font_size, frame, x,
                                       y);
                if (shape_frame_extents(resource_title_font_data,
                                        resource_title_font_size, frame,
                                        &right, &left, &top, &bottom))
                    x += (int32_t)right + 2;
            } else if (*cursor == ' ') {
                x += 6;
            }
            cursor++;
        }
        if (*cursor == '\0')
            return;
        cursor++;
        y += 16;
    }
}

static int32_t ceil_div_256(int32_t value)
{
    return value <= 0 ? value >> 8 : (value + 0xff) >> 8;
}

/* DrawTitleLogo(distance, 94) from nav.c.  At angle zero the transformed
 * bounds reduce to these fixed-point expressions; the one-unit sine term is
 * preserved because the DOS bounds routine promotes a zero component to one.
 */
static void draw_intro_title_logo(uint16_t index)
{
    int16_t right;
    int16_t left;
    int16_t top;
    int16_t bottom;
    int32_t distance;
    int32_t horizontal_extent;
    int32_t transformed_width;
    int32_t logo_left;
    int32_t logo_right;
    uint16_t scale;

    distance = 200 - (int32_t)index * 4;
    if (distance < 16)
        distance = 16;
    scale = (uint16_t)(0x1000 / distance);
    if (!shape_frame_extents(resource_title_logo_data,
                             resource_title_logo_size, 1U, &right, &left,
                             &top, &bottom))
        return;
    horizontal_extent = (int32_t)top + bottom;
    transformed_width = ceil_div_256((int32_t)scale *
                                     ((int32_t)right + left) +
                                     horizontal_extent);
    logo_left = ((int32_t)top >> 8) -
        scaled_floor_8_8(left, scale) + (FALCON_FRAME_WIDTH >> 1) -
        ((horizontal_extent >> 8) + 1);
    logo_right = logo_left + transformed_width;
    (void)draw_shape_frame_scaled(resource_title_logo_data,
                                  resource_title_logo_size, 0U,
                                  logo_left - 1, 94, scale);
    (void)draw_shape_frame_scaled(resource_title_logo_data,
                                  resource_title_logo_size, 1U,
                                  FALCON_FRAME_WIDTH >> 1, 94, scale);
    (void)draw_shape_frame_scaled(resource_title_logo_data,
                                  resource_title_logo_size, 2U, logo_right,
                                  94, scale);
}

/* These are SinFixed(degrees) for zero through ninety, truncated just as the
 * DOS mathfp.c routine does. The title camera uses only +/-45 degree star
 * spread and its +30 to zero pitch sweep, so a table avoids a soft-float
 * dependency in the Falcon executable. */
static const uint16_t intro_sin_0_to_90[91] = {
    0, 4, 8, 13, 17, 22, 26, 31, 35, 40, 44, 48, 53, 57, 61, 66,
    70, 74, 79, 83, 87, 91, 95, 100, 104, 108, 112, 116, 120, 124,
    127, 131, 135, 139, 143, 146, 150, 154, 157, 161, 164, 167,
    171, 174, 177, 181, 184, 187, 190, 193, 196, 198, 201, 204,
    207, 209, 212, 214, 217, 219, 221, 223, 226, 228, 230, 232,
    233, 235, 237, 238, 240, 242, 243, 244, 246, 247, 248, 249,
    250, 251, 252, 252, 253, 254, 254, 255, 255, 255, 255, 255,
    256
};

static uint16_t intro_integer_sqrt(uint32_t value);

static int32_t intro_fixed_multiply(int32_t left, int32_t right)
{
    return (left * right) / 256;
}

static int32_t intro_fixed_divide(int32_t left, int32_t right)
{
    int32_t quotient;
    int32_t remainder;

    if (right == 0)
        return 0;
    /* DivideFixed() is 24.8 arithmetic.  Multiplying the numerator by 256
     * first works on a host with 64-bit long, but overflows signed long on
     * the 68030 for the 320-wide perspective numerator.  Split it first so
     * the Falcon receives the same quotient/remainder result without an FPU
     * or an accidental wrapped scale. */
    quotient = left / right;
    remainder = left % right;
    return quotient * 256 + (remainder * 256) / right;
}

static int32_t intro_vector_magnitude(const IntroFixedVector *vector)
{
    int32_t x;
    int32_t y;
    int32_t z;
    int32_t largest;
    uint16_t shift;
    uint32_t magnitude_squared;
    uint32_t magnitude;

    x = vector->x;
    y = vector->y;
    z = vector->z;
    largest = x < 0 ? -x : x;
    if ((y < 0 ? -y : y) > largest)
        largest = y < 0 ? -y : y;
    if ((z < 0 ? -z : z) > largest)
        largest = z < 0 ? -z : z;
    shift = 0U;
    while (largest > 16383) {
        x /= 2;
        y /= 2;
        z /= 2;
        largest /= 2;
        shift++;
    }
    magnitude_squared = (uint32_t)(x * x) + (uint32_t)(y * y) +
        (uint32_t)(z * z);
    magnitude = intro_integer_sqrt(magnitude_squared);
    return (int32_t)(magnitude << shift);
}

static uint16_t intro_integer_sqrt(uint32_t value)
{
    uint32_t bit;
    uint32_t result;

    result = 0;
    bit = 1UL << 30;
    while (bit > value)
        bit >>= 2;
    while (bit != 0U) {
        if (value >= result + bit) {
            value -= result + bit;
            result = (result >> 1) + bit;
        } else {
            result >>= 1;
        }
        bit >>= 2;
    }
    return (uint16_t)result;
}

static void intro_normalize_vector(IntroFixedVector *vector)
{
    uint32_t magnitude_squared;
    uint16_t magnitude;

    magnitude_squared = (uint32_t)(vector->x * vector->x) +
        (uint32_t)(vector->y * vector->y) +
        (uint32_t)(vector->z * vector->z);
    magnitude = intro_integer_sqrt(magnitude_squared);
    if (magnitude != 0U) {
        vector->x = (vector->x * 256) / magnitude;
        vector->y = (vector->y * 256) / magnitude;
        vector->z = (vector->z * 256) / magnitude;
    }
}

/* point_at() first shrinks an arbitrary long target delta before repairing
 * its axes.  A title laser's 5,600-unit aiming target exceeds the small-axis
 * squaring range above, so retain the same 24.8 result through the overflow-
 * safe magnitude path used by the scene projection. */
static int intro_normalize_long_vector(IntroFixedVector *vector)
{
    int32_t magnitude;

    magnitude = intro_vector_magnitude(vector);
    if (magnitude == 0)
        return 0;
    vector->x = intro_fixed_divide(vector->x, magnitude);
    vector->y = intro_fixed_divide(vector->y, magnitude);
    vector->z = intro_fixed_divide(vector->z, magnitude);
    return 1;
}

static void intro_cross_product(const IntroFixedVector *left,
                                const IntroFixedVector *right,
                                IntroFixedVector *product)
{
    product->x = intro_fixed_multiply(left->y, right->z) -
        intro_fixed_multiply(left->z, right->y);
    product->y = intro_fixed_multiply(left->z, right->x) -
        intro_fixed_multiply(left->x, right->z);
    product->z = intro_fixed_multiply(left->x, right->y) -
        intro_fixed_multiply(left->y, right->x);
}

static void intro_copy_vector(IntroFixedVector *destination,
                              const IntroFixedVector *source)
{
    destination->x = source->x;
    destination->y = source->y;
    destination->z = source->z;
}

static int32_t intro_sin_fixed(int16_t degrees)
{
    int16_t angle;
    int32_t value;

    angle = degrees;
    while (angle < 0)
        angle = (int16_t)(angle + 360);
    while (angle >= 360)
        angle = (int16_t)(angle - 360);
    if (angle <= 90)
        return intro_sin_0_to_90[(uint16_t)angle];
    if (angle <= 180)
        return intro_sin_0_to_90[(uint16_t)(180 - angle)];
    if (angle <= 270) {
        value = intro_sin_0_to_90[(uint16_t)(angle - 180)];
        return -value;
    }
    value = intro_sin_0_to_90[(uint16_t)(360 - angle)];
    return -value;
}

static int32_t intro_cos_fixed(int16_t degrees)
{
    return intro_sin_fixed((int16_t)(degrees + 90));
}

static void intro_rotate_about_i(int16_t angle, IntroFixedVector *up,
                                 IntroFixedVector *forward)
{
    int32_t cosine;
    int32_t sine;
    int32_t old;

    cosine = intro_cos_fixed(angle);
    sine = intro_sin_fixed(angle);
    old = up->x;
    up->x = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(forward->x, sine);
    forward->x = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(forward->x, cosine);
    old = up->y;
    up->y = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(forward->y, sine);
    forward->y = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(forward->y, cosine);
    old = up->z;
    up->z = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(forward->z, sine);
    forward->z = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(forward->z, cosine);
}

static void intro_rotate_about_j(int16_t angle, IntroFixedVector *right,
                                 IntroFixedVector *forward)
{
    int32_t cosine;
    int32_t sine;
    int32_t old;

    cosine = intro_cos_fixed(angle);
    sine = intro_sin_fixed(angle);
    old = right->x;
    right->x = intro_fixed_multiply(forward->x, sine) +
        intro_fixed_multiply(old, cosine);
    forward->x = intro_fixed_multiply(forward->x, cosine) -
        intro_fixed_multiply(old, sine);
    old = right->y;
    right->y = intro_fixed_multiply(forward->y, sine) +
        intro_fixed_multiply(old, cosine);
    forward->y = intro_fixed_multiply(forward->y, cosine) -
        intro_fixed_multiply(old, sine);
    old = right->z;
    right->z = intro_fixed_multiply(forward->z, sine) +
        intro_fixed_multiply(old, cosine);
    forward->z = intro_fixed_multiply(forward->z, cosine) -
        intro_fixed_multiply(old, sine);
}

static void intro_rotate_about_k(int16_t angle, IntroFixedVector *right,
                                 IntroFixedVector *up)
{
    int32_t cosine;
    int32_t sine;
    int32_t old;

    cosine = intro_cos_fixed(angle);
    sine = intro_sin_fixed(angle);
    old = right->x;
    right->x = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(up->x, sine);
    up->x = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(up->x, cosine);
    old = right->y;
    right->y = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(up->y, sine);
    up->y = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(up->y, cosine);
    old = right->z;
    right->z = intro_fixed_multiply(old, cosine) -
        intro_fixed_multiply(up->z, sine);
    up->z = intro_fixed_multiply(old, sine) +
        intro_fixed_multiply(up->z, cosine);
}

/* This follows fix_objects_ijk(): every alter_pitch() in the DOS camera
 * path rebuilds the orthogonal basis and truncates it back to 24.8. Keeping
 * that accumulated rounding is more faithful than recomputing an ideal angle
 * for each visible frame. */
static void intro_fix_axes(IntroFixedVector *right, IntroFixedVector *up,
                           IntroFixedVector *forward)
{
    intro_cross_product(up, forward, right);
    intro_cross_product(forward, right, up);
    intro_normalize_vector(right);
    intro_normalize_vector(up);
    intro_normalize_vector(forward);
}

static void intro_alter_pitch(int16_t angle, IntroFixedVector *right,
                              IntroFixedVector *up,
                              IntroFixedVector *forward)
{
    intro_rotate_about_i(angle, up, forward);
    intro_fix_axes(right, up, forward);
}

static void intro_alter_yaw(int16_t angle, IntroFixedVector *right,
                            IntroFixedVector *up,
                            IntroFixedVector *forward)
{
    intro_rotate_about_j(angle, right, forward);
    intro_fix_axes(right, up, forward);
}

static void intro_alter_roll(int16_t angle, IntroFixedVector *right,
                             IntroFixedVector *up,
                             IntroFixedVector *forward)
{
    intro_rotate_about_k(angle, right, up);
    intro_fix_axes(right, up, forward);
}

static int32_t intro_dot_product(const IntroFixedVector *left,
                                 const IntroFixedVector *right)
{
    return intro_fixed_multiply(left->x, right->x) +
        intro_fixed_multiply(left->y, right->y) +
        intro_fixed_multiply(left->z, right->z);
}

static int16_t intro_absolute_short(int16_t value)
{
    return value < 0 ? (int16_t)-value : value;
}

static int16_t intro_arc_cos(int32_t value)
{
    int16_t angle;
    int16_t best_angle;
    int32_t best_difference;

    if (value >= 256)
        return 0;
    if (value <= -256)
        return 180;
    best_angle = 0;
    best_difference = 256 - value;
    for (angle = 1; angle <= 180; angle++) {
        int32_t difference;

        difference = intro_cos_fixed(angle) - value;
        if (difference < 0)
            difference = -difference;
        if (difference < best_difference) {
            best_difference = difference;
            best_angle = angle;
        }
    }
    return best_angle;
}

static int intro_rectangular_to_spherical(const IntroFixedVector *vector,
                                          int16_t *yaw, int16_t *pitch)
{
    IntroFixedVector planar;
    int32_t magnitude;
    int32_t planar_magnitude;
    int16_t result;

    magnitude = intro_vector_magnitude(vector);
    if (magnitude == 0)
        return 0;
    planar.x = vector->x;
    planar.y = 0;
    planar.z = vector->z;
    planar_magnitude = intro_vector_magnitude(&planar);
    if (planar_magnitude == 0)
        return 0;
    result = intro_arc_cos(intro_fixed_divide(vector->z, planar_magnitude));
    *yaw = vector->x < 0 ? (int16_t)-result : result;
    *pitch = (int16_t)(intro_arc_cos(
        intro_fixed_divide(vector->y, magnitude)) - 90);
    return 1;
}

/* initialize_direction_view_frames() generates these 62 view bases at
 * runtime in the DOS executable. Reconstructing the same lattice avoids a
 * large static table and gives get_right_shape() the exact source ordering. */
static void intro_direction_view_frame(uint16_t index, IntroFixedVector *right,
                                       IntroFixedVector *up,
                                       IntroFixedVector *forward)
{
    int16_t yaw;
    int16_t pitch;

    right->x = 256;
    right->y = 0;
    right->z = 0;
    up->x = 0;
    up->y = 256;
    up->z = 0;
    forward->x = 0;
    forward->y = 0;
    forward->z = 256;
    if (index == 0U) {
        pitch = 90;
        yaw = 0;
    } else if (index == 61U) {
        pitch = -90;
        yaw = 0;
    } else {
        pitch = (int16_t)(60 - ((int16_t)((index - 1U) / 12U) * 30));
        yaw = (int16_t)(((index - 1U) % 12U) * 30U);
    }
    intro_rotate_about_j(yaw, right, forward);
    intro_rotate_about_i(pitch, up, forward);
}

static const int8_t intro_direction_shape_frame[62] = {
    0, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2,
    14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13,
    15, 16, 17, 18, 19, 20, 21, 20, 19, 18, 17, 16,
    28, 27, 26, 25, 24, 23, 22, 23, 24, 25, 26, 27,
    29, 30, 31, 32, 33, 34, 35, 34, 33, 32, 31, 30,
    36
};

static const uint8_t intro_direction_shape_flip[62] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0
};
static const int8_t intro_capital_shape_frame[62] = {
    0U, 1U, 2U, 3U, 1U, 3U, 2U, 1U, 2U, 3U, 1U, 3U, 2U,
    4U, 5U, 6U, 4U, 6U, 5U, 4U, 5U, 6U, 4U, 6U, 5U,
    7U, 8U, 9U, 7U, 9U, 8U, 7U, 8U, 9U, 7U, 9U, 8U,
    10U, 11U, 12U, 10U, 12U, 11U, 10U, 11U, 12U, 10U, 12U, 11U,
    13U, 14U, 15U, 13U, 15U, 14U, 13U, 14U, 15U, 13U, 15U, 14U,
    16U
};
static const uint8_t intro_capital_shape_flip[62] = {
    0U, 0U, 0U, 0U, 0U, 0U, 0U, 0U, 1U, 1U, 1U, 1U, 1U,
    0U, 0U, 0U, 0U, 0U, 0U, 1U, 1U, 1U, 1U, 1U, 1U,
    0U, 0U, 0U, 0U, 0U, 0U, 0U, 1U, 1U, 1U, 1U, 1U,
    0U, 0U, 0U, 0U, 0U, 0U, 0U, 1U, 1U, 1U, 1U, 1U,
    0U, 0U, 0U, 0U, 0U, 0U, 0U, 1U, 1U, 1U, 1U, 1U,
    0U
};

/* This is get_right_shape() for the standard fighter table. It is shared by
 * the title's canned ships and the active mission renderer. Missile/base
 * direction tables and capital-ship per-view packets still belong to their
 * later resource-manager slices. */
static int intro_select_mobile_shape(const IntroFixedVector *ship_right,
                                     const IntroFixedVector *ship_up,
                                     const IntroFixedVector *ship_forward,
                                     const IntroFixedVector *camera_up,
                                     const IntroFixedVector *direction,
                                     const int8_t *shape_frames,
                                     const uint8_t *shape_flips,
                                     uint16_t *frame, int16_t *angle,
                                     uint16_t *flip)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    IntroFixedVector object_forward;
    IntroFixedVector eye_up;
    IntroFixedVector projected_up;
    IntroFixedVector reversed_direction;
    int16_t yaw;
    int16_t pitch;
    int16_t object_yaw;
    int16_t object_pitch;
    int16_t pitch_band;
    int16_t yaw_sector;
    int16_t remainder;
    int16_t direction_index;

    reversed_direction.x = -direction->x;
    reversed_direction.y = -direction->y;
    reversed_direction.z = -direction->z;
    if (!intro_rectangular_to_spherical(&reversed_direction, &yaw, &pitch))
        return 0;
    right.x = 256;
    right.y = 0;
    right.z = 0;
    up.x = 0;
    up.y = 256;
    up.z = 0;
    forward.x = 0;
    forward.y = 0;
    forward.z = 256;
    intro_rotate_about_j((int16_t)-yaw, &right, &forward);
    intro_rotate_about_i((int16_t)-pitch, &up, &forward);
    intro_normalize_vector(&up);
    intro_normalize_vector(&forward);
    object_forward.x = intro_dot_product(&forward, ship_right);
    object_forward.y = intro_dot_product(&forward, ship_up);
    object_forward.z = intro_dot_product(&forward, ship_forward);
    eye_up.x = intro_dot_product(camera_up, ship_right);
    eye_up.y = intro_dot_product(camera_up, ship_up);
    eye_up.z = intro_dot_product(camera_up, ship_forward);
    if (!intro_rectangular_to_spherical(&object_forward, &object_yaw,
                                        &object_pitch))
        return 0;
    pitch_band = (int16_t)(object_pitch / 30 + 3);
    remainder = (int16_t)(object_pitch % 30);
    if (remainder >= 16) {
        pitch_band++;
        if (pitch_band > 5)
            pitch_band = 6;
    } else if (remainder < -15) {
        pitch_band--;
        if (pitch_band < 1)
            pitch_band = 0;
    }
    yaw_sector = (int16_t)((12 - object_yaw / 30) % 12);
    remainder = (int16_t)(object_yaw % 30);
    if (remainder >= 16)
        yaw_sector = (int16_t)((yaw_sector + 11) % 12);
    else if (remainder < -15)
        yaw_sector = (int16_t)((yaw_sector + 1) % 12);
    if (yaw_sector < 0)
        yaw_sector += 12;
    if (pitch_band == 0)
        direction_index = 0;
    else if (pitch_band == 6)
        direction_index = 61;
    else
        direction_index = (int16_t)(pitch_band * 12 + yaw_sector - 11);
    intro_direction_view_frame((uint16_t)direction_index, &right, &up,
                               &forward);
    projected_up.x = intro_dot_product(&eye_up, &right);
    projected_up.y = intro_dot_product(&eye_up, &up);
    projected_up.z = 0;
    intro_normalize_vector(&projected_up);
    *angle = intro_arc_cos(projected_up.y);
    if (projected_up.x >= 0)
        *angle = (int16_t)(360 - *angle);
    *frame = (uint16_t)shape_frames[(uint16_t)direction_index];
    if (*frame == 0U)
        *angle = (int16_t)(*angle + 90);
    if (*frame == 36U)
        *angle = (int16_t)(*angle - 90);
    while (*angle < 0)
        *angle = (int16_t)(*angle + 360);
    while (*angle >= 360)
        *angle = (int16_t)(*angle - 360);
    *flip = (uint16_t)(shape_flips[(uint16_t)direction_index] << 4);
    return 1;
}

static int intro_select_fighter_shape(const IntroTitleShip *ship,
                                      const IntroFixedVector *direction,
                                      uint16_t *frame, int16_t *angle,
                                      uint16_t *flip)
{
    return intro_select_mobile_shape(&ship->right, &ship->up,
                                     &ship->forward,
                                     &resource_intro_camera_up, direction,
                                     intro_direction_shape_frame,
                                     intro_direction_shape_flip,
                                     frame, angle, flip);
}

typedef struct FlightMobileShapeProfile {
    uint16_t collision_radius;
    uint16_t scale;
} FlightMobileShapeProfile;

static int flight_capital_shape_profile(uint16_t object_type,
                                         FlightMobileShapeProfile *profile)
{
    switch (object_type) {
    case 4U:
    case 5U:
    case 6U:
        profile->collision_radius = 240U;
        profile->scale = 4096U;
        break;
    case 7U:
        profile->collision_radius = 500U;
        profile->scale = 2048U;
        break;
    case 8U:
        profile->collision_radius = 700U;
        profile->scale = 4096U;
        break;
    case 14U:
        profile->collision_radius = 200U;
        profile->scale = 1536U;
        break;
    case 15U:
    case 16U:
        profile->collision_radius = 260U;
        profile->scale = 2048U;
        break;
    case 17U:
        profile->collision_radius = 325U;
        profile->scale = 4096U;
        break;
    case 18U:
        profile->collision_radius = 450U;
        profile->scale = 4096U;
        break;
    case 19U:
        profile->collision_radius = 600U;
        profile->scale = 2048U;
        break;
    case 20U:
        profile->collision_radius = 400U;
        profile->scale = 4096U;
        break;
    case 21U:
        profile->collision_radius = 400U;
        profile->scale = 2048U;
        break;
    default:
        return 0;
    }
    return 1;
}

/* Set_up_ship_info() applies the packed mission fields as yaw(-pitch),
 * pitch(-yaw), roll(roll).  Keep that unusual historical field ordering in
 * one place: it drives player movement, non-player drift, the eye frame,
 * hardpoint placement, and fixed projectile velocity. */
static void flight_axes_from_mission_angles(int16_t object_pitch,
                                            int16_t object_yaw,
                                            int16_t object_roll,
                                            IntroFixedVector *right,
                                            IntroFixedVector *up,
                                            IntroFixedVector *forward)
{
    right->x = 256;
    right->y = 0;
    right->z = 0;
    up->x = 0;
    up->y = 256;
    up->z = 0;
    forward->x = 0;
    forward->y = 0;
    forward->z = 256;
    intro_alter_yaw((int16_t)-object_pitch, right, up, forward);
    intro_alter_pitch((int16_t)-object_yaw, right, up, forward);
    intro_alter_roll(object_roll, right, up, forward);
}

static uint16_t flight_background_random_below_or_equal(uint16_t maximum)
{
    resource_flight_background_seed =
        resource_flight_background_seed * 1664525UL + 1013904223UL;
    return (uint16_t)((resource_flight_background_seed >> 16) %
                      ((uint32_t)maximum + 1U));
}

static int32_t flight_background_signed_random(uint16_t range)
{
    return (int32_t)flight_background_random_below_or_equal(
               (uint16_t)(range * 2U)) - range;
}

static int32_t flight_background_random_component(uint16_t range)
{
    return flight_background_signed_random(range) << 8;
}

static void flight_background_start_dust(uint16_t index,
                                         uint16_t forward_distance,
                                         int32_t right_offset,
                                         int32_t up_offset)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    IntroFixedVector offset;
    FlightBackgroundObject *dust;

    dust = &resource_flight_background[index];
    flight_axes_from_mission_angles(object_pitch[0], object_yaw[0],
                                    object_roll[0], &right, &up, &forward);
    dust->position.x = object_x[0];
    dust->position.y = object_y[0];
    dust->position.z = object_z[0];
    offset.x = intro_fixed_multiply(forward.x,
                                    (int32_t)forward_distance << 8);
    offset.y = intro_fixed_multiply(forward.y,
                                    (int32_t)forward_distance << 8);
    offset.z = intro_fixed_multiply(forward.z,
                                    (int32_t)forward_distance << 8);
    dust->position.x += offset.x;
    dust->position.y += offset.y;
    dust->position.z += offset.z;
    offset.x = intro_fixed_multiply(right.x, right_offset);
    offset.y = intro_fixed_multiply(right.y, right_offset);
    offset.z = intro_fixed_multiply(right.z, right_offset);
    dust->position.x += offset.x;
    dust->position.y += offset.y;
    dust->position.z += offset.z;
    offset.x = intro_fixed_multiply(up.x, up_offset);
    offset.y = intro_fixed_multiply(up.y, up_offset);
    offset.z = intro_fixed_multiply(up.z, up_offset);
    dust->position.x += offset.x;
    dust->position.y += offset.y;
    dust->position.z += offset.z;
    dust->velocity.x = flight_background_random_component(2U);
    dust->velocity.y = flight_background_random_component(2U);
    dust->velocity.z = flight_background_random_component(2U);
    dust->screen_angle = (uint16_t)(
        (flight_background_random_below_or_equal(3U) == 0U ? 0x10U : 0U) +
        flight_background_random_below_or_equal(3U));
    dust->star = 0U;
    dust->offscreen = 0U;
}

static void flight_background_start_star(uint16_t index, int16_t pitch,
                                         int16_t yaw)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    FlightBackgroundObject *star;

    star = &resource_flight_background[index];
    flight_axes_from_mission_angles(object_pitch[0], object_yaw[0],
                                    object_roll[0], &right, &up, &forward);
    intro_rotate_about_j(yaw, &right, &forward);
    intro_rotate_about_i(pitch, &up, &forward);
    star->position.x = intro_fixed_multiply(forward.x,
                                             WC1_FLIGHT_STAR_DISTANCE << 8);
    star->position.y = intro_fixed_multiply(forward.y,
                                             WC1_FLIGHT_STAR_DISTANCE << 8);
    star->position.z = intro_fixed_multiply(forward.z,
                                             WC1_FLIGHT_STAR_DISTANCE << 8);
    star->velocity.x = 0;
    star->velocity.y = 0;
    star->velocity.z = 0;
    star->frame = (uint16_t)(32U +
                             flight_background_random_below_or_equal(5U));
    star->screen_angle = 0U;
    star->star = 1U;
    star->offscreen = 0U;
}

/* generate_stars() is called after the eye object is established. The
 * Falcon keeps that same lifetime boundary: no background object is created
 * until game_init has installed the player's world frame. */
void resource_flight_background_reset(void)
{
    uint16_t index;

    resource_flight_background_seed = 0x57433146UL;
    resource_flight_background_frame = 0U;
    resource_flight_background_initialized = 1U;
    for (index = 0U; index < WC1_FLIGHT_DUST_COUNT; index++) {
        uint16_t distance;

        distance = flight_background_random_below_or_equal(
            WC1_FLIGHT_DUST_MAX_DISTANCE);
        flight_background_start_dust(
            index, distance,
            flight_background_signed_random(distance) << 8,
            flight_background_signed_random(distance) << 8);
    }
    for (index = 0U; index < WC1_FLIGHT_STAR_COUNT; index++)
        flight_background_start_star(
            (uint16_t)(WC1_FLIGHT_DUST_COUNT + index),
            (int16_t)flight_background_signed_random(45U),
            (int16_t)flight_background_signed_random(45U));
}

/* update_star_field() moves dust with its tiny source velocity and replaces
 * any record whose previous projection left the view. The complete hazard
 * branch remains owned by the mission-object update, but the ordinary
 * no-hazard path is now the source 8-dust/7-star field rather than a random
 * host-side dot pattern. */
void resource_flight_background_tick(void)
{
    uint16_t index;

    if (resource_flight_background_initialized == 0U)
        resource_flight_background_reset();
    resource_flight_background_frame++;
    for (index = 0U; index < WC1_FLIGHT_DUST_COUNT; index++) {
        FlightBackgroundObject *dust;

        dust = &resource_flight_background[index];
        dust->position.x += dust->velocity.x;
        dust->position.y += dust->velocity.y;
        dust->position.z += dust->velocity.z;
        if (dust->offscreen != 0U) {
            uint16_t distance;

            distance = flight_background_random_below_or_equal(
                WC1_FLIGHT_DUST_MAX_DISTANCE);
            flight_background_start_dust(
                index, distance,
                flight_background_signed_random(distance) << 8,
                flight_background_signed_random(distance) << 8);
        }
    }
    for (index = 0U; index < WC1_FLIGHT_STAR_COUNT; index++) {
        FlightBackgroundObject *star;

        star = &resource_flight_background[WC1_FLIGHT_DUST_COUNT + index];
        if (star->offscreen != 0U)
            flight_background_start_star(
                (uint16_t)(WC1_FLIGHT_DUST_COUNT + index),
                (int16_t)flight_background_signed_random(45U),
                (int16_t)flight_background_signed_random(45U));
    }
}

static int flight_background_project(const FlightBackgroundObject *object,
                                     const IntroFixedVector *camera_right,
                                     const IntroFixedVector *camera_up,
                                     const IntroFixedVector *camera_forward,
                                     int32_t camera_x, int32_t camera_y,
                                     int32_t camera_z, int32_t *distance,
                                     int32_t *screen_x, int32_t *screen_y)
{
    IntroFixedVector direction;
    IntroFixedVector view_position;

    if (object->star != 0U) {
        direction = object->position;
    } else {
        direction.x = object->position.x - camera_x;
        direction.y = object->position.y - camera_y;
        direction.z = object->position.z - camera_z;
    }
    *distance = intro_vector_magnitude(&direction);
    if (*distance <= (WC1_FLIGHT_EYE_RADIUS << 8) ||
        (object->star == 0U &&
         *distance > (int32_t)(WC1_FLIGHT_DUST_MAX_DISTANCE << 8)))
        return 0;
    view_position.x = intro_dot_product(&direction, camera_right);
    view_position.y = intro_dot_product(&direction, camera_up);
    view_position.z = intro_dot_product(&direction, camera_forward);
    if (view_position.z <= (WC1_FLIGHT_EYE_RADIUS << 8) ||
        intro_fixed_divide(view_position.z, *distance) < 0x94)
        return 0;
    *screen_x = (FALCON_FRAME_WIDTH >> 1) +
        view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    *screen_y = (FALCON_FRAME_HEIGHT >> 1) +
        view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    if (*screen_x < 0 || *screen_x >= FALCON_FRAME_WIDTH || *screen_y < 0 ||
        *screen_y >= FALCON_FRAME_HEIGHT)
        return 0;
    return 1;
}

/* Draw the source PLANETS.VGA frame lattice behind contacts and weapons.
 * Dust uses the original 0..31 size/streak lattice; stars retain their
 * generated 32..37 frame. */
void resource_draw_flight_background(void)
{
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    uint16_t index;

    if (render_target == 0 || resource_constellation_size == 0U ||
        (resource_status & RESOURCE_STATUS_PALETTE) == 0U)
        return;
    if (resource_flight_background_initialized == 0U)
        resource_flight_background_reset();
    flight_axes_from_mission_angles(object_pitch[0], object_yaw[0],
                                    object_roll[0], &camera_right, &camera_up,
                                    &camera_forward);
    for (index = 0U; index < WC1_FLIGHT_BACKGROUND_COUNT; index++) {
        FlightBackgroundObject *object;
        int32_t distance;
        int32_t screen_x;
        int32_t screen_y;
        uint16_t frame;

        object = &resource_flight_background[index];
        if (!flight_background_project(
                object, &camera_right, &camera_up, &camera_forward,
                object_x[0], object_y[0], object_z[0], &distance, &screen_x,
                &screen_y)) {
            object->offscreen = 1U;
            continue;
        }
        object->offscreen = 0U;
        if (object->star != 0U) {
            frame = object->frame;
        } else {
            int32_t dust_size;

            dust_size = intro_fixed_multiply(
                0x900, intro_fixed_divide(WC1_FLIGHT_EYE_RADIUS << 8,
                                          distance)) >> 8;
            if (dust_size < 0)
                dust_size = 0;
            if (dust_size > 3)
                dust_size = 3;
            frame = (uint16_t)((resource_flight_background_frame & 3U) +
                               (object->screen_angle & 0x10U) +
                               (uint16_t)(3 - dust_size) * 4U);
        }
        (void)draw_shape_frame(resource_constellation_data,
                               resource_constellation_size, frame, screen_x,
                               screen_y);
    }
}

/* Falcon assembly state owners call this instead of approximating a heading
 * with quadrants.  It is the DOS fix_velocity() operation: scale the current
 * unit forward vector by the 8.8 ship speed and expose a 24.8 velocity. */
void resource_flight_velocity(int16_t object_pitch, int16_t object_yaw,
                              int16_t object_roll, int16_t speed)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    int32_t scale;

    flight_axes_from_mission_angles(object_pitch, object_yaw, object_roll,
                                    &right, &up, &forward);
    scale = (int32_t)speed << 8;
    resource_flight_velocity_x = intro_fixed_multiply(forward.x, scale);
    resource_flight_velocity_y = intro_fixed_multiply(forward.y, scale);
    resource_flight_velocity_z = intro_fixed_multiply(forward.z, scale);
}

/* Compact transform_objects_to_your_view() seam for check_target(). It owns
 * no target state: game.s applies the source policy (retain a visible target,
 * otherwise prefer the nearest visible hostile) across its active roster. */
int resource_flight_target_visible(int32_t direction_x, int32_t direction_y,
                                   int32_t direction_z,
                                   int16_t camera_pitch,
                                   int16_t camera_yaw,
                                   int16_t camera_roll)
{
    IntroFixedVector direction;
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    IntroFixedVector view_position;

    direction.x = direction_x;
    direction.y = direction_y;
    direction.z = direction_z;
    resource_flight_target_distance = intro_vector_magnitude(&direction);
    if (resource_flight_target_distance == 0 ||
        resource_flight_target_distance >= (12000L << 8))
        return 0;
    flight_axes_from_mission_angles(camera_pitch, camera_yaw, camera_roll,
                                    &camera_right, &camera_up,
                                    &camera_forward);
    view_position.x = intro_dot_product(&direction, &camera_right);
    view_position.y = intro_dot_product(&direction, &camera_up);
    view_position.z = intro_dot_product(&direction, &camera_forward);
    if (view_position.z <= 0 ||
        intro_fixed_divide(view_position.z, resource_flight_target_distance) <
            0x94)
        return 0;
    return 1;
}

/* The assembly renderer uses this before its bounded far-to-near sort. It
 * deliberately shares the title/3Space overflow-safe vector magnitude,
 * instead of comparing raw world axes or introducing a Falcon-only metric. */
int32_t resource_flight_distance(int32_t direction_x, int32_t direction_y,
                                 int32_t direction_z)
{
    IntroFixedVector direction;

    direction.x = direction_x;
    direction.y = direction_y;
    direction.z = direction_z;
    return intro_vector_magnitude(&direction);
}

/* The fighter rows of g_aObjectTypeData_00466458. The exact values are
 * sufficient for every standard mobile ship packet (section zero) that the
 * current three-slot manager can retain. Capital rows use the separate
 * per-view profile below. */
static int flight_mobile_shape_profile(uint16_t object_type,
                                       FlightMobileShapeProfile *profile)
{
    switch (object_type) {
    case 0U:  /* Hornet */
        profile->collision_radius = 100U;
        profile->scale = 1024U;
        break;
    case 1U:  /* Rapier */
        profile->collision_radius = 120U;
        profile->scale = 1024U;
        break;
    case 2U:  /* Scimitar */
        profile->collision_radius = 165U;
        profile->scale = 1152U;
        break;
    case 3U:  /* Raptor */
        profile->collision_radius = 180U;
        profile->scale = 1152U;
        break;
    case 9U:  /* Salthi */
        profile->collision_radius = 120U;
        profile->scale = 1024U;
        break;
    case 10U: /* Dralthi */
        profile->collision_radius = 160U;
        profile->scale = 1024U;
        break;
    case 11U: /* Krant */
        profile->collision_radius = 140U;
        profile->scale = 1024U;
        break;
    case 12U: /* Gratha */
        profile->collision_radius = 140U;
        profile->scale = 1024U;
        break;
    case 13U: /* Jalthi */
        profile->collision_radius = 160U;
        profile->scale = 1024U;
        break;
    default:
        return 0;
    }
    return 1;
}

/* Render one active mission ship after render.s has formed its exact 24.8
 * delta from the eye object. Fighters use retained section-zero shape sets;
 * capital ships use the on-demand per-view section selected by get_right_shape
 * and prepared outside the render interval. */
int resource_draw_flight_object(int32_t direction_x, int32_t direction_y,
                                int32_t direction_z, uint16_t object_type,
                                int16_t object_pitch, int16_t object_yaw,
                                int16_t object_roll,
                                int16_t camera_pitch, int16_t camera_yaw,
                                int16_t camera_roll)
{
    FlightMobileShapeProfile profile;
    IntroFixedVector direction;
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    IntroFixedVector view_position;
    IntroFixedVector ship_right;
    IntroFixedVector ship_up;
    IntroFixedVector ship_forward;
    int32_t distance;
    int32_t object_radius;
    int32_t scale_factor;
    int32_t scale;
    int32_t screen_x;
    int32_t screen_y;
    uint16_t frame;
    uint16_t flip;
    int16_t angle;
    uint16_t slot;
    int capital;

    if ((resource_status & RESOURCE_STATUS_PALETTE) == 0U)
        return 0;
    capital = !flight_mobile_shape_profile(object_type, &profile);
    if (capital != 0) {
        if (!flight_capital_shape_profile(object_type, &profile) ||
            (resource_status & RESOURCE_STATUS_CAPITAL_VIEW) == 0U ||
            resource_capital_shape_type != object_type)
            return 0;
    } else if ((resource_status & RESOURCE_STATUS_OBJECT_SHAPE) == 0U) {
        return 0;
    }
    direction.x = direction_x;
    direction.y = direction_y;
    direction.z = direction_z;
    distance = intro_vector_magnitude(&direction);
    if (distance == 0)
        return 0;
    flight_axes_from_mission_angles(camera_pitch, camera_yaw, camera_roll,
                                    &camera_right, &camera_up,
                                    &camera_forward);
    view_position.x = intro_dot_product(&direction, &camera_right);
    view_position.y = intro_dot_product(&direction, &camera_up);
    view_position.z = intro_dot_product(&direction, &camera_forward);
    object_radius = (int32_t)profile.collision_radius << 8;
    if (distance <= object_radius || view_position.z <= object_radius ||
        intro_fixed_divide(view_position.z, distance) < 0x94)
        return 0;
    scale_factor = intro_fixed_divide((int32_t)FALCON_FRAME_WIDTH << 15,
                                      distance - object_radius);
    scale = intro_fixed_multiply((int32_t)profile.scale, scale_factor) >> 8;
    if (scale < 5)
        return 0;
    if (scale > 0x2000)
        scale = 0x2000;
    flight_axes_from_mission_angles(object_pitch, object_yaw, object_roll,
                                    &ship_right, &ship_up, &ship_forward);
    if (!intro_select_mobile_shape(&ship_right, &ship_up, &ship_forward,
                                   &camera_up, &direction,
                                   capital != 0 ? intro_capital_shape_frame :
                                   intro_direction_shape_frame,
                                   capital != 0 ? intro_capital_shape_flip :
                                   intro_direction_shape_flip,
                                   &frame, &angle, &flip))
        return 0;
    screen_x = (FALCON_FRAME_WIDTH >> 1) +
        view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    screen_y = (FALCON_FRAME_HEIGHT >> 1) +
        view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    if (capital != 0) {
        if (resource_capital_shape_frame != frame)
            return 0;
        return draw_shape_frame_transformed(
            resource_capital_shape_data, resource_capital_shape_size, 0U,
            screen_x, screen_y, angle, (uint16_t)scale, flip, 0, 0U);
    }
    for (slot = 0U; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == object_type) {
            return draw_shape_frame_transformed(
                resource_object_data[slot], resource_object_sizes[slot],
                frame, screen_x, screen_y, angle, (uint16_t)scale, flip,
                0, 0U);
        }
    }
    return 0;
}

/* GEMDOS-side capital view service. A capital view is selected with the same
 * 62-direction lattice as the DOS renderer, but its SHIP.Vxx section is
 * loaded here while VBLs are enabled. render_frame() only consumes the
 * retained native packet and therefore remains a pure indexed-pixel pass. */
void resource_flight_service_capital(void)
{
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    uint16_t active_count;
    uint16_t slot;

    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    if (active_count < 2U)
        return;
    flight_axes_from_mission_angles(object_pitch[0], object_yaw[0],
                                    object_roll[0], &camera_right, &camera_up,
                                    &camera_forward);
    for (slot = 1U; slot < active_count; slot++) {
        FlightMobileShapeProfile profile;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        IntroFixedVector ship_right;
        IntroFixedVector ship_up;
        IntroFixedVector ship_forward;
        uint16_t frame;
        uint16_t flip;
        int16_t angle;
        int32_t distance;

        if (object_active[slot] == 0U ||
            !flight_capital_shape_profile(object_types[slot], &profile))
            continue;
        direction.x = object_x[slot] - object_x[0];
        direction.y = object_y[slot] - object_y[0];
        direction.z = object_z[slot] - object_z[0];
        distance = intro_vector_magnitude(&direction);
        if (distance == 0)
            continue;
        view_position.x = intro_dot_product(&direction, &camera_right);
        view_position.y = intro_dot_product(&direction, &camera_up);
        view_position.z = intro_dot_product(&direction, &camera_forward);
        if (view_position.z <= ((int32_t)profile.collision_radius << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        flight_axes_from_mission_angles(object_pitch[slot], object_yaw[slot],
                                        object_roll[slot], &ship_right,
                                        &ship_up, &ship_forward);
        if (!intro_select_mobile_shape(
                &ship_right, &ship_up, &ship_forward, &camera_up, &direction,
                intro_capital_shape_frame, intro_capital_shape_flip, &frame,
                &angle, &flip))
            continue;
        (void)angle;
        (void)flip;
        if (resource_load_capital_view(object_types[slot], frame))
            return;
    }
}

typedef struct FlightWeaponSlot {
    uint16_t type;
    int16_t hardpoint;
} FlightWeaponSlot;

typedef struct FlightHardpoint {
    int16_t x;
    int16_t y;
    int16_t z;
} FlightHardpoint;

/* Exact g_aChildOffsets_004682f0 locations.  position_child() combines these
 * short coordinates with the parent's 24.8 i/j/k frame without an additional
 * fixed-point divide, so retain that representation here. */
static const FlightHardpoint flight_hardpoints[56] = {
    {120, 10, 20}, {-120, 10, 20}, {75, 45, -30}, {-75, 45, -30},
    {0, 50, 10}, {-100, 10, -40}, {-90, 0, 30}, {-30, -40, -30},
    {0, 0, 0}, {30, -40, -30}, {100, 10, -40}, {90, 0, 30},
    {-140, 10, 30}, {-100, 10, 0}, {-75, 0, -40}, {-30, 10, -20},
    {0, 10, 10}, {30, 10, -20}, {75, 0, -40}, {100, 10, 0},
    {140, 10, 30}, {-120, -10, 0}, {-100, 10, -20}, {-90, 0, 40},
    {-30, 20, -20}, {0, 10, -80}, {0, 10, 10}, {30, 20, -20},
    {90, 0, 40}, {100, 10, -20}, {120, -10, 0}, {0, 10, 10},
    {0, 0, -60}, {0, 0, 500}, {-200, 0, 250}, {200, 0, 250},
    {-300, 0, 0}, {300, 0, 0}, {-200, 0, -250}, {200, 0, -250},
    {0, 0, -500}, {-130, 40, 20}, {-110, 20, 20}, {-90, 0, 20},
    {130, 40, 20}, {110, 20, 20}, {90, 0, 20}, {0, 0, 400},
    {-50, -20, 350}, {50, 20, 350}, {-150, 20, 0}, {150, -20, 0},
    {-75, -20, -350}, {75, 20, -350}, {0, 100, 350}, {0, 0, -300}
};

/* The enabled projectile entries of ObjectTypeData.weaponLoadout for the four
 * campaign player hulls.  Missiles are deliberately absent: this is the
 * fire_fixed_projectile_weapon() path, not release-weapon selection. */
static const FlightWeaponSlot flight_hornet_guns[] = {
    {24U, 0}, {24U, 1}
};
static const FlightWeaponSlot flight_rapier_guns[] = {
    {24U, 14}, {24U, 18}, {25U, 12}, {25U, 20}
};
static const FlightWeaponSlot flight_scimitar_guns[] = {
    {26U, 6}, {26U, 11}
};
static const FlightWeaponSlot flight_raptor_guns[] = {
    {25U, 23}, {25U, 28}, {26U, 21}, {26U, 30}
};
/* Enabled projectile slots recovered from the common fighter records. Missile
 * entries remain out of this fixed-cannon slice; turret entries are represented
 * by their source laser projectile and keep their original hardpoint. */
static const FlightWeaponSlot flight_salthi_guns[] = {
    {24U, 0}, {24U, 1}
};
static const FlightWeaponSlot flight_dralthi_guns[] = {
    {24U, 0}, {24U, 1}
};
static const FlightWeaponSlot flight_krant_guns[] = {
    {24U, 0}, {24U, 1}
};
static const FlightWeaponSlot flight_gratha_guns[] = {
    {24U, 0}, {24U, 1}, {26U, 21}, {26U, 30}
};
static const FlightWeaponSlot flight_jalthi_guns[] = {
    {25U, 41}, {25U, 44}, {24U, 42}, {24U, 43},
    {24U, 45}, {24U, 46}
};
static const FlightWeaponSlot flight_venture_guns[] = {
    {24U, 51}, {24U, 50}
};
static const FlightWeaponSlot flight_dilligent_guns[] = {
    {24U, 54}
};
static const FlightWeaponSlot flight_drayman_guns[] = {
    {24U, 54}
};
static const FlightWeaponSlot flight_exeter_guns[] = {
    {24U, 47}, {24U, 48}, {24U, 49}, {24U, 50}, {24U, 51}
};
static const FlightWeaponSlot flight_tigers_claw_guns[] = {
    {24U, 33}, {24U, 34}, {24U, 35}, {24U, 36},
    {24U, 37}, {24U, 38}, {24U, 39}, {24U, 40}
};
static const FlightWeaponSlot flight_spikeri_guns[] = {
    {24U, 0}
};
static const FlightWeaponSlot flight_dorkir_guns[] = {
    {24U, 54}
};
static const FlightWeaponSlot flight_lumbari_guns[] = {
    {24U, 54}
};
static const FlightWeaponSlot flight_ralari_guns[] = {
    {24U, 47}, {24U, 48}, {24U, 49}, {24U, 50},
    {24U, 51}, {24U, 52}, {24U, 53}
};
static const FlightWeaponSlot flight_fralthi_guns[] = {
    {24U, 47}, {24U, 47}, {24U, 48}, {24U, 49},
    {24U, 50}, {24U, 51}, {24U, 52}, {24U, 53}
};
static const FlightWeaponSlot flight_sivar_guns[] = {
    {24U, 47}, {24U, 48}, {24U, 49}, {24U, 50},
    {24U, 51}, {24U, 52}, {24U, 53}, {24U, 54}
};
static const FlightWeaponSlot flight_base_guns[] = {
    {24U, 33}, {24U, 36}, {24U, 37}, {24U, 40},
    {24U, 33}, {24U, 36}, {24U, 37}, {24U, 40}
};

static int flight_ship_loadout(uint16_t ship_type,
                               const FlightWeaponSlot **slots,
                               uint16_t *slot_count)
{
    switch (ship_type) {
    case 0U:
        *slots = flight_hornet_guns;
        *slot_count = (uint16_t)(sizeof(flight_hornet_guns) /
                                 sizeof(flight_hornet_guns[0]));
        break;
    case 1U:
        *slots = flight_rapier_guns;
        *slot_count = (uint16_t)(sizeof(flight_rapier_guns) /
                                 sizeof(flight_rapier_guns[0]));
        break;
    case 2U:
        *slots = flight_scimitar_guns;
        *slot_count = (uint16_t)(sizeof(flight_scimitar_guns) /
                                 sizeof(flight_scimitar_guns[0]));
        break;
    case 3U:
        *slots = flight_raptor_guns;
        *slot_count = (uint16_t)(sizeof(flight_raptor_guns) /
                                 sizeof(flight_raptor_guns[0]));
        break;
    case 4U:
        *slots = flight_venture_guns;
        *slot_count = (uint16_t)(sizeof(flight_venture_guns) /
                                 sizeof(flight_venture_guns[0]));
        break;
    case 5U:
        *slots = flight_dilligent_guns;
        *slot_count = (uint16_t)(sizeof(flight_dilligent_guns) /
                                 sizeof(flight_dilligent_guns[0]));
        break;
    case 6U:
        *slots = flight_drayman_guns;
        *slot_count = (uint16_t)(sizeof(flight_drayman_guns) /
                                 sizeof(flight_drayman_guns[0]));
        break;
    case 7U:
        *slots = flight_exeter_guns;
        *slot_count = (uint16_t)(sizeof(flight_exeter_guns) /
                                 sizeof(flight_exeter_guns[0]));
        break;
    case 8U:
        *slots = flight_tigers_claw_guns;
        *slot_count = (uint16_t)(sizeof(flight_tigers_claw_guns) /
                                 sizeof(flight_tigers_claw_guns[0]));
        break;
    case 9U:
        *slots = flight_salthi_guns;
        *slot_count = (uint16_t)(sizeof(flight_salthi_guns) /
                                 sizeof(flight_salthi_guns[0]));
        break;
    case 10U:
        *slots = flight_dralthi_guns;
        *slot_count = (uint16_t)(sizeof(flight_dralthi_guns) /
                                 sizeof(flight_dralthi_guns[0]));
        break;
    case 11U:
        *slots = flight_krant_guns;
        *slot_count = (uint16_t)(sizeof(flight_krant_guns) /
                                 sizeof(flight_krant_guns[0]));
        break;
    case 12U:
        *slots = flight_gratha_guns;
        *slot_count = (uint16_t)(sizeof(flight_gratha_guns) /
                                 sizeof(flight_gratha_guns[0]));
        break;
    case 13U:
        *slots = flight_jalthi_guns;
        *slot_count = (uint16_t)(sizeof(flight_jalthi_guns) /
                                 sizeof(flight_jalthi_guns[0]));
        break;
    case 14U:
        *slots = flight_spikeri_guns;
        *slot_count = (uint16_t)(sizeof(flight_spikeri_guns) /
                                 sizeof(flight_spikeri_guns[0]));
        break;
    case 15U:
        *slots = flight_dorkir_guns;
        *slot_count = (uint16_t)(sizeof(flight_dorkir_guns) /
                                 sizeof(flight_dorkir_guns[0]));
        break;
    case 16U:
        *slots = flight_lumbari_guns;
        *slot_count = (uint16_t)(sizeof(flight_lumbari_guns) /
                                 sizeof(flight_lumbari_guns[0]));
        break;
    case 17U:
        *slots = flight_ralari_guns;
        *slot_count = (uint16_t)(sizeof(flight_ralari_guns) /
                                 sizeof(flight_ralari_guns[0]));
        break;
    case 18U:
        *slots = flight_fralthi_guns;
        *slot_count = (uint16_t)(sizeof(flight_fralthi_guns) /
                                 sizeof(flight_fralthi_guns[0]));
        break;
    case 20U:
        *slots = flight_sivar_guns;
        *slot_count = (uint16_t)(sizeof(flight_sivar_guns) /
                                 sizeof(flight_sivar_guns[0]));
        break;
    case 21U:
        *slots = flight_base_guns;
        *slot_count = (uint16_t)(sizeof(flight_base_guns) /
                                 sizeof(flight_base_guns[0]));
        break;
    default:
        *slots = 0;
        *slot_count = 0U;
        return 0;
    }
    return 1;
}

static int flight_player_uses_projectile(uint16_t player_type,
                                          uint16_t projectile_type)
{
    const FlightWeaponSlot *slots;
    uint16_t count;
    uint16_t index;

    if (!flight_ship_loadout(player_type, &slots, &count))
        return 0;
    for (index = 0U; index < count; index++) {
        if (slots[index].type == projectile_type)
            return 1;
    }
    return 0;
}

/* The three source projectile ObjectTypeData rows: collision radius, 8.8
 * scale, lifetime, and maximum velocity.  OBJECTS.VGA maps them to sections
 * six, eight, and seven respectively (see g_aShapeSetDefinitions). */
static int flight_projectile_profile(uint16_t type, const uint8_t **shape,
                                     uint32_t *shape_size,
                                     uint16_t *collision_radius,
                                     uint16_t *scale, uint16_t *lifetime,
                                     uint16_t *velocity)
{
    switch (type) {
    case 24U: /* laser cannon */
        *shape = resource_title_laser_data;
        *shape_size = resource_title_laser_size;
        *collision_radius = 10U;
        *scale = 512U;
        *lifetime = 30U;
        *velocity = 160U;
        break;
    case 25U: /* neutron particle gun */
        *shape = resource_flight_neutron_data;
        *shape_size = resource_flight_neutron_size;
        *collision_radius = 10U;
        *scale = 832U;
        *lifetime = 20U;
        *velocity = 140U;
        break;
    case 26U: /* mass driver cannon */
        *shape = resource_flight_mass_driver_data;
        *shape_size = resource_flight_mass_driver_size;
        *collision_radius = 10U;
        *scale = 512U;
        *lifetime = 25U;
        *velocity = 120U;
        break;
    default:
        return 0;
    }
    return *shape_size != 0U;
}

static int16_t flight_projectile_refire_delay(uint16_t type)
{
    switch (type) {
    case 24U:
        return 6;
    case 25U:
        return 10;
    default: /* 26: mass driver */
        return 4;
    }
}

/* ObjectTypeData rows 0..21, reduced only to the fields touched by
 * check_for_collision(), inflict_damage(), and replenish_shields().  The
 * order and values are transcribed from globals.c, preserving the original
 * front/aft and armor-array indexing rather than inventing Falcon values. */
typedef struct FlightCombatProfile {
    uint16_t collision_radius;
    uint16_t damage_capacity;
    uint16_t shield_fore;
    uint16_t shield_aft;
    uint16_t armor_front;
    uint16_t armor_rear;
    uint16_t armor_left;
    uint16_t armor_right;
    uint16_t shield_delay;
    uint8_t capital;
} FlightCombatProfile;

static const FlightCombatProfile flight_combat_profiles[22] = {
    {100U, 5U, 40U, 40U, 45U, 40U, 30U, 30U, 5U, 0U},
    {120U, 6U, 80U, 75U, 60U, 55U, 50U, 50U, 3U, 0U},
    {165U, 7U, 60U, 50U, 85U, 80U, 65U, 65U, 6U, 0U},
    {180U, 8U, 70U, 70U, 100U, 90U, 80U, 80U, 3U, 0U},
    {240U, 70U, 150U, 150U, 110U, 100U, 100U, 110U, 5U, 1U},
    {240U, 60U, 120U, 120U, 80U, 80U, 60U, 60U, 4U, 1U},
    {240U, 60U, 120U, 120U, 80U, 80U, 60U, 60U, 4U, 1U},
    {500U, 200U, 240U, 240U, 220U, 200U, 200U, 200U, 2U, 1U},
    {700U, 560U, 300U, 300U, 240U, 200U, 250U, 250U, 1U, 1U},
    {120U, 5U, 35U, 35U, 30U, 20U, 15U, 15U, 10U, 0U},
    {160U, 7U, 50U, 50U, 45U, 35U, 30U, 30U, 6U, 0U},
    {140U, 6U, 80U, 80U, 90U, 100U, 80U, 80U, 5U, 0U},
    {140U, 7U, 100U, 95U, 140U, 120U, 100U, 100U, 4U, 0U},
    {160U, 7U, 160U, 160U, 200U, 100U, 170U, 170U, 7U, 0U},
    {200U, 45U, 70U, 70U, 80U, 80U, 60U, 60U, 4U, 1U},
    {260U, 35U, 170U, 100U, 90U, 60U, 90U, 90U, 5U, 1U},
    {260U, 35U, 70U, 70U, 80U, 80U, 60U, 60U, 5U, 1U},
    {325U, 90U, 200U, 120U, 200U, 90U, 180U, 180U, 3U, 1U},
    {450U, 110U, 270U, 170U, 280U, 140U, 260U, 260U, 2U, 1U},
    {600U, 320U, 70U, 70U, 80U, 80U, 60U, 60U, 1U, 1U},
    {400U, 200U, 270U, 170U, 280U, 140U, 260U, 260U, 1U, 1U},
    {400U, 120U, 200U, 200U, 180U, 180U, 180U, 180U, 4U, 1U}
};

static const FlightCombatProfile *flight_combat_profile(uint16_t type)
{
    if (type >= sizeof(flight_combat_profiles) /
                    sizeof(flight_combat_profiles[0]))
        return 0;
    return &flight_combat_profiles[type];
}

/* Cockpit bars are the source g_aaCockpitBars_0046dd88 table.  The frame
 * numbers refer to the secondary PCSHIP.Vxx section seven packet retained by
 * resource_load_cockpit(); keeping the table here makes the Falcon draw path
 * use the original bar geometry instead of replacing it with guessed gauges.
 */
typedef struct FlightCockpitBar {
    int8_t direction;
    int16_t left;
    int16_t top;
    int16_t right;
    int16_t bottom;
    uint16_t length;
    uint8_t filled_frame;
    uint8_t empty_frame;
} FlightCockpitBar;

static const FlightCockpitBar flight_cockpit_bars[5][8] = {
    {
        {0, 215, 122, 219, 152, 31, 16, 5},
        {2, 143, 97, 175, 99, 33, 12, 1},
        {0, 114, 127, 123, 130, 4, 17, 6},
        {1, 114, 143, 123, 146, 4, 20, 9},
        {2, 109, 132, 112, 141, 4, 18, 7},
        {3, 125, 132, 128, 141, 4, 19, 8},
        {0, 109, 122, 128, 125, 4, 15, 4},
        {1, 109, 148, 128, 151, 4, 21, 10}
    },
    {
        {2, 96, 14, 134, 17, 39, 10, 0},
        {2, 185, 14, 223, 17, 39, 11, 1},
        {0, 213, 124, 220, 127, 4, 15, 5},
        {1, 213, 138, 220, 141, 4, 18, 8},
        {2, 205, 129, 208, 136, 4, 16, 6},
        {3, 225, 129, 228, 136, 4, 17, 7},
        {0, 205, 116, 228, 122, 7, 14, 4},
        {1, 205, 143, 228, 149, 7, 19, 9}
    },
    {
        {2, 249, 165, 293, 169, 45, 11, 3},
        {2, 131, 13, 189, 17, 59, 8, 0},
        {0, -99, -99, -99, -99, 0, 0, 0},
        {1, -99, -99, -99, -99, 0, 0, 0},
        {2, 45, 172, 51, 181, 7, 12, 4},
        {3, 70, 172, 76, 181, 7, 13, 5},
        {0, 49, 164, 72, 170, 7, 10, 2},
        {1, 49, 183, 72, 189, 7, 15, 7}
    },
    {
        {0, 123, 118, 126, 148, 31, 14, 3},
        {2, 144, 100, 174, 102, 31, 12, 1},
        {0, 207, 124, 216, 127, 4, 17, 6},
        {1, 207, 140, 216, 143, 4, 20, 9},
        {2, 202, 129, 205, 138, 4, 18, 7},
        {3, 218, 129, 221, 138, 4, 19, 8},
        {0, 202, 119, 221, 122, 4, 16, 5},
        {1, 202, 145, 221, 148, 4, 21, 10}
    },
    {
        {0, 180, 124, 184, 146, 22, 6, 2},
        {2, 143, 110, 175, 112, 33, 4, 0},
        {0, -99, -99, 0, 0, 0, 0, 0},
        {0, -99, -99, 0, 0, 0, 0, 0},
        {0, -99, -99, 0, 0, 0, 0, 0},
        {0, -99, -99, 0, 0, 0, 0, 0},
        {0, 134, 124, 138, 146, 32, 7, 3},
        {0, -99, -99, 0, 0, 0, 0, 0}
    }
};

static const int16_t flight_cockpit_light_x[5][7] = {
    {101, 101, 189, 137, 265, -99, 203},
    {198, 198, 133, 145, 234, 234, -99},
    {76, 76, 139, 257, 20, 20, -99},
    {194, 194, 96, 137, 96, 96, -99},
    {-99, -99, 179, 133, -99, -99, -99}
};
static const int16_t flight_cockpit_light_y[5][7] = {
    {122, 145, 121, 7, 121, -99, 147},
    {120, 139, 114, 114, 179, 188, -99},
    {164, 183, 22, 181, 162, 178, -99},
    {119, 142, 136, 15, 126, 116, -99},
    {-99, -99, 115, 114, -99, -99, -99}
};
static const uint8_t flight_cockpit_light_off[5][7] = {
    {14, 14, 14, 11, 13, 14, 14},
    {12, 12, 12, 13, 12, 12, 12},
    {9, 9, 9, 14, 9, 9, 9},
    {15, 15, 13, 11, 13, 13, 13},
    {5, 5, 5, 5, 5, 5, 5}
};
static const uint8_t flight_cockpit_light_on[5][7] = {
    {3, 3, 3, 0, 2, 3, 3},
    {2, 2, 2, 3, 2, 2, 2},
    {1, 1, 1, 6, 1, 1, 1},
    {4, 4, 2, 0, 2, 2, 2},
    {1, 1, 1, 1, 1, 1, 1}
};

static uint16_t flight_cockpit_percent(int32_t value, int32_t maximum)
{
    int32_t percent;

    if (maximum <= 0 || value <= 0)
        return 0U;
    percent = (value * 100L) / maximum;
    if (percent > 100L)
        percent = 100L;
    return (uint16_t)percent;
}

static void resource_draw_cockpit_bar(uint16_t mode, uint16_t bar,
                                      uint16_t percent)
{
    const FlightCockpitBar *definition;
    int16_t extent;
    uint8_t filled_frame;
    uint8_t empty_frame;

    if (mode >= 5U || bar >= 8U ||
        (resource_status & RESOURCE_STATUS_COCKPIT_DAMAGE) == 0U)
        return;
    definition = &flight_cockpit_bars[mode][bar];
    if (definition->left < 0 || definition->length == 0U)
        return;
    if (percent > 100U)
        percent = 100U;
    extent = (int16_t)(((int32_t)percent * definition->length) / 100L);
    filled_frame = definition->filled_frame;
    empty_frame = definition->empty_frame;
    if (definition->direction < 2) {
        if (definition->direction == 1) {
            extent = (int16_t)(definition->length - extent);
            filled_frame = definition->empty_frame;
            empty_frame = definition->filled_frame;
        }
        if (definition->top <= definition->bottom - extent)
            draw_shape_frame_clipped(resource_cockpit_damage_data,
                                     resource_cockpit_damage_size,
                                     filled_frame, definition->left,
                                     definition->top, definition->left,
                                     definition->top,
                                     definition->right,
                                     definition->bottom - extent);
        if (definition->bottom - extent + 1 <= definition->bottom)
            draw_shape_frame_clipped(resource_cockpit_damage_data,
                                     resource_cockpit_damage_size,
                                     empty_frame, definition->left,
                                     definition->top, definition->left,
                                     definition->bottom - extent + 1,
                                     definition->right,
                                     definition->bottom);
    } else {
        if (definition->direction == 3) {
            extent = (int16_t)(definition->length - extent);
            filled_frame = definition->empty_frame;
            empty_frame = definition->filled_frame;
        }
        if (definition->left <= definition->right - extent)
            draw_shape_frame_clipped(resource_cockpit_damage_data,
                                     resource_cockpit_damage_size,
                                     filled_frame, definition->left,
                                     definition->top, definition->left,
                                     definition->top,
                                     definition->right - extent,
                                     definition->bottom);
        if (definition->right - extent + 1 <= definition->right)
            draw_shape_frame_clipped(resource_cockpit_damage_data,
                                     resource_cockpit_damage_size,
                                     empty_frame, definition->left,
                                     definition->top,
                                     definition->right - extent + 1,
                                     definition->top,
                                     definition->right,
                                     definition->bottom);
    }
}

/* Falcon equivalent of update_lights()/update_bars().  The state comes from
 * the same shield and directional-armor arrays used by inflict_damage(); the
 * only platform-specific part is that the original sparse cockpit frames are
 * drawn into the indexed surface before RGB565 presentation. */
void resource_draw_cockpit_indicators(uint16_t fuel_percent,
                                      uint16_t weapon_percent)
{
    const FlightCombatProfile *profile;
    uint16_t mode;
    uint16_t shield_fore;
    uint16_t shield_aft;
    uint16_t armor_front;
    uint16_t armor_rear;
    uint16_t armor_right;
    uint16_t armor_left;
    uint16_t light;

    if ((resource_status & (RESOURCE_STATUS_PRIMARY_COCKPIT |
                            RESOURCE_STATUS_COCKPIT_DAMAGE)) !=
        (RESOURCE_STATUS_PRIMARY_COCKPIT |
         RESOURCE_STATUS_COCKPIT_DAMAGE))
        return;
    mode = resource_cockpit_mode;
    if (mode >= 5U)
        mode = 0U;
    profile = flight_combat_profile(object_types[0]);
    if (profile == 0)
        return;
    shield_fore = flight_cockpit_percent(
        resource_flight_ship_shields[0][0], profile->shield_fore);
    shield_aft = flight_cockpit_percent(
        resource_flight_ship_shields[0][1], profile->shield_aft);
    armor_front = flight_cockpit_percent(
        resource_flight_ship_armor[0][0], profile->armor_front);
    armor_rear = flight_cockpit_percent(
        resource_flight_ship_armor[0][1], profile->armor_rear);
    armor_right = flight_cockpit_percent(
        resource_flight_ship_armor[0][2], profile->armor_left);
    armor_left = flight_cockpit_percent(
        resource_flight_ship_armor[0][3], profile->armor_right);

    resource_draw_cockpit_bar(mode, 0U, fuel_percent);
    resource_draw_cockpit_bar(mode, 1U, weapon_percent);
    resource_draw_cockpit_bar(mode, 2U, armor_front);
    resource_draw_cockpit_bar(mode, 3U, armor_rear);
    resource_draw_cockpit_bar(mode, 4U, armor_right);
    resource_draw_cockpit_bar(mode, 5U, armor_left);
    resource_draw_cockpit_bar(mode, 6U, shield_fore);
    resource_draw_cockpit_bar(mode, 7U, shield_aft);

    /* update_lights() drives the fuel and critical-shield lamps. Draw all
     * seven every frame; this is equivalent visually and avoids an extra
     * cockpit back-buffer just to erase a previous lamp frame. */
    for (light = 0U; light < 7U; light++) {
        uint8_t frame;
        uint16_t on;

        if (flight_cockpit_light_x[mode][light] < 0)
            continue;
        on = 0U;
        if (light == 6U && fuel_percent < 25U)
            on = 1U;
        if (light == 3U && (uint16_t)(shield_fore + shield_aft) < 10U)
            on = 1U;
        frame = on != 0U ? flight_cockpit_light_on[mode][light] :
            flight_cockpit_light_off[mode][light];
        draw_shape_frame(resource_cockpit_damage_data,
                         resource_cockpit_damage_size, frame,
                         flight_cockpit_light_x[mode][light],
                         flight_cockpit_light_y[mode][light]);
    }
}

/* ObjectTypeData.scale is the source EXPLOSION1 anchor scale. Keep this in a
 * compact native table because the mobile renderer already owns the shape
 * scale separately and the Falcon combat path must not reread DOS packets. */
static const uint16_t flight_ship_scales[22] = {
    1024U, 1024U, 1152U, 1152U, 1024U, 1024U, 1024U, 2048U,
    4096U, 1024U, 1024U, 1024U, 1024U, 1024U, 1536U, 2048U,
    2048U, 4096U, 4096U, 2048U, 4096U, 2048U
};

static uint32_t resource_flight_combat_random_state = 0x4d595df4UL;

static uint16_t flight_random_below_or_equal(uint16_t maximum)
{
    resource_flight_combat_random_state =
        resource_flight_combat_random_state * 1103515245UL + 12345UL;
    return (uint16_t)((resource_flight_combat_random_state >> 16) %
                      ((uint32_t)maximum + 1UL));
}

static void flight_explosion_spawn(uint16_t victim)
{
    uint16_t index;
    uint16_t type;
    const FlightCombatProfile *profile;
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;

    if (victim >= WC1_FLIGHT_OBJECT_COUNT)
        return;
    type = object_types[victim];
    profile = flight_combat_profile(type);
    if (profile == 0)
        return;
    for (index = 0U; index < WC1_FLIGHT_EXPLOSION_COUNT; index++) {
        FlightExplosion *explosion;

        explosion = &resource_flight_explosions[index];
        if (explosion->active != 0U)
            continue;
        flight_axes_from_mission_angles(object_pitch[victim],
                                        object_yaw[victim],
                                        object_roll[victim], &right, &up,
                                        &forward);
        explosion->position.x = object_x[victim];
        explosion->position.y = object_y[victim];
        explosion->position.z = object_z[victim];
        explosion->velocity.x = intro_fixed_multiply(
            forward.x, (int32_t)object_speeds[victim] << 8);
        explosion->velocity.y = intro_fixed_multiply(
            forward.y, (int32_t)object_speeds[victim] << 8);
        explosion->velocity.z = intro_fixed_multiply(
            forward.z, (int32_t)object_speeds[victim] << 8);
        explosion->type = type;
        explosion->frame = 0U;
        /* set_objects_data() immediately consumes animation entry zero. */
        explosion->animation_index = 1U;
        explosion->scale = flight_ship_scales[type];
        explosion->active = 1U;
        resource_flight_explosion_count++;
        break;
    }
    /* remove_object() makes the destroyed ship unavailable to target, draw,
     * and movement scans while the EXPLOSION1 object continues independently. */
    object_active[victim] = 0U;
}

static void flight_explosion_tick(void)
{
    uint16_t index;

    for (index = 0U; index < WC1_FLIGHT_EXPLOSION_COUNT; index++) {
        FlightExplosion *explosion;
        uint16_t command;

        explosion = &resource_flight_explosions[index];
        if (explosion->active == 0U)
            continue;
        explosion->position.x += explosion->velocity.x;
        explosion->position.y += explosion->velocity.y;
        explosion->position.z += explosion->velocity.z;
        if (explosion->animation_index >=
            INTRO_EXPLOSION1_ANIMATION_COUNT) {
            explosion->active = 0U;
            if (resource_flight_explosion_count != 0U)
                resource_flight_explosion_count--;
            continue;
        }
        command = intro_explosion1_animation[explosion->animation_index++];
        if ((command & 0xf000U) == 0xa000U) {
            explosion->active = 0U;
            if (resource_flight_explosion_count != 0U)
                resource_flight_explosion_count--;
        } else if ((command & 0x0c00U) == 0x0400U) {
            explosion->scale += (int32_t)(command & 0x003fU) *
                (explosion->scale >> 6);
        } else if ((command & 0x0c00U) == 0x0800U) {
            explosion->scale -= (int32_t)(command & 0x003fU) *
                (explosion->scale >> 6);
        } else {
            explosion->frame = command & 0x003fU;
        }
    }
}

static int flight_internal_damage(uint16_t victim, uint16_t damage,
                                  uint16_t quadrant)
{
    const FlightCombatProfile *profile;
    uint16_t events;

    profile = flight_combat_profile(object_types[victim]);
    if (profile == 0)
        return 0;
    if (profile->capital != 0U) {
        if (object_sides[victim] == 1U)
            events = damage >> 3;
        else
            events = damage / 10U;
        if (events == 0U)
            events = 1U;
        resource_flight_ship_accumulated[victim] = (uint16_t)(
            resource_flight_ship_accumulated[victim] + events);
        if (resource_flight_ship_accumulated[victim] >=
            profile->damage_capacity) {
            flight_explosion_spawn(victim);
            return 1;
        }
        return 0;
    }

    /* The current roster has no recovered pilot-rating field, so it follows
     * the exact source branch for g_acShipRating == -1: one event per six
     * post-armor damage points, with the event loop retained verbatim. */
    events = damage / 6U;
    if (events == 0U)
        events = 1U;
    resource_flight_ship_accumulated[victim] = (uint16_t)(
        resource_flight_ship_accumulated[victim] + events);
    while (events != 0U) {
        uint16_t system;

        system = flight_random_below_or_equal(9U);
        switch (system) {
        case 0U:
            events--;
            if (resource_flight_ship_pilot[victim] != 0U)
                resource_flight_ship_pilot[victim]--;
            if (resource_flight_ship_pilot[victim] == 0U) {
                flight_explosion_spawn(victim);
                return 1;
            }
            break;
        case 1U:
            if (quadrant == 1U)
                events--;
            break;
        case 2U:
            if (quadrant == 1U) {
                flight_explosion_spawn(victim);
                return 1;
            }
            break;
        case 3U:
            resource_flight_ship_shields[victim][0] = 0;
            resource_flight_ship_shields[victim][1] = 0;
            resource_flight_ship_max_shields[victim][0] = 0;
            resource_flight_ship_max_shields[victim][1] = 0;
            break;
        case 4U:
            events--;
            resource_flight_ship_damage[victim]++;
            if (resource_flight_ship_damage[victim] >
                profile->damage_capacity) {
                flight_explosion_spawn(victim);
                return 1;
            }
            break;
        case 5U:
            if (quadrant == 0U) {
                resource_flight_ship_component_damage[victim]++;
                events--;
            }
            break;
        case 6U:
            if (quadrant == 0U) {
                resource_flight_ship_component_damage[victim]++;
                events--;
            }
            break;
        case 7U:
            if (quadrant == 1U)
                events--;
            break;
        case 8U:
            if (quadrant == 0U) {
                resource_flight_ship_component_damage[victim]++;
                events--;
            }
            break;
        default:
            break;
        }
    }
    return 0;
}

void resource_flight_combat_reset(void)
{
    uint16_t index;

    resource_flight_hit_count = 0U;
    resource_flight_explosion_count = 0U;
    resource_flight_player_damage = 0U;
    resource_flight_combat_random_state = 0x4d595df4UL;
    for (index = 0U; index < WC1_FLIGHT_OBJECT_COUNT; index++) {
        uint16_t component;

        resource_flight_ship_types[index] = 0xffffU;
        resource_flight_ship_damage[index] = 0U;
        resource_flight_ship_accumulated[index] = 0U;
        resource_flight_ship_component_damage[index] = 0U;
        resource_flight_ship_pilot[index] = 4U;
        resource_flight_ship_initialized[index] = 0U;
        resource_flight_enemy_refire[index] = 0U;
        object_active[index] = 0U;
        for (component = 0U; component < 2U; component++) {
            resource_flight_ship_shields[index][component] = 0;
            resource_flight_ship_max_shields[index][component] = 0;
        }
        for (component = 0U; component < 4U; component++)
            resource_flight_ship_armor[index][component] = 0;
    }
    for (index = 0U; index < WC1_FLIGHT_EXPLOSION_COUNT; index++)
        resource_flight_explosions[index].active = 0U;
}

/* set_up_ship_info() supplies a type each time the active compact roster is
 * built.  This is the counterpart to set_objects_data() copying the DOS
 * ObjectTypeData shield and armor fields into its per-object runtime arrays. */
void resource_flight_combat_spawn(uint16_t slot, uint16_t type)
{
    const FlightCombatProfile *profile;

    if (slot >= WC1_FLIGHT_OBJECT_COUNT)
        return;
    profile = flight_combat_profile(type);
    resource_flight_ship_types[slot] = type;
    resource_flight_ship_damage[slot] = 0U;
    resource_flight_ship_accumulated[slot] = 0U;
    resource_flight_ship_component_damage[slot] = 0U;
    resource_flight_ship_pilot[slot] = 4U;
    resource_flight_ship_initialized[slot] = profile != 0 ? 1U : 0U;
    object_active[slot] = profile != 0 ? 1U : 0U;
    if (profile == 0) {
        uint16_t component;

        for (component = 0U; component < 2U; component++) {
            resource_flight_ship_shields[slot][component] = 0;
            resource_flight_ship_max_shields[slot][component] = 0;
        }
        for (component = 0U; component < 4U; component++)
            resource_flight_ship_armor[slot][component] = 0;
        return;
    }
    resource_flight_ship_shields[slot][0] = (int16_t)profile->shield_fore;
    resource_flight_ship_shields[slot][1] = (int16_t)profile->shield_aft;
    resource_flight_ship_max_shields[slot][0] =
        (int16_t)profile->shield_fore;
    resource_flight_ship_max_shields[slot][1] =
        (int16_t)profile->shield_aft;
    resource_flight_ship_armor[slot][0] = (int16_t)profile->armor_front;
    resource_flight_ship_armor[slot][1] = (int16_t)profile->armor_rear;
    resource_flight_ship_armor[slot][2] = (int16_t)profile->armor_left;
    resource_flight_ship_armor[slot][3] = (int16_t)profile->armor_right;
}

static uint16_t flight_projectile_damage(uint16_t type)
{
    switch (type) {
    case 24U:
        return 25U;
    case 25U:
        return 40U;
    case 26U:
        return 30U;
    default:
        return 0U;
    }
}

static void flight_projectile_to_spark(FlightProjectile *projectile,
                                       uint16_t partner)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;

    flight_axes_from_mission_angles(object_pitch[partner],
                                    object_yaw[partner],
                                    object_roll[partner], &right, &up,
                                    &forward);
    projectile->velocity.x = intro_fixed_multiply(
        forward.x, (int32_t)object_speeds[partner] << 8);
    projectile->velocity.y = intro_fixed_multiply(
        forward.y, (int32_t)object_speeds[partner] << 8);
    projectile->velocity.z = intro_fixed_multiply(
        forward.z, (int32_t)object_speeds[partner] << 8);
    projectile->ticks = 6U;
    projectile->frame = 0U;
    projectile->spark = 1U;
    projectile->fresh = 1U;
    if (resource_flight_projectile_count != 0U)
        resource_flight_projectile_count--;
    resource_flight_spark_count++;
}

static const uint8_t flight_player_damage_table[50] = {
    0U, 8U, 6U, 5U, 0U, 3U, 5U, 5U, 7U, 6U,
    0U, 8U, 6U, 5U, 4U, 3U, 4U, 0U, 4U, 4U,
    1U, 2U, 5U, 2U, 7U, 3U, 4U, 7U, 5U, 1U,
    1U, 4U, 1U, 5U, 2U, 3U, 4U, 7U, 2U, 1U,
    4U, 4U, 4U, 4U, 0U, 8U, 6U, 5U, 4U, 0U
};

/* your_internal_damage() retains the source table groups and retry rules.
 * The Falcon HUD/component runtime is not yet a separate object, so each
 * event is published as player damage while the native shield/armor and
 * accumulated-damage arrays retain the state needed by later cockpit work. */
static void flight_player_internal_damage(uint16_t damage, uint16_t quadrant)
{
    uint16_t events;
    uint16_t table_group;
    uint16_t severity;
    uint16_t guard;

    table_group = quadrant == 1U ? 2U : 0U;
    events = damage >> 4;
    if (events == 0U)
        events = 1U;
    severity = flight_random_below_or_equal(10U);
    resource_flight_ship_accumulated[0] = (uint16_t)(
        resource_flight_ship_accumulated[0] + events);
    guard = 0U;
    while (events != 0U && guard < 128U) {
        uint16_t system;

        guard++;
        events--;
        resource_flight_player_damage++;
        system = flight_player_damage_table[table_group * 10U +
                                            flight_random_below_or_equal(9U)];
        switch (system) {
        case 0U:
            if (severity >= 4U) {
                resource_flight_ship_component_damage[0]++;
                if (severity >= 7U)
                    resource_flight_ship_damage[0]++;
            }
            break;
        case 1U:
            if (quadrant == 1U)
                resource_flight_ship_component_damage[0]++;
            else
                events++;
            break;
        case 2U:
            if (quadrant == 1U) {
                resource_flight_ship_component_damage[0]++;
                if (flight_random_below_or_equal(3U) == 0U)
                    resource_flight_ship_damage[0]++;
            } else
                events++;
            break;
        case 3U:
            if (severity > 8U) {
                resource_flight_ship_component_damage[0]++;
                resource_flight_ship_damage[0]++;
            } else {
                resource_flight_ship_component_damage[0]++;
                resource_flight_ship_max_shields[0][0] =
                    resource_flight_ship_max_shields[0][0] > 10 ?
                    (int16_t)(resource_flight_ship_max_shields[0][0] - 10) : 0;
                resource_flight_ship_max_shields[0][1] =
                    resource_flight_ship_max_shields[0][1] > 10 ?
                    (int16_t)(resource_flight_ship_max_shields[0][1] - 10) : 0;
            }
            break;
        case 4U:
            resource_flight_ship_damage[0]++;
            if (resource_flight_ship_damage[0] == 1U)
                resource_flight_player_damage++;
            break;
        case 5U:
            if (quadrant != 0U)
                events++;
            else
                resource_flight_ship_component_damage[0]++;
            break;
        case 6U:
            if (quadrant != 0U)
                events++;
            else
                resource_flight_ship_component_damage[0]++;
            break;
        case 7U:
            if (flight_random_below_or_equal(1U) != 0U)
                resource_flight_ship_damage[0]++;
            break;
        case 8U:
            if (quadrant != 0U)
                events++;
            else
                resource_flight_ship_component_damage[0]++;
            break;
        default:
            break;
        }
    }
}

/* inflict_damage(): source hit direction, fore/aft shields, then
 * front/rear/side armor. Post-armor damage enters the source-style NPC
 * internal event loop; the player-specific branch and capital shock-wave
 * side effects remain separate. */
static int flight_inflict_damage(uint16_t victim,
                                 const FlightProjectile *projectile,
                                 uint16_t damage)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    IntroFixedVector target_velocity;
    IntroFixedVector impact;
    int16_t shield;
    int16_t armor;
    int32_t side_dot;

    if (victim == 0U) {
        flight_axes_from_mission_angles(object_pitch[victim],
                                        object_yaw[victim],
                                        object_roll[victim], &right, &up,
                                        &forward);
        target_velocity.x = intro_fixed_multiply(
            forward.x, (int32_t)object_speeds[victim] << 8);
        target_velocity.y = intro_fixed_multiply(
            forward.y, (int32_t)object_speeds[victim] << 8);
        target_velocity.z = intro_fixed_multiply(
            forward.z, (int32_t)object_speeds[victim] << 8);
        impact.x = target_velocity.x - projectile->velocity.x;
        impact.y = target_velocity.y - projectile->velocity.y;
        impact.z = target_velocity.z - projectile->velocity.z;
        if (intro_vector_magnitude(&impact) == 0)
            return 0;
        intro_normalize_long_vector(&impact);
        shield = intro_dot_product(&impact, &forward) > 0 ? 1 : 0;
        damage = (uint16_t)((int32_t)damage -
                            resource_flight_ship_shields[victim][shield]);
        if ((int16_t)damage <= 0) {
            resource_flight_ship_shields[victim][shield] = (int16_t)-damage;
            return 0;
        }
        resource_flight_ship_shields[victim][shield] = 0;
        armor = shield;
        side_dot = intro_dot_product(&impact, &right);
        if (side_dot > 0xb5)
            armor = 3;
        else if (side_dot < -0xb5)
            armor = 2;
        damage = (uint16_t)((int32_t)damage -
                            resource_flight_ship_armor[victim][armor]);
        if ((int16_t)damage <= 0) {
            resource_flight_ship_armor[victim][armor] = (int16_t)-damage;
            return 0;
        }
        resource_flight_ship_armor[victim][armor] = 0;
        flight_player_internal_damage(damage, (uint16_t)armor);
        return 0;
    }

    flight_axes_from_mission_angles(object_pitch[victim], object_yaw[victim],
                                    object_roll[victim], &right, &up,
                                    &forward);
    target_velocity.x = intro_fixed_multiply(
        forward.x, (int32_t)object_speeds[victim] << 8);
    target_velocity.y = intro_fixed_multiply(
        forward.y, (int32_t)object_speeds[victim] << 8);
    target_velocity.z = intro_fixed_multiply(
        forward.z, (int32_t)object_speeds[victim] << 8);
    impact.x = target_velocity.x - projectile->velocity.x;
    impact.y = target_velocity.y - projectile->velocity.y;
    impact.z = target_velocity.z - projectile->velocity.z;
    if (intro_vector_magnitude(&impact) == 0)
        return 0;
    intro_normalize_vector(&impact);
    shield = intro_dot_product(&impact, &forward) > 0 ? 1 : 0;
    damage = (uint16_t)((int32_t)damage -
                        resource_flight_ship_shields[victim][shield]);
    if ((int16_t)damage <= 0) {
        resource_flight_ship_shields[victim][shield] = (int16_t)-damage;
        return 0;
    }
    resource_flight_ship_shields[victim][shield] = 0;
    armor = shield;
    side_dot = intro_dot_product(&impact, &right);
    if (side_dot > 0xb5)
        armor = 3;
    else if (side_dot < -0xb5)
        armor = 2;
    damage = (uint16_t)((int32_t)damage -
                        resource_flight_ship_armor[victim][armor]);
    if ((int16_t)damage <= 0) {
        resource_flight_ship_armor[victim][armor] = (int16_t)-damage;
        return 0;
    }
    resource_flight_ship_armor[victim][armor] = 0;
    return flight_internal_damage(victim, damage, (uint16_t)armor);
}

/* object_collision() checks every active dynamic object before its movement.
 * Owner zero is the player; an enemy-owned bolt is allowed to collide with
 * that player only. Same-side contacts are excluded like the DOS object-side
 * test before check_for_collision(). */
void resource_flight_combat_tick(void)
{
    uint16_t projectile_index;
    uint16_t active_count;

    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    for (projectile_index = 0U;
         projectile_index < WC1_FLIGHT_PROJECTILE_COUNT;
         projectile_index++) {
        FlightProjectile *projectile;
        const uint8_t *shape;
        uint32_t shape_size;
        uint16_t projectile_radius;
        uint16_t scale;
        uint16_t lifetime;
        uint16_t velocity;
        uint16_t partner;

        projectile = &resource_flight_projectiles[projectile_index];
        if (projectile->active == 0U || projectile->spark != 0U ||
            !flight_projectile_profile(projectile->type, &shape, &shape_size,
                                       &projectile_radius, &scale, &lifetime,
                                       &velocity))
            continue;
        (void)shape;
        (void)shape_size;
        (void)scale;
        (void)lifetime;
        (void)velocity;
        for (partner = 0U; partner < active_count; partner++) {
            const FlightCombatProfile *profile;
            IntroFixedVector delta;
            int32_t range;
            uint16_t damage;

            if (object_active[partner] == 0U ||
                resource_flight_ship_initialized[partner] == 0U ||
                resource_flight_ship_types[partner] != object_types[partner])
                continue;
            if (partner == projectile->owner)
                continue;
            if (projectile->owner != 0U && partner != 0U)
                continue;
            if (projectile->owner != 0U &&
                projectile->owner < active_count &&
                object_sides[projectile->owner] == object_sides[partner])
                continue;
            profile = flight_combat_profile(object_types[partner]);
            if (profile == 0)
                continue;
            delta.x = projectile->position.x - object_x[partner];
            delta.y = projectile->position.y - object_y[partner];
            delta.z = projectile->position.z - object_z[partner];
            range = ((int32_t)projectile_radius + profile->collision_radius)
                << 8;
            if (intro_vector_magnitude(&delta) > range)
                continue;
            damage = (uint16_t)(flight_projectile_damage(projectile->type) -
                                projectile->ticks / 2U);
            (void)flight_inflict_damage(partner, projectile, damage);
            flight_projectile_to_spark(projectile, partner);
            resource_flight_hit_count++;
            break;
        }
    }
}

/* house_keep_objects() replenishes a shield after movement.  This call is
 * kept separate from the collision pass so game.s can retain that original
 * ordering even while AI and the broader dynamic-object pool are pending. */
void resource_flight_combat_housekeep(void)
{
    uint16_t slot;
    uint16_t active_count;

    flight_explosion_tick();
    resource_flight_combat_frame++;
    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    for (slot = 0U; slot < active_count; slot++) {
        const FlightCombatProfile *profile;
        uint16_t shield;

        if (resource_flight_ship_initialized[slot] == 0U ||
            resource_flight_ship_types[slot] != object_types[slot])
            continue;
        profile = flight_combat_profile(object_types[slot]);
        if (profile == 0 || profile->shield_delay == 0U ||
            resource_flight_combat_frame % profile->shield_delay != 0U)
            continue;
        for (shield = 0U; shield < 2U; shield++) {
            if (resource_flight_ship_shields[slot][shield] <
                resource_flight_ship_max_shields[slot][shield])
                resource_flight_ship_shields[slot][shield]++;
        }
    }
}

void resource_flight_weapons_reset(void)
{
    uint16_t index;

    resource_flight_gun_refire = -1;
    resource_flight_projectile_count = 0U;
    resource_flight_spark_count = 0U;
    for (index = 0U; index < WC1_FLIGHT_PROJECTILE_COUNT; index++) {
        FlightProjectile *projectile;

        projectile = &resource_flight_projectiles[index];
        projectile->position.x = 0;
        projectile->position.y = 0;
        projectile->position.z = 0;
        projectile->velocity.x = 0;
        projectile->velocity.y = 0;
        projectile->velocity.z = 0;
        projectile->owner = 0U;
        projectile->type = 0U;
        projectile->ticks = 0U;
        projectile->frame = 0U;
        projectile->spark = 0U;
        projectile->fresh = 0U;
        projectile->active = 0U;
    }
}

/* house_keep_objects() counts projectile life down independently of the
 * player counter.  This bounded equivalent runs once per Falcon game tick
 * before a new input event is considered. */
void resource_flight_weapons_tick(void)
{
    uint16_t index;

    if (resource_flight_gun_refire >= 0)
        resource_flight_gun_refire--;
    for (index = 1U; index < WC1_FLIGHT_OBJECT_COUNT; index++) {
        if (resource_flight_enemy_refire[index] != 0U)
            resource_flight_enemy_refire[index]--;
    }
    for (index = 0U; index < WC1_FLIGHT_PROJECTILE_COUNT; index++) {
        FlightProjectile *projectile;

        projectile = &resource_flight_projectiles[index];
        if (projectile->active == 0U)
            continue;
        projectile->position.x += projectile->velocity.x;
        projectile->position.y += projectile->velocity.y;
        projectile->position.z += projectile->velocity.z;
        if (projectile->spark != 0U) {
            if (projectile->fresh != 0U) {
                projectile->fresh = 0U;
                continue;
            }
            if (projectile->ticks != 0U)
                projectile->ticks--;
            if (projectile->ticks == 0U) {
                projectile->active = 0U;
                projectile->spark = 0U;
                if (resource_flight_spark_count != 0U)
                    resource_flight_spark_count--;
            } else {
                projectile->frame++;
            }
            continue;
        }
        if (projectile->ticks != 0U)
            projectile->ticks--;
        if (projectile->ticks == 0U) {
            projectile->active = 0U;
            if (resource_flight_projectile_count != 0U)
                resource_flight_projectile_count--;
        }
    }
}

/* fire_weapon() first copies the parent frame, positions the projectile at
 * its hardpoint, then adds the forward component of the parent velocity and
 * the projectile's maximum velocity.  Keeping this operation owner-aware
 * lets the same source expression serve the player and fighter AI. */
static int flight_spawn_projectile(uint16_t owner, int32_t ship_x,
                                   int32_t ship_y, int32_t ship_z,
                                   int16_t ship_pitch, int16_t ship_yaw,
                                   int16_t ship_roll, int16_t ship_speed,
                                   const FlightWeaponSlot *slot)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    const FlightHardpoint *hardpoint;
    const uint8_t *shape;
    uint32_t shape_size;
    uint16_t collision_radius;
    uint16_t scale;
    uint16_t lifetime;
    uint16_t velocity;
    uint16_t index;

    if (!flight_projectile_profile(slot->type, &shape, &shape_size,
                                   &collision_radius, &scale, &lifetime,
                                   &velocity))
        return 0;
    (void)shape;
    (void)shape_size;
    (void)collision_radius;
    (void)scale;
    if (slot->hardpoint < 0 || slot->hardpoint >= 56)
        return 0;
    for (index = 0U; index < WC1_FLIGHT_PROJECTILE_COUNT; index++) {
        if (resource_flight_projectiles[index].active == 0U)
            break;
    }
    if (index == WC1_FLIGHT_PROJECTILE_COUNT)
        return 0;
    flight_axes_from_mission_angles(ship_pitch, ship_yaw, ship_roll,
                                    &right, &up, &forward);
    hardpoint = &flight_hardpoints[(uint16_t)slot->hardpoint];
    resource_flight_projectiles[index].position.x = ship_x +
        forward.x * hardpoint->z + up.x * hardpoint->y +
        right.x * hardpoint->x;
    resource_flight_projectiles[index].position.y = ship_y +
        forward.y * hardpoint->z + up.y * hardpoint->y +
        right.y * hardpoint->x;
    resource_flight_projectiles[index].position.z = ship_z +
        forward.z * hardpoint->z + up.z * hardpoint->y +
        right.z * hardpoint->x;
    resource_flight_projectiles[index].velocity.x = intro_fixed_multiply(
        forward.x, ((int32_t)ship_speed + velocity) << 8);
    resource_flight_projectiles[index].velocity.y = intro_fixed_multiply(
        forward.y, ((int32_t)ship_speed + velocity) << 8);
    resource_flight_projectiles[index].velocity.z = intro_fixed_multiply(
        forward.z, ((int32_t)ship_speed + velocity) << 8);
    resource_flight_projectiles[index].owner = owner;
    resource_flight_projectiles[index].type = slot->type;
    resource_flight_projectiles[index].ticks = lifetime;
    resource_flight_projectiles[index].frame = 0U;
    resource_flight_projectiles[index].spark = 0U;
    resource_flight_projectiles[index].fresh = 0U;
    resource_flight_projectiles[index].active = 1U;
    resource_flight_projectile_count++;
    return 1;
}

/* fire_fixed_projectile_weapon() fires every enabled player cannon in one
 * source salvo. Return the number of actual dynamic objects, allowing the
 * assembly input path to count skipped mounts correctly. */
int resource_flight_fire(int32_t player_x, int32_t player_y,
                         int32_t player_z, int16_t player_pitch,
                         int16_t player_yaw, int16_t player_roll,
                         int16_t player_speed, uint16_t player_type)
{
    const FlightWeaponSlot *slots;
    uint16_t slot_count;
    uint16_t weapon;
    uint16_t fired;
    int16_t final_delay;

    if ((resource_status & RESOURCE_STATUS_FLIGHT_WEAPONS) == 0U ||
        resource_flight_gun_refire != -1 ||
        !flight_ship_loadout(player_type, &slots, &slot_count))
        return 0;
    fired = 0U;
    final_delay = -1;
    for (weapon = 0U; weapon < slot_count; weapon++) {
        if (flight_spawn_projectile(0U, player_x, player_y, player_z,
                                    player_pitch, player_yaw, player_roll,
                                    player_speed, &slots[weapon])) {
            final_delay = flight_projectile_refire_delay(slots[weapon].type);
            fired++;
        }
    }
    if (final_delay >= 0)
        resource_flight_gun_refire = final_delay;
    return (int)fired;
}

/* fire() is the source fighter-AI gate: the target must be in the cannon's
 * lifetime/range envelope and inside the ship's forward cone.  The DOS code
 * then fires the fixed projectile mounts in their original order.  Its
 * maneuvering/behaviour dispatcher is still outside this compact roster, so
 * this preserves the weapon decision and leaves steering to objects.s. */
void resource_flight_enemy_tick(void)
{
    uint16_t owner;
    uint16_t active_count;

    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    for (owner = 1U; owner < active_count; owner++) {
        const FlightWeaponSlot *slots;
        uint16_t slot_count;
        IntroFixedVector right;
        IntroFixedVector up;
        IntroFixedVector forward;
        IntroFixedVector direction;
        int32_t range;
        int32_t facing;
        int fired;
        uint16_t weapon;

        if (object_active[owner] == 0U ||
            resource_flight_ship_initialized[owner] == 0U ||
            resource_flight_ship_types[owner] != object_types[owner] ||
            object_sides[owner] == object_sides[0] ||
            resource_flight_enemy_refire[owner] != 0U ||
            !flight_ship_loadout(object_types[owner], &slots, &slot_count))
            continue;
        direction.x = object_x[0] - object_x[owner];
        direction.y = object_y[0] - object_y[owner];
        direction.z = object_z[0] - object_z[owner];
        range = intro_vector_magnitude(&direction);
        if (range == 0 || range >= (7000L << 8) ||
            !intro_normalize_long_vector(&direction))
            continue;
        flight_axes_from_mission_angles(object_pitch[owner],
                                        object_yaw[owner], object_roll[owner],
                                        &right, &up, &forward);
        facing = intro_dot_product(&forward, &direction) * 100 / 256;
        fired = 0;
        for (weapon = 0U; weapon < slot_count; weapon++) {
            const uint8_t *shape;
            uint32_t shape_size;
            uint16_t collision_radius;
            uint16_t scale;
            uint16_t lifetime;
            uint16_t velocity;
            int32_t reach;
            int32_t threshold;

            if (!flight_projectile_profile(slots[weapon].type, &shape,
                                           &shape_size, &collision_radius,
                                           &scale, &lifetime, &velocity))
                continue;
            (void)shape;
            (void)shape_size;
            (void)collision_radius;
            (void)scale;
            reach = (int32_t)lifetime * velocity;
            threshold = slots[weapon].type == 24U ? 70 :
                (slots[weapon].type == 25U ? 80 : 85);
            if ((range >> 8) >= reach || facing <= threshold)
                continue;
            if (flight_spawn_projectile(owner, object_x[owner],
                                        object_y[owner], object_z[owner],
                                        object_pitch[owner], object_yaw[owner],
                                        object_roll[owner], object_speeds[owner],
                                        &slots[weapon]))
                fired = 1;
        }
        if (fired != 0)
            resource_flight_enemy_refire[owner] = 6U;
    }
}

/* point_ship_at_object() subset for the compact hostile-fighter roster. The
 * source dispatcher stores yaw/pitch goals and advances them according to a
 * pilot manoeuvre; this Falcon slice keeps the same local-frame target
 * calculation and applies a conservative six-degree turn step each update.
 * Capital ships retain their source straight/orbit path until their packet
 * and turret manager is ported. */
void resource_flight_ai_tick(void)
{
    uint16_t owner;
    uint16_t active_count;

    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    for (owner = 1U; owner < active_count; owner++) {
        const FlightCombatProfile *profile;
        IntroFixedVector right;
        IntroFixedVector up;
        IntroFixedVector forward;
        IntroFixedVector direction;
        IntroFixedVector local;
        int16_t target_yaw;
        int16_t target_pitch;
        int16_t step;

        profile = flight_combat_profile(object_types[owner]);
        if (object_active[owner] == 0U || profile == 0 ||
            profile->capital != 0U || object_types[owner] < 9U ||
            object_types[owner] > 13U ||
            object_sides[owner] == object_sides[0])
            continue;
        direction.x = object_x[0] - object_x[owner];
        direction.y = object_y[0] - object_y[owner];
        direction.z = object_z[0] - object_z[owner];
        if (!intro_normalize_long_vector(&direction))
            continue;
        flight_axes_from_mission_angles(object_pitch[owner],
                                        object_yaw[owner], object_roll[owner],
                                        &right, &up, &forward);
        local.x = intro_dot_product(&direction, &right);
        local.y = intro_dot_product(&direction, &up);
        local.z = intro_dot_product(&direction, &forward);
        if (!intro_rectangular_to_spherical(&local, &target_yaw,
                                            &target_pitch))
            continue;
        step = target_yaw;
        if (step > 6)
            step = 6;
        else if (step < -6)
            step = -6;
        object_pitch[owner] = (int16_t)(object_pitch[owner] + step);
        step = target_pitch;
        if (step > 6)
            step = 6;
        else if (step < -6)
            step = -6;
        object_yaw[owner] = (int16_t)(object_yaw[owner] - step);
    }
}

/* Draw the active dynamic projectile subset in the same eye frame and
 * far-to-near order as the mobile-fighter pass.  It remains separate from the
 * mission roster because the next slice must merge all dynamic effects and
 * ship objects into the full 3Space object sorter. */
void resource_draw_flight_projectiles(int32_t camera_x, int32_t camera_y,
                                      int32_t camera_z, int16_t camera_pitch,
                                      int16_t camera_yaw, int16_t camera_roll)
{
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    uint16_t order[WC1_FLIGHT_PROJECTILE_COUNT];
    int32_t distance[WC1_FLIGHT_PROJECTILE_COUNT];
    uint16_t count;
    uint16_t index;

    if ((resource_status & RESOURCE_STATUS_FLIGHT_WEAPONS) == 0U)
        return;
    flight_axes_from_mission_angles(camera_pitch, camera_yaw, camera_roll,
                                    &camera_right, &camera_up,
                                    &camera_forward);
    count = 0U;
    for (index = 0U; index < WC1_FLIGHT_PROJECTILE_COUNT; index++) {
        const FlightProjectile *projectile;
        const uint8_t *shape;
        uint32_t shape_size;
        uint16_t collision_radius;
        uint16_t scale;
        uint16_t lifetime;
        uint16_t velocity;
        IntroFixedVector direction;

        projectile = &resource_flight_projectiles[index];
        if (projectile->active == 0U ||
            !flight_projectile_profile(projectile->type, &shape, &shape_size,
                                       &collision_radius, &scale, &lifetime,
                                       &velocity))
            continue;
        if (projectile->spark != 0U && resource_flight_hit_spark_size == 0U)
            continue;
        (void)shape;
        (void)shape_size;
        (void)collision_radius;
        (void)scale;
        (void)lifetime;
        (void)velocity;
        direction.x = projectile->position.x - camera_x;
        direction.y = projectile->position.y - camera_y;
        direction.z = projectile->position.z - camera_z;
        order[count] = index;
        distance[count] = intro_vector_magnitude(&direction);
        count++;
    }
    for (index = 0U; index < count; index++) {
        uint16_t inner;

        for (inner = (uint16_t)(index + 1U); inner < count; inner++) {
            if (distance[index] < distance[inner]) {
                uint16_t order_swap;
                int32_t distance_swap;

                order_swap = order[index];
                order[index] = order[inner];
                order[inner] = order_swap;
                distance_swap = distance[index];
                distance[index] = distance[inner];
                distance[inner] = distance_swap;
            }
        }
    }
    for (index = 0U; index < count; index++) {
        const FlightProjectile *projectile;
        const uint8_t *shape;
        uint32_t shape_size;
        uint16_t collision_radius;
        uint16_t object_scale;
        uint16_t lifetime;
        uint16_t velocity;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t object_radius;
        int32_t scale_factor;
        int32_t scale;
        int32_t screen_x;
        int32_t screen_y;

        projectile = &resource_flight_projectiles[order[index]];
        if (!flight_projectile_profile(projectile->type, &shape, &shape_size,
                                       &collision_radius, &object_scale,
                                       &lifetime, &velocity))
            continue;
        if (projectile->spark != 0U) {
            shape = resource_flight_hit_spark_data;
            shape_size = resource_flight_hit_spark_size;
            collision_radius = 0U;
            object_scale = (uint16_t)(object_scale * 2U);
            if (shape_size == 0U)
                continue;
        }
        (void)lifetime;
        (void)velocity;
        direction.x = projectile->position.x - camera_x;
        direction.y = projectile->position.y - camera_y;
        direction.z = projectile->position.z - camera_z;
        view_position.x = intro_dot_product(&direction, &camera_right);
        view_position.y = intro_dot_product(&direction, &camera_up);
        view_position.z = intro_dot_product(&direction, &camera_forward);
        object_radius = (int32_t)collision_radius << 8;
        if (distance[index] <= object_radius ||
            view_position.z <= object_radius ||
            intro_fixed_divide(view_position.z, distance[index]) < 0x94)
            continue;
        scale_factor = intro_fixed_divide((int32_t)FALCON_FRAME_WIDTH << 15,
                                          distance[index] - object_radius);
        scale = intro_fixed_multiply((int32_t)object_scale, scale_factor) >> 8;
        if (scale < 5)
            continue;
        if (scale > 0x2000)
            scale = 0x2000;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        (void)draw_shape_frame_scaled(shape, shape_size,
                                      projectile->spark != 0U ?
                                          projectile->frame : 0U,
                                      screen_x, screen_y, (uint16_t)scale);
    }
}

/* ShipExplosion() creates an independent EXPLOSION1 object.  Keep its six
 * source frames in front of the active roster but behind the cockpit, using
 * the same eye-space projection and 8.8 scaling as cannon objects. */
void resource_draw_flight_explosions(int32_t camera_x, int32_t camera_y,
                                     int32_t camera_z, int16_t camera_pitch,
                                     int16_t camera_yaw, int16_t camera_roll)
{
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    uint16_t index;

    if (resource_title_explosion_size == 0U)
        return;
    flight_axes_from_mission_angles(camera_pitch, camera_yaw, camera_roll,
                                    &camera_right, &camera_up,
                                    &camera_forward);
    for (index = 0U; index < WC1_FLIGHT_EXPLOSION_COUNT; index++) {
        FlightExplosion *explosion;
        const FlightCombatProfile *profile;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t object_radius;
        int32_t scale_factor;
        int32_t scale;
        int32_t screen_x;
        int32_t screen_y;

        explosion = &resource_flight_explosions[index];
        if (explosion->active == 0U)
            continue;
        profile = flight_combat_profile(explosion->type);
        if (profile == 0)
            continue;
        direction.x = explosion->position.x - camera_x;
        direction.y = explosion->position.y - camera_y;
        direction.z = explosion->position.z - camera_z;
        distance = intro_vector_magnitude(&direction);
        object_radius = (int32_t)profile->collision_radius << 8;
        if (distance <= object_radius)
            continue;
        view_position.x = intro_dot_product(&direction, &camera_right);
        view_position.y = intro_dot_product(&direction, &camera_up);
        view_position.z = intro_dot_product(&direction, &camera_forward);
        if (view_position.z <= object_radius ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        scale_factor = intro_fixed_divide((int32_t)FALCON_FRAME_WIDTH << 15,
                                          distance - object_radius);
        scale = intro_fixed_multiply(explosion->scale, scale_factor) >> 8;
        if (scale < 5)
            continue;
        if (scale > 0x2000)
            scale = 0x2000;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        (void)draw_shape_frame_scaled(resource_title_explosion_data,
                                      resource_title_explosion_size,
                                      explosion->frame, screen_x, screen_y,
                                      (uint16_t)scale);
    }
}

/* DOS: 1990 canonical entry/range TBD (Draw_3Space_Frame candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition.
 * Draw one retained PLANETS.VGA object after the scene merger has selected
 * its position.  This is deliberately the same project/frame calculation as
 * resource_draw_flight_background(), but it does not impose a background
 * layer over nearer objects. */
static int flight_scene_draw_background(uint16_t index,
                                        const IntroFixedVector *camera_right,
                                        const IntroFixedVector *camera_up,
                                        const IntroFixedVector *camera_forward,
                                        int32_t camera_x, int32_t camera_y,
                                        int32_t camera_z)
{
    FlightBackgroundObject *object;
    int32_t distance;
    int32_t screen_x;
    int32_t screen_y;
    uint16_t frame;

    object = &resource_flight_background[index];
    if (!flight_background_project(object, camera_right, camera_up,
                                   camera_forward, camera_x, camera_y,
                                   camera_z, &distance, &screen_x,
                                   &screen_y)) {
        object->offscreen = 1U;
        return 0;
    }
    object->offscreen = 0U;
    if (object->star != 0U) {
        frame = object->frame;
    } else {
        int32_t dust_size;

        dust_size = intro_fixed_multiply(
            0x900, intro_fixed_divide(WC1_FLIGHT_EYE_RADIUS << 8,
                                      distance)) >> 8;
        if (dust_size < 0)
            dust_size = 0;
        if (dust_size > 3)
            dust_size = 3;
        frame = (uint16_t)((resource_flight_background_frame & 3U) +
                           (object->screen_angle & 0x10U) +
                           (uint16_t)(3 - dust_size) * 4U);
    }
    return draw_shape_frame(resource_constellation_data,
                            resource_constellation_size, frame, screen_x,
                            screen_y);
}

/* DOS: 1990 canonical entry/range TBD (Draw_3Space_Frame candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition. */
static int flight_scene_projectile_distance(uint16_t index, int32_t camera_x,
                                            int32_t camera_y,
                                            int32_t camera_z,
                                            int32_t *distance)
{
    const FlightProjectile *projectile;
    const uint8_t *shape;
    uint32_t shape_size;
    uint16_t collision_radius;
    uint16_t scale;
    uint16_t lifetime;
    uint16_t velocity;
    IntroFixedVector direction;

    projectile = &resource_flight_projectiles[index];
    if (projectile->active == 0U ||
        !flight_projectile_profile(projectile->type, &shape, &shape_size,
                                   &collision_radius, &scale, &lifetime,
                                   &velocity) ||
        (projectile->spark != 0U && resource_flight_hit_spark_size == 0U))
        return 0;
    (void)shape;
    (void)shape_size;
    (void)collision_radius;
    (void)scale;
    (void)lifetime;
    (void)velocity;
    direction.x = projectile->position.x - camera_x;
    direction.y = projectile->position.y - camera_y;
    direction.z = projectile->position.z - camera_z;
    *distance = intro_vector_magnitude(&direction);
    return 1;
}

/* DOS: 1990 canonical entry/range TBD (Draw_3Space_Frame candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition. */
static void flight_scene_draw_projectile(uint16_t index,
                                         const IntroFixedVector *camera_right,
                                         const IntroFixedVector *camera_up,
                                         const IntroFixedVector *camera_forward,
                                         int32_t camera_x, int32_t camera_y,
                                         int32_t camera_z)
{
    const FlightProjectile *projectile;
    const uint8_t *shape;
    uint32_t shape_size;
    uint16_t collision_radius;
    uint16_t object_scale;
    uint16_t lifetime;
    uint16_t velocity;
    IntroFixedVector direction;
    IntroFixedVector view_position;
    int32_t distance;
    int32_t object_radius;
    int32_t scale_factor;
    int32_t scale;
    int32_t screen_x;
    int32_t screen_y;

    projectile = &resource_flight_projectiles[index];
    if (!flight_scene_projectile_distance(index, camera_x, camera_y,
                                          camera_z, &distance) ||
        !flight_projectile_profile(projectile->type, &shape, &shape_size,
                                   &collision_radius, &object_scale,
                                   &lifetime, &velocity))
        return;
    if (projectile->spark != 0U) {
        shape = resource_flight_hit_spark_data;
        shape_size = resource_flight_hit_spark_size;
        collision_radius = 0U;
        object_scale = (uint16_t)(object_scale * 2U);
        if (shape_size == 0U)
            return;
    }
    (void)lifetime;
    (void)velocity;
    direction.x = projectile->position.x - camera_x;
    direction.y = projectile->position.y - camera_y;
    direction.z = projectile->position.z - camera_z;
    view_position.x = intro_dot_product(&direction, camera_right);
    view_position.y = intro_dot_product(&direction, camera_up);
    view_position.z = intro_dot_product(&direction, camera_forward);
    object_radius = (int32_t)collision_radius << 8;
    if (distance <= object_radius || view_position.z <= object_radius ||
        intro_fixed_divide(view_position.z, distance) < 0x94)
        return;
    scale_factor = intro_fixed_divide((int32_t)FALCON_FRAME_WIDTH << 15,
                                      distance - object_radius);
    scale = intro_fixed_multiply((int32_t)object_scale, scale_factor) >> 8;
    if (scale < 5)
        return;
    if (scale > 0x2000)
        scale = 0x2000;
    screen_x = (FALCON_FRAME_WIDTH >> 1) +
        view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    screen_y = (FALCON_FRAME_HEIGHT >> 1) +
        view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    (void)draw_shape_frame_scaled(shape, shape_size,
                                  projectile->spark != 0U ?
                                      projectile->frame : 0U,
                                  screen_x, screen_y, (uint16_t)scale);
}

/* DOS: 1990 canonical entry/range TBD (Draw_3Space_Frame candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition. */
static int flight_scene_explosion_distance(uint16_t index, int32_t camera_x,
                                           int32_t camera_y,
                                           int32_t camera_z,
                                           int32_t *distance)
{
    const FlightExplosion *explosion;
    const FlightCombatProfile *profile;
    IntroFixedVector direction;

    explosion = &resource_flight_explosions[index];
    if (explosion->active == 0U ||
        (profile = flight_combat_profile(explosion->type)) == 0)
        return 0;
    (void)profile;
    direction.x = explosion->position.x - camera_x;
    direction.y = explosion->position.y - camera_y;
    direction.z = explosion->position.z - camera_z;
    *distance = intro_vector_magnitude(&direction);
    return 1;
}

/* DOS: 1990 canonical entry/range TBD (Draw_3Space_Frame candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition. */
static void flight_scene_draw_explosion(uint16_t index,
                                        const IntroFixedVector *camera_right,
                                        const IntroFixedVector *camera_up,
                                        const IntroFixedVector *camera_forward,
                                        int32_t camera_x, int32_t camera_y,
                                        int32_t camera_z)
{
    const FlightExplosion *explosion;
    const FlightCombatProfile *profile;
    IntroFixedVector direction;
    IntroFixedVector view_position;
    int32_t distance;
    int32_t object_radius;
    int32_t scale_factor;
    int32_t scale;
    int32_t screen_x;
    int32_t screen_y;

    explosion = &resource_flight_explosions[index];
    if (!flight_scene_explosion_distance(index, camera_x, camera_y,
                                         camera_z, &distance) ||
        (profile = flight_combat_profile(explosion->type)) == 0)
        return;
    direction.x = explosion->position.x - camera_x;
    direction.y = explosion->position.y - camera_y;
    direction.z = explosion->position.z - camera_z;
    view_position.x = intro_dot_product(&direction, camera_right);
    view_position.y = intro_dot_product(&direction, camera_up);
    view_position.z = intro_dot_product(&direction, camera_forward);
    object_radius = (int32_t)profile->collision_radius << 8;
    if (distance <= object_radius || view_position.z <= object_radius ||
        intro_fixed_divide(view_position.z, distance) < 0x94)
        return;
    scale_factor = intro_fixed_divide((int32_t)FALCON_FRAME_WIDTH << 15,
                                      distance - object_radius);
    scale = intro_fixed_multiply(explosion->scale, scale_factor) >> 8;
    if (scale < 5)
        return;
    if (scale > 0x2000)
        scale = 0x2000;
    screen_x = (FALCON_FRAME_WIDTH >> 1) +
        view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    screen_y = (FALCON_FRAME_HEIGHT >> 1) +
        view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    (void)draw_shape_frame_scaled(resource_title_explosion_data,
                                  resource_title_explosion_size,
                                  explosion->frame, screen_x, screen_y,
                                  (uint16_t)scale);
}

/* Target artefact: flight_scene_append; record:
 * analysis/functions/FlightSceneDepthMerge.md. N/A - platform replacement:
 * the separate Falcon arrays need bounded queue storage before rendering. */
static void flight_scene_append(uint16_t *count, FlightSceneKind kind,
                                uint16_t index, int32_t distance)
{
    FlightSceneEntry *entry;

    if (*count >= WC1_FLIGHT_SCENE_MAX)
        return;
    entry = &resource_flight_scene[*count];
    entry->depth = (uint16_t)((uint32_t)distance >> 8);
    entry->kind = (uint16_t)kind;
    entry->index = index;
    (*count)++;
}

/* DOS: 1990 canonical entry/range TBD (sort_object_depth candidate); record:
 * analysis/functions/FlightSceneDepthMerge.md. Unproven target decomposition. */
static void flight_scene_sort(uint16_t count)
{
    uint16_t index;

    /* The DOS depth list is selected far-to-near from distance >> 8.  Moving
     * only on a strictly greater key leaves equal-depth objects in collection
     * order, which is the target's deterministic tie rule. */
    for (index = 1U; index < count; index++) {
        FlightSceneEntry entry;
        uint16_t previous;

        entry = resource_flight_scene[index];
        previous = index;
        while (previous != 0U &&
               resource_flight_scene[previous - 1U].depth < entry.depth) {
            resource_flight_scene[previous] =
                resource_flight_scene[previous - 1U];
            previous--;
        }
        resource_flight_scene[previous] = entry;
    }
}

/* DOS: 1990 canonical entry/range TBD; record:
 * analysis/functions/FlightSceneDepthMerge.md. Supporting-only identity:
 * Draw_3Space_Frame (1996 0x00429dd0), transform_objects_to_your_view
 * (1996 0x0041a1d0), sort_object_depth (1996 0x00436460), and
 * draw_sorted_objects_to_buffer (1996 0x00436520). This is an Unproven
 * diagnostic flight seam and must not be represented as a supported DOS path.
 *
 * The Falcon's bounded queue merges every currently represented 3Space class:
 * stars/dust, compact roster ships, dynamic cannon projectiles/sparks, and
 * EXPLOSION1 effects. Cockpit and HUD overlays intentionally remain outside
 * this queue, as they are not world objects in the source renderer. */
void resource_draw_flight_scene(void)
{
    IntroFixedVector camera_right;
    IntroFixedVector camera_up;
    IntroFixedVector camera_forward;
    uint16_t count;
    uint16_t active_count;
    uint16_t index;

    resource_flight_scene_order_count = 0U;
    if (render_target == 0)
        return;
    flight_axes_from_mission_angles(object_pitch[0], object_yaw[0],
                                    object_roll[0], &camera_right, &camera_up,
                                    &camera_forward);
    count = 0U;

    if (resource_constellation_size != 0U &&
        (resource_status & RESOURCE_STATUS_PALETTE) != 0U) {
        if (resource_flight_background_initialized == 0U)
            resource_flight_background_reset();
        for (index = 0U; index < WC1_FLIGHT_BACKGROUND_COUNT; index++) {
            FlightBackgroundObject *object;
            int32_t distance;
            int32_t screen_x;
            int32_t screen_y;

            object = &resource_flight_background[index];
            if (!flight_background_project(object, &camera_right, &camera_up,
                                         &camera_forward, object_x[0],
                                         object_y[0], object_z[0], &distance,
                                         &screen_x, &screen_y)) {
                object->offscreen = 1U;
                continue;
            }
            object->offscreen = 0U;
            (void)screen_x;
            (void)screen_y;
            flight_scene_append(&count, FLIGHT_SCENE_BACKGROUND, index,
                                distance);
        }
    }

    active_count = object_count;
    if (active_count > WC1_FLIGHT_OBJECT_COUNT)
        active_count = WC1_FLIGHT_OBJECT_COUNT;
    for (index = 1U; index < active_count; index++) {
        IntroFixedVector direction;

        if (object_active[index] == 0U)
            continue;
        direction.x = object_x[index] - object_x[0];
        direction.y = object_y[index] - object_y[0];
        direction.z = object_z[index] - object_z[0];
        flight_scene_append(&count, FLIGHT_SCENE_SHIP, index,
                            intro_vector_magnitude(&direction));
    }

    if ((resource_status & RESOURCE_STATUS_FLIGHT_WEAPONS) != 0U) {
        for (index = 0U; index < WC1_FLIGHT_PROJECTILE_COUNT; index++) {
            int32_t distance;

            if (flight_scene_projectile_distance(index, object_x[0],
                                                 object_y[0], object_z[0],
                                                 &distance))
                flight_scene_append(&count, FLIGHT_SCENE_PROJECTILE, index,
                                    distance);
        }
    }

    if (resource_title_explosion_size != 0U) {
        for (index = 0U; index < WC1_FLIGHT_EXPLOSION_COUNT; index++) {
            int32_t distance;

            if (flight_scene_explosion_distance(index, object_x[0],
                                                object_y[0], object_z[0],
                                                &distance))
                flight_scene_append(&count, FLIGHT_SCENE_EXPLOSION, index,
                                    distance);
        }
    }

    flight_scene_sort(count);
    resource_flight_scene_order_count = count;
    for (index = 0U; index < count; index++) {
        const FlightSceneEntry *entry;

        entry = &resource_flight_scene[index];
        resource_flight_scene_order[index] =
            (uint16_t)((entry->kind << 8) | entry->index);
        resource_flight_scene_depth[index] = entry->depth;
        switch ((FlightSceneKind)entry->kind) {
        case FLIGHT_SCENE_BACKGROUND:
            (void)flight_scene_draw_background(entry->index, &camera_right,
                                               &camera_up, &camera_forward,
                                               object_x[0], object_y[0],
                                               object_z[0]);
            break;
        case FLIGHT_SCENE_SHIP:
            (void)resource_draw_flight_object(
                object_x[entry->index] - object_x[0],
                object_y[entry->index] - object_y[0],
                object_z[entry->index] - object_z[0],
                object_types[entry->index], object_pitch[entry->index],
                object_yaw[entry->index], object_roll[entry->index],
                object_pitch[0], object_yaw[0], object_roll[0]);
            break;
        case FLIGHT_SCENE_PROJECTILE:
            flight_scene_draw_projectile(entry->index, &camera_right,
                                         &camera_up, &camera_forward,
                                         object_x[0], object_y[0], object_z[0]);
            break;
        case FLIGHT_SCENE_EXPLOSION:
            flight_scene_draw_explosion(entry->index, &camera_right,
                                        &camera_up, &camera_forward,
                                        object_x[0], object_y[0], object_z[0]);
            break;
        default:
            break;
        }
    }
}

static void intro_match_rotation(int16_t *rotation, int16_t *goal,
                                 int16_t total_error, int16_t rate)
{
    int16_t step;

    if (total_error != 0) {
        int16_t error;

        if (*goal > 180)
            *goal = (int16_t)(*goal - 360);
        if (*goal < -180)
            *goal = (int16_t)(*goal + 360);
        error = intro_absolute_short((int16_t)(*rotation - *goal));
        step = (int16_t)(error * rate / total_error);
        if (step < 1)
            step = 1;
        if (*goal != *rotation || step < intro_absolute_short(*rotation)) {
            if (*goal < 1) {
                int16_t minimum;

                minimum = *goal > -step ? *goal : (int16_t)-step;
                minimum = (int16_t)(minimum - *rotation);
                if (minimum < -step)
                    minimum = (int16_t)-step;
                *rotation = (int16_t)(*rotation +
                    (minimum > step ? step : minimum));
            } else {
                int16_t maximum;

                maximum = *goal < step ? *goal : step;
                maximum = (int16_t)(maximum - *rotation);
                if (maximum > step)
                    maximum = step;
                *rotation = (int16_t)(*rotation +
                    (maximum < -step ? (int16_t)-step : maximum));
            }
        }
    }
    if (*goal > 0)
        *goal = *goal > *rotation ? (int16_t)(*goal - *rotation) : 0;
    else if (*goal < 0)
        *goal = *goal < *rotation ? (int16_t)(*goal - *rotation) : 0;
}

static const int16_t intro_canned_sequence_32[] = {
    0, 20, 1, 0, 0, 180, 40, 1, 0, 0, 180, 40, 2, 0, 400, -1
};
static const int16_t intro_canned_sequence_33[] = {
    0, 20, 0, 20, 1, 0, -15, -60, 50, 0, 400, -1
};
static const int16_t intro_canned_sequence_34[] = {
    0, 20, 0, 20, 1, 0, 15, 60, 50, 0, 400, -1
};
static const int16_t intro_canned_sequence_35[] = {
    0, 17, 0, 6, 3, 0, 6, 3, 0, 6, 3, 0, 6, 3, 0, 6, 3, 0, 6,
    3, 0, 6, 3, 1, 0, 0, 180, 40, 1, 0, 0, 180, 40,
    1, 0, -30, 60, 40, 0, 400, -1
};

/* g_anAnimExplosion1_00466060.  The DOS table consists of low words from
 * four-byte entries; frame commands are interleaved with 0x406 grow commands
 * and terminate with 0xa000.  Its yawRate is one, so one entry advances per
 * rendered 3Space update. */
static const uint16_t intro_explosion1_animation[] = {
    0U, 0x0406U, 1U, 0x0406U, 2U, 0x0406U, 0x0406U, 3U,
    0x0406U, 0x0406U, 4U, 0x0406U, 0x0406U, 0x0406U, 5U,
    0x0406U, 0x0406U, 0x0406U, 0x0406U, 0x0406U, 0xa000U
};

static void intro_spawn_explosion(IntroTitleShip *ship)
{
    IntroTitleExplosion *explosion;

    explosion = &resource_intro_explosions[0];
    explosion->position.x = ship->position.x;
    explosion->position.y = ship->position.y;
    explosion->position.z = ship->position.z;
    explosion->velocity.x = ship->velocity.x;
    explosion->velocity.y = ship->velocity.y;
    explosion->velocity.z = ship->velocity.z;
    /* ShipExplosion(): EXPLOSION1 starts at scale 0x100, then restores the
     * destroyed Dralthi's object scale (0x400) through its 8.8 product. */
    explosion->scale = 0x400L;
    explosion->frame = 0U;
    /* set_objects_data() immediately runs animation entry zero, selecting
     * source frame zero and leaving the cursor at entry one. */
    explosion->animation_index = 1U;
    explosion->active = 1U;
    resource_intro_explosion_count++;
}

static void update_intro_explosions(void)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_EXPLOSION_COUNT; index++) {
        IntroTitleExplosion *explosion;
        uint16_t command;

        explosion = &resource_intro_explosions[index];
        if (explosion->active == 0U)
            continue;
        explosion->position.x += explosion->velocity.x;
        explosion->position.y += explosion->velocity.y;
        explosion->position.z += explosion->velocity.z;
        if (explosion->animation_index >=
            sizeof(intro_explosion1_animation) /
            sizeof(intro_explosion1_animation[0])) {
            explosion->active = 0U;
            continue;
        }
        command = intro_explosion1_animation[explosion->animation_index++];
        if ((command & 0xf000U) == 0xa000U) {
            explosion->active = 0U;
        } else if ((command & 0x0c00U) == 0x0400U) {
            explosion->scale += (int32_t)(command & 0x003fU) *
                (explosion->scale >> 6);
        } else if ((command & 0x0c00U) == 0x0800U) {
            explosion->scale -= (int32_t)(command & 0x003fU) *
                (explosion->scale >> 6);
        } else {
            explosion->frame = command & 0x003fU;
        }
    }
}

/* Hornet's two enabled projectile loadout entries are laser cannon hardpoints
 * zero and one.  These are g_aChildOffsets[0..1], expressed directly against
 * the 24.8 ship axes just as position_child() does. */
static const int16_t intro_hornet_laser_hardpoints[2][3] = {
    { 120, 10, 20 }, { -120, 10, 20 }
};

static void intro_spawn_laser(const IntroTitleShip *ship, uint16_t hardpoint)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_LASER_COUNT; index++) {
        IntroTitleLaser *laser;
        IntroFixedVector target;
        IntroFixedVector direction;
        int32_t inherited_speed;

        laser = &resource_intro_lasers[index];
        if (laser->active != 0U)
            continue;
        laser->position.x = ship->position.x +
            ship->forward.x * intro_hornet_laser_hardpoints[hardpoint][2] +
            ship->up.x * intro_hornet_laser_hardpoints[hardpoint][1] +
            ship->right.x * intro_hornet_laser_hardpoints[hardpoint][0];
        laser->position.y = ship->position.y +
            ship->forward.y * intro_hornet_laser_hardpoints[hardpoint][2] +
            ship->up.y * intro_hornet_laser_hardpoints[hardpoint][1] +
            ship->right.y * intro_hornet_laser_hardpoints[hardpoint][0];
        laser->position.z = ship->position.z +
            ship->forward.z * intro_hornet_laser_hardpoints[hardpoint][2] +
            ship->up.z * intro_hornet_laser_hardpoints[hardpoint][1] +
            ship->right.z * intro_hornet_laser_hardpoints[hardpoint][0];
        /* fire_weapon() aims a projectile at the parent's forward vector
         * 35 (lifetime + five) laser ranges ahead, then adds its 160-unit
         * velocity to the parent's component along that new direction. */
        target.x = ship->position.x + ship->forward.x * 5600L;
        target.y = ship->position.y + ship->forward.y * 5600L;
        target.z = ship->position.z + ship->forward.z * 5600L;
        direction.x = target.x - laser->position.x;
        direction.y = target.y - laser->position.y;
        direction.z = target.z - laser->position.z;
        if (!intro_normalize_long_vector(&direction))
            return;
        inherited_speed = intro_dot_product(&ship->velocity, &direction);
        laser->velocity.x = intro_fixed_multiply(direction.x,
            inherited_speed) + intro_fixed_multiply(direction.x, 160L << 8);
        laser->velocity.y = intro_fixed_multiply(direction.y,
            inherited_speed) + intro_fixed_multiply(direction.y, 160L << 8);
        laser->velocity.z = intro_fixed_multiply(direction.z,
            inherited_speed) + intro_fixed_multiply(direction.z, 160L << 8);
        laser->ticks = 30U;
        laser->active = 1U;
        resource_intro_laser_count++;
        return;
    }
}

static void intro_fire_laser_pair(const IntroTitleShip *ship)
{
    if (ship->type != 0U)
        return;
    intro_spawn_laser(ship, 0U);
    intro_spawn_laser(ship, 1U);
}

static void update_intro_lasers(void)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_LASER_COUNT; index++) {
        IntroTitleLaser *laser;

        laser = &resource_intro_lasers[index];
        if (laser->active == 0U)
            continue;
        laser->position.x += laser->velocity.x;
        laser->position.y += laser->velocity.y;
        laser->position.z += laser->velocity.z;
        if (laser->ticks != 0U) {
            laser->ticks--;
            if (laser->ticks == 0U)
                laser->active = 0U;
        }
    }
}

/* Create_explosion_debris() takes one of these source sets after a ship's
 * eight-tick explosion countdown. The shapes are split between common packet
 * four and mission packet five exactly as init_3Space_objects() aliases them. */
static const uint16_t intro_explosion_debris_sets[4][WC1_INTRO_DEBRIS_COUNT] = {
    { 47U, 46U, 41U, 42U, 43U, 44U, 45U },
    { 46U, 46U, 41U, 42U, 43U, 41U, 45U },
    { 47U, 46U, 43U, 42U, 43U, 44U, 42U },
    { 45U, 42U, 43U, 44U, 47U, 46U, 45U }
};
static const uint16_t intro_debris_glass_frames[16] = {
    12U, 13U, 14U, 15U, 16U, 17U, 18U, 19U, 20U, 18U, 17U, 16U,
    15U, 14U, 13U, 12U
};

static uint16_t intro_debris_random_below_or_equal(uint16_t maximum)
{
    resource_intro_debris_seed = resource_intro_debris_seed * 1103515245UL +
        12345UL;
    return (uint16_t)((resource_intro_debris_seed >> 16) %
                      ((uint32_t)maximum + 1U));
}

static int32_t intro_debris_random_component(uint16_t limit)
{
    int32_t value;

    value = (int32_t)intro_debris_random_below_or_equal(limit) << 8;
    if (intro_debris_random_below_or_equal(1U) != 0U)
        value = -value;
    return value;
}

static uint16_t intro_debris_animation_delay(uint16_t type)
{
    return (type == 41U || type == 42U) ? 2U : 1U;
}

static uint16_t intro_debris_animation_length(uint16_t type)
{
    switch (type) {
    case 41U:
    case 42U:
    case 46U:
    case 47U:
        return 6U;
    case 43U:
        return 13U;
    case 44U:
    case 45U:
        return 16U;
    default:
        return 0U;
    }
}

static void intro_debris_animation_value(uint16_t type, uint16_t index,
                                         uint16_t *frame, uint16_t *flip)
{
    uint16_t length;

    length = intro_debris_animation_length(type);
    if (length == 0U)
        return;
    index %= length;
    *flip = 0U;
    switch (type) {
    case 41U:
        *frame = index;
        break;
    case 42U:
        *frame = (uint16_t)(6U + index);
        break;
    case 43U:
        *frame = index;
        break;
    case 44U:
        *frame = (uint16_t)(13U + index);
        break;
    case 45U:
        *frame = intro_debris_glass_frames[index];
        if (index >= 9U)
            *flip = 0x20U;
        break;
    case 46U:
        *frame = (uint16_t)(21U + index);
        break;
    default: /* 47: pipe */
        *frame = (uint16_t)(27U + index);
        break;
    }
}

static void update_intro_debris_animation(IntroTitleDebris *debris)
{
    uint16_t length;

    if (debris->animation_delay > 1U) {
        debris->animation_delay--;
        return;
    }
    debris->animation_delay = intro_debris_animation_delay(debris->type);
    intro_debris_animation_value(debris->type, debris->animation_index,
                                 &debris->frame, &debris->flip);
    length = intro_debris_animation_length(debris->type);
    debris->animation_index++;
    if (debris->animation_index >= length)
        debris->animation_index = 0U;
}

static void intro_spawn_explosion_debris(const IntroTitleShip *ship)
{
    uint16_t set;
    uint16_t index;

    /* The DOS game seeds rand() from its clock. Keep this effect independent
     * and repeatable on Falcon while retaining its exact source type table,
     * seven fragments, component ranges, and 40-tick lifetime. */
    resource_intro_debris_seed = 0x44454252UL;
    resource_intro_debris_count = 0U;
    set = intro_debris_random_below_or_equal(3U);
    for (index = 0U; index < WC1_INTRO_DEBRIS_COUNT; index++) {
        IntroTitleDebris *debris;
        IntroFixedVector inherited_velocity;

        debris = &resource_intro_debris[index];
        debris->type = intro_explosion_debris_sets[set][index];
        debris->position.x = ship->position.x +
            intro_debris_random_component(50U);
        debris->position.y = ship->position.y +
            intro_debris_random_component(50U);
        debris->position.z = ship->position.z +
            intro_debris_random_component(50U);
        inherited_velocity.x = intro_fixed_divide(ship->velocity.x, 0x200);
        inherited_velocity.y = intro_fixed_divide(ship->velocity.y, 0x200);
        inherited_velocity.z = intro_fixed_divide(ship->velocity.z, 0x200);
        debris->velocity.x = inherited_velocity.x +
            intro_debris_random_component(25U);
        debris->velocity.y = inherited_velocity.y +
            intro_debris_random_component(25U);
        debris->velocity.z = inherited_velocity.z +
            intro_debris_random_component(25U);
        debris->frame = 0U;
        debris->flip = 0U;
        intro_debris_animation_value(debris->type, 0U, &debris->frame,
                                     &debris->flip);
        debris->animation_index = 1U;
        debris->animation_delay = intro_debris_animation_delay(debris->type);
        debris->ticks = 40U;
        debris->active = 1U;
        resource_intro_debris_count++;
    }
    resource_intro_debris_dust_count = 0U;
    for (index = 0U; index < WC1_INTRO_DEBRIS_DUST_COUNT; index++) {
        IntroTitleDust *dust;
        IntroFixedVector inherited_velocity;

        dust = &resource_intro_debris_dust[index];
        dust->position.x = ship->position.x +
            intro_debris_random_component(50U);
        dust->position.y = ship->position.y +
            intro_debris_random_component(50U);
        dust->position.z = ship->position.z +
            intro_debris_random_component(50U);
        inherited_velocity.x = intro_fixed_divide(ship->velocity.x, 0x200);
        inherited_velocity.y = intro_fixed_divide(ship->velocity.y, 0x200);
        inherited_velocity.z = intro_fixed_divide(ship->velocity.z, 0x200);
        dust->velocity.x = inherited_velocity.x +
            intro_debris_random_component(25U);
        dust->velocity.y = inherited_velocity.y +
            intro_debris_random_component(25U);
        dust->velocity.z = inherited_velocity.z +
            intro_debris_random_component(25U);
        dust->screen_angle = (uint16_t)(0x10U +
            intro_debris_random_below_or_equal(3U));
        dust->ticks = 40U;
        dust->active = 1U;
        resource_intro_debris_dust_count++;
    }
}

static void update_intro_debris(void)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_DEBRIS_COUNT; index++) {
        IntroTitleDebris *debris;

        debris = &resource_intro_debris[index];
        if (debris->active == 0U)
            continue;
        debris->position.x += debris->velocity.x;
        debris->position.y += debris->velocity.y;
        debris->position.z += debris->velocity.z;
        update_intro_debris_animation(debris);
        if (debris->ticks != 0U) {
            debris->ticks--;
            if (debris->ticks == 0U)
                debris->active = 0U;
        }
    }
    for (index = 0U; index < WC1_INTRO_DEBRIS_DUST_COUNT; index++) {
        IntroTitleDust *dust;

        dust = &resource_intro_debris_dust[index];
        if (dust->active == 0U)
            continue;
        dust->position.x += dust->velocity.x;
        dust->position.y += dust->velocity.y;
        dust->position.z += dust->velocity.z;
        if (dust->ticks != 0U) {
            dust->ticks--;
            if (dust->ticks == 0U)
                dust->active = 0U;
        }
    }
}

static void intro_advance_canned_sequence(IntroTitleShip *ship)
{
    int16_t command;

    command = ship->sequence[ship->sequence_offset++];
    ship->command = command;
    if (command == -1) {
        ship->active = 0U;
    } else if (command == 0) {
        ship->action_count = ship->sequence[ship->sequence_offset++];
    } else if (command == 1) {
        ship->yaw_goal = ship->sequence[ship->sequence_offset++];
        ship->pitch_goal = ship->sequence[ship->sequence_offset++];
        ship->roll_goal = ship->sequence[ship->sequence_offset++];
        ship->speed = (int32_t)ship->sequence[ship->sequence_offset++] << 8;
    } else if (command == 2) {
        /* advance_canned_sequence() calls explode(-1,obj). Explosion() keeps
         * the original fighter alive for its eight-tick destruction counter,
         * while ShipExplosion() creates the separate OBJECTS.VGA explosion. */
        intro_spawn_explosion(ship);
        ship->destroying = 1U;
        ship->destruction_ticks = 8U;
    }
}

static void intro_update_fighter(IntroTitleShip *ship)
{
    IntroFixedVector desired_velocity;
    IntroFixedVector delta;
    IntroFixedVector acceleration;
    int32_t magnitude;
    int32_t requested_acceleration;
    int16_t total_error;

    if (ship->active == 0U)
        return;
    if (ship->destroying != 0U) {
        /* house_keep_objects() counts the original ship down after the
         * explosion was created. It still drifts with its last velocity
         * until Create_explosion_debris() removes it at zero. */
        ship->position.x += ship->velocity.x;
        ship->position.y += ship->velocity.y;
        ship->position.z += ship->velocity.z;
        if (ship->destruction_ticks != 0U) {
            ship->destruction_ticks--;
            if (ship->destruction_ticks == 0U) {
                intro_spawn_explosion_debris(ship);
                ship->active = 0U;
            }
        }
        return;
    }
    if (ship->pitch_rotation != 0)
        intro_alter_pitch(ship->pitch_rotation, &ship->right, &ship->up,
                          &ship->forward);
    if (ship->yaw_rotation != 0)
        intro_alter_yaw(ship->yaw_rotation, &ship->right, &ship->up,
                        &ship->forward);
    if (ship->roll_rotation != 0)
        intro_alter_roll(ship->roll_rotation, &ship->right, &ship->up,
                         &ship->forward);
    if (ship->command == 0) {
        ship->action_count--;
        if (ship->action_count == 0)
            intro_advance_canned_sequence(ship);
    } else if (ship->command == 1 && ship->yaw_goal == 0 &&
               ship->pitch_goal == 0 && ship->roll_goal == 0) {
        intro_advance_canned_sequence(ship);
    } else if (ship->command == 3 || ship->command == 4) {
        if (ship->command == 3)
            intro_fire_laser_pair(ship);
        intro_advance_canned_sequence(ship);
    }
    total_error = (int16_t)(intro_absolute_short((int16_t)(
        ship->yaw_rotation - ship->yaw_goal)) +
        intro_absolute_short((int16_t)(ship->pitch_rotation -
                                       ship->pitch_goal)) +
        intro_absolute_short((int16_t)(ship->roll_rotation -
                                       ship->roll_goal)));
    intro_match_rotation(&ship->pitch_rotation, &ship->pitch_goal,
                         total_error, ship->yaw_rate);
    intro_match_rotation(&ship->yaw_rotation, &ship->yaw_goal, total_error,
                         ship->pitch_rate);
    intro_match_rotation(&ship->roll_rotation, &ship->roll_goal, total_error,
                         ship->roll_rate);
    desired_velocity.x = intro_fixed_multiply(ship->forward.x, ship->speed);
    desired_velocity.y = intro_fixed_multiply(ship->forward.y, ship->speed);
    desired_velocity.z = intro_fixed_multiply(ship->forward.z, ship->speed);
    delta.x = desired_velocity.x - ship->velocity.x;
    delta.y = desired_velocity.y - ship->velocity.y;
    delta.z = desired_velocity.z - ship->velocity.z;
    magnitude = intro_vector_magnitude(&delta);
    acceleration.x = 0;
    acceleration.y = 0;
    acceleration.z = 0;
    if (magnitude != 0) {
        int32_t scale;

        requested_acceleration = intro_fixed_multiply(ship->acceleration,
            intro_fixed_divide(intro_dot_product(&delta, &ship->forward),
                               magnitude) + 0x200);
        scale = intro_fixed_divide(requested_acceleration >> 1, magnitude);
        if (scale > 256)
            scale = 256;
        acceleration.x = intro_fixed_multiply(delta.x, scale);
        acceleration.y = intro_fixed_multiply(delta.y, scale);
        acceleration.z = intro_fixed_multiply(delta.z, scale);
    }
    ship->velocity.x += acceleration.x;
    ship->velocity.y += acceleration.y;
    ship->velocity.z += acceleration.z;
    ship->position.x += ship->velocity.x;
    ship->position.y += ship->velocity.y;
    ship->position.z += ship->velocity.z;
}

static void update_intro_fighters(void)
{
    uint16_t fighter;

    for (fighter = 0U; fighter < WC1_INTRO_FIGHTER_COUNT; fighter++)
        intro_update_fighter(&resource_intro_fighters[fighter]);
}

static void draw_intro_fighter(const IntroTitleShip *ship, int solid)
{
    IntroFixedVector direction;
    IntroFixedVector view_position;
    int32_t distance;
    int32_t scale;
    int32_t screen_x;
    int32_t screen_y;
    uint16_t frame;
    uint16_t flip;
    int16_t angle;
    uint16_t slot;

    if (ship->active == 0U)
        return;
    direction.x = ship->position.x - resource_intro_camera_position.x;
    direction.y = ship->position.y - resource_intro_camera_position.y;
    direction.z = ship->position.z - resource_intro_camera_position.z;
    distance = intro_vector_magnitude(&direction);
    if (distance <= (int32_t)ship->collision_radius << 8)
        return;
    view_position.x = intro_dot_product(&direction,
                                        &resource_intro_camera_right);
    view_position.y = intro_dot_product(&direction, &resource_intro_camera_up);
    view_position.z = intro_dot_product(&direction,
                                        &resource_intro_camera_forward);
    if (view_position.z <= (100L << 8) ||
        intro_fixed_divide(view_position.z, distance) < 0x94)
        return;
    scale = 4L * (FALCON_FRAME_WIDTH << 15) /
        (distance - ((int32_t)ship->collision_radius << 8));
    if (scale < 5 || scale > 0x2000)
        return;
    if (!intro_select_fighter_shape(ship, &direction, &frame, &angle, &flip))
        return;
    screen_x = (FALCON_FRAME_WIDTH >> 1) +
        view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    screen_y = (FALCON_FRAME_HEIGHT >> 1) +
        view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
    for (slot = 0U; slot < RESOURCE_OBJECT_SLOT_COUNT; slot++) {
        if (resource_object_types[slot] == ship->type) {
            (void)draw_shape_frame_transformed(
                resource_object_data[slot], resource_object_sizes[slot],
                frame, screen_x, screen_y, angle, (uint16_t)scale, flip,
                solid, 0xbfU);
            return;
        }
    }
}

static void draw_intro_explosions(int solid)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_EXPLOSION_COUNT; index++) {
        const IntroTitleExplosion *explosion;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t screen_x;
        int32_t screen_y;
        int32_t scale;

        explosion = &resource_intro_explosions[index];
        if (explosion->active == 0U)
            continue;
        direction.x = explosion->position.x -
            resource_intro_camera_position.x;
        direction.y = explosion->position.y -
            resource_intro_camera_position.y;
        direction.z = explosion->position.z -
            resource_intro_camera_position.z;
        distance = intro_vector_magnitude(&direction);
        if (distance <= (100L << 8))
            continue;
        view_position.x = intro_dot_product(&direction,
                                            &resource_intro_camera_right);
        view_position.y = intro_dot_product(&direction,
                                            &resource_intro_camera_up);
        view_position.z = intro_dot_product(&direction,
                                            &resource_intro_camera_forward);
        if (view_position.z <= (100L << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        /* transform_objects_to_your_view(): the explosion collision radius
         * is zero and its base 8.8 scale is multiplied through the same
         * screen factor used by ordinary 3Space objects. */
        scale = intro_fixed_divide(explosion->scale *
                                   FALCON_FRAME_WIDTH * 128L, distance);
        if (scale < 5 || scale > 0x2000)
            continue;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        if (solid) {
            (void)draw_shape_frame_transformed(
                resource_title_explosion_data, resource_title_explosion_size,
                explosion->frame, screen_x, screen_y, 0,
                (uint16_t)scale, 0U, 1, 0xbfU);
        } else {
            (void)draw_shape_frame_scaled(
                resource_title_explosion_data, resource_title_explosion_size,
                explosion->frame, screen_x, screen_y, (uint16_t)scale);
        }
    }
}

static void draw_intro_lasers(int solid)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_LASER_COUNT; index++) {
        const IntroTitleLaser *laser;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t screen_x;
        int32_t screen_y;
        int32_t scale;

        laser = &resource_intro_lasers[index];
        if (laser->active == 0U)
            continue;
        direction.x = laser->position.x - resource_intro_camera_position.x;
        direction.y = laser->position.y - resource_intro_camera_position.y;
        direction.z = laser->position.z - resource_intro_camera_position.z;
        distance = intro_vector_magnitude(&direction);
        if (distance <= (100L << 8))
            continue;
        view_position.x = intro_dot_product(&direction,
                                            &resource_intro_camera_right);
        view_position.y = intro_dot_product(&direction,
                                            &resource_intro_camera_up);
        view_position.z = intro_dot_product(&direction,
                                            &resource_intro_camera_forward);
        if (view_position.z <= (100L << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        /* Laser cannon: object scale 0x200, collision radius ten. */
        scale = intro_fixed_divide(0x200L * FALCON_FRAME_WIDTH * 128L,
                                   distance - (10L << 8));
        if (scale < 5 || scale > 0x2000)
            continue;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        if (solid) {
            (void)draw_shape_frame_transformed(
                resource_title_laser_data, resource_title_laser_size, 0U,
                screen_x, screen_y, 0, (uint16_t)scale, 0U, 1, 0xbfU);
        } else {
            (void)draw_shape_frame_scaled(resource_title_laser_data,
                                          resource_title_laser_size, 0U,
                                          screen_x, screen_y,
                                          (uint16_t)scale);
        }
    }
}

static uint16_t intro_debris_scale(uint16_t type)
{
    switch (type) {
    case 41U:
    case 42U:
        return 2048U;
    case 43U:
    case 44U:
        return 1280U;
    case 45U:
        return 768U;
    case 46U:
        return 1792U;
    default: /* 47: pipe */
        return 1536U;
    }
}

static uint16_t intro_debris_collision_radius(uint16_t type)
{
    switch (type) {
    case 41U:
    case 42U:
        return 10U;
    case 43U:
    case 44U:
    case 45U:
        return 20U;
    case 46U:
        return 2U;
    default: /* 47: pipe */
        return 6U;
    }
}

static void draw_intro_debris(void)
{
    uint16_t order[WC1_INTRO_DEBRIS_COUNT];
    uint16_t count;
    uint16_t index;

    count = 0U;
    for (index = 0U; index < WC1_INTRO_DEBRIS_COUNT; index++) {
        if (resource_intro_debris[index].active != 0U)
            order[count++] = index;
    }
    /* The normal renderer depth-sorts all non-background objects. Preserve
     * that far-to-near ordering for the title's transient debris subset. */
    for (index = 0U; index < count; index++) {
        uint16_t inner;

        for (inner = (uint16_t)(index + 1U); inner < count; inner++) {
            IntroFixedVector left;
            IntroFixedVector right;

            left.x = resource_intro_debris[order[index]].position.x -
                resource_intro_camera_position.x;
            left.y = resource_intro_debris[order[index]].position.y -
                resource_intro_camera_position.y;
            left.z = resource_intro_debris[order[index]].position.z -
                resource_intro_camera_position.z;
            right.x = resource_intro_debris[order[inner]].position.x -
                resource_intro_camera_position.x;
            right.y = resource_intro_debris[order[inner]].position.y -
                resource_intro_camera_position.y;
            right.z = resource_intro_debris[order[inner]].position.z -
                resource_intro_camera_position.z;
            if (intro_vector_magnitude(&left) < intro_vector_magnitude(&right)) {
                uint16_t swap;

                swap = order[index];
                order[index] = order[inner];
                order[inner] = swap;
            }
        }
    }
    for (index = 0U; index < count; index++) {
        const IntroTitleDebris *debris;
        const uint8_t *shape;
        uint32_t shape_size;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t denominator;
        int32_t scale;
        int32_t screen_x;
        int32_t screen_y;
        uint16_t collision_radius;

        debris = &resource_intro_debris[order[index]];
        direction.x = debris->position.x - resource_intro_camera_position.x;
        direction.y = debris->position.y - resource_intro_camera_position.y;
        direction.z = debris->position.z - resource_intro_camera_position.z;
        distance = intro_vector_magnitude(&direction);
        collision_radius = intro_debris_collision_radius(debris->type);
        if (distance <= (100L << 8))
            continue;
        view_position.x = intro_dot_product(&direction,
                                            &resource_intro_camera_right);
        view_position.y = intro_dot_product(&direction,
                                            &resource_intro_camera_up);
        view_position.z = intro_dot_product(&direction,
                                            &resource_intro_camera_forward);
        if (view_position.z <= (100L << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        denominator = distance - ((int32_t)collision_radius << 8);
        if (denominator <= 0)
            continue;
        scale = (int32_t)intro_debris_scale(debris->type) *
            (FALCON_FRAME_WIDTH << 7) / denominator;
        if (scale < 5)
            continue;
        if (scale > 0x1fff)
            scale = 0x2000;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        if (debris->type == 43U || debris->type == 44U) {
            shape = resource_title_debris_data;
            shape_size = resource_title_debris_size;
        } else {
            shape = resource_title_common_debris_data;
            shape_size = resource_title_common_debris_size;
        }
        (void)draw_shape_frame_transformed(shape, shape_size, debris->frame,
                                           screen_x, screen_y, 0,
                                           (uint16_t)scale, debris->flip,
                                           0, 0U);
    }
}

static void draw_intro_debris_dust(void)
{
    uint16_t index;

    for (index = 0U; index < WC1_INTRO_DEBRIS_DUST_COUNT; index++) {
        const IntroTitleDust *dust;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t screen_x;
        int32_t screen_y;
        int32_t dust_size;
        uint16_t frame;

        dust = &resource_intro_debris_dust[index];
        if (dust->active == 0U)
            continue;
        direction.x = dust->position.x - resource_intro_camera_position.x;
        direction.y = dust->position.y - resource_intro_camera_position.y;
        direction.z = dust->position.z - resource_intro_camera_position.z;
        distance = intro_vector_magnitude(&direction);
        if (distance <= (100L << 8) || distance > (1400L << 8))
            continue;
        view_position.x = intro_dot_product(&direction,
                                            &resource_intro_camera_right);
        view_position.y = intro_dot_product(&direction,
                                            &resource_intro_camera_up);
        view_position.z = intro_dot_product(&direction,
                                            &resource_intro_camera_forward);
        if (view_position.z <= (100L << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        dust_size = intro_fixed_multiply(0x900,
            intro_fixed_divide(100L << 8, distance)) >> 8;
        if (dust_size > 3)
            dust_size = 3;
        if (dust_size < 0)
            dust_size = 0;
        frame = (uint16_t)(((dust->ticks + resource_intro_space_frame) & 3U) +
            (dust->screen_angle & 0x10U) + (uint16_t)(3 - dust_size) * 4U);
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        (void)draw_shape_frame(resource_constellation_data,
                               resource_constellation_size, frame,
                               screen_x, screen_y);
    }
}

static void draw_intro_fighters(int solid)
{
    uint16_t order[WC1_INTRO_FIGHTER_COUNT];
    uint16_t fighter;

    for (fighter = 0U; fighter < WC1_INTRO_FIGHTER_COUNT; fighter++)
        order[fighter] = fighter;
    /* Normal Draw_3Space_Frame() draws depth-sorted objects far to near;
     * intro_drawbackgroundships() instead walks object slots. */
    if (!solid) {
        uint16_t outer;

        for (outer = 0U; outer < WC1_INTRO_FIGHTER_COUNT - 1U; outer++) {
            uint16_t inner;

            for (inner = (uint16_t)(outer + 1U);
                 inner < WC1_INTRO_FIGHTER_COUNT; inner++) {
                IntroFixedVector left;
                IntroFixedVector right;

                left.x = resource_intro_fighters[order[outer]].position.x -
                    resource_intro_camera_position.x;
                left.y = resource_intro_fighters[order[outer]].position.y -
                    resource_intro_camera_position.y;
                left.z = resource_intro_fighters[order[outer]].position.z -
                    resource_intro_camera_position.z;
                right.x = resource_intro_fighters[order[inner]].position.x -
                    resource_intro_camera_position.x;
                right.y = resource_intro_fighters[order[inner]].position.y -
                    resource_intro_camera_position.y;
                right.z = resource_intro_fighters[order[inner]].position.z -
                    resource_intro_camera_position.z;
                if (intro_vector_magnitude(&left) < intro_vector_magnitude(&right)) {
                    uint16_t swap;

                    swap = order[outer];
                    order[outer] = order[inner];
                    order[inner] = swap;
                }
            }
        }
    }
    for (fighter = 0U; fighter < WC1_INTRO_FIGHTER_COUNT; fighter++)
        draw_intro_fighter(&resource_intro_fighters[order[fighter]], solid);
}

static void reset_intro_fighter(IntroTitleShip *ship, uint16_t type,
                                uint16_t collision_radius,
                                int16_t pitch_rate, int16_t yaw_rate,
                                int16_t roll_rate, int16_t acceleration,
                                int32_t x, int32_t y, int32_t z,
                                const int16_t *sequence)
{
    ship->type = type;
    ship->collision_radius = collision_radius;
    ship->pitch_rate = pitch_rate;
    ship->yaw_rate = yaw_rate;
    ship->roll_rate = roll_rate;
    ship->acceleration = acceleration;
    ship->position.x = x;
    ship->position.y = y;
    ship->position.z = z;
    ship->velocity.x = 0;
    ship->velocity.y = 0;
    ship->velocity.z = 0;
    ship->right.x = 256;
    ship->right.y = 0;
    ship->right.z = 0;
    ship->up.x = 0;
    ship->up.y = 256;
    ship->up.z = 0;
    ship->forward.x = 0;
    ship->forward.y = 0;
    ship->forward.z = 256;
    ship->sequence = sequence;
    ship->sequence_offset = 0U;
    ship->command = 0;
    ship->action_count = 0;
    ship->yaw_goal = 0;
    ship->pitch_goal = 0;
    ship->roll_goal = 0;
    ship->yaw_rotation = 0;
    ship->pitch_rotation = 0;
    ship->roll_rotation = 0;
    ship->speed = 40L << 8;
    ship->destruction_ticks = 0U;
    ship->destroying = 0U;
    ship->active = 1U;
    /* Set_up_ship_info(): the record's yaw -155 is applied as
     * alter_pitch(-yaw), after the zero yaw/pitch/roll fields. */
    intro_alter_pitch(155, &ship->right, &ship->up, &ship->forward);
    intro_advance_canned_sequence(ship);
}

static uint16_t intro_random_below_or_equal(uint16_t maximum)
{
    resource_intro_star_seed = resource_intro_star_seed * 1103515245UL +
        12345UL;
    return (uint16_t)((resource_intro_star_seed >> 16) %
                      ((uint32_t)maximum + 1U));
}

static int16_t intro_signed_random(int16_t range)
{
    return (int16_t)intro_random_below_or_equal((uint16_t)(range * 2)) -
        range;
}

/* DOS seeds rand() from its clock, so the original credit asteroid placement
 * is deliberately different on each run.  This independent, repeatable seed
 * preserves the source ranges and hazard cadence without coupling the credit
 * field to constellation construction or to the Falcon's wall clock. */
static uint16_t intro_credit_random_below_or_equal(uint16_t maximum)
{
    resource_intro_credit_seed = resource_intro_credit_seed * 1103515245UL +
        12345UL;
    return (uint16_t)((resource_intro_credit_seed >> 16) %
                      ((uint32_t)maximum + 1U));
}

static uint16_t intro_credit_random_below(uint16_t maximum)
{
    if (maximum == 0U)
        return 0U;
    return intro_credit_random_below_or_equal((uint16_t)(maximum - 1U));
}

static int16_t intro_credit_signed_random(int16_t range)
{
    return (int16_t)intro_credit_random_below_or_equal(
        (uint16_t)(range * 2)) - range;
}

static void intro_credit_set_velocity(IntroTitleAsteroid *asteroid,
                                      int16_t speed)
{
    int32_t fixed_speed;

    fixed_speed = (int32_t)speed << 8;
    asteroid->velocity.x = intro_fixed_multiply(asteroid->forward.x,
                                                fixed_speed);
    asteroid->velocity.y = intro_fixed_multiply(asteroid->forward.y,
                                                fixed_speed);
    asteroid->velocity.z = intro_fixed_multiply(asteroid->forward.z,
                                                fixed_speed);
}

static int intro_credit_point_at(IntroTitleAsteroid *asteroid,
                                 const IntroFixedVector *point)
{
    IntroFixedVector direction;

    direction.x = point->x - asteroid->position.x;
    direction.y = point->y - asteroid->position.y;
    direction.z = point->z - asteroid->position.z;
    if (!intro_normalize_long_vector(&direction))
        return 0;
    asteroid->forward.x = direction.x;
    asteroid->forward.y = direction.y;
    asteroid->forward.z = direction.z;
    intro_fix_axes(&asteroid->right, &asteroid->up, &asteroid->forward);
    return 1;
}

static void intro_credit_skew_randomly(IntroTitleAsteroid *asteroid)
{
    IntroFixedVector saved;

    if (intro_credit_random_below(100U) < 50U) {
        intro_copy_vector(&saved, &asteroid->right);
        intro_copy_vector(&asteroid->right, &asteroid->forward);
        intro_copy_vector(&asteroid->forward, &asteroid->up);
        intro_copy_vector(&asteroid->up, &saved);
    } else {
        intro_copy_vector(&saved, &asteroid->up);
        intro_copy_vector(&asteroid->up, &asteroid->forward);
        intro_copy_vector(&asteroid->forward, &asteroid->right);
        intro_copy_vector(&asteroid->right, &saved);
    }
    if (intro_credit_random_below(100U) < 50U) {
        asteroid->forward.x = -asteroid->forward.x;
        asteroid->forward.y = -asteroid->forward.y;
        asteroid->forward.z = -asteroid->forward.z;
    }
}

static uint16_t intro_credit_asteroid_limit(uint16_t type)
{
    return (type == 35U || type == 37U || type == 39U) ? 13U : 14U;
}

static uint16_t intro_credit_asteroid_delay(uint16_t type)
{
    return (type == 38U || type == 39U) ? 2U : 1U;
}

static uint16_t intro_credit_asteroid_frame(uint16_t type,
                                             uint16_t index)
{
    uint16_t limit;

    limit = intro_credit_asteroid_limit(type);
    if (index >= limit)
        index = 0U;
    if (type == 36U || type == 37U)
        return (uint16_t)(limit - 1U - index);
    return index;
}

/* animate_shape() has already selected animation entry zero during
 * set_objects_data().  This carries its post-spawn delay/index semantics for
 * the ASTEROID1..6 forward, short, and reverse packet sequences. */
static void update_intro_credit_asteroid_animation(
    IntroTitleAsteroid *asteroid)
{
    uint16_t limit;

    if (asteroid->animation_delay > 1U) {
        asteroid->animation_delay--;
        return;
    }
    asteroid->animation_delay = intro_credit_asteroid_delay(asteroid->type);
    limit = intro_credit_asteroid_limit(asteroid->type);
    asteroid->frame = intro_credit_asteroid_frame(asteroid->type,
                                                   asteroid->animation_index);
    asteroid->animation_index++;
    if (asteroid->animation_index >= limit)
        asteroid->animation_index = 0U;
}

static int intro_spawn_credit_asteroid(uint16_t slot)
{
    IntroTitleAsteroid *asteroid;
    IntroFixedVector target;
    IntroFixedVector offset;
    int16_t pitch;
    int16_t yaw;
    int16_t moving;
    int16_t speed;
    int16_t travel_time;
    int32_t distance;

    if (slot >= WC1_INTRO_ASTEROID_COUNT)
        return 0;
    asteroid = &resource_intro_asteroids[slot];
    pitch = intro_credit_signed_random(20);
    yaw = intro_credit_signed_random(35);
    moving = 0;
    if (intro_absolute_short(pitch) > 5 && intro_absolute_short(pitch) < 20 &&
        intro_absolute_short(yaw) > 5 && intro_absolute_short(yaw) < 20 &&
        intro_credit_random_below(100U) < 30U)
        moving = 1;
    asteroid->position.x = resource_intro_camera_position.x;
    asteroid->position.y = resource_intro_camera_position.y;
    asteroid->position.z = resource_intro_camera_position.z;
    intro_copy_vector(&asteroid->right, &resource_intro_camera_right);
    intro_copy_vector(&asteroid->up, &resource_intro_camera_up);
    intro_copy_vector(&asteroid->forward, &resource_intro_camera_forward);
    intro_alter_yaw(yaw, &asteroid->right, &asteroid->up,
                    &asteroid->forward);
    intro_alter_pitch(pitch, &asteroid->right, &asteroid->up,
                      &asteroid->forward);
    offset.x = intro_fixed_multiply(asteroid->forward.x, 3050L << 8);
    offset.y = intro_fixed_multiply(asteroid->forward.y, 3050L << 8);
    offset.z = intro_fixed_multiply(asteroid->forward.z, 3050L << 8);
    asteroid->position.x += offset.x;
    asteroid->position.y += offset.y;
    asteroid->position.z += offset.z;
    asteroid->type = (uint16_t)(34U + intro_credit_random_below_or_equal(5U));
    speed = 0;
    if (moving != 0) {
        /* The title sets g_nHazardReferenceSpeed to 100. With the normal
         * forward cockpit view, source travel time is 56..71 less its
         * difficulty roll, floored at 45 updates. */
        travel_time = (int16_t)(56 +
            intro_credit_random_below_or_equal(15U));
        travel_time = (int16_t)(travel_time -
            intro_credit_random_below_or_equal(150U));
        if (travel_time < 45)
            travel_time = 45;
        target.x = resource_intro_camera_position.x +
            intro_fixed_multiply(resource_intro_camera_forward.x,
                                 (int32_t)travel_time * 100L * 256L);
        target.y = resource_intro_camera_position.y +
            intro_fixed_multiply(resource_intro_camera_forward.y,
                                 (int32_t)travel_time * 100L * 256L);
        target.z = resource_intro_camera_position.z +
            intro_fixed_multiply(resource_intro_camera_forward.z,
                                 (int32_t)travel_time * 100L * 256L);
        if (!intro_credit_point_at(asteroid, &target))
            return 0;
        offset.x = target.x - asteroid->position.x;
        offset.y = target.y - asteroid->position.y;
        offset.z = target.z - asteroid->position.z;
        distance = intro_vector_magnitude(&offset);
        travel_time = (int16_t)(travel_time -
            intro_credit_random_below(5U));
        if (travel_time < 3)
            travel_time = 3;
        speed = (int16_t)((distance >> 8) / travel_time);
    } else {
        if (!intro_credit_point_at(asteroid,
                                   &resource_intro_camera_position))
            return 0;
        intro_credit_skew_randomly(asteroid);
        if (intro_credit_random_below(100U) >= 20U)
            speed = (int16_t)(10 + intro_credit_random_below_or_equal(7U));
        offset.x = intro_fixed_multiply(asteroid->forward.x,
            (int32_t)intro_credit_random_below_or_equal(1000U) << 8);
        offset.y = intro_fixed_multiply(asteroid->forward.y,
            (int32_t)intro_credit_random_below_or_equal(1000U) << 8);
        offset.z = intro_fixed_multiply(asteroid->forward.z,
            (int32_t)intro_credit_random_below_or_equal(1000U) << 8);
        asteroid->position.x -= offset.x;
        asteroid->position.y -= offset.y;
        asteroid->position.z -= offset.z;
    }
    intro_credit_set_velocity(asteroid, speed);
    asteroid->frame = intro_credit_asteroid_frame(asteroid->type, 0U);
    asteroid->animation_index = 1U;
    asteroid->animation_delay = intro_credit_asteroid_delay(asteroid->type);
    asteroid->active = 1U;
    return 1;
}

static void begin_intro_credit_scene(void)
{
    uint16_t asteroid;

    if (resource_intro_credit_scene_active != 0U)
        return;
    resource_intro_credit_scene_active = 1U;
    resource_intro_credit_seed = 0x43454449UL;
    resource_intro_credit_frame = 0U;
    resource_intro_asteroid_count = 0U;
    /* Title_Sequence() changes the eye from its initial 15-unit drift to
     * forward[61] * 0x9600 before action sphere 17 begins. */
    resource_intro_camera_velocity.x = intro_fixed_multiply(
        resource_intro_camera_forward.x, 150L << 8);
    resource_intro_camera_velocity.y = intro_fixed_multiply(
        resource_intro_camera_forward.y, 150L << 8);
    resource_intro_camera_velocity.z = intro_fixed_multiply(
        resource_intro_camera_forward.z, 150L << 8);
    for (asteroid = 0U; asteroid < WC1_INTRO_ASTEROID_COUNT; asteroid++)
        resource_intro_asteroids[asteroid].active = 0U;
    for (asteroid = 0U; asteroid < WC1_INTRO_DEBRIS_COUNT; asteroid++)
        resource_intro_debris[asteroid].active = 0U;
    for (asteroid = 0U; asteroid < WC1_INTRO_DEBRIS_DUST_COUNT; asteroid++)
        resource_intro_debris_dust[asteroid].active = 0U;
    /* start_hazard_field() reserves source slots zero and then creates
     * hazards in slots one through three. */
    for (asteroid = 1U; asteroid <= 3U; asteroid++) {
        if (intro_spawn_credit_asteroid(asteroid))
            resource_intro_asteroid_count++;
    }
}

static void update_intro_credit_scene(void)
{
    uint16_t asteroid;
    uint16_t empty_slot;
    uint16_t active;

    if (resource_intro_credit_scene_active == 0U)
        return;
    empty_slot = WC1_INTRO_ASTEROID_COUNT;
    for (asteroid = 0U; asteroid < WC1_INTRO_ASTEROID_COUNT; asteroid++) {
        IntroTitleAsteroid *current;
        IntroFixedVector direction;

        current = &resource_intro_asteroids[asteroid];
        if (current->active == 0U) {
            empty_slot = asteroid;
            continue;
        }
        current->position.x += current->velocity.x;
        current->position.y += current->velocity.y;
        current->position.z += current->velocity.z;
        update_intro_credit_asteroid_animation(current);
        /* manage_hazard() tests one slot each update. The eye is the active
         * field centre during g_bIntroSecondaryScene, and 4300 is its normal
         * forward-view keep radius. */
        if ((resource_intro_credit_frame % WC1_INTRO_ASTEROID_COUNT) ==
            asteroid) {
            direction.x = current->position.x - resource_intro_camera_position.x;
            direction.y = current->position.y - resource_intro_camera_position.y;
            direction.z = current->position.z - resource_intro_camera_position.z;
            if (intro_vector_magnitude(&direction) > (4300L << 8)) {
                current->active = 0U;
                empty_slot = asteroid;
            }
        }
    }
    /* update_hazards() adds at the last observed empty slot when its exact
     * RandomBelowOrEqual(215) < referenceSpeed + 30 test succeeds. */
    if (empty_slot < WC1_INTRO_ASTEROID_COUNT &&
        intro_credit_random_below_or_equal(215U) < 130U)
        (void)intro_spawn_credit_asteroid(empty_slot);
    active = 0U;
    for (asteroid = 0U; asteroid < WC1_INTRO_ASTEROID_COUNT; asteroid++) {
        if (resource_intro_asteroids[asteroid].active != 0U)
            active++;
    }
    resource_intro_asteroid_count = active;
    resource_intro_credit_frame++;
}

static void draw_intro_credit_asteroids(void)
{
    uint16_t order[WC1_INTRO_ASTEROID_COUNT];
    uint16_t count;
    uint16_t asteroid;

    count = 0U;
    for (asteroid = 0U; asteroid < WC1_INTRO_ASTEROID_COUNT; asteroid++) {
        if (resource_intro_asteroids[asteroid].active != 0U)
            order[count++] = asteroid;
    }
    /* Draw_3Space_Frame() follows sort_object_depth(): far to near. */
    for (asteroid = 0U; asteroid < count; asteroid++) {
        uint16_t inner;

        for (inner = (uint16_t)(asteroid + 1U); inner < count; inner++) {
            IntroFixedVector left;
            IntroFixedVector right;

            left.x = resource_intro_asteroids[order[asteroid]].position.x -
                resource_intro_camera_position.x;
            left.y = resource_intro_asteroids[order[asteroid]].position.y -
                resource_intro_camera_position.y;
            left.z = resource_intro_asteroids[order[asteroid]].position.z -
                resource_intro_camera_position.z;
            right.x = resource_intro_asteroids[order[inner]].position.x -
                resource_intro_camera_position.x;
            right.y = resource_intro_asteroids[order[inner]].position.y -
                resource_intro_camera_position.y;
            right.z = resource_intro_asteroids[order[inner]].position.z -
                resource_intro_camera_position.z;
            if (intro_vector_magnitude(&left) < intro_vector_magnitude(&right)) {
                uint16_t swap;

                swap = order[asteroid];
                order[asteroid] = order[inner];
                order[inner] = swap;
            }
        }
    }
    for (asteroid = 0U; asteroid < count; asteroid++) {
        const IntroTitleAsteroid *current;
        IntroFixedVector direction;
        IntroFixedVector view_position;
        int32_t distance;
        int32_t denominator;
        int32_t scale;
        int32_t screen_x;
        int32_t screen_y;

        current = &resource_intro_asteroids[order[asteroid]];
        direction.x = current->position.x - resource_intro_camera_position.x;
        direction.y = current->position.y - resource_intro_camera_position.y;
        direction.z = current->position.z - resource_intro_camera_position.z;
        distance = intro_vector_magnitude(&direction);
        if (distance <= (100L << 8))
            continue;
        view_position.x = intro_dot_product(&direction,
                                            &resource_intro_camera_right);
        view_position.y = intro_dot_product(&direction,
                                            &resource_intro_camera_up);
        view_position.z = intro_dot_product(&direction,
                                            &resource_intro_camera_forward);
        if (view_position.z <= (100L << 8) ||
            intro_fixed_divide(view_position.z, distance) < 0x94)
            continue;
        denominator = distance - (100L << 8);
        if (denominator <= 0)
            continue;
        /* transform_objects_to_your_view() reduces to objectScale *
         * (screenWidth << 7) / (distance - collisionRadius) after the two
         * 24.8 MultiplyFixed/DivideFixed operations. Asteroid scale is 640. */
        scale = 640L * (FALCON_FRAME_WIDTH << 7) / denominator;
        if (scale < 5)
            continue;
        if (scale > 0x1fff)
            scale = 0x2000;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            view_position.x * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            view_position.y * (FALCON_FRAME_WIDTH >> 1) / view_position.z;
        (void)draw_shape_frame_scaled(resource_title_asteroid_data,
                                      resource_title_asteroid_size,
                                      current->frame, screen_x, screen_y,
                                      (uint16_t)scale);
    }
}

static void intro_camera_axes(IntroFixedVector *right, IntroFixedVector *up,
                              IntroFixedVector *forward)
{
    intro_copy_vector(right, &resource_intro_camera_right);
    intro_copy_vector(up, &resource_intro_camera_up);
    intro_copy_vector(forward, &resource_intro_camera_forward);
}

/* The Title_Sequence script is
 * { 0,-1000,0,-4263, 2,15, 1,0,30,0, 3,15, 4,30,1, 13, 14,400,-1 }.
 * In the original, command one establishes +30 degrees and command four
 * drains that pitch offset one degree per 3Space update. Stars are special:
 * transform_objects_to_your_view() projects their world positions directly,
 * without subtracting the camera position. That is why this limited port
 * needs the original orientation/projection math, but no fake parallax.
 */
static void reset_intro_scene_state(void)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    uint16_t star;
    uint16_t explosion;
    uint16_t laser;
    uint16_t debris;
    uint16_t asteroid;

    resource_intro_star_seed = 0x57433131UL;
    resource_intro_camera_pitch = 30;
    resource_intro_camera_position.x = -1000L * 256L;
    resource_intro_camera_position.y = 0;
    /* Update_3Space() advances command-two's 15-unit eye velocity before
     * its first draw. Store that first post-update position here; subsequent
     * title frames advance it below with the same 24.8 velocity. */
    resource_intro_camera_position.z = (-4263L + 15L) * 256L;
    resource_intro_camera_velocity.x = 0;
    resource_intro_camera_velocity.y = 0;
    resource_intro_camera_velocity.z = 15L << 8;
    resource_intro_camera_right.x = 256;
    resource_intro_camera_right.y = 0;
    resource_intro_camera_right.z = 0;
    resource_intro_camera_up.x = 0;
    resource_intro_camera_up.y = 256;
    resource_intro_camera_up.z = 0;
    resource_intro_camera_forward.x = 0;
    resource_intro_camera_forward.y = 0;
    resource_intro_camera_forward.z = 256;
    intro_alter_pitch(30, &resource_intro_camera_right,
                      &resource_intro_camera_up,
                      &resource_intro_camera_forward);
    resource_intro_explosion_count = 0U;
    for (explosion = 0U; explosion < WC1_INTRO_EXPLOSION_COUNT;
         explosion++) {
        resource_intro_explosions[explosion].position.x = 0;
        resource_intro_explosions[explosion].position.y = 0;
        resource_intro_explosions[explosion].position.z = 0;
        resource_intro_explosions[explosion].velocity.x = 0;
        resource_intro_explosions[explosion].velocity.y = 0;
        resource_intro_explosions[explosion].velocity.z = 0;
        resource_intro_explosions[explosion].scale = 0;
        resource_intro_explosions[explosion].frame = 0U;
        resource_intro_explosions[explosion].animation_index = 0U;
        resource_intro_explosions[explosion].active = 0U;
    }
    resource_intro_laser_count = 0U;
    for (laser = 0U; laser < WC1_INTRO_LASER_COUNT; laser++) {
        resource_intro_lasers[laser].position.x = 0;
        resource_intro_lasers[laser].position.y = 0;
        resource_intro_lasers[laser].position.z = 0;
        resource_intro_lasers[laser].velocity.x = 0;
        resource_intro_lasers[laser].velocity.y = 0;
        resource_intro_lasers[laser].velocity.z = 0;
        resource_intro_lasers[laser].ticks = 0U;
        resource_intro_lasers[laser].active = 0U;
    }
    resource_intro_debris_count = 0U;
    resource_intro_debris_dust_count = 0U;
    resource_intro_debris_seed = 0U;
    resource_intro_space_frame = 0U;
    for (debris = 0U; debris < WC1_INTRO_DEBRIS_COUNT; debris++) {
        resource_intro_debris[debris].position.x = 0;
        resource_intro_debris[debris].position.y = 0;
        resource_intro_debris[debris].position.z = 0;
        resource_intro_debris[debris].velocity.x = 0;
        resource_intro_debris[debris].velocity.y = 0;
        resource_intro_debris[debris].velocity.z = 0;
        resource_intro_debris[debris].type = 0U;
        resource_intro_debris[debris].frame = 0U;
        resource_intro_debris[debris].flip = 0U;
        resource_intro_debris[debris].animation_index = 0U;
        resource_intro_debris[debris].animation_delay = 0U;
        resource_intro_debris[debris].ticks = 0U;
        resource_intro_debris[debris].active = 0U;
    }
    for (debris = 0U; debris < WC1_INTRO_DEBRIS_DUST_COUNT; debris++) {
        resource_intro_debris_dust[debris].position.x = 0;
        resource_intro_debris_dust[debris].position.y = 0;
        resource_intro_debris_dust[debris].position.z = 0;
        resource_intro_debris_dust[debris].velocity.x = 0;
        resource_intro_debris_dust[debris].velocity.y = 0;
        resource_intro_debris_dust[debris].velocity.z = 0;
        resource_intro_debris_dust[debris].screen_angle = 0U;
        resource_intro_debris_dust[debris].ticks = 0U;
        resource_intro_debris_dust[debris].active = 0U;
    }
    resource_intro_asteroid_count = 0U;
    resource_intro_credit_seed = 0U;
    resource_intro_credit_frame = 0U;
    resource_intro_credit_scene_active = 0U;
    for (asteroid = 0U; asteroid < WC1_INTRO_ASTEROID_COUNT; asteroid++) {
        resource_intro_asteroids[asteroid].position.x = 0;
        resource_intro_asteroids[asteroid].position.y = 0;
        resource_intro_asteroids[asteroid].position.z = 0;
        resource_intro_asteroids[asteroid].velocity.x = 0;
        resource_intro_asteroids[asteroid].velocity.y = 0;
        resource_intro_asteroids[asteroid].velocity.z = 0;
        resource_intro_asteroids[asteroid].right.x = 0;
        resource_intro_asteroids[asteroid].right.y = 0;
        resource_intro_asteroids[asteroid].right.z = 0;
        resource_intro_asteroids[asteroid].up.x = 0;
        resource_intro_asteroids[asteroid].up.y = 0;
        resource_intro_asteroids[asteroid].up.z = 0;
        resource_intro_asteroids[asteroid].forward.x = 0;
        resource_intro_asteroids[asteroid].forward.y = 0;
        resource_intro_asteroids[asteroid].forward.z = 0;
        resource_intro_asteroids[asteroid].type = 0U;
        resource_intro_asteroids[asteroid].frame = 0U;
        resource_intro_asteroids[asteroid].animation_index = 0U;
        resource_intro_asteroids[asteroid].animation_delay = 0U;
        resource_intro_asteroids[asteroid].active = 0U;
    }
    reset_intro_fighter(&resource_intro_fighters[0], 10U, 160U, 10, 14, 10,
                        768, 0, 0, 0, intro_canned_sequence_32);
    reset_intro_fighter(&resource_intro_fighters[1], 10U, 160U, 10, 14, 10,
                        768, -154521L, -25600L, -232012L,
                        intro_canned_sequence_33);
    reset_intro_fighter(&resource_intro_fighters[2], 10U, 160U, 10, 14, 10,
                        768, -61849L, 25600L, -232012L,
                        intro_canned_sequence_34);
    reset_intro_fighter(&resource_intro_fighters[3], 0U, 100U, 8, 9, 8, 819,
                        324582L, 0, 696038L, intro_canned_sequence_35);
    intro_camera_axes(&right, &up, &forward);
    for (star = 0; star < WC1_INTRO_STAR_COUNT; star++) {
        IntroFixedVector star_right;
        IntroFixedVector star_up;
        IntroFixedVector star_forward;

        intro_copy_vector(&star_right, &right);
        intro_copy_vector(&star_up, &up);
        intro_copy_vector(&star_forward, &forward);
        intro_rotate_about_j(intro_signed_random(45), &star_right,
                             &star_forward);
        intro_rotate_about_i(intro_signed_random(45), &star_up,
                             &star_forward);
        resource_intro_star_position[star].x =
            intro_fixed_multiply(star_forward.x, 15000L << 8);
        resource_intro_star_position[star].y =
            intro_fixed_multiply(star_forward.y, 15000L << 8);
        resource_intro_star_position[star].z =
            intro_fixed_multiply(star_forward.z, 15000L << 8);
        resource_intro_star_frame[star] = (uint16_t)(32U +
            intro_random_below_or_equal(5U));
    }
}

void resource_reset_intro_scene(void)
{
    reset_intro_scene_state();
}

/* init_3Space_objects() calls init_constellation(), and generate_stars()
 * populates exactly seven far OBJECT_CLASS_STAR entries with PLANETS.VGA
 * frames 32 through 37. Project those stored 24.8 positions through the
 * title script's active eye axes, using transform_objects_to_your_view()'s
 * centre-of-screen projection. */
static void draw_intro_constellation(void)
{
    IntroFixedVector right;
    IntroFixedVector up;
    IntroFixedVector forward;
    uint16_t star;

    intro_camera_axes(&right, &up, &forward);
    for (star = 0; star < WC1_INTRO_STAR_COUNT; star++) {
        int32_t view_x;
        int32_t view_y;
        int32_t view_z;
        int32_t screen_x;
        int32_t screen_y;

        view_x = intro_dot_product(&resource_intro_star_position[star],
                                   &right);
        view_y = intro_dot_product(&resource_intro_star_position[star], &up);
        view_z = intro_dot_product(&resource_intro_star_position[star],
                                   &forward);
        /* This is the original eye collision-radius near plane: 100 << 8.
         * Keeping it avoids an unsafe perspective divide on a behind-camera
         * star while the 3Space depth sorter is still scoped separately. */
        if (view_z <= (100L << 8))
            continue;
        screen_x = (FALCON_FRAME_WIDTH >> 1) +
            (view_x * (FALCON_FRAME_WIDTH >> 1)) / view_z;
        screen_y = (FALCON_FRAME_HEIGHT >> 1) +
            (view_y * (FALCON_FRAME_WIDTH >> 1)) / view_z;
        (void)draw_shape_frame(resource_constellation_data,
                               resource_constellation_size,
                               resource_intro_star_frame[star],
                               screen_x, screen_y);
    }
}

/* Advance the recovered title simulation without touching the raster target.
 * The Falcon can spend several VBLs transferring one finished page; front.s
 * uses this bounded catch-up path so that transfer latency does not stretch
 * the source attract timeline. */
void resource_advance_intro_scene(uint16_t stage, uint16_t count)
{
    uint16_t update;

    if (stage == RESOURCE_INTRO_STAGE_CREDIT &&
        resource_intro_credit_scene_active == 0U)
        begin_intro_credit_scene();
    for (update = 0U; update < count; update++) {
        if (resource_intro_credit_scene_active == 0U) {
            update_intro_fighters();
            update_intro_explosions();
            update_intro_lasers();
            update_intro_debris();
            resource_intro_space_frame++;
        } else {
            update_intro_credit_scene();
        }
        if (resource_intro_camera_pitch > 0) {
            intro_alter_pitch(-1, &resource_intro_camera_right,
                              &resource_intro_camera_up,
                              &resource_intro_camera_forward);
            resource_intro_camera_pitch--;
        }
        resource_intro_camera_position.x += resource_intro_camera_velocity.x;
        resource_intro_camera_position.y += resource_intro_camera_velocity.y;
        resource_intro_camera_position.z += resource_intro_camera_velocity.z;
    }
}

/* Asset-backed frames of the DOS intro. The caller owns its Title_Sequence
 * timing and VBL publication. Advance the recovered camera script after
 * drawing, matching Update_3Space() before each following rendered frame. */
void resource_draw_intro_frame(uint8_t *target, uint16_t stage,
                               uint16_t index)
{
    render_target = target;
    if (target == 0)
        return;
    clear_intro_target(target);
    if ((resource_status & (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_TITLE))
        != (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_TITLE))
        return;
    /* Title frame count is part of the accepted Falcon capture contract. Its
     * callback must not reach a later phase merely because a target renderer
     * became faster, so keep the optimized axis-aligned flight path fenced
     * out while this function owns the attract raster. */
    resource_intro_rendering = 1U;
    /* The first credit call is exactly where Title_Sequence() switches from
     * action sphere 16 to record 36's asteroid field. From then through each
     * 40-frame credit-space gap and tail, stage SPACE belongs to that second
     * scene rather than to the departed Dralthi/Hornet action sphere. */
    /* Update_3Space() advances canned ships before set_eye_direction... and
     * Draw_3Space_Frame(). The title's initial 25-frame special path uses
     * the same object state, then recolours it through
     * intro_drawbackgroundships(). */
    resource_advance_intro_scene(stage, 1U);
    draw_intro_constellation();
    if (resource_intro_credit_scene_active != 0U) {
        draw_intro_credit_asteroids();
        if (stage == RESOURCE_INTRO_STAGE_CREDIT && index < 11U)
            draw_intro_text(resource_intro_credit_text[index]);
    } else if (stage == RESOURCE_INTRO_STAGE_OPENING) {
        draw_intro_text(resource_intro_opening_text);
        draw_intro_fighters(1);
        draw_intro_explosions(1);
        draw_intro_lasers(1);
        draw_intro_debris();
        draw_intro_debris_dust();
    } else if (stage == RESOURCE_INTRO_STAGE_LOGO) {
        draw_intro_fighters(0);
        draw_intro_explosions(0);
        draw_intro_lasers(0);
        draw_intro_debris();
        draw_intro_debris_dust();
        draw_intro_title_logo(index);
    } else if (stage != RESOURCE_INTRO_STAGE_CREDIT) {
        draw_intro_fighters(0);
        draw_intro_explosions(0);
        draw_intro_lasers(0);
        draw_intro_debris();
        draw_intro_debris_dust();
    }
    resource_intro_rendering = 0U;
}

/* Native Falcon presentation of the static endpoint of the DOS title
 * sequence. The title camera/star layer is active above; dust, ships, depth
 * sorting, and music remain separate porting slices. This preserves source
 * artwork and its entry into the title menu without replacement graphics. */
void resource_draw_title_screen(uint8_t *target, uint16_t selection)
{
    uint32_t pixel;
    uint8_t background;

    render_target = target;
    if (target == 0)
        return;
    background = 0U;
    for (pixel = 0; pixel < (uint32_t)FALCON_FRAME_WIDTH *
         FALCON_FRAME_HEIGHT; pixel++)
        target[pixel] = background;
    if ((resource_status & (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_TITLE))
        != (RESOURCE_STATUS_PALETTE | RESOURCE_STATUS_TITLE))
        return;

    /* Section zero is split around its centre origin. These anchors recreate
     * the unscaled, settled 320-pixel logo used before the menu waits. */
    (void)draw_shape_frame(resource_title_logo_data,
                           resource_title_logo_size, 0U, 106, 70);
    (void)draw_shape_frame(resource_title_logo_data,
                           resource_title_logo_size, 1U, 160, 70);
    (void)draw_shape_frame(resource_title_logo_data,
                           resource_title_logo_size, 2U, 214, 70);

    /* The stock title flow always exposes New Game (frame zero); save-game
     * selection and its campaign records have not yet been ported. */
    (void)selection;
    (void)draw_shape_frame(resource_title_menu_data,
                           resource_title_menu_size, 0U, 42, 164);
}
