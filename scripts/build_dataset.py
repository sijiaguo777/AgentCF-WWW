"""
Build AI-Science interaction dataset from ScientificKG concept graph.

Analogous to a recommender system:
  - AI Method = user (asks "which science problems can I solve?")
  - Science Method = item (long-term memory: historical neighbors+weight; short-term memory: current topology)
  - Interaction = co-occurrence edge in papers

Outputs both RecBole format (.inter/.user/.item) and JSON memory format.
"""

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Ontology type classification
# ---------------------------------------------------------------------------
AI_TYPES = {"AIAlgorithm", "AIModel", "AITask", "AIInfrastructure", "AIMetric"}

SCIENCE_TYPES = {
    "BiologicalEntity", "PhysicalPhenomenon", "ChemicalSubstance",
    "ScientificTheory", "MaterialStructure", "EngineeringSystem",
    "ExperimentalMethod", "MeasurementTechnique", "AnalyticalMethod",
    "ComputationalMethod",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify(ontology_type: str) -> str | None:
    """Return 'ai', 'science', or None."""
    if ontology_type in AI_TYPES:
        return "ai"
    if ontology_type in SCIENCE_TYPES:
        return "science"
    return None


def load_concepts(conn: sqlite3.Connection, min_weight: int = 5):
    """Load concept nodes with domain info, return {node_key: dict}."""
    cur = conn.execute("""
        SELECT dataset_id, node_id, concept, ontology_type, mention_count
        FROM concept_nodes
        WHERE in_graph = 1
    """)
    concepts = {}
    for ds, nid, name, otype, mentions in cur:
        side = classify(otype)
        if side is None:
            continue
        key = (ds, nid)
        concepts[key] = {
            "id": f"{ds}_{nid}",
            "name": name,
            "ontology_type": otype,
            "side": side,
            "mentions": mentions,
        }

    # Load domains
    cur = conn.execute("SELECT dataset_id, node_id, domain FROM concept_domains")
    domain_map = defaultdict(list)
    for ds, nid, domain in cur:
        domain_map[(ds, nid)].append(domain)
    for key, domains in domain_map.items():
        if key in concepts:
            concepts[key]["domains"] = domains

    return concepts


def load_interactions(conn: sqlite3.Connection, concepts: dict, min_weight: int = 5):
    """Load AI↔Science co-occurrence edges, return list of interaction dicts."""
    cur = conn.execute("""
        SELECT dataset_id, source_node_id, target_node_id, event_year, weight
        FROM edge_weights_by_year_cache
        WHERE weight >= ?
    """, (min_weight,))

    interactions = []
    for ds, src, tgt, year, weight in cur:
        src_key = (ds, src)
        tgt_key = (ds, tgt)
        if src_key not in concepts or tgt_key not in concepts:
            continue

        src_info = concepts[src_key]
        tgt_info = concepts[tgt_key]

        # Determine which is AI and which is Science
        if src_info["side"] == "ai" and tgt_info["side"] == "science":
            ai_key, sci_key = src_key, tgt_key
        elif src_info["side"] == "science" and tgt_info["side"] == "ai":
            ai_key, sci_key = tgt_key, src_key
        else:
            continue  # skip ai-ai or science-science

        interactions.append({
            "ai_key": ai_key,
            "sci_key": sci_key,
            "ai_id": concepts[ai_key]["id"],
            "sci_id": concepts[sci_key]["id"],
            "year": year,
            "weight": weight,
        })

    return interactions


def build_memories(concepts: dict, interactions: list):
    """Build long-term and short-term memory for each concept."""

    # Group interactions by ai_key / sci_key / year
    ai_neighbors = defaultdict(lambda: defaultdict(list))   # ai_key -> year -> [(sci_key, weight)]
    sci_neighbors = defaultdict(lambda: defaultdict(list))   # sci_key -> year -> [(ai_key, weight)]

    for inter in interactions:
        ai_neighbors[inter["ai_key"]][inter["year"]].append(
            (inter["sci_key"], inter["weight"])
        )
        sci_neighbors[inter["sci_key"]][inter["year"]].append(
            (inter["ai_key"], inter["weight"])
        )

    # --- AI Method Memory (user-side) ---
    ai_memory = {}
    for ai_key, info in concepts.items():
        if info["side"] != "ai":
            continue
        if ai_key not in ai_neighbors:
            continue

        year_data = ai_neighbors[ai_key]
        sorted_years = sorted(year_data.keys())

        # Long-term: aggregate all years — "which science problems have I solved?"
        lt_neighbors = defaultdict(float)
        for year, neighbors in year_data.items():
            for sci_key, w in neighbors:
                lt_neighbors[sci_key] += w

        lt_sorted = sorted(lt_neighbors.items(), key=lambda x: -x[1])
        long_term = [
            {"neighbor": concepts[k]["name"], "neighbor_type": concepts[k]["ontology_type"], "weight": round(w, 2)}
            for k, w in lt_sorted
            if k in concepts
        ]

        # Short-term: latest year topology
        latest_year = sorted_years[-1]
        st_neighbors = year_data[latest_year]
        st_sorted = sorted(st_neighbors, key=lambda x: -x[1])
        short_term = {
            "year": latest_year,
            "neighbors": [
                {"neighbor": concepts[k]["name"], "neighbor_type": concepts[k]["ontology_type"], "weight": w}
                for k, w in st_sorted
                if k in concepts
            ],
        }

        ai_memory[info["id"]] = {
            "name": info["name"],
            "ontology_type": info["ontology_type"],
            "domains": info.get("domains", []),
            "long_term_memory": long_term,
            "short_term_memory": short_term,
            "total_interactions": sum(len(v) for v in year_data.values()),
            "active_years": sorted_years,
        }

    # --- Science Method Memory (item-side) ---
    sci_memory = {}
    for sci_key, info in concepts.items():
        if info["side"] != "science":
            continue
        if sci_key not in sci_neighbors:
            continue

        year_data = sci_neighbors[sci_key]

        # "Which AI methods have solved me" — sorted by cumulative weight
        ai_solutions = defaultdict(float)
        for year, neighbors in year_data.items():
            for ai_key, w in neighbors:
                ai_solutions[ai_key] += w

        ai_sorted = sorted(ai_solutions.items(), key=lambda x: -x[1])
        solutions = [
            {
                "ai_method": concepts[k]["name"],
                "ai_type": concepts[k]["ontology_type"],
                "weight": round(w, 2),
            }
            for k, w in ai_sorted
            if k in concepts
        ]

        sci_memory[info["id"]] = {
            "name": info["name"],
            "ontology_type": info["ontology_type"],
            "domains": info.get("domains", []),
            "which_ai_solved_me": solutions,
            "total_interactions": sum(len(v) for v in year_data.values()),
            "active_years": sorted(year_data.keys()),
        }

    return ai_memory, sci_memory


# ---------------------------------------------------------------------------
# Output: RecBole format
# ---------------------------------------------------------------------------

def write_recbole(output_dir: Path, concepts: dict, interactions: list,
                  train_year: int = 2020, valid_year: int = 2023):
    """Write .inter, .user, .item files in RecBole format.

    Mapping: AI Method = user, Science Method = item.
    """

    # --- .inter ---
    splits = {"train": [], "valid": [], "test": []}
    for inter in interactions:
        y = inter["year"]
        line = f"{inter['ai_id']}\t{inter['sci_id']}\t{inter['weight']}\t{inter['year']}"
        if y <= train_year:
            splits["train"].append(line)
        elif y <= valid_year:
            splits["valid"].append(line)
        else:
            splits["test"].append(line)

    inter_path = output_dir / "ScientificKG.inter"
    with open(inter_path, "w") as f:
        f.write("user_id:token\titem_id:token\tweight:float\tyear:int\n")
        for split_name in ["train", "valid", "test"]:
            for line in splits[split_name]:
                f.write(line + "\n")
    print(f"  .inter: {inter_path}  (train={len(splits['train'])}, valid={len(splits['valid'])}, test={len(splits['test'])})")

    # --- .user (AI methods) ---
    ai_concepts = {k: v for k, v in concepts.items() if v["side"] == "ai"}
    user_path = output_dir / "ScientificKG.user"
    with open(user_path, "w") as f:
        f.write("user_id:token\tontology_type:token\tconcept_name:token_seq\tdomain:token_seq\n")
        for info in ai_concepts.values():
            domains = " ".join(info.get("domains", []))
            f.write(f"{info['id']}\t{info['ontology_type']}\t{info['name']}\t{domains}\n")
    print(f"  .user: {user_path}  ({len(ai_concepts)} AI methods as users)")

    # --- .item (Science methods) ---
    sci_concepts = {k: v for k, v in concepts.items() if v["side"] == "science"}
    item_path = output_dir / "ScientificKG.item"
    with open(item_path, "w") as f:
        f.write("item_id:token\tontology_type:token\tconcept_name:token_seq\tdomain:token_seq\n")
        for info in sci_concepts.values():
            domains = " ".join(info.get("domains", []))
            f.write(f"{info['id']}\t{info['ontology_type']}\t{info['name']}\t{domains}\n")
    print(f"  .item: {item_path}  ({len(sci_concepts)} Science methods as items)")


# ---------------------------------------------------------------------------
# Output: JSON memory format
# ---------------------------------------------------------------------------

def write_json(output_dir: Path, ai_memory: dict, sci_memory: dict,
               interactions: list, train_year: int = 2020, valid_year: int = 2023):
    """Write JSON memory files.

    Mapping: AI Method = user, Science Method = item.
    """

    # AI method memory (user-side)
    ai_path = output_dir / "user_memory.json"
    with open(ai_path, "w") as f:
        json.dump(ai_memory, f, indent=2, ensure_ascii=False)
    print(f"  User memory (AI methods): {ai_path}  ({len(ai_memory)} methods)")

    # Science method memory (item-side)
    sci_path = output_dir / "item_memory.json"
    with open(sci_path, "w") as f:
        json.dump(sci_memory, f, indent=2, ensure_ascii=False)
    print(f"  Item memory (Science methods): {sci_path}  ({len(sci_memory)} methods)")

    # Interaction data by year
    by_year = defaultdict(list)
    for inter in interactions:
        by_year[inter["year"]].append({
            "user_id": inter["ai_id"],
            "item_id": inter["sci_id"],
            "weight": inter["weight"],
        })

    inter_json = {
        "split": {
            "train": f"year <= {train_year}",
            "valid": f"{train_year} < year <= {valid_year}",
            "test": f"year > {valid_year}",
        },
        "year_range": [min(by_year.keys()), max(by_year.keys())],
        "interactions_by_year": {
            str(y): items for y, items in sorted(by_year.items())
        },
    }
    inter_path = output_dir / "interaction_data.json"
    with open(inter_path, "w") as f:
        json.dump(inter_json, f, indent=2, ensure_ascii=False)
    print(f"  Interactions: {inter_path}  ({len(interactions)} total)")


# ---------------------------------------------------------------------------
# Stats report
# ---------------------------------------------------------------------------

def print_stats(concepts: dict, interactions: list, ai_memory: dict, sci_memory: dict):
    ai = [v for v in concepts.values() if v["side"] == "ai"]
    sci = [v for v in concepts.values() if v["side"] == "science"]

    print("\n" + "=" * 60)
    print("Dataset Statistics  (AI=user, Science=item)")
    print("=" * 60)
    print(f"  AI methods (users):     {len(ai):,}")
    for otype in AI_TYPES:
        cnt = sum(1 for v in ai if v["ontology_type"] == otype)
        if cnt:
            print(f"    {otype}: {cnt:,}")
    print(f"  Science methods (items): {len(sci):,}")
    for otype in SCIENCE_TYPES:
        cnt = sum(1 for v in sci if v["ontology_type"] == otype)
        if cnt:
            print(f"    {otype}: {cnt:,}")
    print(f"  Total interactions:      {len(interactions):,}")

    years = [i["year"] for i in interactions]
    if years:
        print(f"  Year range:              {min(years)} - {max(years)}")

    # Filter: science methods (items) with >= 2 AI interactions
    sci_with_enough = sum(1 for v in sci_memory.values() if len(v["which_ai_solved_me"]) >= 2)
    print(f"  Science methods (items) with >= 2 AI interactions: {sci_with_enough:,}")

    # Top AI methods (users)
    print("\n  Top 10 AI methods (users) by interaction count:")
    top_ai = sorted(ai_memory.values(), key=lambda x: -x["total_interactions"])[:10]
    for m in top_ai:
        print(f"    {m['name']} ({m['ontology_type']}): {m['total_interactions']} interactions")

    # Top Science methods (items)
    print("\n  Top 10 Science methods (items) by # of AI solutions:")
    top_sci = sorted(sci_memory.values(), key=lambda x: -len(x["which_ai_solved_me"]))[:10]
    for m in top_sci:
        print(f"    {m['name']} ({m['ontology_type']}): {len(m['which_ai_solved_me'])} AI methods")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build AI-Science interaction dataset from ScientificKG")
    parser.add_argument("--db", type=str,
                        default="/Users/guosijia/Desktop/downloaded_files/ScientificKG/artifacts/db/concept_graph_compact.db",
                        help="Path to concept_graph_compact.db")
    parser.add_argument("--output", type=str,
                        default="/Users/guosijia/Desktop/AgentCF-WWW/agentcf/dataset/ScientificKG",
                        help="Output directory")
    parser.add_argument("--min-weight", type=int, default=5,
                        help="Minimum edge weight threshold (default: 5)")
    parser.add_argument("--min-interactions", type=int, default=2,
                        help="Minimum AI interactions per science method (default: 2)")
    parser.add_argument("--train-year", type=int, default=2020,
                        help="Train split: year <= this value")
    parser.add_argument("--valid-year", type=int, default=2023,
                        help="Valid split: train_year < year <= this value")
    args = parser.parse_args()

    db_path = Path(args.db)
    output_dir = Path(args.output)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading data from {db_path} ...")
    conn = sqlite3.connect(str(db_path))

    print("  Loading concepts ...")
    concepts = load_concepts(conn, args.min_weight)
    print(f"  Loaded {len(concepts)} concepts (AI + Science)")

    print("  Loading interactions ...")
    interactions = load_interactions(conn, concepts, args.min_weight)
    print(f"  Loaded {len(interactions)} interactions")

    conn.close()

    # Filter: science methods with too few interactions
    if args.min_interactions > 1:
        sci_interaction_count = defaultdict(int)
        for inter in interactions:
            sci_interaction_count[inter["sci_key"]] += 1
        valid_sci = {k for k, v in sci_interaction_count.items() if v >= args.min_interactions}
        interactions = [i for i in interactions if i["sci_key"] in valid_sci]
        print(f"  After filtering (min_interactions={args.min_interactions}): {len(interactions)} interactions")

    print("Building memories ...")
    ai_memory, sci_memory = build_memories(concepts, interactions)

    print_stats(concepts, interactions, ai_memory, sci_memory)

    print("\nWriting RecBole format ...")
    write_recbole(output_dir, concepts, interactions, args.train_year, args.valid_year)

    print("\nWriting JSON memory format ...")
    write_json(output_dir, ai_memory, sci_memory, interactions, args.train_year, args.valid_year)

    print("\nDone! Output directory:", output_dir)


if __name__ == "__main__":
    main()
