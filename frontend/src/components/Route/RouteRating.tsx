import { useState } from 'react';
import type { TripSummary } from '../../hooks/useRouteTracking';
import { formatDistance, formatDuration } from '../../navigation';

interface RouteRatingProps {
	selectedRouteId: string | null;
	summary: TripSummary | null; // how the walk went, shown above the rating
	onReset: () => void;
}

export function RouteRating({ selectedRouteId, summary, onReset }: RouteRatingProps) {
	const [rating, setRating] = useState<number>(5);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isSubmitted, setIsSubmitted] = useState(false);

	const getRatingLabel = (score: number) => {
		if (score <= 3) return 'Disappointing 🙁';
		if (score <= 5) return 'Average 😐';
		if (score <= 7) return 'Good 🙂';
		if (score <= 9) return 'Great 😄';
		return 'Excellent! 🤩';
	};

	const handleRateRoute = async () => {
		if (isSubmitted) {
			alert('Already submitted rating');
			return;
		}

		setIsSubmitting(true);

		try {
			const response = await fetch('http://localhost:8000/feedback/', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ route_id: selectedRouteId, grade: rating }),
			});

			if (!response.ok) {
				throw new Error(`Server responded with status ${response.status}: ${response.statusText}`);
			}

			setIsSubmitted(true);
		} catch (err) {
			console.error('Failed to submit rating:', err);
			alert('Failed to submit rating. Please try again.');
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="rating-container">
			{summary && (
				<div className={`trip-summary ${summary.finished ? 'finished' : ''}`}>
					<div className="trip-summary-title">
						{summary.finished ? 'You have arrived' : 'Route ended early'}
					</div>
					<div className="trip-summary-stats">
						{summary.finished
							? formatDistance(summary.totalM)
							: `${formatDistance(summary.walkedM)} of ${formatDistance(summary.totalM)}`}{' '}
						in {formatDuration(summary.durationS)}
					</div>
				</div>
			)}

			<p className="rating-title">Rate this route</p>

			<div className="slider-wrapper">
				<div
					style={{
						display: 'flex',
						justifyContent: 'space-between',
						alignItems: 'center',
						marginBottom: '8px',
					}}>
					<span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>
						⭐ {rating}{' '}
						<span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 'normal' }}>
							/ 10
						</span>
					</span>
					<span
						style={{
							fontSize: '0.85rem',
							fontWeight: 600,
							color: 'var(--primary)',
							backgroundColor: 'var(--primary-light)',
							padding: '2px 8px',
							borderRadius: '12px',
						}}>
						{getRatingLabel(rating)}
					</span>
				</div>

				<input
					type="range"
					min={1}
					max={10}
					step={1}
					value={rating}
					onChange={(e) => setRating(Number(e.target.value))}
					disabled={isSubmitting || isSubmitted}
					className="rating-slider"
				/>

				<div
					style={{
						display: 'flex',
						justifyContent: 'space-between',
						fontSize: '0.75rem',
						color: 'var(--text-muted)',
						marginTop: '4px',
					}}>
					<span>1</span>
					<span>5</span>
					<span>10</span>
				</div>
			</div>

			{!isSubmitted ? (
				<button className="btn-submit-rating" onClick={handleRateRoute} disabled={isSubmitting}>
					{isSubmitting ? 'Submitting...' : 'Submit Rating'}
				</button>
			) : (
				<div className="rating-success-box">
					✅ Thank you! Rating of <strong>{rating}/10</strong> submitted.
				</div>
			)}

			<button className="btn-reset" style={{ width: '100%' }} onClick={onReset}>
				Done
			</button>
		</div>
	);
}
