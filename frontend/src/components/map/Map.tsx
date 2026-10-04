import React from 'react';
import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import type { Coordinate, GeoJSONRouteData, SelectionMode } from '../../interfaces';
import { MapRecenter } from './MapRecenter';
import { MapResizer } from './MapResizer';
import { MapClickHandler } from './MapClickHandler';
import { MapMarkers } from './MapMarkers';
import { RouteLayer } from '../Route/RouteLayer';
import { NavigationLayer } from './NavigationLayer';
import type { PreparedRoute, Tracking } from '../../navigation';

const DEFAULT_CENTER: [number, number] = [50.0617, 19.9373];

interface MapProps {
	mode: SelectionMode;
	start: Coordinate | null;
	destination: Coordinate | null;
	singlePoint: Coordinate | null;
	distance: number;
	geoJsonData: GeoJSONRouteData | null;
	selectedRouteId: string | null;
	userLocation: Coordinate | null;
	isConfirmedMode?: boolean;
	isGpsActive?: boolean;
	navigation?: { route: PreparedRoute; tracking: Tracking } | null; // while walking a route
	onMapClick: (coord: Coordinate) => void;
}

export const Map: React.FC<MapProps> = ({
	mode,
	start,
	destination,
	singlePoint,
	distance,
	geoJsonData,
	selectedRouteId,
	userLocation,
	isConfirmedMode = false,
	isGpsActive = false,
	navigation = null,
	onMapClick,
}) => {
	const startLocation = mode === 'two_points' ? start : singlePoint;

	return (
		<div style={{ height: '100vh', width: '100vw' }}>
			<MapContainer center={DEFAULT_CENTER} zoom={13} style={{ height: '100%', width: '100%' }}>
				<MapRecenter
					userLocation={userLocation}
					startLocation={startLocation}
					isConfirmedMode={isConfirmedMode}
					isGpsActive={isGpsActive}
				/>
				<MapResizer />
				<MapClickHandler onMapClick={onMapClick} />

				<TileLayer
					attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
					url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
				/>

				<MapMarkers
					mode={mode}
					start={start}
					destination={destination}
					singlePoint={singlePoint}
					distance={distance}
					userLocation={userLocation}
				/>

				<RouteLayer geoJsonData={geoJsonData} selectedRouteId={selectedRouteId} />

				{navigation && <NavigationLayer route={navigation.route} tracking={navigation.tracking} />}
			</MapContainer>
		</div>
	);
};

export default Map;
