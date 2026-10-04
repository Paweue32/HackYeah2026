import React from 'react';
import { Marker, Popup, Circle } from 'react-leaflet';
import type { Coordinate, SelectionMode } from '../../interfaces';
import { startIcon, destIcon, userIcon } from '../../leafletIcons';

interface MapMarkersProps {
	mode: SelectionMode;
	start: Coordinate | null;
	destination: Coordinate | null;
	singlePoint: Coordinate | null;
	distance: number;
	userLocation: Coordinate | null;
}

export const MapMarkers: React.FC<MapMarkersProps> = ({
	mode,
	start,
	destination,
	singlePoint,
	distance,
	userLocation,
}) => {
	return (
		<>
			{mode === 'two_points' && (
				<>
					{start && (
						<Marker position={[start.lat, start.lng]} icon={userLocation ? userIcon : startIcon}>
							<Popup>Start Point</Popup>
						</Marker>
					)}
					{destination && (
						<Marker position={[destination.lat, destination.lng]} icon={destIcon}>
							<Popup>Destination Point</Popup>
						</Marker>
					)}
				</>
			)}

			{mode === 'point_distance' && singlePoint && (
				<>
					<Marker
						position={[singlePoint.lat, singlePoint.lng]}
						icon={userLocation ? userIcon : startIcon}>
						<Popup>Selected Center Point</Popup>
					</Marker>

					{distance > 0 && (
						<Circle
							center={[singlePoint.lat, singlePoint.lng]}
							radius={distance}
							pathOptions={{
								color: '#2563eb',
								fillColor: '#3b82f6',
								fillOpacity: 0.2,
								weight: 2,
							}}
						/>
					)}
				</>
			)}
		</>
	);
};
