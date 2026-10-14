#ifndef WC1_FALCON_DATA_H
#define WC1_FALCON_DATA_H

/*
 * Packed campaign records from wc1-re/src/cmpgn.c.  These are deliberately
 * kept separate from the 68030 assembly until the packet loader is verified.
 */
#include <stddef.h>
#include <stdint.h>

typedef struct {
    int32_t x;
    int32_t y;
    int32_t z;
} Wc1FixedVector;

#pragma pack(push, 1)
typedef struct {
    int16_t entry_nav_point;
    int16_t home_mission_ship;
    int16_t player_mission_ship;
    int16_t initial_mission_ships[8];
    int16_t reserved;
} Wc1MissionHeaderDisk;

typedef struct {
    char name[30];
    int8_t type;
    Wc1FixedVector position;
    uint16_t proximity_radius;
    int8_t triggers[4][2];
    int16_t preload_object_types[2];
    int16_t mission_ships[10];
} Wc1MissionNavPointDisk;

typedef struct {
    int16_t type;
    int16_t index;
    char description[60];
} Wc1MissionObjectiveDisk;

typedef struct {
    int16_t type;
    int16_t side;
    int8_t leader;
    int8_t reserved_05;
    int16_t mission_type;
    int8_t nav_point;
    Wc1FixedVector position;
    int16_t pitch;
    int16_t yaw;
    int16_t roll;
    int8_t formation_spot;
    int16_t speed;
    int16_t rating;
    int16_t pilot;
    int16_t reserved_2c;
    int16_t reserved_2e;
    int8_t state;
    int8_t leader_mission_index;
    int8_t formation_index;
    int8_t target_mission_index;
} Wc1MissionShipDisk;
#pragma pack(pop)

typedef char MissionHeaderDisk_size_must_be_0x18[
    sizeof(Wc1MissionHeaderDisk) == 0x18 ? 1 : -1];
typedef char MissionNavPointDisk_size_must_be_0x4d[
    sizeof(Wc1MissionNavPointDisk) == 0x4d ? 1 : -1];
typedef char MissionObjectiveDisk_size_must_be_0x40[
    sizeof(Wc1MissionObjectiveDisk) == 0x40 ? 1 : -1];
typedef char MissionShipDisk_size_must_be_0x2a[
    sizeof(Wc1MissionShipDisk) == 0x2a ? 1 : -1];

enum Wc1ObjectType {
    WC1_OBJECT_HORNET = 0,
    WC1_OBJECT_RAPIER = 1,
    WC1_OBJECT_SCIMITAR = 2,
    WC1_OBJECT_RAPTOR = 3,
    WC1_OBJECT_SALTHI = 9,
    WC1_OBJECT_DRALTHI = 10,
    WC1_OBJECT_KRANT = 11,
    WC1_OBJECT_LASER = 24,
    WC1_OBJECT_NEUTRON_GUN = 25,
    WC1_OBJECT_MASS_DRIVER = 26,
    WC1_OBJECT_DUMB_FIRE_MISSILE = 28,
    WC1_OBJECT_HEAT_SEEKING_MISSILE = 29,
};

#endif
