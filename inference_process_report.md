# AgentCF 推荐系统推理流程文档

> 数据集：ScientificKG-10-user
> 生成日期：2026-06-09
> 代码版本：基于 `agentcf/model/agentcf.py` (1256行) 完整分析

---

## 1. 系统架构总览

AgentCF推荐系统的推理流程分为三个阶段，形成完整的数据→训练→推理管线：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AgentCF 推理管线                              │
│                                                                     │
│  阶段1: 训练 (calculate_loss)                                       │
│  ┌─────────────────────────────────────────────┐                    │
│  │  Forward → Backward → ... → Backward_true   │                    │
│  │  (反思阶段, all_update_rounds 轮)            │                    │
│  │         ↓                                     │                    │
│  │  logging_after_updation                       │                    │
│  │  memory_1 ← update_memory[-1]                │                    │
│  │  memory_embedding ← item描述                  │                    │
│  └─────────────────────────────────────────────┘                    │
│                     ↓                                               │
│  阶段2: 记忆持久化                                                   │
│  ┌─────────────────────────────────────────────┐                    │
│  │  saved/user        → 用户自描述文本           │                    │
│  │  saved/user_embeddings_*.npy → 历史交互嵌入   │                    │
│  │  saved/item_embeddings_*.npy  → 物品描述嵌入   │                    │
│  └─────────────────────────────────────────────┘                    │
│                     ↓                                               │
│  阶段3: 推理/评估 (full_sort_predict)                               │
│  ┌─────────────────────────────────────────────┐                    │
│  │  加载记忆 → 构建候选集 → 生成评估Prompt       │                    │
│  │  → LLM排序 → 解析输出 → 分数计算              │                    │
│  └─────────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心术语映射

| AgentCF术语        | ScientificKG实际含义                                              | 本文档用语          |
| ------------------ | ----------------------------------------------------------------- | ------------------- |
| User               | AI方法 (AITask, AIInfrastructure, AIAlgorithm, AIMetric, AIModel) | AI方法agent         |
| Item               | 科学方法/实体 (BiologicalEntity, PhysicalPhenomenon等)            | 科学方法            |
| Interaction        | AI方法 × 科学方法的适配关系                                       | 适配/兼容关系       |
| Preference/Dislike | AI方法对科学方法的适配/不适配                                     | 适配方向/不适配方向 |

---

## 2. 阶段1：训练阶段 (calculate_loss)

### 2.1 入口与数据流

训练由 `calculate_loss(interaction)` 方法驱动（`agentcf.py:785`），每个batch的interaction包含：

- `batch_user`: AI方法agent ID列表
- `batch_pos_item`: 正例科学方法ID列表（实际适配的）
- `batch_neg_item`: 负例科学方法ID列表（实际不适配的）

### 2.2 反思阶段：多轮Forward-Backward循环

训练核心是 `all_update_rounds` 轮（YAML配置中为1轮）的反思循环：

```python
for i in range(self.config['all_update_rounds']):
    # 1. Forward: 推荐agent在两个候选中选择一个
    system_selections, system_reasons = self.forward(batch_user, batch_pos_item, batch_neg_item)

    # 2. 计算准确率，分为"推荐错误"和"推荐正确"两组
    accuracy = self.convert_system_selections_to_accuracy(...)
    # accuracy[j] == 0 → 推荐agent选错了（选了neg_item而非pos_item）
    # accuracy[j] == 1 → 推荐agent选对了

    # 3. Backward: 对"推荐错误"的交互更新描述
    self.backward(backward_system_reasons, backward_user, backward_pos_item, backward_neg_item)

    # 4. Backward_true: 对"推荐正确"的交互更新描述（仅第一轮更新用户）
    if i == 0:
        self.backward_true(..., round_1=True)

# 最终一轮backward_true，round_1=False（仅更新科学方法描述）
self.backward_true(..., round_1=False)
```

### 2.3 Forward阶段详解（推荐agent推理）

**功能**：推荐agent (RecAgent) 根据AI方法的当前自描述，在两个候选科学方法中选择一个。

**代码路径**：`forward()` → `RecAgent.astep_forward()` → `_fill_prompt_template()` → LLM调用

**Prompt模板** (`system_prompt_template`)：

```
You are a researcher in scientific concepts. Here is your self-introduction,
expressing your preferences and dislikes: '$user_description'.

Now, you are considering to select a scientific concept from two candidate
scientific concepts. The features of these two candidate scientific concepts
are listed as follows:
$list_of_item_description.

Please select the scientific concept that aligns best with your preferences.
Furthermore, you must articulate why you've chosen that particular scientific
concept while rejecting the other.
```

**关键机制**：

1. 用户描述使用 `update_memory[-1]`（最近一次更新的自描述）
2. 候选对按**随机顺序**排列（50%概率正例在前或负例在前）
3. LLM输出格式：`Choice: [名称] \n Explanation: [推理]`
4. 解析失败时，使用fuzzy matching在raw response中猜测选择

**实际推理示例**（user.1, record_11, 第1轮反思）：

- AI方法：observer based controller (AIInfrastructure, domain: ai)
- 候选1 (neg)：phylogenomic studies (AnalyticalMethod, domain: science)
- 候选2 (pos)：antimalarial compounds (BiologicalEntity, domain: science)
- 推荐agent的推理：
  > "As a researcher in observer-based controller (AIInfrastructure, domain: ai), my work fundamentally revolves around developing and applying analytical methods to design control systems. 'Phylogenomic studies' is explicitly categorized as an AnalyticalMethod, which directly correlates with my methodological orientation..."
- 推荐agent的选择：phylogenomic studies（选了负例，**推荐错误**）
- 推荐准确率：~0%（几乎所有推荐都基于语义相似性推理，而实际适配方向与之相反）

### 2.4 Backward阶段详解（推荐错误时的描述更新）

**触发条件**：推荐agent选了neg_item而非pos_item（accuracy == 0）

**功能**：更新AI方法agent和科学方法agent的描述，使其反映真实的适配关系。

#### 2.4.1 AI方法描述更新

**Prompt构造**（`UserAgent._fill_prompt_template_backward`）：

- System Role: `"You are a researcher in scientific concepts. Here is your previous self-introduction, exhibiting your past research preferences and dislikes: '$update_memory[-1]'."`
- User Role: `user_prompt_template` 模板填充：
  - 告知agent"你选错了"——实际上喜欢的是pos_item，不喜欢的是neg_item
  - 要求agent按4个步骤更新自描述

**YAML中的Prompt模板步骤**（`user_prompt_template`）：

```
1. Analyze the misconceptions in your previous judgment about your preferences
   and dislikes, as recorded in your explanation, and correct these mistakes.
2. Explore your new preferences based on the features of scientific concepts
   you really enjoy ('$pos_item_title'), and determine your dislikes based on
   the features of scientific concepts you truly don't enjoy ('$neg_item_title').
3. Reconcile your newfound preferences and dislikes with your established
   preferences and dislikes from your previous self-introduction. If your new
   experience is compatible with your past preferences, keep both — a researcher
   can appreciate multiple domains simultaneously. Only revise a specific past
   preference if the new experience directly and specifically contradicts it.
   Do NOT discard past preferences simply because a new one was discovered.
4. Update your self-introduction. Integrate your newfound preferences with your
   established preferences, maintaining a coherent and cumulative research identity.
   Describe your preferences as a growing profile that reflects all your confirmed
   interests, not just the latest one.
```

> **注**：步骤3和4已在之前的修复中从"Filter and Remove conflicting"改为"Reconcile"，从"start with newfound preferences"改为"Integrate"，以解决振荡问题。

**输出格式**：`My updated self-introduction: [新自描述]`

**更新机制**：

```python
# agentcf.py:620-626
for i, user in enumerate(batch_user):
    if user_update_descriptions[i] is not None:
        self.user_agents[int(user)].update_memory.append(user_update_descriptions[i])
    else:
        # 解析失败时保留上一次记忆
        self.user_agents[int(user)].update_memory.append(
            self.user_agents[int(user)].update_memory[-1])
```

**解析失败处理**：

- `parse_update` 提取 `My updated self-introduction:` 之后的内容
- 若提取结果为空或包含"parse failed"，则保留上一次有效记忆
- 这确保了`update_memory`的长度始终与反思轮次一致

#### 2.4.2 科学方法描述更新

**Prompt模板**（`item_prompt_template`）：

告知LLM"推荐agent因为描述误导而选错了"，要求更新两个候选方法的描述：

- 正例（pos_item）描述：强化与用户适配的特征
- 负例（neg_item）描述：强化与用户不适配的特征
- 两者差异应被放大

**输出格式**：`The updated description of the first scientific concept is: [描述]. \n The updated description of the second scientific concept is: [描述].`

**更新机制**：

```python
# agentcf.py:668-671
self.item_agents[int(batch_pos_item[i])].update_memory.append(item_update_memories[i][1])
if self.config['update_neg_item']:
    self.item_agents[int(batch_neg_item[i])].update_memory.append(item_update_memories[i][0])
```

**实际更新示例**（user.1, record_11, 第1轮）：

- antimalarial compounds (BiologicalEntity) 更新为：
  > "This AI method, 'antimalarial compounds', is a BiologicalEntity in science, targeting actual chemical substances for malaria treatment. Perfect for researchers who value concrete biological entities over abstract analytical methods."

### 2.5 Backward_true阶段详解（推荐正确时的描述更新）

**触发条件**：推荐agent选了pos_item（accuracy == 1）

**与Backward的区别**：

| 维度         | backward (推荐错误)     | backward_true (推荐正确)    |
| ------------ | ----------------------- | --------------------------- |
| 用户更新     | 每轮都更新              | 仅 round_1=True 时更新      |
| Prompt模板   | `user_prompt_template`  | `user_prompt_template_true` |
| Prompt叙事   | "你选错了" → 纠正性更新 | "你选对了" → 强化性更新     |
| 科学方法更新 | 正例+负例都更新         | 正例+负例都更新             |

**round_1参数逻辑**：

```python
# 第一轮(i=0): round_1=True → 同时更新用户和科学方法
if i == 0 and len(backward_user_true):
    self.backward_true(..., round_1=True)

# 最后一轮: round_1=False → 仅更新科学方法
self.backward_true(..., round_1=False)
```

**Prompt差异**（`user_prompt_template_true`）：

```
Congratulations, after actually using these two scientific concepts, you find
that you very like the scientific concept that your initially chose ('$pos_item_title').
And you indeed dislike the scientific concept that you did not choose before
('$neg_item_title').

This indicates that you made a correct choice, and your judgment about your
preferences and dislikes, as recorded in your explanation, was correct.
```

步骤3和4同样使用"Reconcile"和"Integrate"策略。

### 2.6 推荐agent的策略更新

**功能**：推荐agent为每个用户维护一个推荐策略，在backward阶段更新。

**Prompt模板**（`system_prompt_template_backward`）：

推荐agent接收用户自描述、候选对描述、自己的推荐结果和用户反馈，分析推荐正确/错误的原因，并更新推荐策略。

**输出格式**：`Updated Strategy: [更新后的推荐策略]`

**初始策略**（当`user_id2memory`为空时）：

> "Analyze the user's preference and aversions based on his self-description. Compare the difference between the two candidate CDs. Select the CD that meets the user's preference and goes against the user's aversions."

**策略存储**：`self.rec_agent.user_id2memory[user_id]`，每次backward更新时append新策略。

### 2.7 训练后的记忆转移

反思阶段结束后，`calculate_loss`执行以下关键操作：

```python
# 1. 记录交互日志
self.logging_after_updation(batch_user, batch_pos_item, batch_neg_item)

# 2. 将update_memory最终状态转移到memory_1
for i in range(batch_size):
    self.user_agents[int(batch_user[i])].memory_1.append(
        self.user_agents[int(batch_user[i])].update_memory[-1])

# 3. 构建科学方法的memory_embedding
if self.config['evaluation'] == 'rag':
    # 生成嵌入向量
    batch_pos_item_descriptions_embeddings = self.generate_embedding(batch_pos_item_descriptions)
    for i in range(batch_size):
        self.item_agents[int(batch_pos_item[i])].memory_embedding[
            batch_pos_item_descriptions[i]] = batch_pos_item_descriptions_embeddings[i]
else:
    # 直接存储描述文本
    for i in range(batch_size):
        self.item_agents[int(batch_pos_item[i])].memory_embedding[
            batch_pos_item_descriptions[i]] = None
```

**记忆结构总结**：

| 记忆类型                  | AI方法agent                              | 科学方法agent                |
| ------------------------- | ---------------------------------------- | ---------------------------- |
| `update_memory`           | 训练过程中累积的所有自描述版本           | 训练过程中累积的所有描述版本 |
| `memory_1`                | 每个batch结束后从`update_memory[-1]`追加 | 不使用                       |
| `memory_embedding`        | 不使用                                   | {描述文本: 嵌入向量或None}   |
| `historical_interactions` | 推荐agent为该用户累积的交互历史          | 不使用                       |

### 2.8 训练记录日志

**反思阶段日志**（`logging_during_updation`, agentcf.py:887）：

每个更新轮次记录：

1. 候选对信息（正例和负例的描述）
2. 推荐agent的推理
3. 用户前一轮自描述（`update_memory[-1]`）
4. 更新Prompt（完整prompt内容）
5. 更新后的自描述
6. 科学方法更新后的描述

**交互阶段日志**（`logging_after_updation`, agentcf.py:915）：

每次交互记录：

1. 候选对信息
2. 用户"前一轮"自描述 → **BUG**: 写的是`update_memory[-1]`
3. 用户"更新后"自描述 → **BUG**: 也写的是`update_memory[-1]`（与"前一轮"相同）
4. 科学方法更新后的描述

**已知BUG**：`logging_after_updation`中，"previous self-description"和"updates his self-description"写入的是同一个值`update_memory[-1]`，因为交互阶段不再触发LLM更新用户描述。但从训练记录（如user.1）观察，交互阶段记录的`user's previous self-description`实际上是**初始描述**（`"I am a researcher in observer based controller (AIInfrastructure, domain: ai)."`），这说明在多batch训练中，每个新batch开始时`update_memory`可能被重置。

---

## 3. 阶段2：记忆持久化与加载

### 3.1 保存机制

当`config['saved'] = True`时，训练完成后的`full_sort_predict`调用中保存：

**保存文件结构**：

```
dataset/ScientificKG-10-user/saved/{record_idx}/
├── user                           # 用户描述 (TSV格式)
├── user_embeddings_{token}.npy    # 用户历史交互嵌入
├── user_examples_{token}.npy      # 推荐agent为用户累积的示例
└── item_embeddings_{token}.npy    # 科学方法描述嵌入 (每个item一个)
```

**user文件格式**：

```
user_id:token\tuser_description:token_seq
1_5542\tI have a strong preference for BiologicalEntity...
1_69560\tI prefer reef building corals and causal estimation...
```

- 每行一个用户，使用`memory_1[-1]`作为最终自描述
- 换行符被替换为空格

**item_embeddings格式**：

- 以.npy格式存储dict
- Key: 科学方法的最新描述文本
- Value: 嵌入向量（RAG模式）或None（basic/sequential模式）

### 3.2 加载机制

当`config['loaded']`不为空时，`full_sort_predict`从保存的文件中恢复状态：

```python
# 1. 加载用户自描述到memory_1
with open(f'{path}/user','r') as f:
    f.readline()  # 跳过header
    for line in f:
        user, user_description = line.strip().split('\t')
        user_id = self.user_token_id[user]
        self.user_agents[user_id].memory_1.append(user_description)

# 2. 加载用户历史交互和推荐示例
self.user_agents[int(user)].historical_interactions = np.load(...)
self.rec_agent.user_examples[int(user)] = np.load(...)

# 3. 加载科学方法嵌入
self.item_agents[int(item)].memory_embedding = np.load(...)
```

---

## 4. 阶段3：推理/评估阶段 (full_sort_predict)

### 4.1 总体流程

```
full_sort_predict(interaction, idxs)
│
├── 4.1 加载/保存记忆
│
├── 4.2 检测未训练候选
│   └── 扫描所有候选item的memory_embedding，找出未被训练的
│
├── 4.3 获取用户描述
│   └── memory_1[-1] → batch_user_descriptions
│
├── 4.4 构建评估输入 (get_batch_inputs)
│   ├── 用户历史交互序列
│   ├── 候选集文本
│   └── 候选集描述（含科学方法特征）
│
├── 4.5 生成评估Prompt (evaluation)
│   ├── basic模式: 用户描述 + 候选列表
│   ├── sequential模式: 用户描述 + 历史交互 + 候选列表
│   └── rag模式: 用户描述 + 检索到的历史自描述 + 候选列表
│
├── 4.6 LLM排序调用
│   └── 批量调用LLM，解析排序结果
│
└── 4.7 解析输出与分数计算 (parsing_output_text)
    ├── fuzzy matching: LLM输出 → 候选方法名称
    └── 分数赋值: score = recall_budget - rank_position
```

### 4.2 未训练候选检测

在排序前，系统检测哪些候选科学方法从未被训练过：

```python
for item in range(1, self.n_items):
    mem = self.item_agents[item].memory_embedding
    if not mem:
        continue
    last_key = list(mem.keys())[-1]
    # 如果最后一个key仍以"The CD is called"或原始格式开头，
    # 说明该科学方法未被LLM更新过描述
    if last_key.startswith('The CD is called') or (last_key.startswith('The ') and ' is ' in last_key and '(type:' in last_key):
        if item in all_candidate_idxs:
            untrained_candidates.append(item)
```

这会输出统计信息：`"There are X candidates in total. There are Y have not been trained."`

### 4.3 构建评估输入 (get_batch_inputs)

**函数**：`get_batch_inputs(interaction, idxs, i, user_embedding)` (agentcf.py:1177)

**输入**：

- `interaction`: 包含用户历史交互序列
- `idxs[i]`: 该用户的候选科学方法ID列表
- `user_embedding`: 用户描述嵌入向量（仅RAG模式使用）

**输出**：

| 输出                               | 含义             | 格式示例                                                        |
| ---------------------------------- | ---------------- | --------------------------------------------------------------- |
| `user_his_text`                    | 用户历史交互文本 | `["1. reef building corals: ...", "2. causal estimation: ..."]` |
| `candidate_text`                   | 候选方法名称列表 | `["malassezia", "frequency oscillations", ...]`                 |
| `candidate_text_order`             | 带编号的候选名称 | `["1. malassezia", "2. frequency oscillations", ...]`           |
| `candidate_idx`                    | 候选方法ID列表   | `[3, 7, 15, ...]`                                               |
| `candidate_text_order_description` | 带描述的候选列表 | `["1. malassezia: A skin microbiome entity...", ...]`           |

**item_representation模式**：

1. **direct模式**：直接使用`memory_embedding`的最后一个key作为描述

```python
candidate_text_order_description = [
    f"{j+1}. {self.item_text[idxs[i,j].item()]}: {self._last_memory_key(idxs[i,j].item())}"
    for j in range(idxs.shape[1])
]
```

2. **rag模式**：对每个候选方法，从其多个版本的描述嵌入中，检索与当前用户描述最相似的版本

```python
for item in idxs[i]:
    mem = self.item_agents[item].memory_embedding
    item_embeddings = list(mem.values())
    distances = distances_from_embeddings(user_embedding, item_embeddings)
    nearest = indices_of_nearest_neighbors_from_distances(distances)[0]
    item_descriptions.append(list(mem.keys())[nearest])
```

**直观理解**：一个科学方法在训练中可能被多次更新描述，产生多个版本。RAG模式选择与当前用户最相关的那版描述，而direct模式总是使用最新版本。

### 4.4 三种评估模式

#### 4.4.1 Basic模式

**适用场景**：默认评估模式，不使用历史交互信息

**System Prompt**：

```
You are a recommender system. During interactions, a user will provide a
self-introduction that includes their preferences and dislikes, along with
a list of candidate CDs. Your task is to reorder this list of CDs,
prioritizing those that align with the user's preferences at the top and
placing those that the user dislikes at the bottom.
```

**Evaluation Prompt模板**（`system_prompt_template_evaluation_basic`）：

```
I am a researcher in scientific concepts. Here is my self-introduction,
which includes my preferences and dislikes:

'$user_description'.

Now, I am looking to find scientific concepts that matches my preferences
from a selection of $candidate_num candidates. The features of these
candidate scientific concepts are listed as follows:
$example_list_of_item_description.

Please rearrange these candidate scientific concepts based on my preferences
and dislikes by following these steps:
1. Analyze my preferences and dislikes from my self-introduction.
2. Compare these candidate scientific concepts according to my preferences
   and dislikes, and then make a recommendation.
3. Output Format: 'Rank: {1. scientific concept title \n 2. ...}'
```

**输入参数**：

- `user_description`: 用户最终自描述（`memory_1[-1]`）
- `candidate_num`: 候选数量（固定为10）
- `example_list_of_item_description`: 候选方法列表（带描述）

#### 4.4.2 Sequential模式

**适用场景**：利用用户历史交互序列辅助排序

**与Basic的区别**：Prompt中增加了历史交互信息：

```
In addition, following is my usage history of scientific concepts:
$historical_interactions.
```

**输入参数**额外包含：

- `historical_interactions`: 用户历史交互的科学方法列表（带编号）

**Prompt额外步骤**：

```
2. Compare these candidate scientific concepts according to my preferences
   and dislikes. You can also consider the candidate scientific concepts'
   relationships to my previous usage history.
```

#### 4.4.3 RAG/Retrieval模式

**适用场景**：从用户多版自描述中检索与当前候选最相关的历史版本

**与Basic/Sequential的区别**：

1. **检索过程**：

```python
# 从memory_1[1:-1]（排除初始和最终描述）中检索
user_his_descriptions = self.user_agents[int(batch_user[i])].memory_1[1:-1]
user_his_description_embeddings = self.generate_embedding(user_his_descriptions)

# 计算候选列表描述与每个历史自描述的相似度
distances = distances_from_embeddings(query_embeddings[i], user_his_description_embeddings)
index = indices_of_nearest_neighbors_from_distances(distances)[0]
batch_select_examples.append(user_his_descriptions[index])
```

2. **Prompt结构**：同时提供历史自描述和当前自描述

**Evaluation Prompt模板**（`system_prompt_template_evaluation_retrieval`）：

```
I am a researcher in scientific concepts. Here is my previous self-introduction,
exhibiting my past preferences and dislikes: '$user_past_description'.

Recently, after using some scientific concepts, I found my new preferences
and dislikes, thereby updating my self-introduction as follows:
'$user_description'.

Now, I want to find some scientific concepts that matches my preferences from
a selection of $candidate_num candidate scientific concepts. The features of
these candidate scientific concepts are listed as follows:
$example_list_of_item_description.

Please rearrange these candidate scientific concepts based on my preferences
and dislikes. To do this, please follow these steps:
1. Analyze my past preferences and dislikes from my previous self-introduction.
2. Analyze my current preferences and dislikes from my updated self-introduction.
3. Compare these candidate scientific concepts and analyze their relationships
   to my preferences and dislikes.
4. Generate your output in the following format: 'Rank: {1. ... \n 2. ...}'

Important note: When recommending scientific concepts, you should primarily
consider my current preferences and dislikes. However, my past preferences and
dislikes are also valuable information. When you are unable to determine what
scientific concept to recommend based on my current preferences and dislikes,
do not forget to refer to my past preferences and dislikes.
```

**三种模式对比**：

| 维度        | Basic                     | Sequential                | RAG                                    |
| ----------- | ------------------------- | ------------------------- | -------------------------------------- |
| 用户描述    | `memory_1[-1]`            | `memory_1[-1]`            | `memory_1[-1]` + 检索的历史描述        |
| 历史交互    | 无                        | 有（交互序列）            | 无（通过检索替代）                     |
| 候选描述    | `memory_embedding`最新key | `memory_embedding`最新key | `memory_embedding`中与用户最相关的版本 |
| 信息量      | 最少                      | 中等                      | 最多                                   |
| API调用次数 | 1次LLM                    | 1次LLM                    | 1次LLM + 多次Embedding                 |

### 4.5 LLM排序调用 (evaluation)

**函数**：`evaluation(batch_user, user_descriptions, user_his_texts, list_of_item_descriptions, batch_select_examples)` (agentcf.py:1100)

**流程**：

1. 为每个用户构造评估Prompt
2. 按批次调用LLM（`chat_api_batch`大小，YAML中为5）
3. 解析LLM输出（`parse_evaluation`提取排序行）
4. 对解析失败的请求重试一次
5. 重试仍失败的，尝试从raw text中提取行

**LLM调用**：

```python
messages = []
for i in tqdm(range(0, batch_size, self.chat_api_batch)):
    messages += self.user_agents[0].llm_chat.generate_response_without_construction_batch(
        evaluation_prompts[i:i+self.chat_api_batch])
```

**注意**：LLM调用使用的是`llm_chat`（配置为deepseek-v4-flash），而非训练时的`llm`。测试温度`llm_temperature_test`设为0（确定性输出）。

### 4.6 输出解析与分数计算 (parsing_output_text)

**函数**：`parsing_output_text(scores, messages, idxs, candidate_texts, batch_pos_item)` (agentcf.py:1217)

**流程**：

1. **初始化分数矩阵**：`scores = torch.full((batch_user, n_items), -10000.)`（默认极低分）

2. **逐行解析LLM输出**：

```
LLM输出示例：
Rank: 1. antimalarial compounds
2. frequency oscillations
3. reef building corals
...
```

3. **名称匹配**：

- **exact模式**：在`candidate_text`中查找包含`item_name`的候选
- **fuzzy模式**（ScientificKG默认）：使用`process.extractOne(item_name, candidate_text)`进行模糊匹配

4. **分数赋值**：

```python
scores[i, item_id] = self.config['recall_budget'] - j
# recall_budget = 20（默认），j是排序位置（0-indexed）
# 排名第1的方法得分 = 20 - 0 = 20
# 排名第2的方法得分 = 20 - 1 = 19
# ...
```

5. **去重处理**：如果某个方法已被赋分（`scores[i, item_id] > -5000`），则跳过后续的同名匹配

6. **未匹配方法**：保持默认的-10000分（不会出现在推荐列表中）

**分数含义**：

| 分数   | 含义                                  |
| ------ | ------------------------------------- |
| 20     | 排名第1（最适配）                     |
| 19     | 排名第2                               |
| ...    | ...                                   |
| 1      | 排名第20（最不适配）                  |
| -10000 | 未被LLM排序（不在候选集中或匹配失败） |

### 4.7 推理完整示例

以user.1 (observer based controller) 在Basic模式下的推理为例：

**输入**：

- 用户描述（`memory_1[-1]`）：
  > "I now have a strong preference for AI methods that are computational, such as cellular automata, due to their modelability and integration into observer-based controllers and AI infrastructure. I also favor biological entity methods like calcium atpase for their direct biological relevance and bio-inspired control potential. In contrast, I dislike physical phenomena lacking computational or control properties, such as lake tanganyika, and experimental methods like magnesiothermic reduction..."
- 候选集：20个科学方法，包含描述

**评估Prompt**（Basic模式）：

```
[System] You are a recommender system...

[User] I am a researcher in scientific concepts. Here is my self-introduction,
which includes my preferences and dislikes:

'I now have a strong preference for AI methods that are computational...'

Now, I am looking to find scientific concepts that matches my preferences from
a selection of 10 candidates. The features of these candidate scientific concepts
are listed as follows:
1. malassezia: A BiologicalEntity associated with skin microbiome...
2. frequency oscillations: A PhysicalPhenomenon involving signal analysis...
3. payne effect: A PhysicalPhenomenon describing viscoelastic dynamics...
...

Please rearrange these candidate scientific concepts based on my preferences
and dislikes...
```

**LLM输出**：

```
Rank: 1. malassezia
2. frequency oscillations
3. reef building corals
...
```

**分数计算**：

| 科学方法               | 排名位置 | 分数 |
| ---------------------- | -------- | ---- |
| malassezia             | 1        | 20   |
| frequency oscillations | 2        | 19   |
| reef building corals   | 3        | 18   |
| ...                    | ...      | ...  |

---

## 5. 推荐agent (RecAgent) 的推理逻辑

### 5.1 训练阶段：Forward推理

推荐agent在Forward阶段扮演**用户角色**，使用用户的自描述来判断偏好：

**推理路径**：

1. 从用户自描述中提取偏好和不适配方向
2. 评估两个候选科学方法与偏好的关联度
3. 选择关联度更高的方法

**系统性失败原因**：

- 用户初始自描述过于简略（仅含名称+类型+领域，如"I am a researcher in observer based controller (AIInfrastructure, domain: ai)."）
- 推荐agent只能基于**表面语义关联**推理（如"AIInfrastructure → 选择AnalyticalMethod"）
- 实际适配方向由**知识图谱中的正例标注**决定，与语义关联几乎完全无关
- 结果：推荐准确率接近0%

### 5.2 训练阶段：策略更新

推荐agent为每个用户维护独立推荐策略（`user_id2memory[user_id]`），在每次backward时更新：

**初始策略**：

> "Analyze the user's preference and aversions based on his self-description. Compare the difference between the two candidate CDs. Select the CD that meets the user's preference and goes against the user's aversions."

**更新Prompt**（`system_prompt_template_backward`）：

```
According to the recommendation strategy that specific to this user:
'$recommendation_strategy', you recommended '$recommended_movie' to the user.
However, the user ultimately selected $pos_movie to use, and provided reasons
for his decision: '$user_reasons'. The user's choice in this interactions
confirms your recommendation strategy and the recommended scientific concept
are $truth_or_falsity.

You task is to update the recommendation strategy to make it more personalized.
```

**策略演化**：随着训练进行，推荐策略从通用的"分析偏好"演化为针对特定用户的策略（如"该用户偏好BiologicalEntity而非AnalyticalMethod"），但由于推荐准确率始终接近0%，策略更新的实际效果有限。

### 5.3 评估阶段：排序推理

推荐agent在评估阶段扮演**排序器**角色，根据用户自描述对候选集重新排序：

**与训练阶段的差异**：

| 维度         | 训练(Forward)                           | 评估(Evaluation)                 |
| ------------ | --------------------------------------- | -------------------------------- |
| 任务         | 从2个候选中选1个                        | 对10-20个候选排序                |
| 用户描述来源 | `update_memory[-1]`                     | `memory_1[-1]`                   |
| 推荐策略     | 使用`user_id2memory`策略                | 不使用推荐策略                   |
| 输出格式     | `Choice: [名称] \n Explanation: [推理]` | `Rank: {1. 名称 \n 2. 名称 ...}` |
| LLM温度      | `llm_temperature` (0.2)                 | `llm_temperature_test` (0)       |

---

## 6. ScientificKG数据集上的推理特征

### 6.1 推荐准确率

在ScientificKG-10-user数据集上，推荐agent的Forward阶段准确率接近0%，这是因为：

1. **语义鸿沟**：AI方法（如"function approximation"）与科学方法（如"malassezia"）之间缺乏直接语义关联
2. **推荐逻辑与标注逻辑的矛盾**：推荐agent基于用户自描述推理偏好，但Ground Truth标注基于知识图谱结构中的实际适配关系
3. **自描述信息不足**：初始自描述仅含概念名称和本体类型，无法支撑有效的偏好推理

### 6.2 记忆更新方向

由于推荐agent几乎总是选错（accuracy ≈ 0%），backward阶段（推荐错误时的更新）被频繁触发，而backward_true阶段（推荐正确时的更新）几乎不触发。这导致：

- AI方法agent的自描述在反思阶段被频繁更新
- 更新方向由**正例（pos_item）的特征**驱动——即AI方法agent的偏好总是朝着实际适配的科学方法类型方向演化
- 但由于推荐agent的推理始终基于表面语义，而更新又是完全重写式的，导致自描述在每轮反思中都剧烈振荡

### 6.3 评估阶段的实际表现

评估阶段使用`memory_1[-1]`（训练后最终自描述），通过LLM对候选集排序：

- **信息来源**：用户的最终自描述 + 候选方法的描述
- **排序逻辑**：LLM根据自描述中表达的偏好/不适配方向，对候选方法的相关性排序
- **关键问题**：如果训练阶段的自描述振荡导致最终自描述与实际适配方向不一致，评估结果将受到影响

### 6.4 推理流程中的信息损失点

| 阶段      | 损失类型     | 原因                                                |
| --------- | ------------ | --------------------------------------------------- |
| Forward   | 推理方向错误 | 基于语义关联推理，而非实际适配关系                  |
| Backward  | 自描述振荡   | 完全重写式更新导致偏好方向每轮反转                  |
| 训练→评估 | 偏好信息丢失 | 3/5的agent在交互阶段自描述被重置或冻结              |
| 评估      | 候选描述选择 | direct模式仅使用最新描述，可能丢失有用的历史版本    |
| 解析      | 匹配误差     | fuzzy matching可能将LLM输出的方法名称错误映射到候选 |

---

## 7. 完整推理流程图

```
ScientificKG数据集
    │
    ├── user特征: 1_5542\tfunction approximation\tAITask\tai
    ├── item特征: 1_3\tmalassezia\tBiologicalEntity\tscience
    ├── 交互标注: (1_5542, 1_3) → 正例
    └── 候选集: 1_5542\t[1_3, 1_7, 1_15, ...]
         │
         ▼
┌─── calculate_loss ──────────────────────────────────────────┐
│                                                              │
│  初始化:                                                     │
│  ├── user_agents[5542].update_memory = ["I am a researcher  │
│  │   in function approximation (AITask, domain: ai)."]      │
│  ├── item_agents[3].update_memory = ["malassezia..."]       │
│  └── rec_agent.user_id2memory[5542] = []                    │
│                                                              │
│  反思轮次 (all_update_rounds=1):                             │
│  ├── Forward:                                                │
│  │   ├── 输入: user_desc + pos_item_desc + neg_item_desc    │
│  │   ├── LLM推理: 基于语义关联选择 → 选错(选了neg)          │
│  │   └── accuracy = 0 (几乎所有)                             │
│  │                                                           │
│  ├── Backward (accuracy=0):                                  │
│  │   ├── 用户更新:                                           │
│  │   │   ├── Prompt: "你选错了，实际上你更喜欢pos_item"     │
│  │   │   ├── LLM生成: 新自描述 → append to update_memory    │
│  │   │   └── 示例: "I have a newfound preference for        │
│  │   │       BiologicalEntity such as antimalarial           │
│  │   │       compounds..."                                   │
│  │   └── 科学方法更新:                                       │
│  │       ├── LLM生成: 更新pos/neg item描述                  │
│  │       └── append to item update_memory                    │
│  │                                                           │
│  └── Backward_true (accuracy=1, 罕见):                       │
│      ├── round_1=True: 更新用户+科学方法                     │
│      └── round_1=False: 仅更新科学方法                       │
│                                                              │
│  训练后转移:                                                  │
│  ├── memory_1[-1] ← update_memory[-1]                       │
│  ├── memory_embedding ← {描述: 嵌入/None}                    │
│  └── user_examples ← 交互历史                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌─── full_sort_predict ───────────────────────────────────────┐
│                                                              │
│  1. 加载记忆 (如果loaded)                                    │
│     ├── user_agents[i].memory_1 ← saved/user                │
│     ├── item_agents[i].memory_embedding ← saved/item_*.npy  │
│     └── rec_agent.user_examples ← saved/user_examples_*.npy │
│                                                              │
│  2. 检测未训练候选                                           │
│     └── 统计memory_embedding中仍为原始格式的item             │
│                                                              │
│  3. 构建评估输入                                             │
│     ├── 用户描述: memory_1[-1]                               │
│     ├── 候选描述: memory_embedding[key] (direct/rag)        │
│     └── 历史交互: historical_interactions (sequential)       │
│                                                              │
│  4. 生成评估Prompt                                           │
│     ├── basic: user_desc + candidate_list                    │
│     ├── sequential: + historical_interactions                │
│     └── rag: + 检索的历史自描述 + RAG版本候选描述           │
│                                                              │
│  5. LLM排序                                                  │
│     ├── 输入: 评估Prompt                                     │
│     ├── LLM: deepseek-v4-flash, temperature=0               │
│     └── 输出: "Rank: 1. malassezia\n2. frequency..."        │
│                                                              │
│  6. 解析与分数计算                                           │
│     ├── fuzzy matching: LLM输出名 → 候集方法名              │
│     ├── score[item_id] = 20 - rank_position                  │
│     └── 返回: scores tensor [batch_size, n_items]            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
    评估指标计算 (RecBole框架)
    ├── Hit@K: 正例是否在Top-K中
    ├── NDCG@K: 排序质量
    └── MRR: 正例排名倒数均值
```

---

## 8. 代码引用索引

| 功能                | 函数                                        | 文件:行号                 |
| ------------------- | ------------------------------------------- | ------------------------- |
| 模型初始化          | `AgentCF.__init__`                          | agentcf.py:67             |
| 用户上下文加载      | `load_user_context`                         | agentcf.py:291            |
| Forward推理         | `forward`                                   | agentcf.py:539            |
| Backward(错误)更新  | `backward`                                  | agentcf.py:586            |
| Backward(正确)更新  | `backward_true`                             | agentcf.py:677            |
| 训练主循环          | `calculate_loss`                            | agentcf.py:785            |
| 反思阶段日志        | `logging_during_updation`                   | agentcf.py:887            |
| 交互阶段日志        | `logging_after_updation`                    | agentcf.py:915            |
| 嵌入生成            | `generate_embedding`                        | agentcf.py:521            |
| 推理入口            | `full_sort_predict`                         | agentcf.py:981            |
| 评估Prompt生成      | `evaluation`                                | agentcf.py:1100           |
| 候选输入构建        | `get_batch_inputs`                          | agentcf.py:1177           |
| 输出解析与评分      | `parsing_output_text`                       | agentcf.py:1217           |
| Forward Prompt填充  | `RecAgent._fill_prompt_template`            | conversation_agent.py:149 |
| 评估Prompt填充      | `RecAgent._fill_prompt_template_evaluation` | conversation_agent.py:157 |
| Backward Prompt填充 | `UserAgent._fill_prompt_template_backward`  | conversation_agent.py:354 |
| 推荐策略更新Prompt  | `RecAgent._fill_prompt_template_backward`   | conversation_agent.py:187 |

---

## 9. 数据来源

- 训练记录：`agentcf/dataset/ScientificKG-10-user/record/user_record_11/user.{1-10}`
- 用户特征：`agentcf/dataset/ScientificKG-10-user/ScientificKG-10-user.user`
- 用户记忆：`agentcf/dataset/ScientificKG-10-user/user_memory.json`
- 科学方法记忆：`agentcf/dataset/ScientificKG-10-user/science_method_memory.json`
- 配置文件：`agentcf/props/AgentCF-ScientificKG-10-user.yaml`
- 模型代码：`agentcf/model/agentcf.py`
- Agent代码：`agentcf/agentverse/agents/conversation_agent.py`
- Trainer代码：`agentcf/trainer.py`
