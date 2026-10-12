package com.ikolvi.tracelet.flutter

import android.content.Context
import com.ikolvi.tracelet.TlAuthorizationStatus
import com.ikolvi.tracelet.flutter.service.HeadlessTaskService
import org.junit.Test
import org.mockito.Mockito.mock
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class TraceletHostApiImplTest {

    @Test
    fun testRegisterHeadlessHeadersCallback_delegatesToService() {
        val context = mock(Context::class.java)
        val headlessService = mock(HeadlessTaskService::class.java)
        val hostApi = TraceletHostApiImpl(context, headlessService)

        hostApi.registerHeadlessHeadersCallback(listOf(100L, 200L)) {}

        org.mockito.Mockito.verify(headlessService).registerCallbacks(
            HeadlessTaskService.CallbackType.HEADERS,
            100L,
            200L
        )
    }

    @Test
    fun testRegisterHeadlessSyncBodyBuilder_delegatesToService() {
        val context = mock(Context::class.java)
        val headlessService = mock(HeadlessTaskService::class.java)
        val hostApi = TraceletHostApiImpl(context, headlessService)

        hostApi.registerHeadlessSyncBodyBuilder(listOf(300L, 400L)) {}

        org.mockito.Mockito.verify(headlessService).registerCallbacks(
            HeadlessTaskService.CallbackType.SYNC_BODY,
            300L,
            400L
        )
    }

    @Test
    fun testTlConfigMapping_containsAllProperties() {
        val context = mock(Context::class.java)
        val headlessService = mock(HeadlessTaskService::class.java)
        val hostApi = TraceletHostApiImpl(context, headlessService)

        val method = TraceletHostApiImpl::class.java.getDeclaredMethod(
            "tlConfigToSdkMap",
            com.ikolvi.tracelet.TlConfig::class.java
        )
        method.isAccessible = true

        val mockConfig = mock(com.ikolvi.tracelet.TlConfig::class.java, org.mockito.Mockito.RETURNS_DEEP_STUBS)
        
        // Just mock the 'raw' values so we don't need actual enum instances
        org.mockito.Mockito.`when`(mockConfig.http.method.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.http.locationsOrderDirection.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.motion.motionDetectionMode.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.motion.stationaryTrackingMode.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.motion.stationaryPeriodicAccuracy.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.geo.desiredAccuracy.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.geo.periodicDesiredAccuracy.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.geo.filter.policy.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.android.foregroundService.notificationPriority.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.logger.logLevel.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.persistence.persistMode.raw).thenReturn(0)
        org.mockito.Mockito.`when`(mockConfig.audit.hashAlgorithm.raw).thenReturn(0)

        @Suppress("UNCHECKED_CAST")
        val map = method.invoke(hostApi, mockConfig) as Map<String, Any?>

        val httpMap = map["http"] as Map<String, Any?>
        val motionMap = map["motion"] as Map<String, Any?>

        val httpFields = com.ikolvi.tracelet.TlHttpConfig::class.java.declaredFields.map { it.name }.filter { it != "\$stable" && it != "Companion" }
        for (field in httpFields) {
            assertTrue(
                httpMap.containsKey(field),
                "Missing field in HTTP mapping: $field"
            )
        }

        val motionFields = com.ikolvi.tracelet.TlMotionConfig::class.java.declaredFields.map { it.name }.filter { it != "\$stable" && it != "Companion" }
        for (field in motionFields) {
            assertTrue(
                motionMap.containsKey(field),
                "Missing field in Motion mapping: $field"
            )
        }
    }
}
