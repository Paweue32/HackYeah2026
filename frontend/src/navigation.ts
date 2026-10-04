import type { Coordinate, GeoJSONRouteFeature } from './interfaces';

// A position further than this from the route counts as off it, and doesn't move the progress
export const OFF_ROUTE_M = 35;
// Closer than this to the end of the route counts as arrived
export const ARRIVED_M = 25;
// The position is matched only to the route this far ahead of the progress, so a round trip,
// whose end is at its start, isn't finished the moment it begins...
const LOOKAHEAD_M = 400;
// ...plus as far as one could get at this speed since the last position on the route, so the
// progress catches up after a gap in the GPS (phones pause it with the screen off)...
const CATCH_UP_SPEED_MS = 3;
// ...and this far behind it, for GPS noise
const LOOKBEHIND_M = 30;
// Where the route passes the same place more than once, the first pass is taken: the best match
// within this many metres of the first part of the route close enough to the position
const FIRST_PASS_M = 100;
// Average walking pace, for the time left
export const WALKING_SPEED_MS = 1.35;

const EARTH_RADIUS_M = 6378137;

type LngLat = [number, number];

export interface StreetStretch {
	name: string;
	fromM: number; // metres along the route where it starts
	toM: number;
}

/** A route ready for tracking: its line, the metres along it at every vertex and its streets. */
export interface PreparedRoute {
	coords: LngLat[];
	cumulative: number[];
	totalM: number;
	streets: StreetStretch[];
}

export interface Tracking {
	position: Coordinate | null; // last reported position
	walkedM: number; // progress along the route; never goes back
	offRouteM: number | null; // distance from the route when off it, otherwise null
	arrived: boolean;
	lastOnRouteAt: number | null; // ms timestamp of the last position on the route
}

export const INITIAL_TRACKING: Tracking = {
	position: null,
	walkedM: 0,
	offRouteM: null,
	arrived: false,
	lastOnRouteAt: null,
};

function haversineM([lon1, lat1]: LngLat, [lon2, lat2]: LngLat) {
	const toRad = Math.PI / 180;
	const dLat = (lat2 - lat1) * toRad;
	const dLon = (lon2 - lon1) * toRad;
	const a =
		Math.sin(dLat / 2) ** 2 +
		Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2;
	return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
}

export function prepareRoute(feature: GeoJSONRouteFeature): PreparedRoute {
	const coords = feature.geometry.coordinates;
	const cumulative = [0];
	for (let i = 1; i < coords.length; i++) {
		cumulative.push(cumulative[i - 1] + haversineM(coords[i - 1], coords[i]));
	}
	const runs = feature.properties?.street_runs ?? [];
	return {
		coords,
		cumulative,
		totalM: cumulative[cumulative.length - 1] ?? 0,
		streets: runs.map((run) => ({
			name: run.name,
			fromM: cumulative[run.from],
			toM: cumulative[run.to],
		})),
	};
}

/** The point `meters` along the route. */
export function pointAt(route: PreparedRoute, meters: number): LngLat {
	const { coords, cumulative } = route;
	if (meters <= 0) return coords[0];
	for (let i = 1; i < coords.length; i++) {
		if (cumulative[i] >= meters) {
			const length = cumulative[i] - cumulative[i - 1];
			const t = length > 0 ? (meters - cumulative[i - 1]) / length : 0;
			return [
				coords[i - 1][0] + t * (coords[i][0] - coords[i - 1][0]),
				coords[i - 1][1] + t * (coords[i][1] - coords[i - 1][1]),
			];
		}
	}
	return coords[coords.length - 1];
}

/** The route's line up to `meters` along it - the part already walked. */
export function walkedLine(route: PreparedRoute, meters: number): LngLat[] {
	const line: LngLat[] = [];
	for (let i = 0; i < route.coords.length && route.cumulative[i] < meters; i++) {
		line.push(route.coords[i]);
	}
	line.push(pointAt(route, meters));
	return line;
}

/** Closest point to `p` on segment a-b: its distance in metres and how far along the segment (0-1). */
function projectOnSegment(p: LngLat, a: LngLat, b: LngLat) {
	// Flat metres around `a` - plenty accurate over one street segment
	const kx = Math.cos((a[1] * Math.PI) / 180) * ((Math.PI * EARTH_RADIUS_M) / 180);
	const ky = (Math.PI * EARTH_RADIUS_M) / 180;
	const bx = (b[0] - a[0]) * kx;
	const by = (b[1] - a[1]) * ky;
	const px = (p[0] - a[0]) * kx;
	const py = (p[1] - a[1]) * ky;
	const lengthSq = bx * bx + by * by;
	const t = lengthSq > 0 ? Math.min(Math.max((px * bx + py * by) / lengthSq, 0), 1) : 0;
	return { distanceM: Math.hypot(px - t * bx, py - t * by), t };
}

/** Tracking after a new position (taken at `timestamp` ms), matched to the part of the route just
 * ahead of the progress. */
export function advance(
	route: PreparedRoute,
	prev: Tracking,
	position: Coordinate,
	timestamp: number,
): Tracking {
	const p: LngLat = [position.lng, position.lat];
	const { coords, cumulative } = route;

	// Before the first position on the route the window doesn't grow - a round trip's end is at its start
	const secondsSince = prev.lastOnRouteAt === null ? 0 : (timestamp - prev.lastOnRouteAt) / 1000;
	const reachM = LOOKAHEAD_M + Math.max(secondsSince, 0) * CATCH_UP_SPEED_MS;

	let nearestM = Infinity; // to any part of the route, for how far off it the walker is
	let match: { distanceM: number; alongM: number } | null = null;
	let firstPassM: number | null = null;
	for (let i = 0; i < coords.length - 1; i++) {
		const { distanceM, t } = projectOnSegment(p, coords[i], coords[i + 1]);
		nearestM = Math.min(nearestM, distanceM);

		const inWindow =
			cumulative[i + 1] >= prev.walkedM - LOOKBEHIND_M && cumulative[i] <= prev.walkedM + reachM;
		if (!inWindow || distanceM > OFF_ROUTE_M) continue;
		if (firstPassM === null) firstPassM = cumulative[i];
		if (cumulative[i] > firstPassM + FIRST_PASS_M) continue;
		if (!match || distanceM < match.distanceM) {
			match = { distanceM, alongM: cumulative[i] + t * (cumulative[i + 1] - cumulative[i]) };
		}
	}

	const walkedM = match ? Math.max(prev.walkedM, match.alongM) : prev.walkedM;
	return {
		position,
		walkedM,
		offRouteM: match ? null : nearestM,
		arrived: route.totalM - walkedM <= ARRIVED_M,
		lastOnRouteAt: match ? timestamp : prev.lastOnRouteAt,
	};
}

/** Metres from a position to the start of the route. */
export function distanceToStartM(route: PreparedRoute, position: Coordinate) {
	return haversineM([position.lng, position.lat], route.coords[0]);
}

/** The street at `meters` along the route and the next different one with how far it is. */
export function streetsAround(route: PreparedRoute, meters: number) {
	const current = route.streets.find((s) => s.fromM <= meters && meters < s.toM) ?? null;
	const next = route.streets.find((s) => s.fromM > meters && s.name !== current?.name) ?? null;
	return {
		current: current?.name ?? null,
		next: next ? { name: next.name, inM: next.fromM - meters } : null,
	};
}

export function formatDistance(meters: number) {
	return meters < 1000 ? `${Math.round(meters / 10) * 10} m` : `${(meters / 1000).toFixed(1)} km`;
}

export function formatDuration(seconds: number) {
	const minutes = Math.max(1, Math.round(seconds / 60));
	return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}
