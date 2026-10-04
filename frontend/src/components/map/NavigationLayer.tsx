import React, { useEffect, useRef, useState } from 'react';
import { CircleMarker, Polyline, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { walkedLine, type PreparedRoute, type Tracking } from '../../navigation';

interface NavigationLayerProps {
	route: PreparedRoute;
	tracking: Tracking;
}

const FOLLOW_ZOOM = 17;

/** The walker's position and the part of the route already walked; the map follows the walker
 * until they pan it away, then offers to recenter. */
export const NavigationLayer: React.FC<NavigationLayerProps> = ({ route, tracking }) => {
	const map = useMap();
	const [isFollowing, setIsFollowing] = useState(true);
	const hasZoomedRef = useRef(false);
	const recenterRef = useRef<HTMLButtonElement>(null);

	useMapEvents({
		dragstart: () => setIsFollowing(false),
	});

	const position = tracking.position;
	useEffect(() => {
		if (!isFollowing || !position) return;
		if (!hasZoomedRef.current) {
			hasZoomedRef.current = true;
			map.setView([position.lat, position.lng], Math.max(map.getZoom(), FOLLOW_ZOOM));
		} else {
			map.panTo([position.lat, position.lng], { animate: true });
		}
	}, [position, isFollowing, map]);

	// The button sits on the map, so its clicks mustn't reach the map's own click handler
	useEffect(() => {
		if (recenterRef.current) L.DomEvent.disableClickPropagation(recenterRef.current);
	}, [isFollowing]);

	const walked = walkedLine(route, tracking.walkedM).map(
		([lng, lat]) => [lat, lng] as [number, number],
	);

	return (
		<>
			{tracking.walkedM > 0 && (
				<Polyline
					positions={walked}
					pathOptions={{ color: '#64748b', weight: 9, opacity: 0.9, lineJoin: 'round' }}
				/>
			)}
			{position && (
				<>
					<CircleMarker
						center={[position.lat, position.lng]}
						radius={14}
						pathOptions={{ stroke: false, fillColor: '#2563eb', fillOpacity: 0.18 }}
					/>
					<CircleMarker
						center={[position.lat, position.lng]}
						radius={7}
						pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }}
					/>
				</>
			)}
			{!isFollowing && position && (
				<button ref={recenterRef} className="map-recenter-btn" onClick={() => setIsFollowing(true)}>
					Recenter
				</button>
			)}
		</>
	);
};
