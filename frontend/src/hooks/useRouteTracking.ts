import { useCallback, useEffect, useRef, useState } from 'react';
import type { Coordinate, GeoJSONRouteFeature } from '../interfaces';
import {
	INITIAL_TRACKING,
	advance,
	pointAt,
	prepareRoute,
	type PreparedRoute,
	type Tracking,
} from '../navigation';

// Simulated walk: a step every SIM_TICK_MS at SIM_SPEED_MS (several times walking pace, for demos)
const SIM_TICK_MS = 500;
const SIM_SPEED_MS = 35;

export interface TripSummary {
	finished: boolean; // reached the end, rather than ended early
	walkedM: number;
	totalM: number;
	durationS: number;
}

/**
 * Follows the walker along a chosen route - from the GPS, or from a simulated walk - and
 * calls `onArrive` once they reach its end.
 */
export function useRouteTracking(onArrive: (summary: TripSummary) => void) {
	const [route, setRoute] = useState<PreparedRoute | null>(null);
	const [tracking, setTracking] = useState<Tracking>(INITIAL_TRACKING);
	const [isSimulating, setIsSimulating] = useState(false);
	const [gpsError, setGpsError] = useState<string | null>(null);

	// Read by the GPS and timer callbacks, which outlive any one render
	const routeRef = useRef<PreparedRoute | null>(null);
	const trackingRef = useRef<Tracking>(INITIAL_TRACKING);
	const startedAtRef = useRef(0);
	const watchIdRef = useRef<number | null>(null);
	const timerRef = useRef<number | null>(null);
	const onArriveRef = useRef(onArrive);
	useEffect(() => {
		onArriveRef.current = onArrive;
	}, [onArrive]);

	const stopSources = useCallback(() => {
		if (watchIdRef.current !== null) {
			navigator.geolocation.clearWatch(watchIdRef.current);
			watchIdRef.current = null;
		}
		if (timerRef.current !== null) {
			window.clearInterval(timerRef.current);
			timerRef.current = null;
		}
	}, []);

	const summary = useCallback(
		(finished: boolean): TripSummary => ({
			finished,
			walkedM: finished ? (routeRef.current?.totalM ?? 0) : trackingRef.current.walkedM,
			totalM: routeRef.current?.totalM ?? 0,
			durationS: (Date.now() - startedAtRef.current) / 1000,
		}),
		[],
	);

	const handlePosition = useCallback(
		(position: Coordinate, timestamp: number) => {
			const current = routeRef.current;
			if (!current || trackingRef.current.arrived) return;
			const next = advance(current, trackingRef.current, position, timestamp);
			trackingRef.current = next;
			setTracking(next);
			if (next.arrived) {
				stopSources();
				setIsSimulating(false);
				onArriveRef.current(summary(true));
			}
		},
		[stopSources, summary],
	);

	const startGps = useCallback(() => {
		if (!navigator.geolocation) {
			setGpsError('Location is not available in this browser.');
			return;
		}
		setGpsError(null);
		watchIdRef.current = navigator.geolocation.watchPosition(
			(p) => {
				setGpsError(null);
				handlePosition({ lat: p.coords.latitude, lng: p.coords.longitude }, p.timestamp);
			},
			(error) => {
				console.error('GPS error:', error);
				setGpsError(
					error.code === error.PERMISSION_DENIED
						? 'Location access is blocked - allow it in the browser to be tracked.'
						: 'Waiting for your location…',
				);
			},
			{ enableHighAccuracy: true, timeout: 15000, maximumAge: 2000 },
		);
	}, [handlePosition]);

	/** Starts following the given route from its beginning, using the GPS. */
	const start = useCallback(
		(feature: GeoJSONRouteFeature) => {
			stopSources();
			const prepared = prepareRoute(feature);
			routeRef.current = prepared;
			trackingRef.current = INITIAL_TRACKING;
			startedAtRef.current = Date.now();
			setRoute(prepared);
			setTracking(INITIAL_TRACKING);
			setIsSimulating(false);
			startGps();
		},
		[startGps, stopSources],
	);

	/** Stops following; returns how far the walk got. */
	const stop = useCallback(() => {
		stopSources();
		setIsSimulating(false);
		const result = summary(trackingRef.current.arrived);
		routeRef.current = null;
		trackingRef.current = INITIAL_TRACKING;
		setRoute(null);
		setTracking(INITIAL_TRACKING);
		setGpsError(null);
		return result;
	}, [stopSources, summary]);

	/** Switches between the GPS and a simulated walk along the route from the current progress. */
	const toggleSimulation = useCallback(() => {
		const current = routeRef.current;
		if (!current) return;
		stopSources();
		if (isSimulating) {
			setIsSimulating(false);
			startGps();
			return;
		}
		setIsSimulating(true);
		setGpsError(null);
		// The simulated walker keeps their own distance, so they move on whatever the tracking makes
		// of each position - just like a real one
		let simulatedM = trackingRef.current.walkedM;
		timerRef.current = window.setInterval(() => {
			simulatedM = Math.min(simulatedM + (SIM_SPEED_MS * SIM_TICK_MS) / 1000, current.totalM);
			const [lng, lat] = pointAt(current, simulatedM);
			handlePosition({ lat, lng }, Date.now());
		}, SIM_TICK_MS);
	}, [handlePosition, isSimulating, startGps, stopSources]);

	useEffect(() => stopSources, [stopSources]);

	return { route, tracking, isSimulating, gpsError, start, stop, toggleSimulation };
}
