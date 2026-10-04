import React, { useEffect } from 'react';
import { useMap } from 'react-leaflet';

export const MapResizer: React.FC = () => {
	const map = useMap();

	useEffect(() => {
		const timer = setTimeout(() => map.invalidateSize(), 100);
		return () => clearTimeout(timer);
	}, [map]);

	return null;
};
