import { useEffect, useRef, useState } from 'react';
import type { Coordinate } from '../../interfaces';

interface SearchBarProps {
	disabled: boolean;
	placeholder?: string;
	query: string;
	onQueryChange: (query: string) => void;
	onLocationSelect: (coord: Coordinate) => void;
}

// Wait this long after the last keystroke before searching - Nominatim allows 1 request per second
const SEARCH_DELAY_MS = 800;
const MIN_QUERY_LENGTH = 3;
// Results inside Kraków (where the routing graph is) come first; places elsewhere are still found
const VIEWBOX = '19.79,50.13,20.22,49.97';

type SearchStatus = 'idle' | 'searching' | 'found' | 'not_found' | 'error';

export function SearchBar({
	disabled,
	placeholder,
	query,
	onQueryChange,
	onLocationSelect,
}: SearchBarProps) {
	const [status, setStatus] = useState<SearchStatus>('idle');
	// Text the box mounts with (e.g. after start and destination are swapped) already has its pin
	const lastSearched = useRef(query.trim());
	const controller = useRef<AbortController | null>(null);
	// Kept in a ref, so a new callback from the parent doesn't restart the typing delay
	const onSelect = useRef(onLocationSelect);
	useEffect(() => {
		onSelect.current = onLocationSelect;
	}, [onLocationSelect]);

	const search = async (text: string) => {
		const q = text.trim();
		if (q.length < MIN_QUERY_LENGTH || q === lastSearched.current) return;
		lastSearched.current = q;

		// Only the newest search may move the pin
		controller.current?.abort();
		const current = new AbortController();
		controller.current = current;
		setStatus('searching');

		try {
			const response = await fetch(
				`https://nominatim.openstreetmap.org/search?format=json&limit=1&viewbox=${VIEWBOX}&q=${encodeURIComponent(q)}`,
				{ signal: current.signal },
			);
			const data = await response.json();
			if (data && data.length > 0) {
				onSelect.current({
					lat: parseFloat(data[0].lat),
					lng: parseFloat(data[0].lon),
				});
				setStatus('found');
			} else {
				setStatus('not_found');
			}
		} catch (error) {
			if (current.signal.aborted) return;
			console.error('Search error:', error);
			lastSearched.current = ''; // let the same text be retried
			setStatus('error');
		}
	};

	// Search automatically once the user stops typing
	useEffect(() => {
		if (disabled) return;
		const timer = setTimeout(() => search(query), SEARCH_DELAY_MS);
		return () => clearTimeout(timer);
	}, [query, disabled]);

	useEffect(() => () => controller.current?.abort(), []);

	const statusTitle = {
		idle: 'Search',
		searching: 'Searching…',
		found: 'Location found',
		not_found: 'Location not found',
		error: 'Search failed - press Enter to retry',
	}[status];

	return (
		<div
			className={`search-container ${status === 'not_found' || status === 'error' ? 'invalid' : ''}`}>
			<input
				type="text"
				className="search-input"
				placeholder={placeholder}
				aria-label={placeholder}
				aria-invalid={status === 'not_found' || status === 'error'}
				value={query}
				onChange={(e) => {
					onQueryChange(e.target.value);
					if (status !== 'searching') setStatus('idle');
				}}
				onKeyDown={(e) => e.key === 'Enter' && search(query)}
				disabled={disabled}
			/>
			<button
				className="search-btn"
				onClick={() => search(query)}
				disabled={disabled || query.trim().length < MIN_QUERY_LENGTH}
				title={statusTitle}
				aria-label={statusTitle}>
				{status === 'searching' ? (
					'…'
				) : status === 'not_found' || status === 'error' ? (
					'!'
				) : (
					<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
						<circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
						<path
							d="M10.5 10.5 14 14"
							stroke="currentColor"
							strokeWidth="1.6"
							strokeLinecap="round"
						/>
					</svg>
				)}
			</button>
		</div>
	);
}
