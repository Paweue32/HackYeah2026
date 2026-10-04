import type { BestRoad } from '../../interfaces';

interface RouteStreetsProps {
	names?: string[];
	bestRoad?: BestRoad | null;
	full?: boolean; // every street instead of a shortened list
}

const SHORT_COUNT = 4;

export function RouteStreets({ names, bestRoad, full = false }: RouteStreetsProps) {
	if (!names || names.length === 0) return null;

	let shown = full ? names : names.slice(0, SHORT_COUNT);
	// The best-rated street always stays visible in the shortened list
	if (bestRoad && !shown.includes(bestRoad.name)) {
		shown = [...shown.slice(0, -1), bestRoad.name];
	}
	const hidden = names.length - shown.length;

	return (
		<span className={`route-streets ${full ? 'full' : ''}`} title={names.join(' → ')}>
			{full && <strong>Via: </strong>}
			{shown.map((name, i) => (
				<span key={name}>
					{i > 0 && ' → '}
					{name === bestRoad?.name ? (
						<span className="best-road" title={`Best-rated street: ${bestRoad.rating}/10`}>
							★ {name}
						</span>
					) : (
						name
					)}
				</span>
			))}
			{hidden > 0 && ` +${hidden} more`}
		</span>
	);
}
