package com.ikolvi.tracelet.flutter

import android.content.Context
import com.ikolvi.tracelet.TlCurrentPositionOptions
import com.ikolvi.tracelet.TlDesiredAccuracy
import com.ikolvi.tracelet.TlGeofence
import com.ikolvi.tracelet.TlLocation
import com.ikolvi.tracelet.flutter.service.HeadlessTaskService
import org.junit.Test
import org.mockito.Mockito.mock
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Field-by-field regression tests for the native-map ↔ Pigeon converters in
 * [TraceletHostApiImpl] (#175). These guard the exact key contracts between the
 * SDK's enriched location map (snake_case: `is_moving`, `is_charging`) and the
 * Pigeon [TlLocation], and that `getCurrentPosition` options (extras /
 * desiredAccuracy) are forwarded to the SDK. They fail if any field is dropped
 * or read under the wrong key — the class of bug reported in #175.
 */
class LocationMappingRegressionTest {

    private fun hostApi(): TraceletHostApiImpl =
        TraceletHostApiImpl(mock(Context::class.java), mock(HeadlessTaskService::class.java))

    /** Invokes the private `mapToTlLocation(Map)` via reflection. */
    private fun mapToTlLocation(m: Map<String, Any?>): TlLocation {
        val method = TraceletHostApiImpl::class.java
            .getDeclaredMethod("mapToTlLocation", Map::class.java)
        method.isAccessible = true
        return method.invoke(hostApi(), m) as TlLocation
    }

    /** Invokes the private `tlOptionsToMap(TlCurrentPositionOptions)` via reflection. */
    @Suppress("UNCHECKED_CAST")
    private fun tlOptionsToMap(o: TlCurrentPositionOptions): Map<String, Any?> {
        val method = TraceletHostApiImpl::class.java
            .getDeclaredMethod("tlOptionsToMap", TlCurrentPositionOptions::class.java)
        method.isAccessible = true
        return method.invoke(hostApi(), o) as Map<String, Any?>
    }

    /** Invokes the private `tlGeofenceToMap(TlGeofence)` via reflection. */
    @Suppress("UNCHECKED_CAST")
    private fun tlGeofenceToMap(g: TlGeofence): Map<String, Any?> {
        val method = TraceletHostApiImpl::class.java
            .getDeclaredMethod("tlGeofenceToMap", TlGeofence::class.java)
        method.isAccessible = true
        return method.invoke(hostApi(), g) as Map<String, Any?>
    }

    /** A native enriched location map, exactly as the SDK emits it (snake_case). */
    private fun enrichedMap(): Map<String, Any?> = mapOf(
        "uuid" to "uuid-123",
        "timestamp" to "2026-06-15T10:00:00.000Z",
        "is_moving" to true,                       // snake_case — the #175 bug key
        "odometer" to 1234.5,
        "event" to "location",
        "coords" to mapOf(
            "latitude" to 37.4220,
            "longitude" to -122.0841,
            "accuracy" to 8.0,
            "speed" to 14.0,
            "heading" to 90.0,
            "altitude" to 12.0,
            "altitudeAccuracy" to 3.0,
            "speedAccuracy" to 1.0,
            "headingAccuracy" to 2.0,
        ),
        "activity" to mapOf("type" to "in_vehicle", "confidence" to 95),
        "battery" to mapOf("level" to 0.87, "is_charging" to true), // snake_case — the #175 bug key
        "extras" to mapOf("alarm" to "sos"),
        "address" to mapOf("city" to "Mountain View", "country" to "US"),
    )

    @Test
    fun mapToTlLocation_roundtrips_every_field() {
        val loc = mapToTlLocation(enrichedMap())

        // Identity / motion
        assertEquals("uuid-123", loc.uuid)
        assertEquals("2026-06-15T10:00:00.000Z", loc.timestamp)
        assertEquals("location", loc.event)
        assertEquals(1234.5, loc.odometer)
        assertTrue(loc.isMoving, "isMoving must come from native `is_moving` (#175)")

        // Coords
        assertEquals(37.4220, loc.coords.latitude)
        assertEquals(-122.0841, loc.coords.longitude)
        assertEquals(8.0, loc.coords.accuracy)
        assertEquals(14.0, loc.coords.speed)
        assertEquals(90.0, loc.coords.heading)
        assertEquals(12.0, loc.coords.altitude)

        // Battery — the regression: level must be real and isCharging must come
        // from native `is_charging`, not default false.
        assertEquals(0.87, loc.battery.level)
        assertTrue(loc.battery.isCharging, "isCharging must come from native `is_charging` (#175)")

        // Activity
        assertEquals("in_vehicle", loc.activity?.type)
        assertEquals(95L, loc.activity?.confidence)

        // Extras must survive (not be dropped)
        assertEquals("sos", loc.extras?.get("alarm"))

        // Address
        assertEquals("Mountain View", loc.address?.city)
        assertEquals("US", loc.address?.country)
    }

    @Test
    fun mapToTlLocation_accepts_camelCase_battery_and_moving_too() {
        // Robustness: if a path ever emits camelCase, it must still parse.
        val m = enrichedMap().toMutableMap().apply {
            this["is_moving"] = null
            this["isMoving"] = true
            this["battery"] = mapOf("level" to 0.5, "isCharging" to true)
        }
        val loc = mapToTlLocation(m)
        assertTrue(loc.isMoving)
        assertTrue(loc.battery.isCharging)
    }

    @Test
    fun tlOptionsToMap_forwards_extras_and_desiredAccuracy() {
        val opts = TlCurrentPositionOptions(
            desiredAccuracy = TlDesiredAccuracy.HIGH,
            timeout = 30,
            maximumAge = 0,
            persist = true,
            samples = 1,
            extras = mapOf("alarm" to "sos"),
        )
        val map = tlOptionsToMap(opts)

        assertEquals(30L, map["timeout"])
        assertEquals(0L, map["maximumAge"])
        assertEquals(true, map["persist"])
        assertEquals(1L, map["samples"])
        // The #175 fixes: these were previously dropped.
        assertEquals(0, map["desiredAccuracy"], "desiredAccuracy must be forwarded (#175)")
        @Suppress("UNCHECKED_CAST")
        val extras = map["extras"] as? Map<String?, Any?>
        assertEquals("sos", extras?.get("alarm"), "extras must be forwarded to the SDK (#175)")
    }

    /**
     * Phase 1 (#206) completeness guard: every property of the Pigeon
     * [TlCurrentPositionOptions] must be present in the SDK map after conversion.
     * With all fields set to sentinels, a forgotten field in `tlOptionsToMap`
     * (the exact #175/#201 failure mode) makes this fail automatically — and a
     * newly-added Pigeon field that isn't mapped trips it too.
     */
    @Test
    fun tlOptionsToMap_covers_every_pigeon_field() {
        val opts = TlCurrentPositionOptions(
            desiredAccuracy = TlDesiredAccuracy.PASSIVE,
            timeout = 11,
            maximumAge = 22,
            persist = false,
            samples = 3,
            extras = mapOf("k" to "v"),
        )
        val map = tlOptionsToMap(opts)

        val fields = TlCurrentPositionOptions::class.java.declaredFields
            .map { it.name }
            .filterNot { it.startsWith("$") || it == "Companion" || it == "CREATOR" }
        for (field in fields) {
            assertTrue(
                map.containsKey(field),
                "tlOptionsToMap dropped Pigeon field '$field' (#206) — add it to the converter",
            )
        }
    }

    /**
     * Phase 3 (#206) completeness guard for the geofence input converter: every
     * property of the Pigeon [TlGeofence] must survive into the SDK map. A
     * forgotten/newly-added field fails this automatically.
     */
    @Test
    fun tlGeofenceToMap_covers_every_pigeon_field() {
        val geofence = TlGeofence(
            identifier = "g1",
            latitude = 1.0,
            longitude = 2.0,
            radius = 3.0,
            notifyOnEntry = true,
            notifyOnExit = true,
            notifyOnDwell = true,
            loiteringDelay = 5L,
            extras = mapOf("k" to "v"),
            vertices = listOf(listOf(1.0, 2.0)),
        )
        val map = tlGeofenceToMap(geofence)

        val fields = TlGeofence::class.java.declaredFields
            .map { it.name }
            .filterNot { it.startsWith("$") || it == "Companion" || it == "CREATOR" }
        for (field in fields) {
            assertTrue(
                map.containsKey(field),
                "tlGeofenceToMap dropped Pigeon field '$field' (#206) — add it to the converter",
            )
        }
    }
}
