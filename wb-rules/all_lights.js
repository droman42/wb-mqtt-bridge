// All-lights aggregate (VWB-10, 2026-07-04).
//
// Implements the controller side of the bridge contract defined in
// config/devices/wb-devices/global/all_lights.json: the bridge (and the
// WB UI / future Alisa) writes 1/0 to /devices/all_lights/controls/power/on;
// this rule fans the command out to every true light in the flat.
//
// The fan-out list mirrors the bridge's room configs (capability_profile
// light_switch + dimmable_light, all rooms except global) — 36 lights as of
// 2026-07-04. Dimmable lights are driven through the same on/off relay
// controls the bridge's power_on/power_off commands use (brightness channels
// are untouched — a light re-lights at its last level).
//
// State semantics: the virtual switch reflects the LAST COMMANDED value, not
// a computed "any light on" aggregate (keep it simple; individual switches
// remain individually usable).

defineVirtualDevice("all_lights", {
    title: "Весь свет",
    cells: {
        power: { type: "switch", value: false }
    }
});

var ALL_LIGHTS = [
    // bathroom
    "wb-mr6c_52/K2",                    // bathroom_mirror
    "wb-mr6c_58/K6",                    // bathroom_shelf_bath
    "wb-mr6c_58/K5",                    // bathroom_shelf_toilet
    "wb-mdm3_95/K2",                    // bathroom_spots (dimmable)
    // bedroom
    "wb-mr6c_58/K4",                    // bedroom_nightstand_left
    "wb-mr6c_58/K3",                    // bedroom_nightstand_right
    "wb-mr6c_52/K1",                    // bedroom_sconce_left
    "wb-mr6c_51/K6",                    // bedroom_sconce_right
    "wb-mrgbw-d-fw3_10/Channel 1 (B)",  // bedroom_shelves_light (dimmable)
    "wb-mdm3_95/K1",                    // bedroom_spots (dimmable)
    "wb-mrgbw-d-fw3_10/Channel 3 (G)",  // bedroom_window_light (dimmable)
    // cabinet
    "wb-mrgbw-d-fw3_238/Channel 2 (R)", // cabinet_backlight (dimmable)
    "wb-mr6c_51/K4",                    // cabinet_spots
    // children_room
    "wb-mr6c_51/K2",                    // children_room_behind_column
    "wb-mr6c_51/K3",                    // children_room_by_wardrobe
    "wb-mrgbw-d-fw3_11/RGB Strip",      // children_room_ceiling_accent
    "wb-mdm3_87/K3",                    // children_room_spots (dimmable)
    // entrance
    "wb-mr6c_52/K5",                    // entrance_cabinet_accent
    "wb-mdm3_83/K1",                    // entrance_spots (dimmable)
    // hall
    "wb-mdm3_87/K2",                    // hall_spots (dimmable)
    "wb-mr6c_51/K1",                    // hall_track_1
    "wb-mr6c_52/K3",                    // hall_track_2
    // kitchen
    "wb-mr6c_47/K6",                    // kitchen_backlight
    "wb-mr6c_47/K5",                    // kitchen_chandelier
    "wb-mdm3_87/K1",                    // kitchen_spots (dimmable)
    // living_room
    "wb-mr6c_47/K4",                    // living_room_desk_lamp
    "wb-mr6c_47/K3",                    // living_room_floor_lamp
    "wb-mdm3_83/K3",                    // living_room_spots (dimmable)
    "wb-mr6c_58/K2",                    // living_room_union_cabinet
    "wb-mr6c_58/K1",                    // living_room_window_light
    // shower
    "wb-mr6c_47/K2",                    // shower_mirror
    "wb-mrgbw-d-fw3_238/Channel 1 (B)", // shower_sauna (dimmable)
    "wb-mr6c_52/K6",                    // shower_service_closet
    "wb-mdm3_83/K2",                    // shower_spots (dimmable)
    // wardrobe
    "wb-mrgbw-d-fw3_10/Channel 2 (R)",  // wardrobe_shelves_light (dimmable)
    "wb-mr6c_51/K5"                     // wardrobe_spots
];

defineRule("All Lights Fan-out", {
    whenChanged: ["all_lights/power"],
    then: function(newValue, devName, cellName) {
        log("all_lights/power -> " + newValue + " (fanning out to " + ALL_LIGHTS.length + " lights)");
        for (var i = 0; i < ALL_LIGHTS.length; i++) {
            dev[ALL_LIGHTS[i]] = newValue;
        }
    }
});
