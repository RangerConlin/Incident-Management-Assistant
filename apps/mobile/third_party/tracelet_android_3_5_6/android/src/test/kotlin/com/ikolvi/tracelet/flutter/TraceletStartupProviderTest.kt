package com.ikolvi.tracelet.flutter

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.ikolvi.tracelet.flutter.sync.HeadlessSyncInterceptor
import com.ikolvi.tracelet.sdk.TraceletBootstrap
import com.ikolvi.tracelet.sdk.TraceletSdk
import com.ikolvi.tracelet.sdk.sync.DartSyncInterceptor
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowLog
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Regression test for the cold-boot headless-sync bug: on a reboot the Flutter
 * plugin never attaches, so nothing wired `TraceletSdk.dartSyncInterceptor` or
 * `TraceletBootstrap.headlessDispatcherFactory`, and background sync could not
 * refresh the auth token or build the custom body. [TraceletStartupProvider]
 * runs at process start and installs the headless bridge.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TraceletStartupProviderTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        ShadowLog.stream = System.out
        context = ApplicationProvider.getApplicationContext()
        // Simulate a fresh process: nothing wired yet.
        TraceletBootstrap.headlessDispatcherFactory = null
        TraceletSdk.getInstance(context).dartSyncInterceptor = null
    }

    @After
    fun tearDown() {
        TraceletBootstrap.headlessDispatcherFactory = null
        TraceletSdk.getInstance(context).dartSyncInterceptor = null
    }

    @Test
    fun `onCreate installs the headless sync bridge when nothing is wired`() {
        Robolectric.buildContentProvider(TraceletStartupProvider::class.java).create()

        assertNotNull(
            TraceletBootstrap.headlessDispatcherFactory,
            "headlessDispatcherFactory must be installed at process start",
        )
        val interceptor = TraceletSdk.getInstance(context).dartSyncInterceptor
        assertTrue(
            interceptor is HeadlessSyncInterceptor,
            "dartSyncInterceptor must be a HeadlessSyncInterceptor on a headless (no-UI) process",
        )
    }

    @Test
    fun `onCreate does not override an interceptor already set by the UI engine`() {
        val existing = object : DartSyncInterceptor {
            override fun requestSyncBody(locations: List<Map<String, Any?>>): String? = null
            override fun requestFreshHeaders(): Boolean = false
            override fun requestTokenRefresh(): Boolean = false
        }
        TraceletSdk.getInstance(context).dartSyncInterceptor = existing

        Robolectric.buildContentProvider(TraceletStartupProvider::class.java).create()

        assertSame(
            existing,
            TraceletSdk.getInstance(context).dartSyncInterceptor,
            "the richer main-engine interceptor must not be clobbered by the startup provider",
        )
    }
}
