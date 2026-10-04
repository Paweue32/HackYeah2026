import type { GeoJSONRouteFeature } from '../../interfaces';
import { RouteStreets } from './RouteStreets';

interface RouteListProps {
	routes: GeoJSONRouteFeature[];
	selectedRouteId: string | null;
	onSelectRoute: (id: string) => void;
	onConfirmRoute: () => void;
	isConfirming: boolean;
}

function formatLength(meters?: number) {
	if (meters === undefined) return null;
	return meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(1)} km`;
}

export function RouteList({
	routes,
	selectedRouteId,
	onSelectRoute,
	onConfirmRoute,
	isConfirming,
}: RouteListProps) {
	if (routes.length === 0) return null;

	return (
		<section className="routes-section">
			<div className="section-title">Routes · {routes.length}</div>
			<div className="routes-list">
				{routes.map((feature, idx) => {
					const id = String(feature.properties?.id);
					const name = feature.properties?.name || `Route ${idx + 1}`;
					const color = feature.properties?.color || '#2563eb';
					const length = formatLength(feature.properties?.length_m);
					const isSelected = id === selectedRouteId;

					return (
						<button
							key={idx}
							className={`route-item ${isSelected ? 'selected' : ''}`}
							aria-pressed={isSelected}
							onClick={() => onSelectRoute(id)}>
							<span className="route-color-dot" style={{ backgroundColor: color }} />
							<span className="route-text">
								<span className="route-head">
									<span className="route-name">{name}</span>
									{length && <span className="route-length">{length}</span>}
								</span>
								<RouteStreets
									names={feature.properties?.names}
									bestRoad={feature.properties?.best_road}
								/>
							</span>
						</button>
					);
				})}
			</div>
			{selectedRouteId && (
				<button className="btn-confirm-route" onClick={onConfirmRoute} disabled={isConfirming}>
					{isConfirming ? 'Confirming…' : 'Start this route'}
				</button>
			)}
		</section>
	);
}
