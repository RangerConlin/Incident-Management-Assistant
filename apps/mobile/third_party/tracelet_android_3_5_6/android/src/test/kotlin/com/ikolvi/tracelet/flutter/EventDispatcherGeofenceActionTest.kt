package com.ikolvi.tracelet.flutter

import com.ikolvi.tracelet.TlGeofenceAction
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import kotlin.test.assertEquals

/**
 * Regression test: geofence ENTER/EXIT/DWELL must survive the trip from the
 * SDK's structured payload to the Pigeon [com.ikolvi.tracelet.TlGeofenceEvent].
 *
 * The SDK ([com.ikolvi.tracelet.sdk.geofence.GeofenceManager]) emits geofence
 * events as a structured payload — identifier/action/extras nested under
 * `"geofence"`, location coords at the top-level `"coords"`. A prior version of
 * [EventDispatcher] read `action`/`identifier`/`location` from the TOP level, so
 * every field was `null` and `action` silently defaulted to `ENTER` — meaning
 * EXIT (and DWELL) transitions reached Dart as ENTER. This pins the mapping so
 * that can't regress.
 */
@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE)
internal class EventDispatcherGeofenceActionTest {

    /** The exact shape GeofenceManager.handleGeofenceEvent / the high-accuracy
     *  path produce for a transition. */
    private fun structuredPayload(action: String): Map<String, Any?> = mapOf(
        "uuid" to "abc-123",
        "event" to "geofence",
        "timestamp" to "2026-06-09T00:00:00.000Z",
        "coords" to mapOf(
            "latitude" to 12.345,
            "longitude" to 67.890,
            "accuracy" to 0.0,
            "speed" to 0.0,
            "heading" to 0.0,
            "altitude" to 0.0,
        ),
        "geofence" to mapOf(
            "identifier" to "office",
            "action" to action,
            "extras" to mapOf("tier" to "gold"),
        ),
    )

    @Test
    fun structuredPayload_exit_mapsToExit() {
        val event = EventDispatcher().buildGeofenceEvent(structuredPayload("EXIT"))

        assertEquals(TlGeofenceAction.EXIT, event.action, "EXIT must not be mislabeled as ENTER")
        assertEquals("office", event.identifier, "identifier must come from the nested geofence map")
        assertEquals(12.345, event.location.coords.latitude, "location must come from top-level coords")
        assertEquals(67.890, event.location.coords.longitude)
        assertEquals("gold", event.extras?.get("tier"), "extras must come from the nested geofence map")
    }

    @Test
    fun structuredPayload_enter_mapsToEnter() {
        val event = EventDispatcher().buildGeofenceEvent(structuredPayload("ENTER"))
        assertEquals(TlGeofenceAction.ENTER, event.action)
        assertEquals("office", event.identifier)
    }

    @Test
    fun structuredPayload_dwell_mapsToDwell() {
        val event = EventDispatcher().buildGeofenceEvent(structuredPayload("DWELL"))
        assertEquals(TlGeofenceAction.DWELL, event.action)
    }

    @Test
    fun legacyFlatPayload_exit_stillMapsToExit() {
        // Backward-compatibility: the old flat shape must keep working.
        val legacy = mapOf<String, Any?>(
            "identifier" to "legacy_zone",
            "action" to "EXIT",
            "location" to mapOf(
                "coords" to mapOf("latitude" to 1.0, "longitude" to 2.0),
            ),
            "extras" to mapOf("k" to "v"),
        )

        val event = EventDispatcher().buildGeofenceEvent(legacy)

        assertEquals(TlGeofenceAction.EXIT, event.action)
        assertEquals("legacy_zone", event.identifier)
        assertEquals(1.0, event.location.coords.latitude)
        assertEquals("v", event.extras?.get("k"))
    }

    @Test
    fun unknownOrMissingAction_defaultsToEnter() {
        val event = EventDispatcher().buildGeofenceEvent(
            mapOf("geofence" to mapOf("identifier" to "x")),
        )
        assertEquals(TlGeofenceAction.ENTER, event.action)
    }

    /**
     * #231: the SDK now enriches the geofence payload with real coordinate
     * metrics and a top-level `battery` map. Pin that both survive the mapping
     * to the Pigeon [com.ikolvi.tracelet.TlGeofenceEvent] (the foreground path).
     */
    @Test
    fun structuredPayload_enrichedCoordsAndBattery_surviveMapping() {
        val enriched = mapOf<String, Any?>(
            "uuid" to "abc-231",
            "event" to "geofence",
            "timestamp" to "2026-06-30T00:00:00.000Z",
            "coords" to mapOf(
                "latitude" to 12.345,
                "longitude" to 67.890,
                "accuracy" to 25.0,
                "speed" to 3.5,
                "heading" to 90.0,
                "altitude" to 100.0,
            ),
            "battery" to mapOf(
                "level" to 0.42,
                "is_charging" to true,
            ),
            "geofence" to mapOf(
                "identifier" to "office",
                "action" to "ENTER",
                "extras" to mapOf("tier" to "gold"),
            ),
        )

        val event = EventDispatcher().buildGeofenceEvent(enriched)

        assertEquals(25.0, event.location.coords.accuracy, "accuracy must survive (was 0.0)")
        assertEquals(3.5, event.location.coords.speed, "speed must survive (was 0.0)")
        assertEquals(90.0, event.location.coords.heading, "heading must survive (was 0.0)")
        assertEquals(100.0, event.location.coords.altitude, "altitude must survive (was 0.0)")
        assertEquals(0.42, event.location.battery.level, "battery level must survive (was -1.0)")
        assertEquals(true, event.location.battery.isCharging, "battery isCharging must survive")
    }
}
