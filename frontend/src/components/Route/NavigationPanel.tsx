import { useState } from 'react';
import {
	WALKING_SPEED_MS,
	distanceToStartM,
	formatDistance,
	formatDuration,
	streetsAround,
	type PreparedRoute,
	type Tracking,
} from '../../navigation';

interface NavigationPanelProps {
	route: PreparedRoute;
	tracking: Tracking;
	isSimulating: boolean;
	gpsError: string | null;
	onToggleSimulation: () => void;
	onEnd: () => void;
}

/** Turn-by-street guidance while walking a chosen route. */
export function NavigationPanel({
	route,
	tracking,
	isSimulating,
	gpsError,
	onToggleSimulation,
	onEnd,
}: NavigationPanelProps) {
	const [isConfirmingEnd, setIsConfirmingEnd] = useState(false);

	const remainingM = Math.max(route.totalM - tracking.walkedM, 0);
	const progress = route.totalM > 0 ? tracking.walkedM / route.totalM : 0;
	const { current, next } = streetsAround(route, tracking.walkedM);

	let status: string;
	if (!tracking.position) {
		status = gpsError ?? 'Waiting for your location…';
	} else if (tracking.offRouteM !== null && tracking.walkedM === 0) {
		status = `Head to the start - ${formatDistance(distanceToStartM(route, tracking.position))} away`;
	} else if (tracking.offRouteM !== null) {
		status = `Off the route by ${formatDistance(tracking.offRouteM)} - head back to the line`;
	} else {
		status = current ? `On ${current}` : 'On the route';
	}
	const isWarning = !tracking.position || tracking.offRouteM !== null;

	return (
		<div className="nav-panel">
			<div className={`nav-status ${isWarning ? 'warning' : ''}`} role="status">
				{status}
			</div>
			{next && (
				<div className="nav-next">
					Next: <strong>{next.name}</strong> in {formatDistance(next.inM)}
				</div>
			)}

			<div
				className="nav-progress"
				role="progressbar"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={Math.round(progress * 100)}>
				<div className="nav-progress-fill" style={{ width: `${progress * 100}%` }} />
			</div>
			<div className="nav-stats">
				<span>
					<strong>{formatDistance(remainingM)}</strong> left
				</span>
				<span>~{formatDuration(remainingM / WALKING_SPEED_MS)}</span>
				<span>{Math.round(progress * 100)}%</span>
			</div>

			{isConfirmingEnd ? (
				<div className="nav-confirm">
					<span>End the route now?</span>
					<div className="button-group">
						<button className="btn-danger" onClick={onEnd}>
							End route
						</button>
						<button className="btn-reset" onClick={() => setIsConfirmingEnd(false)}>
							Keep going
						</button>
					</div>
				</div>
			) : (
				<div className="button-group">
					<button className="btn-reset nav-end" onClick={() => setIsConfirmingEnd(true)}>
						End route
					</button>
					<button
						className={`btn-reset ${isSimulating ? 'active' : ''}`}
						onClick={onToggleSimulation}
						aria-pressed={isSimulating}
						title="Walk the route automatically - for trying it out without moving">
						{isSimulating ? 'Stop simulation' : 'Simulate walk'}
					</button>
				</div>
			)}
		</div>
	);
}
