import { useState, useCallback, useEffect, useMemo } from 'react';
import type {
	GeoJSONRouteData,
	GeoJSONRouteFeature,
	RouteRequestPayload,
	SelectionMode,
	Coordinate,
} from './interfaces';
import { Map } from './components/map/Map';
import { RoutePlannerForm } from './components/Route/RoutePlannerForm';
import { RouteList } from './components/Route/RouteList';
import { RouteRating } from './components/Route/RouteRating';
import { RouteStreets } from './components/Route/RouteStreets';
import { NavigationPanel } from './components/Route/NavigationPanel';
import { useGeolocation } from './hooks/useGeolocation';
import { useRouteTracking, type TripSummary } from './hooks/useRouteTracking';
import './App.css';

/** Tells the server the routes are still in use, so it doesn't let them expire. */
function refreshRoutes(routeIds: string[]) {
	if (routeIds.length === 0) return;
	fetch('http://localhost:8000/refresh/', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ prolonged_route_ids: routeIds }),
	})
		.then((response) => {
			if (!response.ok) throw new Error(`Status ${response.status}: ${response.statusText}`);
		})
		.catch((error) => console.error('Refreshing routes failed:', error));
}

/** The ids of the given routes, as strings. */
function routeIdsOf(features: GeoJSONRouteFeature[]) {
	return features
		.map((f) => f.properties?.id)
		.filter((id): id is string => id !== undefined && id !== null)
		.map(String);
}

export function App() {
	const [mode, setMode] = useState<SelectionMode>('two_points');
	const [isCollapsed, setIsCollapsed] = useState(false);
	const [geoJsonData, setGeoJsonData] = useState<GeoJSONRouteData | null>(null);
	const [isSending, setIsSending] = useState(false);
	const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
	const [isConfirming, setIsConfirming] = useState(false);

	const [start, setStart] = useState<Coordinate | null>(null);
	const [destination, setDestination] = useState<Coordinate | null>(null);
	const [singlePoint, setSinglePoint] = useState<Coordinate | null>(null);
	const [distance, setDistance] = useState<number>(500);
	const [routeCount, setRouteCount] = useState<number>(3);

	// After a route is chosen: walking it, then rating it (whether finished or ended early)
	const [tripPhase, setTripPhase] = useState<'navigating' | 'rating' | null>(null);
	const [tripSummary, setTripSummary] = useState<TripSummary | null>(null);
	const isConfirmedMode = tripPhase !== null;

	const handleArrive = useCallback((summary: TripSummary) => {
		setTripSummary(summary);
		setTripPhase('rating');
	}, []);
	const navigation = useRouteTracking(handleArrive);

	const handleLocationUpdate = useCallback((loc: Coordinate, currentMode: SelectionMode) => {
		if (currentMode === 'two_points') {
			setStart(loc);
		} else if (currentMode === 'point_distance') {
			setSinglePoint(loc);
		}
	}, []);

	const { isGpsActive, userLocation, toggleGps, disableGps } = useGeolocation({
		mode,
		isConfirmedMode,
		onLocationUpdate: handleLocationUpdate,
	});

	const [startQuery, setStartQuery] = useState('');
	const [destinationQuery, setDestinationQuery] = useState('');
	const [centerQuery, setCenterQuery] = useState('');
	// Bumped whenever the search boxes' text is replaced (reset, swap), so they start afresh
	const [searchKey, setSearchKey] = useState(0);

	const handleReset = () => {
		setSearchKey((n) => n + 1);
		setStartQuery('');
		setDestinationQuery('');
		setCenterQuery('');
		disableGps();
		setStart(null);
		setDestination(null);
		setSinglePoint(null);
		setGeoJsonData(null);
		setSelectedRouteId(null);
		navigation.stop();
		setTripPhase(null);
		setTripSummary(null);
	};

	const handleEndEarly = () => {
		setTripSummary(navigation.stop());
		setTripPhase('rating');
	};

	const handleModeChange = (newMode: SelectionMode) => {
		setMode(newMode);
		handleReset();
	};

	// A searched place moves its pin, so the routes for the old one are out of date
	const selectFromSearch = (select: (coord: Coordinate) => void) => (coord: Coordinate) => {
		setGeoJsonData(null);
		setSelectedRouteId(null);
		select(coord);
	};

	// Walk the other way: the pins and the search boxes' text trade places
	const handleSwap = () => {
		setStart(destination);
		setDestination(start);
		setStartQuery(destinationQuery);
		setDestinationQuery(startQuery);
		setSearchKey((n) => n + 1);
		setGeoJsonData(null);
		setSelectedRouteId(null);
	};

	const handleMapClick = (coord: Coordinate) => {
		if (isConfirmedMode) return;

		if (geoJsonData) {
			setGeoJsonData(null);
			setSelectedRouteId(null);
		}

		if (mode === 'two_points') {
			if ((!start || (start && destination)) && !isGpsActive) {
				setStart(coord);
				setDestination(null);
			} else {
				setDestination(coord);
			}
		} else if (!isGpsActive) {
			setSinglePoint(coord);
		}
	};

	const handleSendRequest = async () => {
		let payload: RouteRequestPayload | null = null;
		if (mode === 'two_points' && start && destination) {
			payload = { mode: 'two_points', start, destination, count: routeCount };
		} else if (mode === 'point_distance' && singlePoint) {
			payload = {
				mode: 'point_distance',
				point: singlePoint,
				distance,
				count: routeCount,
			};
		}

		if (!payload) return;
		setIsSending(true);

		try {
			const response = await fetch('http://localhost:8000/generate/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload),
			});
			if (!response.ok) throw new Error(`Server status ${response.status}: ${response.statusText}`);
			const data = await response.json();
			setGeoJsonData(data);
		} catch (error) {
			console.error('Request failed:', error);
			alert('Failed to connect or process request. Check browser console.');
		} finally {
			setIsSending(false);
		}
	};

	const handleConfirmRoute = async () => {
		if (!selectedRouteId || !geoJsonData) return;
		setIsConfirming(true);

		try {
			const discardedRouteIds = {
				discarded_route_ids: routeIdsOf(geoJsonData.features).filter(
					(id) => id !== String(selectedRouteId),
				),
			};

			const response = await fetch('http://localhost:8000/discard/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(discardedRouteIds),
			});

			if (!response.ok) throw new Error(`Status ${response.status}: ${response.statusText}`);

			const selectedFeature = geoJsonData.features.find(
				(f) => f.properties?.id === selectedRouteId,
			);
			setGeoJsonData({
				...geoJsonData,
				features: selectedFeature ? [selectedFeature] : [],
			});
			if (selectedFeature) {
				// Navigation follows the GPS itself; the planner's location marker would only duplicate it
				disableGps();
				navigation.start(selectedFeature);
			}
			setTripPhase('navigating');
		} catch (err) {
			console.error('Error confirming route:', err);
			alert('Failed to send route selection.');
		} finally {
			setIsConfirming(false);
		}
	};

	// Choosing between the suggestions keeps them all alive - any of them may still be confirmed
	const handleSelectRoute = (routeId: string) => {
		setSelectedRouteId(routeId);
	};

	const canSend = Boolean(
		(mode === 'two_points' && start && destination) ||
		(mode === 'point_distance' && singlePoint && distance > 0),
	);

	const routes = useMemo(() => {
		return geoJsonData?.features ?? [];
	}, [geoJsonData?.features]);

	const selectedRoute = useMemo(() => {
		return routes.find((f) => f.properties?.id === selectedRouteId);
	}, [routes, selectedRouteId]);

	useEffect(() => {
		if (routes.length === 0) return;

		const interval = setInterval(() => {
			refreshRoutes(routes.map((obj) => obj.properties!.id));
		}, 30000);

		return () => clearInterval(interval);
	}, [routes]);

	return (
		<div className="app-container">
			<div className={`action-card ${isCollapsed ? 'collapsed' : ''}`}>
				<div className="card-header">
					<span className="card-title">
						{tripPhase === 'navigating'
							? 'Navigation'
							: tripPhase === 'rating'
								? 'Your walk'
								: 'Route planner'}
					</span>
					{!isConfirmedMode && (
						<div className="header-actions">
							<button
								className={`icon-btn ${isGpsActive ? 'active' : ''}`}
								onClick={toggleGps}
								title={isGpsActive ? 'Stop using my location' : 'Use my location'}
								aria-label={isGpsActive ? 'Stop using my location' : 'Use my location'}
								aria-pressed={isGpsActive}>
								<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
									<circle
										cx="8"
										cy="8"
										r="4.5"
										fill="none"
										stroke="currentColor"
										strokeWidth="1.5"
									/>
									<circle cx="8" cy="8" r="1.6" fill="currentColor" />
									<path
										d="M8 1v2.5M8 12.5V15M1 8h2.5M12.5 8H15"
										stroke="currentColor"
										strokeWidth="1.5"
										strokeLinecap="round"
									/>
								</svg>
							</button>
							<button
								className="icon-btn"
								onClick={() => setIsCollapsed(!isCollapsed)}
								title={isCollapsed ? 'Expand' : 'Collapse'}
								aria-label={isCollapsed ? 'Expand' : 'Collapse'}
								aria-expanded={!isCollapsed}>
								<svg
									viewBox="0 0 16 16"
									width="12"
									height="12"
									aria-hidden="true"
									style={{
										transform: isCollapsed ? 'rotate(180deg)' : undefined,
									}}>
									<path
										d="M4 10l4-4 4 4"
										fill="none"
										stroke="currentColor"
										strokeWidth="1.6"
										strokeLinecap="round"
										strokeLinejoin="round"
									/>
								</svg>
							</button>
						</div>
					)}
				</div>

				{!isCollapsed && !isConfirmedMode && (
					<>
						<RoutePlannerForm
							mode={mode}
							onModeChange={handleModeChange}
							start={start}
							destination={destination}
							distance={distance}
							onDistanceChange={setDistance}
							routeCount={routeCount}
							onRouteCountChange={setRouteCount}
							isGpsActive={isGpsActive}
							isSending={isSending}
							canSend={canSend}
							onSend={handleSendRequest}
							onReset={handleReset}
							searchKey={searchKey}
							startQuery={startQuery}
							destinationQuery={destinationQuery}
							centerQuery={centerQuery}
							onStartQueryChange={setStartQuery}
							onDestinationQueryChange={setDestinationQuery}
							onCenterQueryChange={setCenterQuery}
							onSwap={handleSwap}
							onSelectStart={selectFromSearch(setStart)}
							onSelectDestination={selectFromSearch(setDestination)}
							onSelectCenter={selectFromSearch(setSinglePoint)}
						/>
					</>
				)}

				{!isCollapsed && !isConfirmedMode && (
					<RouteList
						routes={routes}
						selectedRouteId={selectedRouteId}
						onSelectRoute={handleSelectRoute}
						onConfirmRoute={handleConfirmRoute}
						isConfirming={isConfirming}
					/>
				)}

				{tripPhase === 'navigating' && navigation.route && (
					<>
						<NavigationPanel
							route={navigation.route}
							tracking={navigation.tracking}
							isSimulating={navigation.isSimulating}
							gpsError={navigation.gpsError}
							onToggleSimulation={navigation.toggleSimulation}
							onEnd={handleEndEarly}
						/>
						<RouteStreets
							names={selectedRoute?.properties?.names}
							bestRoad={selectedRoute?.properties?.best_road}
							full
						/>
					</>
				)}

				{tripPhase === 'rating' && (
					<RouteRating
						selectedRouteId={selectedRouteId}
						summary={tripSummary}
						onReset={handleReset}
					/>
				)}
			</div>

			<Map
				mode={mode}
				start={start}
				destination={destination}
				singlePoint={singlePoint}
				distance={distance}
				geoJsonData={geoJsonData}
				userLocation={userLocation}
				selectedRouteId={selectedRouteId}
				isConfirmedMode={isConfirmedMode}
				isGpsActive={isGpsActive}
				navigation={
					tripPhase === 'navigating' && navigation.route
						? { route: navigation.route, tracking: navigation.tracking }
						: null
				}
				onMapClick={handleMapClick}
			/>
		</div>
	);
}

export default App;
