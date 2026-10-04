export interface Coordinate {
	lat: number;
	lng: number;
}

export type SelectionMode = 'two_points' | 'point_distance';

export interface RouteRequestPayload {
	mode: SelectionMode;
	start?: Coordinate;
	destination?: Coordinate;
	point?: Coordinate;
	distance?: number;
	count?: number; // how many suggestions to get back
}

export interface BestRoad {
	name: string;
	rating: number; // 1-10
	length_m: number;
	geometry: {
		type: 'MultiLineString';
		coordinates: [number, number][][]; // [longitude, latitude]
	};
}

/** A stretch of a route along one named street; indices into the route's coordinates. */
export interface StreetRun {
	name: string;
	from: number;
	to: number;
}

export interface RouteProperties {
	id: string;
	name?: string;
	color?: string;
	distance?: number;
	duration?: number;
	names?: string[]; // street names along the route, in walking order
	length_m?: number;
	best_road?: BestRoad | null; // highest-rated street on the route
	street_runs?: StreetRun[];
	[key: string]: unknown;
}

export interface GeoJSONRouteFeature {
	type: 'Feature';
	properties?: RouteProperties | null;
	geometry: {
		type: 'LineString';
		coordinates: [number, number][]; // [longitude, latitude]
	};
}

export interface GeoJSONRouteData {
	type: 'FeatureCollection';
	features: GeoJSONRouteFeature[];
}
