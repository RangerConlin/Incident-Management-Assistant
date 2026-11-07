import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../models/home_nav_args.dart';
import '../widgets/app_drawer.dart';

typedef QrScannerViewBuilder =
    Widget Function(BuildContext context, ValueChanged<String> onScan);

/// Camera-based QR utility for field equipment, location, team, and incident
/// codes. Interpreting a scanned payload belongs to the workflow that consumes
/// it; this screen deliberately preserves and displays the exact QR contents.
class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key, required this.args, this.scannerBuilder});

  final HomeNavArgs args;

  @visibleForTesting
  final QrScannerViewBuilder? scannerBuilder;

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen>
    with WidgetsBindingObserver {
  late final MobileScannerController _controller;
  StreamSubscription<BarcodeCapture>? _barcodeSubscription;
  String? _result;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _controller = MobileScannerController(
      autoStart: false,
      detectionSpeed: DetectionSpeed.noDuplicates,
      formats: const [BarcodeFormat.qrCode],
    );
    if (widget.scannerBuilder == null) {
      _barcodeSubscription = _controller.barcodes.listen(_handleCapture);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          unawaited(_controller.start());
        }
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (widget.scannerBuilder != null ||
        !_controller.value.hasCameraPermission ||
        _result != null) {
      return;
    }

    switch (state) {
      case AppLifecycleState.resumed:
        _barcodeSubscription ??= _controller.barcodes.listen(_handleCapture);
        unawaited(_controller.start());
      case AppLifecycleState.inactive:
        unawaited(_barcodeSubscription?.cancel());
        _barcodeSubscription = null;
        unawaited(_controller.stop());
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
        return;
    }
  }

  void _handleCapture(BarcodeCapture capture) {
    for (final barcode in capture.barcodes) {
      final value = barcode.rawValue;
      if (value != null && value.isNotEmpty) {
        _acceptResult(value);
        return;
      }
    }
  }

  void _acceptResult(String value) {
    if (!mounted || _result != null || value.isEmpty) {
      return;
    }
    setState(() => _result = value);
    if (_controller.value.isRunning) {
      unawaited(_controller.stop());
    }
  }

  Future<void> _scanAnother() async {
    setState(() => _result = null);
    if (widget.scannerBuilder == null) {
      _barcodeSubscription ??= _controller.barcodes.listen(_handleCapture);
      await _controller.start();
    }
  }

  Future<void> _copyResult() async {
    final result = _result;
    if (result == null) {
      return;
    }
    await Clipboard.setData(ClipboardData(text: result));
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('QR contents copied.')));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_barcodeSubscription?.cancel());
    unawaited(_controller.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QR Scanner')),
      drawer: AppDrawer(args: widget.args),
      body: SafeArea(
        child: _result == null ? _buildScanner(context) : _buildResult(context),
      ),
    );
  }

  Widget _buildScanner(BuildContext context) {
    final customBuilder = widget.scannerBuilder;
    final scanner = customBuilder != null
        ? customBuilder(context, _acceptResult)
        : MobileScanner(controller: _controller, errorBuilder: _buildError);

    return Column(
      children: [
        Expanded(
          child: Stack(
            fit: StackFit.expand,
            children: [
              scanner,
              const _ScanGuide(),
              if (customBuilder == null)
                Align(
                  alignment: Alignment.topCenter,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: _CameraControls(controller: _controller),
                  ),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'Center a QR code in the frame. Scanning stops after one code is read.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      ],
    );
  }

  Widget _buildError(BuildContext context, MobileScannerException error) {
    final permissionDenied =
        error.errorCode == MobileScannerErrorCode.permissionDenied;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.no_photography_outlined, size: 56),
            const SizedBox(height: 16),
            Text(
              permissionDenied
                  ? 'Camera permission is required to scan QR codes. Enable it in device settings and reopen the scanner.'
                  : error.errorCode.message,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResult(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Icon(
          Icons.check_circle_outline,
          size: 64,
          color: theme.colorScheme.primary,
        ),
        const SizedBox(height: 16),
        Text(
          'QR code scanned',
          textAlign: TextAlign.center,
          style: theme.textTheme.headlineSmall,
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: SelectableText(
              _result!,
              key: const Key('qr-scan-result'),
              style: theme.textTheme.bodyLarge,
            ),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _copyResult,
          icon: const Icon(Icons.copy_outlined),
          label: const Text('Copy contents'),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _scanAnother,
          icon: const Icon(Icons.qr_code_scanner_outlined),
          label: const Text('Scan another'),
        ),
      ],
    );
  }
}

class _ScanGuide extends StatelessWidget {
  const _ScanGuide();

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return IgnorePointer(
      child: Center(
        child: FractionallySizedBox(
          widthFactor: 0.68,
          child: AspectRatio(
            aspectRatio: 1,
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(color: colorScheme.primary, width: 3),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CameraControls extends StatelessWidget {
  const _CameraControls({required this.controller});

  final MobileScannerController controller;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return ValueListenableBuilder<MobileScannerState>(
      valueListenable: controller,
      builder: (context, state, _) {
        if (!state.isInitialized || !state.isRunning) {
          return const SizedBox.shrink();
        }
        return DecoratedBox(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                tooltip: 'Toggle flashlight',
                onPressed: state.torchState == TorchState.unavailable
                    ? null
                    : controller.toggleTorch,
                icon: Icon(
                  state.torchState == TorchState.on
                      ? Icons.flash_on
                      : Icons.flash_off,
                ),
              ),
              if ((state.availableCameras ?? 0) > 1)
                IconButton(
                  tooltip: 'Switch camera',
                  onPressed: controller.switchCamera,
                  icon: const Icon(Icons.cameraswitch_outlined),
                ),
            ],
          ),
        );
      },
    );
  }
}
