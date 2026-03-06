# Cargo and Route Data Structures

## Cargo

```typescript
interface Cargo {
  id: string;
  type: string;
  origin: string;
  destination: string;
  quantity: number;
  deadline?: number;
  value: number;
}
```

## Route

```typescript
interface Route {
  id: string;
  waypoints: string[];
  distance: number;
  travelTime: number;
  cost: number;
  capacity: number;
}
```

## Relationships

- Cargo references routes by waypoint IDs
- Routes define the transport network graph
- Cargo flows from origin to destination along available routes
