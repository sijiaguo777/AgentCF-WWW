# AgentCF 交互过程分析报告

## 1. 概述

本报告基于 AgentCF 框架在 ScientificKG-10-user 数据集上的训练交互记录，选取 **record_7 批次中 user.1** 的交互过程进行详细分析。

**数据集语义**：在 ScientificKG 中，user 和 item 都是知识图谱中的概念节点，而非传统推荐系统中的"人"和"商品"：

- **User 侧（共10个）= AI 方法**，ontology 类型包括 AITask、AIInfrastructure、AIAlgorithm、AIMetric、AIModel
- **Item 侧（共1467个）= 科学方法/实体**，ontology 类型包括 BiologicalEntity、PhysicalPhenomenon、ChemicalSubstance、EngineeringSystem、ExperimentalMethod 等
- **交互 = AI 方法与科学方法的适配关系**，即"某个 AI 方法适合与哪些科学方法搭配使用"

因此，下文中的"用户"即指 AI 方法 agent，"偏好"即指 AI 方法对科学方法的适配倾向。

该批次包含 58 轮反思更新和 80 轮交互，完整展现了 AI 方法 agent 从初始标签逐步发现自身与科学方法适配关系的过程。

---

## 2. 交互机制说明

AgentCF 的训练过程包含两个核心阶段，循环执行：

### 2.1 反思阶段（Updation during reflection）

当推荐系统做出错误推荐时触发。流程如下：

1. **候选呈现**：系统向 AI 方法 agent 展示一对候选科学方法（positive CD 和 negative CD）
2. **推荐决策**：推荐系统基于 AI 方法当前自我描述选择其中一个，并给出理由
3. **反馈纠正**：系统告知 AI 方法 agent"你选错了"——实际适配关系与推荐相反
4. **适配更新**：AI 方法 agent 根据反馈重新审视自身与科学方法的适配关系，更新自我描述
5. **科学方法更新**：被选中的科学方法 agent 同步更新自身描述，以更准确地反映其特征

### 2.2 交互阶段（New interaction）

反思完成后，AI 方法 agent 带着更新后的描述进入新一轮交互：

1. **候选呈现**：系统再次展示候选科学方法（可能包含新的候选对）
2. **适配表达**：AI 方法基于更新后的自我描述做出选择
3. **双向更新**：AI 方法和科学方法 agent 各自更新描述

---

## 3. 交互过程详细分析

### 3.1 初始状态

AI 方法 agent（user.1）的初始自我描述：

> I am a researcher in observer based controller (AIInfrastructure, domain: ai).

对应知识图谱中的节点：**observer based controller**，类型为 AIInfrastructure，属于 AI 领域。这是一个领域标签式的初始描述，仅包含类型信息，缺乏对适配科学方法的具体表达。

### 3.2 第一轮反思：从"分析方法"到"生物实体"

**候选对**：

- Positive CD：`antimalarial compounds`（BiologicalEntity, science）— 实际适配
- Negative CD：`phylogenomic studies`（AnalyticalMethod, science）— 实际不适配

**推荐系统的选择与理由**：

推荐系统选择了 `phylogenomic studies`，理由如下：

> As a researcher in observer-based controller and AI infrastructure, my domain is artificial intelligence, where I focus on methods and analytical frameworks rather than specific biological entities. The candidate 'phylogenomic studies' is classified as an AnalyticalMethod within the science domain, which directly aligns with my preference for structured, computational approaches. Phylogenomic studies often employ machine learning, statistical inference, and data-driven modeling—tools that are integral to AI infrastructure and control systems. In contrast, 'antimalarial compounds' is a BiologicalEntity, which represents a concrete substance rather than an analytical or methodological AI technique.

**分析**：推荐系统基于"observer based controller 属于 AI 基础设施"这一身份，推断其应适配同样属于方法类的 phylogenomic studies。这一推理在表层逻辑上合理，但忽略了 AI 方法与科学方法的深层适配关系——observer based controller 实际上更适合与具体的生物实体搭配。

**AI 方法自我描述更新**：

> I prefer AI methods that are concrete entities or systems, such as antimalarial compounds (biological entities) in science and observer-based controllers (AI infrastructure). I dislike abstract analytical methods like phylogenomic studies, which are purely computational frameworks and lack tangible, domain-specific substance.

**科学方法描述更新**（antimalarial compounds）：

> Concrete biological compounds with explicit molecular structures and physical presence; directly applicable as tangible entities in drug discovery—preferred by users seeking domain-specific, non-abstract systems.

**关键变化**：

- AI 方法从"类型标签"转变为"适配描述"，新增了"适配具体实体"和"不适配抽象方法"两个维度
- 科学方法描述从简单标签变为带有适配画像的推荐理由

### 3.3 第一轮交互：适配关系的进一步分化

**候选对**：与反思阶段相同

**AI 方法自我描述更新**：

> I now prioritize computational methods like cellular automata (type ComputationalMethod, domain science), which are essential for modeling dynamic systems and observer-based control within AI infrastructure. I also continue to prefer biological entities such as calcium ATPase from the science domain, and observer-based controller methods. Conversely, I dislike physical phenomena like Lake Tanganyika (type PhysicalPhenomenon, domain science) that lack computational or AI relevance, and I reject experimental methods such as magnesiothermic reduction.

**分析**：交互阶段中，适配描述更加具体和结构化：

- **适配维度扩展**：从"具体实体"细化为"计算方法"（cellular automata）和"生物实体"（calcium ATPase）两个子类
- **不适配维度扩展**：从"抽象方法"细化为"无关物理现象"和"实验方法"两类
- **保留了类型锚点**：仍然提及 observer-based controller，但将其作为适配倾向之一而非唯一标识

### 3.4 第五轮反思：适配关系的意外反转

**候选对**：

- Positive CD：`quechers method`（ExperimentalMethod, science）— 实际适配
- Negative CD：`enterprise networks`（EngineeringSystem, ai）— 实际不适配

**推荐系统的选择与理由**：

> I selected 'enterprise networks' because it directly aligns with my preference for engineering systems and practical, process-oriented applications in AI infrastructure. As an EngineeringSystem in the AI domain, it embodies the computational and systems-oriented approach I value, fitting seamlessly with my interest in observer-based control and dynamic system modeling. In contrast, 'quechers method' is an ExperimentalMethod from the science domain that is fundamentally a chemical sample preparation technique (used for pesticide residue analysis). This method lacks biological or computational relevance, falls under the category of chemical substances I dislike, and is an experimental method isolated from computational or AI integration—all of which I explicitly reject.

**分析**：推荐系统严格遵循了 AI 方法当前的适配描述——其明确表示"不适配实验方法"和"适配工程系统"，因此选择 enterprise networks 是逻辑自洽的。然而实际适配关系相反，observer based controller 更适合与 quechers method 搭配。

**AI 方法自我描述更新**：

> I now favor experimental methods from the science domain, particularly chemical sample preparation techniques like quechers method, which are practical and hands-on. I continue to favor biological entities from the science domain for modeling dynamic systems, as well as computational methods like cellular automata and observer-based controller approaches for their direct applicability. My dislikes include engineering systems that are purely network-based or abstract, such as enterprise networks, scientific theories without tangible value, and purely descriptive physical phenomena.

**关键变化**：

- **适配反转**：AI 方法从"不适配实验方法"反转为"适配实验方法"（特别是实操性的化学制备技术）
- **不适配反转**：AI 方法从"适配工程系统"反转为"不适配纯网络型工程系统"
- **适配收敛**：适配核心从"计算/AI相关"转向"实操性、有形的方法"，无论是生物实体还是实验方法

---

## 4. 适配关系演化轨迹总结

| 阶段        | 适配                         | 不适配                | 描述粒度           |
| ----------- | ---------------------------- | --------------------- | ------------------ |
| 初始        | AI基础设施、分析方法         | （无）                | 类型标签级         |
| 第1轮反思后 | 具体实体/系统                | 抽象分析方法          | 适配-不适配二元    |
| 第1轮交互后 | 计算方法+生物实体            | 无关物理现象+实验方法 | 多维度结构化       |
| 第5轮反思后 | 实操性方法（实验+生物+计算） | 抽象工程系统+纯理论   | 细粒度、带具体实例 |

**演化特征**：

1. **从粗到细**：适配描述从类型标签逐步细化为带有具体实例的多维适配关系
2. **动态修正**：适配关系并非单调收敛，会出现反转（如对实验方法的态度）
3. **核心收敛**：尽管表面适配波动，底层趋势是适配"有形、实操、可量化"的方法，不适配"抽象、纯理论、无直接应用"的方法
4. **科学方法协同演化**：科学方法描述随 AI 方法的适配更新同步更新，从静态标签变为带有适配画像的描述

---

## 5. 机制评价

### 5.1 优势

- **适配可解释性**：每轮更新都有明确的推理链，适配变化可追溯
- **双向适应**：AI 方法和科学方法 agent 同时更新，形成协同演化
- **错误驱动学习**：仅当推荐错误时触发反思更新，学习信号明确

### 5.2 局限

- **适配振荡**：如第5轮所示，适配关系可能出现反转，缺乏稳定性保障
- **初始描述依赖**：初始类型标签过于粗粒度时，早期推荐几乎必然错误
- **LLM 非确定性**：同一候选对在不同批次中产生的适配更新文本不同，影响可复现性
- **负样本更新缺失**：当前配置下（`update_neg_item=False`），未被选中的科学方法不更新描述，可能导致负样本信息丢失

---

## 6. 数据来源

- 交互记录路径：`agentcf/dataset/ScientificKG-10-user/record/user_record_7/user.1`
- 物品记录路径：`agentcf/dataset/ScientificKG-10-user/record/item_record_7/`
- 记忆文件路径：`agentcf/dataset/ScientificKG-10-user/user_memory.json`、`ai_method_memory.json`
- 代码逻辑：`agentcf/model/agentcf.py`（`logging_during_updation`、`logging_after_updation` 方法）
