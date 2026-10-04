import { useState, useRef, useEffect, useCallback } from 'react';
import type { Coordinate, SelectionMode } from '../interfaces';

interface UseGeolocationProps {
	mode: SelectionMode;
	isConfirmedMode: boolean;
	onLocationUpdate: (loc: Coordinate, mode: SelectionMode) => void;
}

export function useGeolocation({ mode, isConfirmedMode, onLocationUpdate }: UseGeolocationProps) {
	const [isGpsActive, setIsGpsActive] = useState(false);
	const [userLocation, setUserLocation] = useState<Coordinate | null>(null);
	const watchIdRef = useRef<number | null>(null);

	const modeRef = useRef(mode);
	const isConfirmedModeRef = useRef(isConfirmedMode);

	useEffect(() => {
		modeRef.current = mode;
	}, [mode]);

	useEffect(() => {
		isConfirmedModeRef.current = isConfirmedMode;
	}, [isConfirmedMode]);

	const disableGps = useCallback(() => {
		if (watchIdRef.current !== null) {
			navigator.geolocation.clearWatch(watchIdRef.current);
			watchIdRef.current = null;
		}
		setIsGpsActive(false);
		setUserLocation(null);
	}, []);

	const enableGps = useCallback(() => {
		if (!navigator.geolocation) {
			alert('Geolocation is not supported by your browser.');
			return;
		}

		setIsGpsActive(true);
		if (watchIdRef.current !== null) return;

		watchIdRef.current = navigator.geolocation.watchPosition(
			(position) => {
				const loc = {
					lat: position.coords.latitude,
					lng: position.coords.longitude,
				};
				setUserLocation(loc);

				if (!isConfirmedModeRef.current) {
					onLocationUpdate(loc, modeRef.current);
				}
			},
			(error) => {
				console.error('GPS error:', error);
				alert('Could not access your location. Please check browser permissions.');
				disableGps();
			},
			{
				enableHighAccuracy: true,
				timeout: 15000,
				maximumAge: 5000,
			},
		);
	}, [disableGps, onLocationUpdate]);

	useEffect(() => {
		return () => {
			if (watchIdRef.current !== null) {
				navigator.geolocation.clearWatch(watchIdRef.current);
			}
		};
	}, []);

	const toggleGps = () => (isGpsActive ? disableGps() : enableGps());

	return { isGpsActive, userLocation, toggleGps, disableGps };
}
