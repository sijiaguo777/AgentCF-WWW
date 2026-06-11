#!/usr/bin/env python3
"""Run Louvain community detection on ScientificKG concept graph using SQLite DB directly.

Reuses louvain_style_partition() from the ScientificKG communities module.
Outputs concept_communities_sqlite.json with node_to_community mapping and community summaries.
"""

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add ScientificKG src to path for importing louvain functions
SCIENTIFICKG_SRC = Path("/Users/guosijia/Desktop/downloaded_files/ScientificKG/src")
if str(SCIENTIFICKG_SRC) not in sys.path:
    sys.path.insert(0, str(SCIENTIFICKG_SRC))

from scientifickg.communities.discover_modularity import (
    louvain_style_partition,
    make_simple_adjacency,
    normalize_labels,
    split_oversized_communities,
    invert_labels,
)
from scientifickg.communities.discover_hub_filtered import summarize_communities


def load_graph_from_sqlite(db_path: str, min_edge_weight: int = 2, hub_percent: float = 0.1):
    """Load concept graph from SQLite DB.

    Returns:
        nodes: dict[node_id] -> {concept, ontology_type}
        weighted_adjacency: dict[src][dst] -> int weight
    """
    conn = sqlite3.connect(db_path)

    # Load nodes
    nodes = {}
    for row in conn.execute(
        "SELECT node_id, concept, ontology_type FROM concept_nodes WHERE in_graph=1"
    ):
        node_id, concept, ontology_type = row
        nodes[node_id] = {"concept": concept, "ontology_type": ontology_type}

    # Aggregate edges by (src, dst) with SUM(event_count) as weight
    pair_counts: Counter = Counter()
    for row in conn.execute(
        "SELECT source_node_id, target_node_id, SUM(event_count) "
        "FROM edge_event_groups GROUP BY source_node_id, target_node_id"
    ):
        src, dst, weight = row
        if src == dst:
            continue
        left, right = (src, dst) if src <= dst else (dst, src)
        pair_counts[(left, right)] += weight

    conn.close()

    # Build weighted adjacency, filtering by min_edge_weight
    weighted_adjacency: dict[int, dict[int, int]] = defaultdict(dict)
    for (left, right), weight in pair_counts.items():
        if weight < min_edge_weight:
            continue
        weighted_adjacency[left][right] = weight
        weighted_adjacency[right][left] = weight

    # Ensure all nodes with no edges still appear
    for node_id in nodes:
        weighted_adjacency.setdefault(node_id, {})

    # Hub filtering: remove top hub_percent nodes by degree
    if hub_percent > 0:
        degrees = {}
        for nid in weighted_adjacency:
            degrees[nid] = sum(weighted_adjacency[nid].values())
        sorted_nodes = sorted(degrees.items(), key=lambda x: -x[1])
        n_hubs = max(1, int(len(sorted_nodes) * hub_percent / 100.0))
        hub_ids = set(nid for nid, _ in sorted_nodes[:n_hubs])
        # Remove hubs from adjacency
        for hub_id in hub_ids:
            for neighbor in list(weighted_adjacency.get(hub_id, {}).keys()):
                weighted_adjacency[neighbor].pop(hub_id, None)
            weighted_adjacency.pop(hub_id, None)
        print(f"Filtered {len(hub_ids)} hub nodes (top {hub_percent}%)")
    else:
        hub_ids = set()

    return nodes, weighted_adjacency, hub_ids


def build_lookup_rows(nodes):
    """Build lookup_rows dict compatible with summarize_communities()."""
    lookup_rows = {}
    for node_id, info in nodes.items():
        lookup_rows[node_id] = {
            "id": node_id,
            "concept": info["concept"],
            "type": info["ontology_type"],
            "count": "",
            "domains": "",
        }
    return lookup_rows


def merge_small_communities(
    weighted_adjacency: dict[int, dict[int, int]],
    labels: dict[int, int],
    min_community_size: int = 5,
) -> tuple[dict[int, int], list[dict]]:
    """Merge communities smaller than min_community_size into neighbor communities
    with the strongest total edge weight connection.

    Returns updated labels and merge history.
    """
    from scientifickg.communities.discover_modularity import invert_labels, normalize_labels

    labels = dict(labels)
    merge_history = []
    next_label = max(labels.values(), default=0) + 1

    for iteration in range(500):  # max iterations to handle cascading merges
        members = invert_labels(labels)
        small_communities = [
            (label, node_ids) for label, node_ids in members.items()
            if len(node_ids) < min_community_size
        ]
        if not small_communities:
            break

        # Sort by size ascending — merge smallest first
        small_communities.sort(key=lambda x: (len(x[1]), x[0]))

        merged_this_round = 0
        for label, node_ids in small_communities:
            # Compute total edge weight from this community's nodes to each neighbor community
            neighbor_weights: dict[int, float] = {}
            for node_id in node_ids:
                for nbr, w in weighted_adjacency.get(node_id, {}).items():
                    nbr_label = labels.get(nbr)
                    if nbr_label is not None and nbr_label != label:
                        neighbor_weights[nbr_label] = neighbor_weights.get(nbr_label, 0.0) + float(w)

            # Pick the neighbor community with strongest connection
            if neighbor_weights:
                best_target = max(neighbor_weights, key=neighbor_weights.get)
            else:
                # No neighbor edges — merge into the largest community
                comm_sizes = {c: len(ns) for c, ns in members.items() if c != label}
                if not comm_sizes:
                    continue
                best_target = max(comm_sizes, key=comm_sizes.get)

            original_size = len(node_ids)
            target_size = len(members.get(best_target, []))
            for node_id in node_ids:
                labels[node_id] = best_target

            merge_history.append({
                "round": iteration + 1,
                "merged_label": int(label),
                "merged_size": original_size,
                "into_label": int(best_target),
                "target_size_before": target_size,
            })
            merged_this_round += 1

        if merged_this_round == 0:
            break

    labels = normalize_labels(labels)
    return labels, merge_history


def main():
    parser = argparse.ArgumentParser(
        description="Run Louvain community detection on ScientificKG SQLite DB"
    )
    parser.add_argument(
        "--db-path",
        default="/Users/guosijia/Desktop/downloaded_files/ScientificKG/artifacts/db/concept_graph_compact.db",
        help="Path to concept_graph_compact.db",
    )
    parser.add_argument(
        "--output-json",
        default="/Users/guosijia/Desktop/downloaded_files/ScientificKG/artifacts/reports/concept_communities_sqlite.json",
        help="Output JSON path",
    )
    parser.add_argument("--min-edge-weight", type=int, default=2)
    parser.add_argument("--hub-percent", type=float, default=0.1, help="Top X%% nodes to filter as hubs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-levels", type=int, default=10)
    parser.add_argument("--max-passes", type=int, default=15)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--max-community-ratio", type=float, default=0.002)
    parser.add_argument("--min-community-size", type=int, default=5, help="Merge communities smaller than this into neighbor communities")
    parser.add_argument("--top-k", type=int, default=30, help="Number of largest communities to summarize in detail")
    args = parser.parse_args()

    print(f"Loading graph from {args.db_path}...")
    nodes, weighted_adjacency, hub_ids = load_graph_from_sqlite(
        args.db_path, args.min_edge_weight, args.hub_percent
    )
    print(f"Nodes: {len(nodes)}, Active nodes in graph: {len(weighted_adjacency)}")

    # Build simple adjacency for Louvain
    adjacency = make_simple_adjacency(weighted_adjacency)
    print(f"Running Louvain (resolution={args.resolution}, seed={args.seed})...")

    labels, history, communities_by_level = louvain_style_partition(
        adjacency, args.seed, args.max_levels, args.max_passes, args.resolution
    )
    print(f"Louvain complete: {len(set(labels.values()))} communities")
    for h in history:
        print(f"  Level {h['level']}: {h['node_count']} nodes -> {h['community_count']} communities ({h['moves']} moves)")

    # Split oversized communities
    split_args = argparse.Namespace(
        max_community_ratio=args.max_community_ratio,
        max_community_size=0,
        balance_rounds=4,
        resolution=args.resolution,
        split_resolution_scale=1.5,
        min_splittable_size=50,
        seed=args.seed,
        max_levels=args.max_levels,
        max_passes=args.max_passes,
    )
    labels, balance_history = split_oversized_communities(
        weighted_adjacency, labels, split_args
    )
    labels = normalize_labels(labels)
    n_communities = len(set(labels.values()))
    print(f"After balancing: {n_communities} communities")
    for bh in balance_history:
        print(f"  Round {bh['round']}: split community {bh['original_label']} (size {bh['original_size']}) into {bh['split_sizes']}")

    # Merge small communities
    if args.min_community_size > 1:
        labels, merge_history = merge_small_communities(
            weighted_adjacency, labels, args.min_community_size
        )
        labels = normalize_labels(labels)
        n_communities = len(set(labels.values()))
        print(f"After merging small communities (<{args.min_community_size} nodes): {n_communities} communities")
        print(f"  Merged {len(merge_history)} small communities")

        # Re-split any communities that became oversized after merging
        labels, rebalance_history = split_oversized_communities(
            weighted_adjacency, labels, split_args
        )
        labels = normalize_labels(labels)
        n_communities = len(set(labels.values()))
        if rebalance_history:
            print(f"After re-splitting oversized: {n_communities} communities")
            for bh in rebalance_history:
                print(f"  Round {bh['round']}: split community {bh['original_label']} (size {bh['original_size']}) into {bh['split_sizes']}")
    else:
        merge_history = []
        rebalance_history = []

    # Summarize communities
    lookup_rows = build_lookup_rows(nodes)
    summaries = summarize_communities(labels, weighted_adjacency, lookup_rows, top_k=args.top_k)

    # Build output
    output = {
        "metadata": {
            "algorithm": "louvain_style_modularity",
            "source": "concept_graph_compact.db",
            "seed": args.seed,
            "min_edge_weight": args.min_edge_weight,
            "resolution": args.resolution,
            "max_community_ratio": args.max_community_ratio,
            "hub_percent": args.hub_percent,
            "original_node_count": len(nodes),
            "hub_count": len(hub_ids),
            "active_node_count": len(weighted_adjacency),
            "community_count": n_communities,
            "louvain_history": history,
            "balance_history": balance_history,
            "merge_history": merge_history,
            "min_community_size": args.min_community_size,
        },
        "communities": summaries,
        "node_to_community": {str(node): int(label) for node, label in labels.items()},
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output_path}")

    # Print summary stats
    members = invert_labels(labels)
    sizes = sorted([len(v) for v in members.values()], reverse=True)
    print(f"\nCommunity size distribution:")
    print(f"  Total communities: {len(sizes)}")
    print(f"  Largest: {sizes[0]}, Median: {sizes[len(sizes)//2]}, Smallest: {sizes[-1]}")
    print(f"  Top 10 sizes: {sizes[:10]}")


if __name__ == "__main__":
    main()
