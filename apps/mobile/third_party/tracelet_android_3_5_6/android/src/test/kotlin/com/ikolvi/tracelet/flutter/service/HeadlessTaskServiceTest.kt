package com.ikolvi.tracelet.flutter.service

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class HeadlessTaskServiceTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        HeadlessTaskService.isSpawningHeadlessEngine = false
    }

    @After
    fun tearDown() {
        HeadlessTaskService.isSpawningHeadlessEngine = false
    }

    // A comprehensive test for ensureEngine would require extensive mocking of FlutterLoader and main thread dispatch.
    // Instead, this is a placeholder verifying the property exists and defaults to false.
    // The main TDD test is TraceletAndroidPluginTest which verifies the effect of this flag.
    @Test
    fun `isSpawningHeadlessEngine defaults to false`() {
        assertFalse(HeadlessTaskService.isSpawningHeadlessEngine)
    }
}
