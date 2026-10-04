<div align="center">

<!-- TODO: Add a screenshot of the app or a title slide -->
<!-- <img src="docs/hero.png" alt="<NAZWA_PROJEKTU> — walking loops on a map of Kraków" width="900"/> -->

# 🚶 <NAZWA_PROJEKTU>

### Pick how far you want to walk from home. Get three loop routes and come back a different way.

**HackYeah 2026 · SPORT & HEALTHCARE · task: <NAZWA_ZADANIA>**

[🎬 Demo](<LINK_DO_DEMO>) · [📊 Presentation](<LINK_DO_PREZENTACJI>) · [🎨 Figma](<LINK_DO_FIGMY>) · [🌐 Live app](<LINK_DO_APLIKACJI>)

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![NetworkX](https://img.shields.io/badge/NetworkX-A*-orange)
![GeoPandas](https://img.shields.io/badge/GeoPandas-Shapely-139C5A)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Leaflet](https://img.shields.io/badge/Leaflet-map-199900?logo=leaflet&logoColor=white)
![OpenStreetMap](https://img.shields.io/badge/data-OpenStreetMap-7EBC6F?logo=openstreetmap&logoColor=white)

</div>

---

## What it does

Most navigation apps assume you have a destination. This project is for the times when you just want to go for a walk.

Choose a starting point and a radius — say, 500 metres — and the app generates three walking loops around Kraków. The routes head towards the edge of the selected area, follow different directions, and return to the starting point. The routing engine gives more weight to streets rated as pleasant to walk along, rather than simply choosing the shortest route.

After a walk, you can rate the route from 1 to 10. That rating updates the scores of the streets you used, so future routes can take previous feedback into account.

## The problem

The [WHO recommends](https://www.who.int/news-room/fact-sheets/detail/physical-activity) at least **150 minutes of moderate physical activity per week** for adults. Walking is an accessible way to get moving, but finding a route can be awkward when you don't have a specific destination in mind.

- **You don't have a destination.** Most navigation apps ask where you want to go, not how long or how far you want to walk.
- **Routes get repetitive.** It's easy to end up walking the same streets every time.
- **The shortest route isn't always the nicest.** A route can follow busy roads even when a park or riverside path is nearby.

## How to use it

1. **Choose a starting point.** Click the map, search for an address, or use your GPS location.
2. **Set the radius.** The circle on the map shows how far from the start the route can go.
3. **Pick one of three loops.** Each route takes a different direction and includes its length and street names.
4. **Start walking.** Navigation mode tracks your GPS position along the selected route.
5. **Leave a rating.** Rate the walk from 1 to 10. The rating is applied to the streets on that route.

There's also an **A→B mode** for when you do have a destination. It finds a low-cost route between two points and shows its length alongside the shortest available route.

## Features

| | Feature | Details |
|---|---|---|
| 🔁 | **Three loops per request** | Generates three routes in different directions, with a random starting angle to vary the results. |
| ⭕ | **Choose a radius** | Routes stay within the selected circle. |
| ↩️ | **Less repeated walking** | Streets already used on one leg receive a higher cost on later legs, encouraging a different way back. |
| 📍 | **A→B routing** | Uses A* to find a minimum-cost route under the routing model. |
| 🌳 | **Street ratings** | Each of the 72,668 OSM ways has an initial score based on greenery, water, traffic and other features. |
| ⭐ | **Community feedback** | A submitted rating updates the average score of the streets on the route and their graph costs. |
| 🏷️ | **Street names** | Route details include the street names in travel order. |
| 🛰️ | **GPS and address search** | Start from your current location or search for an address with Nominatim. |

---

## Architecture

```mermaid
flowchart LR
    subgraph Dane [Data preparation]
        A[Overpass API<br/>OpenStreetMap] -->|72,668 roads| B[(SQLite<br/>ways)]
        A -->|road tags, parks, water| GR[generate_ratings.py<br/>rating model]
        GR -->|scores 1–10| B
    end
    subgraph Backend [Backend · FastAPI]
        B -->|server startup| C[NetworkX graph<br/>194,625 nodes]
        D["POST /generate/"] --> E[RoutingEngine]
        C --> E
        E --> S[(active routes<br/>TTL 30 min)]
        FB["POST /feedback/"] -->|updated street averages| B
        FB -->|updated costs| C
    end
    subgraph Frontend [Frontend · React + Leaflet]
        U[start + radius<br/>or A→B] --> D
        E -->|GeoJSON FeatureCollection| F[3 routes on map]
        F -->|route selection| X["POST /discard/"] --> S
        F -->|post-walk rating| FB
    end
