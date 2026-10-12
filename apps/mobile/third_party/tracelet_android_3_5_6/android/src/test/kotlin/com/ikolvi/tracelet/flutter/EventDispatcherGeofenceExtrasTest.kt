package com.ikolvi.tracelet.flutter

import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Regression test for #58: geofence extras must reach the headless fallback
 * (and equivalently the Pigeon FlutterApi) as a real Map, not as null/empty.
 *
 * This exercises the dispatch path that runs after the SDK reads a geofence
 * back from SQLite via cursorToGeofence (already covered by
 * GeofenceExtrasRoundTripTest in the SDK module). Here we verify that
 * EventDispatcher does not silently drop the parsed Map when forwarding to
 * the headless fallback.
 */
@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE)
internal class EventDispatcherGeofenceExtrasTest {

    @Test
    fun headlessFallback_receivesExtrasAsMap() {
        val dispatcher = EventDispatcher()

        var capturedEventName: String? = null
        var capturedData: Map<String, Any?>? = null
        dispatcher.headlessFallback = { name, data ->
            capturedEventName = name
            capturedData = data
        }

        // This is exactly the shape GeofenceManager.handleGeofenceEvent / the
        // high-accuracy path produce after cursorToGeofence parses the JSON
        // back into a Map.
        val extras = mapOf<String, Any?>(
            "demo_test" to "Hello from the geofence extras!",
            "Hello" to "World",
        )
        val eventData = mapOf<String, Any?>(
            "identifier" to "test_zone_2",
            "action" to "ENTER",
            "location" to mapOf(
                "coords" to mapOf(
                    "latitude" to 12.345,
                    "longitude" to 67.89,
                ),
            ),
            "extras" to extras,
        )

        dispatcher.sendGeofence(eventData)

        assertEquals("geofence", capturedEventName)
        assertNotNull(capturedData)
        @Suppress("UNCHECKED_CAST")
        val forwardedExtras = capturedData!!["extras"] as? Map<String, Any?>
        assertNotNull(
            forwardedExtras,
            "Headless fallback must receive extras as a Map (#58)",
        )
        assertTrue(forwardedExtras.isNotEmpty(), "extras must not be empty")
        assertEquals("Hello from the geofence extras!", forwardedExtras["demo_test"])
        assertEquals("World", forwardedExtras["Hello"])
    }

    @Test
    fun headlessFallback_extrasNullStaysNull() {
        val dispatcher = EventDispatcher()

        var capturedData: Map<String, Any?>? = null
        dispatcher.headlessFallback = { _, data -> capturedData = data }

        val eventData = mapOf<String, Any?>(
            "identifier" to "no_extras_zone",
            "action" to "EXIT",
            "location" to mapOf(
                "coords" to mapOf("latitude" to 0.0, "longitude" to 0.0),
            ),
            "extras" to null,
        )

        dispatcher.sendGeofence(eventData)

        assertNotNull(capturedData)
        // Null in → null out (the Pigeon TlGeofenceEvent.extras field is
        // nullable; the Dart-side GeofenceEvent.fromMap treats null as an
        // empty map).
        assertEquals(null, capturedData!!["extras"])
    }
}
