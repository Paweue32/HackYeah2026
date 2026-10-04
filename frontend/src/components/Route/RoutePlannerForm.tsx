import type { Coordinate, SelectionMode } from '../../interfaces';
import { SearchBar } from './SearchBar';

interface RoutePlannerFormProps {
	mode: SelectionMode;
	onModeChange: (mode: SelectionMode) => void;
	start: Coordinate | null;
	destination: Coordinate | null;
	distance: number;
	onDistanceChange: (distance: number) => void;
	routeCount: number;
	onRouteCountChange: (count: number) => void;
	isGpsActive: boolean;
	isSending: boolean;
	canSend: boolean;
	onSend: () => void;
	onReset: () => void;
	searchKey: number; // changes when the search boxes' text is replaced (reset, swap)
	startQuery: string;
	destinationQuery: string;
	centerQuery: string;
	onStartQueryChange: (query: string) => void;
	onDestinationQueryChange: (query: string) => void;
	onCenterQueryChange: (query: string) => void;
	onSwap: () => void;
	onSelectStart: (coord: Coordinate) => void;
	onSelectDestination: (coord: Coordinate) => void;
	onSelectCenter: (coord: Coordinate) => void;
}

const ROUTE_COUNTS = [1, 2, 3, 4, 5];

export function RoutePlannerForm({
	mode,
	onModeChange,
	start,
	destination,
	distance,
	onDistanceChange,
	routeCount,
	onRouteCountChange,
	isGpsActive,
	isSending,
	canSend,
	onSend,
	onReset,
	searchKey,
	startQuery,
	destinationQuery,
	centerQuery,
	onStartQueryChange,
	onDestinationQueryChange,
	onCenterQueryChange,
	onSwap,
	onSelectStart,
	onSelectDestination,
	onSelectCenter,
}: RoutePlannerFormProps) {
	return (
		<>
			<div className="tab-group">
				<button
					className={`tab-btn ${mode === 'two_points' ? 'active' : ''}`}
					onClick={() => onModeChange('two_points')}>
					A → B
				</button>
				<button
					className={`tab-btn ${mode === 'point_distance' ? 'active' : ''}`}
					onClick={() => onModeChange('point_distance')}>
					Round trip
				</button>
			</div>

			{mode === 'two_points' ? (
				<div className="field-stack">
					<div className="search-pair">
						<div className="search-pair-fields">
							<SearchBar
								key={`start-${searchKey}`}
								placeholder="Start"
								disabled={isGpsActive}
								query={startQuery}
								onQueryChange={onStartQueryChange}
								onLocationSelect={onSelectStart}
							/>
							<SearchBar
								key={`destination-${searchKey}`}
								placeholder="Destination"
								disabled={false}
								query={destinationQuery}
								onQueryChange={onDestinationQueryChange}
								onLocationSelect={onSelectDestination}
							/>
						</div>
						<button
							className="icon-btn"
							onClick={onSwap}
							disabled={isGpsActive || (!start && !destination)}
							title={isGpsActive ? 'Turn off my location to swap' : 'Swap start and destination'}
							aria-label="Swap start and destination">
							<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
								<path
									d="M5 13V3M2.5 5.5 5 3l2.5 2.5M11 3v10M8.5 10.5 11 13l2.5-2.5"
									fill="none"
									stroke="currentColor"
									strokeWidth="1.5"
									strokeLinecap="round"
									strokeLinejoin="round"
								/>
							</svg>
						</button>
					</div>
				</div>
			) : (
				<div className="field-stack">
					<SearchBar
						key={`center-${searchKey}`}
						placeholder="Center"
						disabled={isGpsActive}
						query={centerQuery}
						onQueryChange={onCenterQueryChange}
						onLocationSelect={onSelectCenter}
					/>
				</div>
			)}

			<div className="options-row">
				{mode === 'point_distance' && (
					<label className="option">
						<span className="option-label">Radius, m</span>
						<input
							type="number"
							min="100"
							step="100"
							value={distance}
							onChange={(e) => onDistanceChange(Number(e.target.value))}
							className="distance-input"
						/>
					</label>
				)}
				<div className="option">
					<span className="option-label" id="route-count-label">
						Routes
					</span>
					<div className="tab-group count-group" role="group" aria-labelledby="route-count-label">
						{ROUTE_COUNTS.map((n) => (
							<button
								key={n}
								className={`tab-btn ${routeCount === n ? 'active' : ''}`}
								aria-pressed={routeCount === n}
								onClick={() => onRouteCountChange(n)}>
								{n}
							</button>
						))}
					</div>
				</div>
			</div>

			<div className="button-group">
				<button className="btn-send" onClick={onSend} disabled={!canSend || isSending}>
					{isSending ? 'Finding routes…' : 'Find routes'}
				</button>
				<button className="btn-reset" onClick={onReset}>
					Reset
				</button>
			</div>
		</>
	);
}
