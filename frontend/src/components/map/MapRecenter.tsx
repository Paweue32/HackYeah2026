import React, { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import type { Coordinate } from '../../interfaces';

interface MapRecenterProps {
	userLocation: Coordinate | null;
	startLocation: Coordinate | null;
	isConfirmedMode: boolean;
	isGpsActive: boolean;
}

export const MapRecenter: React.FC<MapRecenterProps> = ({
	userLocation,
	startLocation,
	isConfirmedMode,
	isGpsActive,
}) => {
	const map = useMap();
	const prevConfirmedRef = useRef<boolean>(false);

	useEffect(() => {
		if (isConfirmedMode && !prevConfirmedRef.current && startLocation) {
			map.flyTo([startLocation.lat, startLocation.lng], 15, { animate: true, duration: 1.2 });
		}
		prevConfirmedRef.current = isConfirmedMode;
	}, [isConfirmedMode, startLocation, map]);

	useEffect(() => {
		if (isGpsActive && userLocation) {
			map.panTo([userLocation.lat, userLocation.lng], { animate: true });
		}
	}, [userLocation, isGpsActive, map]);

	return null;
};
