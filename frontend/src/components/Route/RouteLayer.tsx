import React from 'react';
import { GeoJSON } from 'react-leaflet';
import type L from 'leaflet';
import type { GeoJSONRouteData } from '../../interfaces';

interface RouteLayerProps {
	geoJsonData: GeoJSONRouteData | null;
	selectedRouteId: string | null;
}

const BEST_ROAD_COLOR = '#facc15';

export const RouteLayer: React.FC<RouteLayerProps> = ({ geoJsonData, selectedRouteId }) => {
	if (!geoJsonData) return null;

	// Glow under the highest-rated street of every route (only the selected one once a route is chosen)
	const bestRoads: GeoJSON.FeatureCollection = {
		type: 'FeatureCollection',
		features: geoJsonData.features
			.filter((f) => f.properties?.best_road)
			.filter((f) => selectedRouteId === null || f.properties?.id === String(selectedRouteId))
			.map((f) => {
				const road = f.properties!.best_road!;
				return {
					type: 'Feature',
					properties: { name: road.name, rating: road.rating },
					geometry: road.geometry,
				};
			}),
	};

	return (
		<>
			<GeoJSON
				key={`best-${selectedRouteId}-${JSON.stringify(geoJsonData)}`}
				data={bestRoads}
				style={() => ({
					color: BEST_ROAD_COLOR,
					weight: selectedRouteId !== null ? 18 : 14,
					opacity: 0.75,
					lineCap: 'round',
					lineJoin: 'round',
				})}
				onEachFeature={(feature, layer) => {
					layer.bindPopup(`★ Best-rated street: ${feature.properties.name} (${feature.properties.rating}/10)`);
				}}
			/>
			<GeoJSON
				key={JSON.stringify(geoJsonData)}
				data={geoJsonData}
				style={(feature) => {
					const isSelected = feature?.properties?.id === String(selectedRouteId);

					return {
						color: feature?.properties?.color || '#2563eb',
						weight: isSelected ? 8 : 4,
						opacity: selectedRouteId !== null ? (isSelected ? 1.0 : 0.35) : 0.8,
						lineJoin: 'round',
					};
				}}
				onEachFeature={(feature, layer) => {
					const isSelected = feature?.properties?.id === String(selectedRouteId);

					if (isSelected && 'bringToFront' in layer) {
						(layer as L.Path).bringToFront();
					}

					if (feature?.properties?.name) {
						layer.bindPopup(feature.properties.name);
					}
				}}
			/>
		</>
	);
};
