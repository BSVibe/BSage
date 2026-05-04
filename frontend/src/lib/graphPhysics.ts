/**
 * Pure helpers for the knowledge graph view (Phase 1).
 *
 * These keep the React component free of side-effect-laden physics math
 * so each piece is independently testable and the canvas render path
 * stays readable.
 */

import type { VaultGraphLink, VaultCommunity } from "../api/types";

/** node id → degree (count of incident links). */
export function computeDegree(links: readonly VaultGraphLink[]): Record<string, number> {
  const degree: Record<string, number> = {};
  for (const l of links) {
    const s = typeof l.source === "string" ? l.source : (l.source as { id: string }).id;
    const t = typeof l.target === "string" ? l.target : (l.target as { id: string }).id;
    degree[s] = (degree[s] ?? 0) + 1;
    degree[t] = (degree[t] ?? 0) + 1;
  }
  return degree;
}

/** Hub-aware node radius: log-scaled by degree. */
export function nodeRadius(degree: number, isSelected: boolean): number {
  if (isSelected) return 7;
  return 4 + Math.min(8, Math.log2(degree + 1));
}

/** Degree threshold below which labels are hidden at low zoom (top-percentile cutoff). */
export function labelDegreeThreshold(
  degreeMap: Record<string, number>,
  topPercentile = 0.05,
): number {
  const values = Object.values(degreeMap);
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => b - a);
  const cutoffIdx = Math.max(0, Math.floor(sorted.length * topPercentile) - 1);
  return sorted[cutoffIdx] ?? 0;
}

/**
 * LOD label visibility — show when zoomed in OR for hub nodes.
 *
 * @param globalScale current zoom level from ForceGraph2D
 * @param degree node degree
 * @param hubThreshold degree at-or-above which a node is considered a hub
 * @param zoomThreshold zoom above which all labels render
 */
export function shouldShowLabel(
  globalScale: number,
  degree: number,
  hubThreshold: number,
  zoomThreshold = 1.2,
): boolean {
  if (globalScale >= zoomThreshold) return true;
  return degree >= hubThreshold && hubThreshold > 0;
}

/**
 * Cached label-width measurement. Returns half the width in *world* units
 * so callers can use it as a collision radius regardless of zoom.
 */
export function labelHalfWidth(
  text: string,
  ctx: CanvasRenderingContext2D,
  cache: Map<string, number>,
  fontSize: number,
): number {
  const key = `${text}::${fontSize}`;
  const cached = cache.get(key);
  if (cached !== undefined) return cached;
  ctx.font = `${fontSize}px "Plus Jakarta Sans", sans-serif`;
  const width = ctx.measureText(text).width / 2;
  cache.set(key, width);
  return width;
}

/**
 * Map node id → community centroid coords (computed once per simulation tick).
 * Returns null when no communities are loaded.
 */
export type Centroid = { x: number; y: number };

export function computeCommunityCentroids(
  nodes: readonly { id: string; x?: number; y?: number }[],
  communities: readonly VaultCommunity[],
): Map<number, Centroid> {
  const centroids = new Map<number, Centroid>();
  if (communities.length === 0) return centroids;

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  for (const c of communities) {
    let sx = 0;
    let sy = 0;
    let count = 0;
    for (const id of c.members) {
      const n = nodeById.get(id);
      if (!n || n.x === undefined || n.y === undefined) continue;
      sx += n.x;
      sy += n.y;
      count += 1;
    }
    if (count > 0) centroids.set(c.id, { x: sx / count, y: sy / count });
  }
  return centroids;
}

/** node id → community id lookup. */
export function buildNodeCommunityIdMap(
  communities: readonly VaultCommunity[],
): Map<string, number> {
  const map = new Map<string, number>();
  for (const c of communities) {
    for (const id of c.members) map.set(id, c.id);
  }
  return map;
}
