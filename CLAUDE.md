# AgentCF-WWW

AgentCF: Collaborative Filtering with Autonomous Agents. AI method agents (user side) and scientific method agents (item side) interact on ScientificKG knowledge graph to discover adaptation relationships through LLM-driven reflection and interaction.

## ScientificKG Terminology

**CRITICAL**: In this codebase, "user" and "item" are NOT people and products. They are knowledge graph concept nodes.

| Code Term          | Actual Meaning                                        | Examples                                                                   |
| ------------------ | ----------------------------------------------------- | -------------------------------------------------------------------------- |
| User               | AI method agent                                       | AITask, AIInfrastructure, AIAlgorithm, AIMetric, AIModel                   |
| Item               | Scientific method/entity                              | BiologicalEntity, PhysicalPhenomenon, ChemicalSubstance, EngineeringSystem |
| Interaction        | AI method x scientific method adaptation relationship | compatibility/adaptation, not preference                                   |
| Preference/Dislike | Adaptation direction / non-adaptation direction       | not consumer taste                                                         |

Use "AI method agent" instead of "user", "scientific method" instead of "item", "adaptation" instead of "preference" in analysis and documentation.

## Three-Phase Inference Pipeline

### Phase 1: Training (`calculate_loss`, agentcf.py:785)

Each batch runs `all_update_rounds` (YAML: 1) reflection iterations:

1. **Forward** (agentcf.py:539): RecAgent selects between pos/neg items using `update_memory[-1]` as user description. Accuracy ~0% on ScientificKG due to semantic gap.
2. **Backward** (agentcf.py:586): When recommender is wrong (accuracy=0): LLM generates new user description appended to `update_memory`; also updates item descriptions.
3. **Backward_true** (agentcf.py:677): When recommender is correct (accuracy=1): `round_1=True` updates both user and item; `round_1=False` updates only items.
4. **Post-training transfer**: `memory_1[-1] <- update_memory[-1]`; `memory_embedding <- {description: embedding_or_None}`

### Phase 2: Memory Persistence

Saved to `dataset/ScientificKG-10-user/saved/{record_idx}/`:

- `user` — TSV file with `memory_1[-1]` as final self-description
- `user_embeddings_*.npy` — historical interaction embeddings
- `item_embeddings_*.npy` — item description embeddings (per item dict)

### Phase 3: Inference/Evaluation (`full_sort_predict`, agentcf.py:981)

1. Load memories → detect untrained candidates → construct evaluation prompts
2. Three evaluation modes:
   - **basic**: user_desc + candidate list
   - **sequential**: + historical_interactions
   - **rag**: + retrieved historical self-description + RAG version of candidate descriptions
3. LLM ranking (deepseek-v4-flash, temperature=0) → parse output → score assignment
4. Score: `scores[i, item_id] = recall_budget - rank_position` (recall_budget=20 default)
5. Name matching: `fuzzy` mode uses `process.extractOne(item_name, candidate_text)`

## Memory Structure

| Memory Type               | AI Method Agent                                           | Scientific Method Agent                              |
| ------------------------- | --------------------------------------------------------- | ---------------------------------------------------- |
| `update_memory`           | All self-description versions accumulated during training | All description versions accumulated during training |
| `memory_1`                | Appended from `update_memory[-1]` after each batch        | Not used                                             |
| `memory_embedding`        | Not used                                                  | {description_text: embedding_vector_or_None}         |
| `historical_interactions` | Accumulated by RecAgent for this user                     | Not used                                             |

Key: `update_memory[-1]` = current description during training; `memory_1[-1]` = description used for evaluation.

## Key Code Architecture

| Function                                    | File:Line                 | Purpose                                        |
| ------------------------------------------- | ------------------------- | ---------------------------------------------- |
| `AgentCF.__init__`                          | agentcf.py:67             | Model initialization                           |
| `load_user_context`                         | agentcf.py:291            | User context creation for ScientificKG         |
| `forward`                                   | agentcf.py:539            | RecAgent selects between pos/neg items         |
| `backward`                                  | agentcf.py:586            | Description update when recommender is wrong   |
| `backward_true`                             | agentcf.py:677            | Description update when recommender is correct |
| `calculate_loss`                            | agentcf.py:785            | Main training loop                             |
| `logging_during_updation`                   | agentcf.py:887            | Reflection phase logging                       |
| `logging_after_updation`                    | agentcf.py:915            | Interaction phase logging                      |
| `generate_embedding`                        | agentcf.py:521            | Embedding generation                           |
| `full_sort_predict`                         | agentcf.py:981            | Inference/evaluation entry point               |
| `evaluation`                                | agentcf.py:1100           | Evaluation prompt generation + LLM call        |
| `get_batch_inputs`                          | agentcf.py:1177           | Candidate item description construction        |
| `parsing_output_text`                       | agentcf.py:1217           | LLM output parsing + score assignment          |
| `RecAgent._fill_prompt_template`            | conversation_agent.py:149 | Forward prompt construction                    |
| `RecAgent._fill_prompt_template_evaluation` | conversation_agent.py:157 | Evaluation prompt construction                 |
| `UserAgent._fill_prompt_template_backward`  | conversation_agent.py:354 | Backward prompt construction                   |

## Known Bugs

1. **`logging_after_updation` writes same value for "previous" and "updated" self-description** (agentcf.py:927-930): Both fields use `update_memory[-1]`, because interaction phase doesn't trigger LLM user description updates.

2. **Interaction phase doesn't update user descriptions**: Only item descriptions are updated during interaction. User self-descriptions are frozen, causing 3/5 agents to lose preference information accumulated during reflection.

3. **Reflection-to-interaction state transfer breaks for some agents**: Self-descriptions get reset to initial values or frozen at early states when entering interaction phase.

## Prompt Template Fix (Applied)

The `user_prompt_template` and `user_prompt_template_true` in `AgentCF-ScientificKG-10-user.yaml` were modified to fix self-description oscillation:

- **Original step 3**: "Filter and Remove conflicting or repetitive parts" → **Fixed**: "Reconcile your newfound preferences with your established preferences. If compatible, keep both."
- **Original step 4**: "Start by describing your newfound preferences" → **Fixed**: "Integrate your newfound preferences with your established preferences, maintaining a coherent and cumulative research identity."
- **Added note 6**: "Your updated self-introduction must preserve your established preferences unless directly contradicted. Do NOT overwrite your entire profile — update incrementally."

## Systematic Findings from Training Analysis

- **Recommender accuracy ~0%**: Forward phase recommendations based on semantic similarity almost always contradict actual adaptation labels
- **BiologicalEntity systematic advantage**: ~32-36% of all long-term memory entries across all agents, likely due to node frequency in ScientificKG
- **Super-anchor effect**: Early high-frequency interactions get weight amplification (e.g., reef building corals weight=1470, 3.5x the second entry)
- **Cross-agent preference overlap**: Same scientific methods (e.g., malassezia, mucopolysaccharidosis type I) appear in top adaptations for agents with completely different initial identities
- **Weight power-law distribution**: Few methods dominate total weight; Top-3 accounts for 10-51% of total weight depending on agent

## Configuration

- LLM: `deepseek-v4-flash` (training), same for evaluation with temperature=0
- Embedding: `nomic-embed-text-v1`
- Evaluation mode: `basic`
- Match rule: `fuzzy`
- Recall budget: 20 (default, not in YAML)
- `all_update_rounds`: 1
- `chat_api_batch`: 5

## Data Paths

- Training records: `agentcf/dataset/ScientificKG-10-user/record/user_record_{N}/user.{1-10}`
- User features: `agentcf/dataset/ScientificKG-10-user/ScientificKG-10-user.user`
- User memory: `agentcf/dataset/ScientificKG-10-user/user_memory.json`
- Science method memory: `agentcf/dataset/ScientificKG-10-user/science_method_memory.json`
- Config: `agentcf/props/AgentCF-ScientificKG-10-user.yaml`
- Model: `agentcf/model/agentcf.py`
- Agents: `agentcf/agentverse/agents/conversation_agent.py`
- Trainer: `agentcf/trainer.py`
