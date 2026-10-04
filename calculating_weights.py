import osmnx as ox
import sqlite3



paths = list(ox.routing.k_shortest_paths(G, orig, dest, k=3, weight="stroll_cost"))
