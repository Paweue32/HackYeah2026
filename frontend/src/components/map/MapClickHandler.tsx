import React from 'react';
import { useMapEvents } from 'react-leaflet';
import type { LeafletMouseEvent } from 'leaflet';
import type { Coordinate } from '../../interfaces';

interface MapClickHandlerProps {
	onMapClick: (coord: Coordinate) => void;
}

export const MapClickHandler: React.FC<MapClickHandlerProps> = ({ onMapClick }) => {
	useMapEvents({
		click(e: LeafletMouseEvent) {
			onMapClick({ lat: e.latlng.lat, lng: e.latlng.lng });
		},
	});

	return null;
};
