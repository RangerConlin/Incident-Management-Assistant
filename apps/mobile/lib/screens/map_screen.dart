import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/home_nav_args.dart';
import '../models/map/map_basemap.dart';
import '../models/map/map_search_result.dart';
import '../models/team_location.dart';
import '../models/team_type_definition.dart';
import '../services/map_preferences_store.dart';
import '../services/sarapp_api_client.dart';
import '../services/tracking_service.dart';
import '../utils/coordinate_format.dart';
import '../utils/date_format.dart';
import '../widgets/app_bottom_nav.dart';
import '../widgets/app_drawer.dart';

/// Primary bottom-tab incident map showing the current location for each
/// actively tracking team.
class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.args, SarAppApiClient? apiClient})
    : _injectedApiClient = apiClient;

  final HomeNavArgs args;
  final SarAppApiClient? _injectedApiClient;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  late final SarAppApiClient _apiClient =
      widget._injectedApiClient ?? SarAppApiClient();
  late final bool _ownsApiClient = widget._injectedApiClient == null;
  final MapController _mapController = MapController();
  final TextEditingController _searchController = TextEditingController();

  MapBasemap _selectedBasemap = MapBasemaps.osm;
  List<TeamLocation> _locations = const [];
  Map<String, String> _teamTypeByTeamId = const {};
  Map<String, TeamTypeDefinition> _teamTypes = const {};
  TeamLocation? _myLocation;
  MapSearchResult? _searchPin;
  LatLng? _coordinatePin;
  bool _showTeams = true;
  bool _trackingEnabled = false;
  bool _loading = true;
  bool _refreshing = false;
  bool _centeringOnDevice = false;
  bool _searching = false;
  bool _coordinateMode = false;
  String? _errorMessage;
  Timer? _refreshTimer;

  static const _minZoom = 3.0;
  static const _maxZoom = 18.0;
  static final _fallbackCenter = LatLng(39.8283, -98.5795);

  @override
  void initState() {
    super.initState();
    _loadMapPreferences();
    _refreshTrackingState();
    _load();
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) async {
      await _refreshTrackingState();
      await _load(showFullScreenLoader: false);
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _searchController.dispose();
    if (_ownsApiClient) _apiClient.dispose();
    super.dispose();
  }

  Future<void> _loadMapPreferences() async {
    final basemapId = await MapPreferencesStore.selectedBasemapId();
    final showTeams = await MapPreferencesStore.showTeams();
    if (!mounted) return;
    setState(() {
      _selectedBasemap = MapBasemaps.byId(basemapId);
      _showTeams = showTeams;
    });
  }

  Future<void> _refreshTrackingState() async {
    final enabled = await TrackingService.isEnabled();
    if (!mounted) return;
    setState(() => _trackingEnabled = enabled);
    if (enabled) {
      await _refreshMyLocation();
    } else if (mounted) {
      setState(() => _myLocation = null);
    }
  }

  Future<void> _refreshMyLocation() async {
    try {
      final location = await TrackingService.currentTeamLocation(
        teamId: widget.args.teamId,
        teamName: widget.args.teamName,
        sourcePersonRecord: _personRecord,
        sourcePersonId: '${widget.args.session['person_id'] ?? ''}',
      );
      if (!mounted) return;
      setState(() => _myLocation = location);
    } catch (e) {
      debugPrint('MapScreen: unable to refresh current device location: $e');
    }
  }

  Future<void> _load({bool showFullScreenLoader = true}) async {
    if (showFullScreenLoader) {
      setState(() {
        _loading = true;
        _errorMessage = null;
      });
    } else if (!_refreshing) {
      setState(() {
        _refreshing = true;
        _errorMessage = null;
      });
    }

    try {
      final results = await Future.wait([
        _apiClient.fetchTeamLocations(widget.args.incidentId),
        _apiClient.fetchTeams(widget.args.incidentId),
        _apiClient.fetchTeamTypes(),
      ]);
      final locations = List<TeamLocation>.from(results[0]);
      final teamTypeByTeamId = <String, String>{
        for (final row in results[1].whereType<Map>())
          '${row['int_id'] ?? row['id'] ?? ''}': '${row['team_type'] ?? ''}'.toUpperCase(),
      };
      final teamTypes = <String, TeamTypeDefinition>{};
      for (final raw in results[2].whereType<Map>()) {
        final definition = TeamTypeDefinition.fromJson(Map<String, dynamic>.from(raw));
        if (definition.code.isNotEmpty) teamTypes[definition.code] = definition;
      }
      if (!mounted) return;
      setState(() {
        _locations = locations;
        _teamTypeByTeamId = teamTypeByTeamId;
        _teamTypes = teamTypes;
      });
    } on SarAppApiException catch (e) {
      if (!mounted) return;
      setState(
        () => _errorMessage = 'Unable to load team locations: ${e.message}',
      );
    } on FormatException catch (e) {
      if (!mounted) return;
      setState(
        () => _errorMessage = 'Unable to read team locations: ${e.message}',
      );
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _refreshing = false;
        });
      }
    }
  }

  LatLng get _center {
    final points = _visiblePoints;
    if (points.isEmpty) return _fallbackCenter;
    final lat =
        points.map((e) => e.latitude).reduce((a, b) => a + b) / points.length;
    final lon =
        points.map((e) => e.longitude).reduce((a, b) => a + b) / points.length;
    return LatLng(lat, lon);
  }

  double get _initialZoom {
    if (_visiblePoints.length <= 1) return 13;
    return 10;
  }

  List<TeamLocation> get _visibleTeamLocations {
    if (!_showTeams) return const [];
    if (!_trackingEnabled) return _locations;
    return _locations
        .where((location) => location.teamId != widget.args.teamId)
        .toList();
  }

  List<LatLng> get _visiblePoints {
    return [
      if (_myLocation != null)
        LatLng(_myLocation!.latitude, _myLocation!.longitude),
      for (final location in _visibleTeamLocations)
        LatLng(location.latitude, location.longitude),
      if (_searchPin != null) _searchPin!.point,
      ?_coordinatePin,
    ];
  }

  String? get _personRecord {
    final value =
        widget.args.session['person_record'] ??
        widget.args.session['user']?['person_record'];
    return value == null ? null : '$value';
  }

  Future<void> _centerOnDevice() async {
    if (_centeringOnDevice) return;
    setState(() => _centeringOnDevice = true);
    try {
      final location = await TrackingService.currentTeamLocation(
        teamId: widget.args.teamId,
        teamName: widget.args.teamName,
        sourcePersonRecord: _personRecord,
        sourcePersonId: '${widget.args.session['person_id'] ?? ''}',
      );
      if (!mounted) return;
      setState(() => _myLocation = location);
      _mapController.move(
        LatLng(location.latitude, location.longitude),
        _mapController.camera.zoom < 15 ? 15 : _mapController.camera.zoom,
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to get current location: $e')),
      );
    } finally {
      if (mounted) setState(() => _centeringOnDevice = false);
    }
  }

  void _zoomBy(double delta) {
    final nextZoom = (_mapController.camera.zoom + delta)
        .clamp(_minZoom, _maxZoom)
        .toDouble();
    _mapController.move(_mapController.camera.center, nextZoom);
  }

  void _fitVisible() {
    final points = _visiblePoints;
    if (points.isEmpty) {
      _centerOnDevice();
      return;
    }
    if (points.length == 1) {
      _mapController.move(points.first, 15);
      return;
    }
    final bounds = LatLngBounds.fromPoints(points);
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: bounds,
        padding: const EdgeInsets.all(72),
        maxZoom: 16.0,
      ),
    );
  }

  Future<void> _showLayersSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return SafeArea(
              child: ListView(
                shrinkWrap: true,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                    child: Text(
                      'Basemap',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  for (final basemap in MapBasemaps.all)
                    ListTile(
                      title: Text(basemap.label),
                      subtitle: Text(basemap.description),
                      trailing: _selectedBasemap.id == basemap.id
                          ? const Icon(Icons.check)
                          : null,
                      onTap: () async {
                        final selected = MapBasemaps.byId(basemap.id);
                        setState(() => _selectedBasemap = selected);
                        setModalState(() {});
                        await MapPreferencesStore.setSelectedBasemapId(
                          basemap.id,
                        );
                      },
                    ),
                  const Divider(),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                    child: Text(
                      'Layers',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  SwitchListTile(
                    secondary: const Icon(Icons.groups_outlined),
                    title: const Text('Team locations'),
                    subtitle: _trackingEnabled
                        ? const Text(
                            'Your own team is hidden while this device is tracking.',
                          )
                        : null,
                    value: _showTeams,
                    onChanged: (value) async {
                      setState(() => _showTeams = value);
                      setModalState(() {});
                      await MapPreferencesStore.setShowTeams(value);
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.my_location_outlined),
                    title: const Text('My location'),
                    subtitle: Text(
                      _trackingEnabled
                          ? 'Always shown while GPS tracking is enabled.'
                          : 'Enable Location Tracking in Settings to show this layer.',
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _runSearch(String rawQuery) async {
    final query = rawQuery.trim();
    if (query.isEmpty || _searching) return;

    setState(() => _searching = true);
    try {
      final coordinate = parseDecimalCoordinate(query);
      if (coordinate != null) {
        final result = MapSearchResult(
          title: 'Coordinates',
          subtitle: formatDecimalDegrees(coordinate),
          point: coordinate,
          kind: MapSearchResultKind.coordinate,
        );
        _selectSearchResult(result);
        return;
      }

      final localResults = _localSearch(query);
      if (localResults.isNotEmpty) {
        if (localResults.length == 1) {
          _selectSearchResult(localResults.first);
        } else {
          await _showSearchResults(localResults);
        }
        return;
      }

      final geocode = await _apiClient.geocode(query);
      final result = MapSearchResult(
        title: geocode.address,
        subtitle: 'Address / point of interest',
        point: geocode.point,
        kind: MapSearchResultKind.geocode,
      );
      _selectSearchResult(result);
    } on SarAppApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Search failed: ${e.message}')));
    } on FormatException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Search result was unreadable: ${e.message}')),
      );
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  List<MapSearchResult> _localSearch(String query) {
    final needle = query.toLowerCase();
    return [
      if (_myLocation != null &&
          ('my location'.contains(needle) ||
              widget.args.teamName.toLowerCase().contains(needle)))
        MapSearchResult(
          title: 'My Location',
          subtitle: widget.args.teamName,
          point: LatLng(_myLocation!.latitude, _myLocation!.longitude),
          kind: MapSearchResultKind.myLocation,
        ),
      for (final location in _visibleTeamLocations)
        if (location.displayName.toLowerCase().contains(needle) ||
            location.teamId.toLowerCase().contains(needle))
          MapSearchResult(
            title: location.displayName,
            subtitle: 'Team ${location.teamId}',
            point: LatLng(location.latitude, location.longitude),
            kind: MapSearchResultKind.team,
          ),
    ];
  }

  Future<void> _showSearchResults(List<MapSearchResult> results) {
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
              child: Text(
                'Search Results',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            for (final result in results)
              ListTile(
                leading: Icon(_iconForSearchKind(result.kind)),
                title: Text(result.title),
                subtitle: Text(result.subtitle),
                onTap: () {
                  Navigator.of(context).pop();
                  _selectSearchResult(result);
                },
              ),
          ],
        ),
      ),
    );
  }

  IconData _iconForSearchKind(MapSearchResultKind kind) {
    return switch (kind) {
      MapSearchResultKind.team => Icons.groups_outlined,
      MapSearchResultKind.myLocation => Icons.my_location_outlined,
      MapSearchResultKind.coordinate => Icons.pin_drop_outlined,
      MapSearchResultKind.geocode => Icons.search_outlined,
      MapSearchResultKind.feature => Icons.place_outlined,
    };
  }

  void _selectSearchResult(MapSearchResult result) {
    if (!mounted) return;
    setState(() => _searchPin = result);
    _mapController.move(
      result.point,
      _mapController.camera.zoom < 15 ? 15 : _mapController.camera.zoom,
    );
    FocusScope.of(context).unfocus();
  }

  Future<void> _showPointActions({
    required String title,
    required LatLng point,
    String? subtitle,
    bool includeNavigate = true,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        final decimal = formatDecimalDegrees(point);
        final dms = formatDms(point);
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                title: Text(title),
                subtitle: Text(
                  [
                    if (subtitle != null && subtitle.isNotEmpty) subtitle,
                    decimal,
                    dms,
                  ].join('\n'),
                ),
              ),
              if (includeNavigate)
                ListTile(
                  leading: const Icon(Icons.navigation_outlined),
                  title: const Text('Navigate to'),
                  onTap: () {
                    Navigator.of(context).pop();
                    _navigateTo(point, title);
                  },
                ),
              ListTile(
                leading: const Icon(Icons.copy_outlined),
                title: const Text('Copy decimal coordinates'),
                onTap: () {
                  Clipboard.setData(ClipboardData(text: decimal));
                  Navigator.of(context).pop();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Coordinates copied')),
                  );
                },
              ),
              ListTile(
                leading: const Icon(Icons.center_focus_strong_outlined),
                title: const Text('Center map here'),
                onTap: () {
                  Navigator.of(context).pop();
                  _mapController.move(point, 16);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _navigateTo(LatLng point, String label) async {
    final encodedLabel = Uri.encodeComponent(label);
    final geoUri = Uri.parse(
      'geo:${point.latitude},${point.longitude}?q=${point.latitude},${point.longitude}($encodedLabel)',
    );
    final webUri = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=${point.latitude},${point.longitude}',
    );

    if (await canLaunchUrl(geoUri)) {
      await launchUrl(geoUri, mode: LaunchMode.externalApplication);
      return;
    }
    if (await canLaunchUrl(webUri)) {
      await launchUrl(webUri, mode: LaunchMode.externalApplication);
      return;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('No navigation app is available.')),
    );
  }

  void _setCoordinatePin(LatLng point) {
    setState(() => _coordinatePin = point);
    _showCoordinateTools(point);
  }

  Future<void> _showCoordinateTools(LatLng point) {
    final decimal = formatDecimalDegrees(point);
    final dms = formatDms(point);
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            ListTile(
              leading: const Icon(Icons.pin_drop_outlined),
              title: const Text('Coordinate Pin'),
              subtitle: Text('$decimal\n$dms'),
            ),
            ListTile(
              leading: const Icon(Icons.navigation_outlined),
              title: const Text('Navigate to'),
              onTap: () {
                Navigator.of(context).pop();
                _navigateTo(point, 'Coordinate Pin');
              },
            ),
            ListTile(
              leading: const Icon(Icons.copy_outlined),
              title: const Text('Copy decimal coordinates'),
              onTap: () {
                Clipboard.setData(ClipboardData(text: decimal));
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Coordinates copied')),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline),
              title: const Text('Clear pin'),
              onTap: () {
                Navigator.of(context).pop();
                setState(() => _coordinatePin = null);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showTeamDetails(TeamLocation location) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        final theme = Theme.of(context);
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(location.displayName, style: theme.textTheme.titleLarge),
                const SizedBox(height: 12),
                _DetailRow(label: 'Team ID', value: location.teamId),
                _DetailRow(
                  label: 'Coordinates',
                  value:
                      '${location.latitude.toStringAsFixed(5)}, ${location.longitude.toStringAsFixed(5)}',
                ),
                _DetailRow(
                  label: 'Updated',
                  value: formatTimestamp(location.updatedAt),
                ),
                if (location.sourcePersonId != null)
                  _DetailRow(
                    label: 'Source',
                    value: location.localOnly
                        ? '${location.sourcePersonId!} (this device)'
                        : location.sourcePersonId!,
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  List<Marker> _markers(BuildContext context) {
    final theme = Theme.of(context);
    return [
      for (final location in _visibleTeamLocations)
        Marker(
          width: 88,
          height: 72,
          point: LatLng(location.latitude, location.longitude),
          child: Semantics(
            button: true,
            label: location.displayName,
            child: GestureDetector(
              onTap: () => _showTeamDetails(location),
              onLongPress: () => _showPointActions(
                title: location.displayName,
                subtitle: 'Team ${location.teamId}',
                point: LatLng(location.latitude, location.longitude),
              ),
              child: _MapMarkerLabel(
                icon: Icons.groups,
                label: location.displayName,
                color: _teamTypes[_teamTypeByTeamId[location.teamId]]?.backgroundColor ?? theme.colorScheme.primary,
                foreground: _teamTypes[_teamTypeByTeamId[location.teamId]]?.textColor ?? theme.colorScheme.onPrimary,
                assetIcon: _teamTypes[_teamTypeByTeamId[location.teamId]] == null
                    ? null
                    : 'assets/team_symbols/light/${_teamTypes[_teamTypeByTeamId[location.teamId]]!.iconKey}.png',
              ),
            ),
          ),
        ),
      if (_myLocation != null)
        Marker(
          width: 94,
          height: 94,
          point: LatLng(_myLocation!.latitude, _myLocation!.longitude),
          child: Semantics(
            button: true,
            label: 'My Location',
            child: GestureDetector(
              onTap: () => _showTeamDetails(_myLocation!),
              onLongPress: () => _showPointActions(
                title: 'My Location',
                subtitle: widget.args.teamName,
                point: LatLng(_myLocation!.latitude, _myLocation!.longitude),
                includeNavigate: false,
              ),
              child: _MapMarkerLabel(
                icon: Icons.my_location,
                label: 'ME',
                badge: 'THIS DEVICE',
                color: theme.colorScheme.secondary,
                foreground: theme.colorScheme.onSecondary,
              ),
            ),
          ),
        ),
      if (_searchPin != null)
        Marker(
          width: 112,
          height: 82,
          point: _searchPin!.point,
          child: GestureDetector(
            onTap: () => _showPointActions(
              title: _searchPin!.title,
              subtitle: _searchPin!.subtitle,
              point: _searchPin!.point,
            ),
            onLongPress: () => _showPointActions(
              title: _searchPin!.title,
              subtitle: _searchPin!.subtitle,
              point: _searchPin!.point,
            ),
            child: _MapMarkerLabel(
              icon: Icons.search,
              label: _searchPin!.title,
              color: theme.colorScheme.tertiary,
              foreground: theme.colorScheme.onTertiary,
            ),
          ),
        ),
      if (_coordinatePin != null)
        Marker(
          width: 112,
          height: 82,
          point: _coordinatePin!,
          child: GestureDetector(
            onTap: () => _showCoordinateTools(_coordinatePin!),
            onLongPress: () => _showCoordinateTools(_coordinatePin!),
            child: _MapMarkerLabel(
              icon: Icons.pin_drop,
              label: 'Coordinate',
              color: theme.colorScheme.error,
              foreground: theme.colorScheme.onError,
            ),
          ),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final center = _center;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Map'),
        actions: [
          IconButton(
            tooltip: 'Refresh locations',
            onPressed: _refreshing
                ? null
                : () => _load(showFullScreenLoader: false),
            icon: _refreshing
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_outlined),
          ),
        ],
      ),
      drawer: AppDrawer(args: widget.args),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Stack(
              children: [
                FlutterMap(
                  key: ValueKey(
                    '${center.latitude.toStringAsFixed(4)},${center.longitude.toStringAsFixed(4)},${_locations.length}',
                  ),
                  mapController: _mapController,
                  options: MapOptions(
                    initialCenter: center,
                    initialZoom: _initialZoom,
                    minZoom: _minZoom,
                    maxZoom: _maxZoom,
                    interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                    ),
                    onTap: (tapPosition, point) {
                      if (_coordinateMode) _setCoordinatePin(point);
                    },
                    onLongPress: (tapPosition, point) =>
                        _setCoordinatePin(point),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: _selectedBasemap.urlTemplate,
                      subdomains: _selectedBasemap.subdomains,
                      userAgentPackageName: 'com.icscommand.ics_mobile_app',
                      maxNativeZoom: _selectedBasemap.maxNativeZoom,
                      errorTileCallback: (tile, error, stackTrace) {
                        debugPrint('Map tile failed: $error');
                      },
                    ),
                    MarkerLayer(markers: _markers(context)),
                  ],
                ),
                Positioned(
                  left: 12,
                  right: 12,
                  top: 12,
                  child: _MapSearchBar(
                    controller: _searchController,
                    searching: _searching,
                    onSubmitted: _runSearch,
                    onClear: () {
                      _searchController.clear();
                      setState(() => _searchPin = null);
                    },
                  ),
                ),
                Positioned(
                  left: 8,
                  bottom: 8,
                  child: _AttributionLabel(text: _selectedBasemap.attribution),
                ),
                Positioned(
                  right: 16,
                  bottom: 16,
                  child: _MapControls(
                    busy: _centeringOnDevice,
                    coordinateMode: _coordinateMode,
                    onCenterPressed: _centerOnDevice,
                    onZoomIn: () => _zoomBy(1),
                    onZoomOut: () => _zoomBy(-1),
                    onLayers: _showLayersSheet,
                    onFitVisible: _fitVisible,
                    onCoordinateMode: () =>
                        setState(() => _coordinateMode = !_coordinateMode),
                  ),
                ),
                if (_visibleTeamLocations.isEmpty && _myLocation == null)
                  Positioned(
                    left: 12,
                    right: 12,
                    top: 78,
                    child: _MapBannerCard(
                      icon: Icons.location_off_outlined,
                      message:
                          'No active map locations yet. Enable tracking in Settings or wait for team locations to report.',
                    ),
                  ),
                if (_coordinateMode)
                  const Positioned(
                    left: 12,
                    right: 88,
                    bottom: 16,
                    child: _MapBannerCard(
                      icon: Icons.pin_drop_outlined,
                      message:
                          'Coordinate tool on — tap the map to drop a pin.',
                    ),
                  ),
                if (_errorMessage != null)
                  _MapBanner(
                    icon: Icons.warning_amber_outlined,
                    message: _errorMessage!,
                  ),
              ],
            ),
      bottomNavigationBar: AppBottomNav(current: AppTab.map, args: widget.args),
    );
  }
}

class _MapControls extends StatelessWidget {
  const _MapControls({
    required this.busy,
    required this.coordinateMode,
    required this.onCenterPressed,
    required this.onZoomIn,
    required this.onZoomOut,
    required this.onLayers,
    required this.onFitVisible,
    required this.onCoordinateMode,
  });

  final bool busy;
  final bool coordinateMode;
  final VoidCallback onCenterPressed;
  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;
  final VoidCallback onLayers;
  final VoidCallback onFitVisible;
  final VoidCallback onCoordinateMode;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Material(
          elevation: 4,
          color: theme.colorScheme.surface,
          borderRadius: BorderRadius.circular(6),
          clipBehavior: Clip.antiAlias,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _MapControlIconButton(
                tooltip: 'Zoom in',
                icon: Icons.add,
                onPressed: onZoomIn,
              ),
              SizedBox(
                width: 40,
                child: Divider(
                  height: 1,
                  thickness: 1,
                  color: theme.colorScheme.outlineVariant,
                ),
              ),
              _MapControlIconButton(
                tooltip: 'Zoom out',
                icon: Icons.remove,
                onPressed: onZoomOut,
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        _RoundMapButton(
          tooltip: 'Layers and basemaps',
          icon: Icons.layers_outlined,
          onPressed: onLayers,
        ),
        const SizedBox(height: 10),
        _RoundMapButton(
          tooltip: 'Fit visible map items',
          icon: Icons.fit_screen_outlined,
          onPressed: onFitVisible,
        ),
        const SizedBox(height: 10),
        _RoundMapButton(
          tooltip: coordinateMode
              ? 'Turn coordinate tool off'
              : 'Turn coordinate tool on',
          icon: Icons.pin_drop_outlined,
          selected: coordinateMode,
          onPressed: onCoordinateMode,
        ),
        const SizedBox(height: 10),
        Tooltip(
          message: 'Center on current location',
          child: FloatingActionButton.small(
            heroTag: 'map-center-on-device',
            onPressed: busy ? null : onCenterPressed,
            backgroundColor: theme.colorScheme.surface,
            foregroundColor: theme.colorScheme.primary,
            child: busy
                ? SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: theme.colorScheme.primary,
                    ),
                  )
                : const Icon(Icons.my_location_outlined),
          ),
        ),
      ],
    );
  }
}

class _RoundMapButton extends StatelessWidget {
  const _RoundMapButton({
    required this.tooltip,
    required this.icon,
    required this.onPressed,
    this.selected = false,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback onPressed;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Tooltip(
      message: tooltip,
      child: FloatingActionButton.small(
        heroTag: tooltip,
        onPressed: onPressed,
        backgroundColor: selected
            ? theme.colorScheme.primary
            : theme.colorScheme.surface,
        foregroundColor: selected
            ? theme.colorScheme.onPrimary
            : theme.colorScheme.primary,
        child: Icon(icon),
      ),
    );
  }
}

class _MapControlIconButton extends StatelessWidget {
  const _MapControlIconButton({
    required this.tooltip,
    required this.icon,
    required this.onPressed,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Tooltip(
      message: tooltip,
      child: SizedBox.square(
        dimension: 40,
        child: IconButton(
          padding: EdgeInsets.zero,
          iconSize: 22,
          color: theme.colorScheme.primary,
          onPressed: onPressed,
          icon: Icon(icon),
        ),
      ),
    );
  }
}

class _MapSearchBar extends StatelessWidget {
  const _MapSearchBar({
    required this.controller,
    required this.searching,
    required this.onSubmitted,
    required this.onClear,
  });

  final TextEditingController controller;
  final bool searching;
  final ValueChanged<String> onSubmitted;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(12),
      color: theme.colorScheme.surface.withValues(alpha: 0.96),
      child: TextField(
        controller: controller,
        textInputAction: TextInputAction.search,
        onSubmitted: onSubmitted,
        decoration: InputDecoration(
          hintText: 'Search teams, addresses, POIs, or coordinates',
          prefixIcon: searching
              ? const Padding(
                  padding: EdgeInsets.all(14),
                  child: SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : const Icon(Icons.search_outlined),
          suffixIcon: IconButton(
            tooltip: 'Clear search',
            onPressed: onClear,
            icon: const Icon(Icons.close),
          ),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 4,
            vertical: 14,
          ),
        ),
      ),
    );
  }
}

class _MapMarkerLabel extends StatelessWidget {
  const _MapMarkerLabel({
    required this.icon,
    required this.label,
    required this.color,
    required this.foreground,
    this.badge,
    this.assetIcon,
  });

  final IconData icon;
  final String label;
  final Color color;
  final Color foreground;
  final String? badge;
  final String? assetIcon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            boxShadow: const [
              BoxShadow(
                blurRadius: 8,
                color: Colors.black45,
                offset: Offset(0, 2),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: assetIcon == null
                ? Icon(icon, size: 20, color: foreground)
                : Image.asset(assetIcon!, width: 20, height: 20, color: foreground),
          ),
        ),
        if (badge != null)
          Container(
            margin: const EdgeInsets.only(top: 4),
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: theme.colorScheme.secondaryContainer,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              badge!,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSecondaryContainer,
                fontSize: 9,
              ),
            ),
          ),
        const SizedBox(height: 4),
        Container(
          constraints: const BoxConstraints(maxWidth: 94),
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: theme.colorScheme.surface.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            label,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: theme.textTheme.labelSmall,
          ),
        ),
      ],
    );
  }
}

class _MapBanner extends StatelessWidget {
  const _MapBanner({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Positioned(
      left: 12,
      right: 12,
      top: 12,
      child: Material(
        elevation: 4,
        borderRadius: BorderRadius.circular(6),
        color: theme.colorScheme.surface.withValues(alpha: 0.95),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AttributionLabel extends StatelessWidget {
  const _AttributionLabel({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
        child: Text(
          text,
          style: theme.textTheme.labelSmall?.copyWith(fontSize: 10),
        ),
      ),
    );
  }
}

class _MapBannerCard extends StatelessWidget {
  const _MapBannerCard({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(6),
      color: theme.colorScheme.surface.withValues(alpha: 0.95),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
