-- AYN Odin 2 Portal with the Visionox VTDR6130 panel (1080x1920 DSI, DSC,
-- command mode). Needs kernel patch 0101: the panel then reports an EDID
-- (PNP "AYN", "Odin2 Portal") and runs any front-porch-stretched mode at its
-- own rate (frame length 0xb1 = vertical front porch).
--
-- Colour and HDR values are the factory ones from Android's
-- qdcm_calib_data_vtdr6130_amoled_cmd_mode_dsi_visionox_1080p_panel_with_DSC
-- (HDR blob: DCIP3, gamma 2.2, 736.885681 nits at 100 % APL, 0.002 nits min,
-- SDR peak 400 nits; PCC identity, so no per-unit correction).

local portal_refresh_rates = {}
for hz = 40, 120 do
    table.insert(portal_refresh_rates, hz)
end

gamescope.config.known_displays.ayn_odin2portal_vtdr6130 = {
    pretty_name = "AYN Odin 2 Portal (Visionox VTDR6130)",
    colorimetry = {
        r = { x = 0.680,  y = 0.320 },
        g = { x = 0.265,  y = 0.690 },
        b = { x = 0.150,  y = 0.060 },
        w = { x = 0.3127, y = 0.3290 },
    },
    dynamic_refresh_rates = portal_refresh_rates,
    hdr = {
        supported = true,
        force_enabled = false,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 736.885681,
        max_frame_average_luminance = 736.885681,
        min_content_light_level = 0.002,
    },
    dynamic_modegen = function(base_mode, refresh)
        -- 120 Hz: 289644 kHz, htotal 1234, vdisplay 1920, VFP 18, vsync 4,
        -- vback 14 -> vtotal 1956. Keep the clock, grow the front porch.
        local htotal = 1234
        local vtotal = math.floor(289644 * 1000 / (htotal * refresh) + 0.5)
        local vfp = vtotal - 1920 - 4 - 14
        if vfp < 18 then
            warn("[odin2portal] refusing " .. refresh .. " Hz (vfp " .. vfp .. ")")
            return base_mode
        end
        debug("[odin2portal] " .. refresh .. " Hz: vfp " .. vfp .. " vtotal " .. vtotal)
        local mode = base_mode
        gamescope.modegen.adjust_front_porch(mode, vfp)
        mode.vrefresh = gamescope.modegen.calc_vrefresh(mode)
        return mode
    end,
    matches = function(display)
        if display.vendor == "AYN" and display.model == "Odin2 Portal" then
            debug("[odin2portal] Matched AYN Odin2 Portal")
            return 5000
        end
        return -1
    end,
}
debug("Registered AYN Odin 2 Portal (VTDR6130) as a known display")
