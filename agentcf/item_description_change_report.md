# AgentCF Item 描述变化分析报告

> 数据来源：ScientificKG-10-user 数据集，训练 checkpoint batch_132  
> 分析时间：2026-06-08

---

## 1. 总体统计

| 指标                         | 数值         |
| ---------------------------- | ------------ |
| 总物品数                     | 1767         |
| 描述被更新过的物品 (≥2 版本) | 1463 (82.8%) |
| 描述从未更新的物品 (1 版本)  | 303 (17.2%)  |
| 单物品最大版本数             | 10           |
| 平均版本数                   | 2.49         |

### 版本数分布

| 版本数 | 物品数 | 占比  |
| ------ | ------ | ----- |
| 0      | 1      | 0.06% |
| 1      | 303    | 17.1% |
| 2      | 910    | 51.5% |
| 3      | 274    | 15.5% |
| 4      | 130    | 7.4%  |
| 5      | 70     | 4.0%  |
| 6      | 26     | 1.5%  |
| 7      | 21     | 1.2%  |
| 8      | 13     | 0.7%  |
| 9      | 11     | 0.6%  |
| 10     | 8      | 0.5%  |

**关键发现**：超过一半的物品 (51.5%) 只被更新了一次（2 个版本），仅 0.5% 的物品达到了最大 10 个版本。这说明大部分物品在训练中只被少量用户交互更新，而少数热门物品被反复更新。

---

## 2. 10 个典型物品的详细分析

以下选取描述版本数最多（9-10 版本）的 10 个物品，覆盖不同 ontology_type，展示描述从初始化到最终版本的完整演变。

---

### 2.1 Item 750: well control

**类型**: EngineeringSystem | **版本数**: 10 | **长度变化**: 75 → 265 → 244 → 237 → 0 → 239 → 236 → 236 → 313 → 335

| 版本 | 描述                                                                                                                                                                                                                                                                                                                                        | 关键变化                                                                              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| v1   | The AI method is 'well control' (type: EngineeringSystem, domain: science).                                                                                                                                                                                                                                                                 | **初始模板**：仅包含类型和域信息                                                      |
| v2   | Well control: a computational AI method integrating data-driven algorithms with theoretical models for precise measurement of physical metrics (e.g., pressure, flow)—aligned with users preferring broad, observable phenomena and rigorous mathematical frameworks.                                                                       | **首次丰富化**：加入具体物理量（pressure, flow）、计算方法特征、用户偏好标签          |
| v3   | SOD3: a static molecular assay measuring antioxidant activity, lacking temporal dynamics, causal inference, and hypothesis-driven analysis.                                                                                                                                                                                                 | **严重偏移**：描述变成了完全不同的概念（SOD3/抗氧化），丢失了 well control 的核心特征 |
| v4   | Static molecular assay measuring antioxidant activity, a health-relevant biomarker.                                                                                                                                                                                                                                                         | **偏移延续**：继续描述抗氧化，well control 信息完全丢失                               |
| v5   | _(空描述)_                                                                                                                                                                                                                                                                                                                                  | **更新失败**：LLM 返回空内容                                                          |
| v6   | Focuses on bioterrorism via abstract computational modeling of biological networks and molecular techniques like microscopy and isotope labeling...                                                                                                                                                                                         | **再次偏移**：转向生物恐怖主义相关描述                                                |
| v7   | Well control in engineering systems: direct manipulation of quantifiable physical parameters (pressure, flow, damping) for clear, measurable outcomes grounded in static non-biological phenomena.                                                                                                                                          | **回归正轨**：重新描述 well control，强调工程系统、物理参数                           |
| v8   | Direct manipulation of static quantifiable physical parameters (pressure, flow, damping) in non-biological systems.                                                                                                                                                                                                                         | **精简**：去除冗余，保留核心特征                                                      |
| v9   | Acenaphthene: Static crystalline structure via crystallography...                                                                                                                                                                                                                                                                           | **再次偏移**：描述变成了蒽（化学物质）                                                |
| v10  | Well control AI: physics-based molecular measurements (MD, binding affinity) for causal biochemical inference; natural molecular binding for biomarker quantification; direct physical quantification (flow cytometry, mass spectrometry) with temporal dynamics; computationally tractable, empirically validated for engineering systems. | **最终版**：回归 well control，融合了物理测量和生化推理                               |

**变化模式**：**剧烈振荡型** — 描述在正确概念和完全无关概念之间反复跳转，出现了 3 次严重偏移（v3→SOD3, v6→bioterrorism, v9→acenaphthene）。最终版本虽然回归正轨，但混入了不属于 well control 的生化术语。

---

### 2.2 Item 37: monolithic active pixel sensor

**类型**: EngineeringSystem | **版本数**: 10 | **长度变化**: 93 → 299 → 300 → 288 → 281 → 246 → 0 → 402 → 273 → 343

| 版本 | 描述                                                                                                                                                                                                                                                                                                                                                | 关键变化                                             |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| v1   | The AI method is 'monolithic active pixel sensor' (type: EngineeringSystem, domain: science).                                                                                                                                                                                                                                                       | 初始模板                                             |
| v2   | Monolithic active pixel sensor is a hardware component enabling precise observational data for observer-based control and bio-inspired AI. Its computational modeling and distributed system integration appeal to those favoring hardware-algorithmic synthesis and biologically plausible mechanisms.                                             | 首次丰富化：硬件特征 + 用户偏好标签                  |
| v3   | Electrochemical storage is a purely physical phenomenon lacking biological context...                                                                                                                                                                                                                                                               | **偏移**：变成电化学存储                             |
| v4   | Monolithic active pixel sensors offer direct, high-speed, low-noise light detection via physical sensor arrays.                                                                                                                                                                                                                                     | **回归**：重新描述传感器                             |
| v5   | Monolithic active pixel sensors provide direct high-speed low-noise light detection integrated into imaging systems for computational modeling.                                                                                                                                                                                                     | 精简优化                                             |
| v6   | Optical limiting is an abstract macroscopic phenomenon...                                                                                                                                                                                                                                                                                           | **偏移**：变成光学限制                               |
| v7   | _(空描述)_                                                                                                                                                                                                                                                                                                                                          | 更新失败                                             |
| v8   | Monolithic active pixel sensor: Solid-state imaging sensor providing direct photonic measurement with high temporal resolution and quantifiable digital outputs.                                                                                                                                                                                    | **回归并深化**：加入固态成像、光子测量等具体技术细节 |
| v9   | Direct physical measurement via solid-state imaging sensor offering high temporal resolution, quantifiable digital outputs.                                                                                                                                                                                                                         | 精简                                                 |
| v10  | Direct physical measurement via solid-state imaging sensor with high temporal resolution and quantifiable digital outputs. Enables computationally intensive image processing and causal inference from tangible sensor data for reproducible biologically grounded metrics, integrating first-principles simulations and dimensionality reduction. | 最终版：融合计算和推理能力                           |

**变化模式**：**振荡回归型** — 出现 2 次偏移，但最终版本准确且丰富。

---

### 2.3 Item 691: high resolution melting curve analysis

**类型**: AnalyticalMethod | **版本数**: 10 | **长度变化**: 100 → 334 → 331 → 230 → 260 → 276 → 288 → 0 → 275 → 289

| 版本 | 描述                                                                                                                                                                                                                                                                                          | 关键变化                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| v1   | The AI method is 'high resolution melting curve analysis' (type: AnalyticalMethod, domain: science).                                                                                                                                                                                          | 初始模板                          |
| v2   | High resolution melting curve analysis measures DNA denaturation over temperature, providing temporal dynamics and quantifiable metrics (Tm, curve geometry).                                                                                                                                 | 首次丰富化：DNA 变性、温度、Tm 值 |
| v3   | High resolution melting curve analysis captures temporal dynamics of DNA denaturation via temperature ramping, delivering dynamic metrics (Tm, curve geometry) for causal inference on mutations.                                                                                             | 深化：加入突变因果推理            |
| v4   | High resolution melting curve analysis is an experimentally validated, data-driven method yielding quantifiable diagnostic outputs for mutation analysis.                                                                                                                                     | 精简：聚焦诊断输出                |
| v5   | High resolution melting curve analysis: experimentally validated fluorescence method capturing dynamic base-pair denaturation with exchangeable ion effects and quantifiable temporal states.                                                                                                 | 加入荧光方法和离子效应            |
| v6   | ...enabling predictive disease modeling without relying on natural biological proxies.                                                                                                                                                                                                        | 明确排除生物代理                  |
| v7   | ...enabling predictive disease modeling via direct, validated measurements ideal for mathematically grounded users.                                                                                                                                                                           | 加入用户偏好标签                  |
| v8   | _(空描述)_                                                                                                                                                                                                                                                                                    | 更新失败                          |
| v9   | High-resolution melting curve analysis delivers precise, time-resolved empirical metrics from direct physical measurements of DNA melting, using computationally intensive spectroscopy.                                                                                                      | 回归核心：DNA 熔解 + 光谱学       |
| v10  | High resolution melting curve analysis: Direct, quantifiable molecular measurements via fluorescence and temperature. Provides empirically validated, temporally dynamic data on biological entities. Computationally tractable, physics-based, and avoids opaque proxies or abstract models. | 最终版：简洁准确                  |

**变化模式**：**渐进优化型** — 始终围绕正确概念，逐步增加技术细节和用户偏好信息，仅在 v8 出现空描述。

---

### 2.4 Item 269: infodemiology

**类型**: AnalyticalMethod | **版本数**: 10 | **长度变化**: 75 → 195 → 288 → 274 → 242 → 319 → 276 → 187 → 283 → 261

| 版本 | 描述                                                                                                                                                                                                                                                              | 关键变化                        |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| v1   | The AI method is 'infodemiology' (type: AnalyticalMethod, domain: science).                                                                                                                                                                                       | 初始模板                        |
| v2   | Infodemiology: an analytical method with computational AI, integrated modeling, control systems, and real-time optimization.                                                                                                                                      | 首次丰富化：计算方法 + 实时优化 |
| v3   | Infodemiology uses analytical, computationally driven AI with integrated modeling, control systems, and real-time optimization. It offers measurable, data-driven analysis of information dissemination for health and ecological systems.                        | 加入信息传播 + 健康/生态应用    |
| v4   | Infodemiology: AI method leveraging real-world health data for real-time monitoring and control.                                                                                                                                                                  | 聚焦健康数据                    |
| v5   | Gas inflow modeling remains an abstract computational method disconnected from experimental health data...                                                                                                                                                        | **偏移**：变成气体流入建模      |
| v6   | Gas inflow modeling remains an abstract computational method...                                                                                                                                                                                                   | 偏移延续                        |
| v7   | Infodemiology: an AI method leveraging real-world health data and online information patterns for epidemiological insights.                                                                                                                                       | **回归**：重新描述信息流行病学  |
| v8   | A data-driven AI method leveraging real-world health data and online patterns for epidemiological insights.                                                                                                                                                       | 精简                            |
| v9   | Infodemiology uses real-world health data with reductionist chemical biomarkers, yielding quantifiable molecular metrics and reproducible time-resolved insights, avoiding abstract AI.                                                                           | 加入生物标志物                  |
| v10  | Infodemiology: Uses real-world health data with reductionist chemical biomarkers for direct quantifiable molecular metrics and reproducible time-resolved insights. Avoids spectroscopy, assays, complex simulations—empirically grounded biological foundations. | 最终版：强调经验基础            |

**变化模式**：**偏移-回归型** — v5-v6 偏移后回归，最终版本准确但加入了不直接属于 infodemiology 的生物标志物术语。

---

### 2.5 Item 207: protein synthesis inhibitor

**类型**: BiologicalEntity | **版本数**: 10 | **长度变化**: 89 → 238 → 261 → 295 → 217 → 295 → 229 → 248 → 337 → 277

| 版本 | 描述                                                                                                                                                                                                                        | 关键变化                                           |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| v1   | The AI method is 'protein synthesis inhibitor' (type: BiologicalEntity, domain: science).                                                                                                                                   | 初始模板                                           |
| v2   | Protein synthesis inhibitor: a natural biological entity with direct diagnostic relevance, producing quantifiable mortality outcomes through AI-integrated predictive modeling.                                             | 首次丰富化：诊断相关性 + 死亡率                    |
| v3   | A natural protein synthesis inhibitor enabling simple empirical mortality measurement via AI predictive modeling.                                                                                                           | 精简                                               |
| v4   | Natural protein synthesis inhibitor enabling mechanistic molecular modeling with AI-driven predictions. Quantifiable mortality metrics, direct biological labeling via stable isotopes, live-cell imaging.                  | 深化：稳定同位素标记 + 活细胞成像                  |
| v5   | Natural protein synthesis inhibitor leveraging high-dimensional proteome data and data-driven AI. Systems-level, non-reductionist, computationally intensive.                                                               | 转向系统级视角                                     |
| v6   | Natural protein synthesis inhibitor using high-dimensional proteome data and data-driven AI. Provides chemically specific quantification of molecular-level cellular signaling, mitochondrial dynamics, and named proteins. | 加入线粒体动力学 + 命名蛋白                        |
| v7   | Data-driven AI method using high-dimensional proteome data. Provides chemically specific quantification of molecular processes.                                                                                             | **标题丢失**：不再提及 protein synthesis inhibitor |
| v8   | Data-driven AI using high-dimensional proteome data for chemically specific quantification. Empirically validated with interpretable biological outputs. No formal physical theory required.                                | 继续泛化                                           |
| v9   | AI method using high-dimensional proteome data for chemically specific quantification. Employs direct experimental intervention (electroporation) with flow cytometry/mass spectrometry.                                    | 加入电穿孔 + 流式细胞术                            |
| v10  | Protein synthesis inhibitor: AI method using high-dimensional proteome data with electroporation, flow cytometry, and mass spectrometry for direct causal analysis of biological entities.                                  | 最终版：**标题回归**，融合实验技术                 |

**变化模式**：**标题丢失-回归型** — v7-v8 丢失了物品名称，v10 回归。描述从具体生物学实体逐步泛化为通用 AI 方法，最终版本重新锚定到 protein synthesis inhibitor。

---

### 2.6 Item 474: reservoir

**类型**: EngineeringSystem | **版本数**: 10 | **长度变化**: 67 → 252 → 224 → 269 → 250 → 276 → 0 → 292 → 239 → 255

| 版本 | 描述                                                                                                                                                                                      | 关键变化                                                |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| v1   | The AI method is 'reservoir' (type: EngineeringSystem, domain: ai).                                                                                                                       | 初始模板                                                |
| v2   | Reservoir computing excels in modeling dynamical systems with control integration, real-time optimization, and direct measurability.                                                      | 首次丰富化：**自动解释为储备池计算**（AI 领域概念）     |
| v3   | Reservoir computing applies AI-driven analysis to biological data for predictive health diagnostics.                                                                                      | 转向生物数据应用                                        |
| v4   | Idiopathic pulmonary arterial hypertension research relies on abstract mathematical hemodynamic models...                                                                                 | **偏移**：变成肺动脉高压                                |
| v5   | Reservoir: abstract mathematical hemodynamic models and molecular assays without real-time physical measurability.                                                                        | 偏移延续                                                |
| v6   | For users who favor abstract mathematical models, reservoir computing for hemodynamic systems...                                                                                          | **半回归**：提及 reservoir computing 但仍围绕血流动力学 |
| v7   | _(空描述)_                                                                                                                                                                                | 更新失败                                                |
| v8   | Reservoir computing-based analysis for direct molecular-level quantification from physical measurements. Integrates depth-resolved mitochondrial imaging with AI metabolic flux analysis. | 回归 + 加入线粒体成像                                   |
| v9   | Electroporation: A broad physical transport method for delivering molecules across membranes...                                                                                           | **偏移**：变成电穿孔                                    |
| v10  | Dynamical reservoir computing for temporal signal processing via acoustic field data. Enables data-driven predictive modeling for quantifiable ecological indices.                        | 最终版：回归储备池计算 + 声学场数据                     |

**变化模式**：**概念歧义型** — "reservoir" 一词在工程和 AI 领域有不同含义（储层 vs 储备池计算），描述在两种解释间摇摆，还出现 2 次无关偏移。

---

### 2.7 Item 667: electrochemical storage

**类型**: PhysicalPhenomenon | **版本数**: 10 | **长度变化**: 82 → 247 → 320 → 309 → 267 → 314 → 263 → 236 → 287 → 278

| 版本 | 描述                                                                                                                                                                                                                         | 关键变化                                                              |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| v1   | The AI method is 'electrochemical storage' (type: PhysicalPhenomenon, domain: ai).                                                                                                                                           | 初始模板                                                              |
| v2   | Engineering system for energy storage with quantifiable performance metrics like capacity and efficiency. Features controllable charge/discharge temporal dynamics.                                                          | 首次丰富化：容量、效率、充放电动力学                                  |
| v3   | Mathematically grounded macroscopic physical phenomenon for energy storage with quantifiable metrics (capacity, efficiency). Integrates with neuroscience and health applications.                                           | **域偏移**：加入神经科学和健康应用                                    |
| v4   | Electrochemical storage: mathematically grounded macroscopic phenomenon... Integrates with health via histology, PCR, hormone spectroscopy.                                                                                  | **严重偏移**：组织学、PCR、激素光谱不属于电化学存储                   |
| v5   | Electrochemical storage: a mathematically grounded system integrating histology, PCR, and hormone spectroscopy to reveal molecular-level cellular signaling and mitochondrial dynamics.                                      | 偏移延续                                                              |
| v6   | Electrochemical storage: a mathematically grounded, model-based system integrating histology, PCR, and hormone spectroscopy for empirical validation, spatial observability, and system-level molecular signaling.           | 偏移延续                                                              |
| v7   | Electrochemical storage: mathematically grounded, model-based system integrating histology, PCR, and hormone spectroscopy for system-level molecular signaling.                                                              | 精简但仍偏移                                                          |
| v8   | A mathematically grounded model-based system integrating histology, PCR, and hormone spectroscopy for system-level molecular signaling with quantifiable dynamics, temporal behavior, and causal inference.                  | **标题丢失**                                                          |
| v9   | Electrochemical storage: mathematically grounded model integrating histology, PCR, and hormone spectroscopy. Enables system-level molecular signaling with quantifiable dynamics, causal inference, and biomarker discovery. | 标题回归但仍偏移                                                      |
| v10  | Mathematically grounded model enabling direct electrochemical measurement of temporal dynamics, integrating natural molecular binding, soliton fission, causal inference.                                                    | 最终版：**部分回归** — 重新提及电化学测量，但仍混入孤子分裂等无关概念 |

**变化模式**：**渐进偏移型** — 从 v3 开始逐步偏移到生物学领域，偏移内容持续累积，最终版本仅部分回归。

---

### 2.8 Item 115: ischemic insult

**类型**: BiologicalEntity | **版本数**: 10 | **长度变化**: 77 → 249 → 195 → 260 → 257 → 228 → 203 → 266 → 255 → 288

| 版本 | 描述                                                                                                                                                                                                       | 关键变化                               |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| v1   | The AI method is 'ischemic insult' (type: BiologicalEntity, domain: science).                                                                                                                              | 初始模板                               |
| v2   | Ischemic insult is a biological entity (disease-related) offering clinical relevance and real-world impact. Its pathophysiological mechanisms provide deep theoretical insights.                           | 首次丰富化：临床相关性 + 病理生理机制  |
| v3   | Ischemic insult: a disease-related entity offering direct clinical relevance, deep pathophysiological insights, and seamless integration with data-driven AI for quantifiable risk forecasting.            | 加入风险预测                           |
| v4   | A biological disease model with direct clinical relevance, integrating data-driven AI for quantifiable risk forecasting. It bridges macroscopic pathophysiology and neuroscience.                          | 加入神经科学                           |
| v5   | A neurological defect model (ischemic insult) grounded in pathophysiology and striatum, enabling reproducible, time-resolved metrics.                                                                      | 聚焦纹状体 + 时间分辨                  |
| v6   | A clinically relevant neurological defect model (ischemic insult) grounded in striatal pathophysiology, enabling reproducible time-resolved metrics and inter-day precision.                               | 加入日间精度                           |
| v7   | Clinically relevant ischemic insult model grounded in striatal pathophysiology.                                                                                                                            | 精简                                   |
| v8   | Clinically relevant ischemic insult model grounded in striatal pathophysiology. Offers reproducible, time-resolved molecular metrics (e.g., neurotransmitter levels) with minimal data-driven AI.          | 加入神经递质水平                       |
| v9   | Integrates striatal pathophysiology with time-resolved neurotransmitter dynamics for causal mechanistic inference at the system level; non-reductionist, empirically validated.                            | **标题丢失**：不再提及 ischemic insult |
| v10  | Ischemic insult: integrates time-resolved neurotransmitter dynamics with causal mechanistic inference at system level. Empirically validated and data-driven, it avoids direct physics-based measurements. | 最终版：**标题回归**                   |

**变化模式**：**渐进深化型** — 始终围绕缺血损伤概念，逐步从宏观临床描述深化到纹状体病理、神经递质动力学等具体机制。v9 短暂丢失标题后 v10 回归。

---

### 2.9 Item 173: androgen independent prostate cancer

**类型**: BiologicalEntity | **版本数**: 9 | **长度变化**: 98 → 297 → 240 → 303 → 302 → 359 → 305 → 284 → 327

| 版本 | 描述                                                                                                                                                                                                                          | 关键变化                                       |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| v1   | The AI method is 'androgen independent prostate cancer' (type: BiologicalEntity, domain: science).                                                                                                                            | 初始模板                                       |
| v2   | Androgen independent prostate cancer: Biological model enabling direct structural/biochemical analysis at molecular/cellular level. Features observable signaling pathways, feedback loops.                                   | 首次丰富化：分子/细胞级分析 + 信号通路         |
| v3   | Androgen independent prostate cancer: Biological model featuring genomic adaptation, evolutionary processes, and empirical grounding in real biological data.                                                                 | 加入基因组适应 + 进化过程                      |
| v4   | AI-powered biological model of androgen-independent prostate cancer featuring genomic adaptation... Delivers quantifiable, time-resolved metrics.                                                                             | 加入 AI 驱动 + 时间分辨指标                    |
| v5   | AI-powered model of androgen-independent prostate cancer: system-level computational modeling of evolutionary dynamics. Uses iterative data-driven empirical methods, avoiding molecular-level mechanistic details.           | **视角偏移**：从分子级转向系统级，回避分子机制 |
| v6   | The updated description of the first AI method is: Electrochemical storage: mathematically grounded system integrating histology, PCR...                                                                                      | **严重偏移**：变成电化学存储（LLM 格式错误）   |
| v7   | Androgen independent prostate cancer: integrates histology, PCR, hormone spectroscopy to reveal molecular signaling and mitochondrial dynamics using named proteins.                                                          | **回归**：重新描述前列腺癌                     |
| v8   | Androgen independent prostate cancer – integrates histology, PCR, hormone spectroscopy to reveal molecular signaling and mitochondrial dynamics via named proteins. Mathematically grounded, holistic, biologically specific. | 深化                                           |
| v9   | Androgen independent prostate cancer – integrates histology, PCR, hormone spectroscopy with mathematical rigor; quantifies emission energy, molecular dynamics, binding affinity via flow cytometry and mass spectrometry.    | 最终版：加入流式细胞术 + 质谱                  |

**变化模式**：**偏移-回归型** — v6 出现 LLM 格式错误导致的严重偏移，v7 回归。最终版本准确且技术细节丰富。

---

### 2.10 Item 503: exchangeable k+

**类型**: ChemicalSubstance | **版本数**: 9 | **长度变化**: 78 → 233 → 308 → 276 → 275 → 226 → 234 → 261 → 0

| 版本 | 描述                                                                                                                                                                                                                                                      | 关键变化                                                              |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| v1   | The AI method is 'exchangeable k+' (type: ChemicalSubstance, domain: science).                                                                                                                                                                            | 初始模板                                                              |
| v2   | A dynamic chemical substance with exchangeable potassium ions, featuring quantifiable states, temporal dynamics, and broad observational breadth via ion-selective measurements.                                                                          | 首次丰富化：钾离子 + 离子选择性测量                                   |
| v3   | A dynamic chemical substance with exchangeable potassium ions, featuring quantifiable states, temporal dynamics. Computationally tractable for modeling ion exchange, enabling AI-driven predictive analysis.                                             | 加入 AI 预测分析                                                      |
| v4   | A dynamic chemical substance with exchangeable potassium ions, enabling direct ion-selective measurement and real-time monitoring. Computationally tractable for AI-driven predictive analysis of cellular ion homeostasis and neurotransmitter dynamics. | 加入细胞离子稳态 + 神经递质动力学                                     |
| v5   | Dynamic chemical substance with exchangeable K+ for real-time depth-resolved ion monitoring. Enables direct quantification of cellular structures like mitochondria and signaling pathways.                                                               | 加入深度分辨 + 线粒体                                                 |
| v6   | Biologically grounded potassium ion exchange system with quantifiable capacity, voltage, and cycle life. Uses rigorous NMR/mass spectrometry.                                                                                                             | **概念偏移**：从化学物质转向电池系统（capacity, voltage, cycle life） |
| v7   | Physically rigorous K⁺ exchange system with quantifiable voltage, capacity, cycle life, validated by NMR/mass spectrometry. Enables time-resolved causal inference.                                                                                       | 偏移延续                                                              |
| v8   | Physically rigorous K⁺ exchange system with quantifiable temporal measurements, causal inference, kinetic Monte Carlo modeling, and direct hardware integration for real-time dynamic control.                                                            | 加入蒙特卡洛 + 硬件集成                                               |
| v9   | _(空描述)_                                                                                                                                                                                                                                                | 更新失败                                                              |

**变化模式**：**渐进偏移型** — v6 开始从化学物质偏移到电池/硬件系统概念，最终以空描述结束。这是一个**更新失败**的案例。

---

## 3. 变化模式分类

根据以上 10 个物品的分析，描述变化可分为以下模式：

| 模式                | 特征                                   | 案例                                                           | 占比(10个中) |
| ------------------- | -------------------------------------- | -------------------------------------------------------------- | ------------ |
| **渐进优化型**      | 始终围绕正确概念，逐步增加细节         | Item 691 (HRMCA), Item 115 (ischemic insult)                   | 20%          |
| **偏移-回归型**     | 出现 1-2 次概念偏移，但最终回归正轨    | Item 37 (MAPS), Item 269 (infodemiology), Item 173 (AIPC)      | 30%          |
| **剧烈振荡型**      | 多次偏移和回归，描述不稳定             | Item 750 (well control)                                        | 10%          |
| **概念歧义型**      | 物品名称存在多义，描述在多种解释间摇摆 | Item 474 (reservoir)                                           | 10%          |
| **渐进偏移型**      | 偏移逐步累积，最终描述偏离原始概念     | Item 667 (electrochemical storage), Item 503 (exchangeable k+) | 20%          |
| **标题丢失-回归型** | 中间版本丢失物品名称，最终回归         | Item 207 (protein synthesis inhibitor)                         | 10%          |

---

## 4. 关键发现

### 4.1 描述偏移（Description Drift）是主要问题

10 个物品中，**8 个**出现了不同程度的描述偏移——LLM 在 backward 更新中引入了与物品本身无关的概念。偏移来源主要有：

1. **用户偏好污染**：backward prompt 要求"amplify the differences between the two items based on user preferences"，LLM 倾向于将交互用户的偏好特征写入物品描述，导致描述逐渐偏向特定用户群体
2. **跨物品信息混淆**：LLM 在更新两个物品描述时，可能混淆 pos_item 和 neg_item 的特征，或将对方物品的特征写入当前物品
3. **格式解析错误**：如 Item 173 v6，LLM 输出了格式错误的内容（"The updated description of the first AI method is: Electrochemical storage..."），被直接写入 memory

### 4.2 空描述问题

10 个物品中，**4 个**在某个版本出现了空描述（长度为 0）。这是 LLM 返回空响应或格式无法解析时的结果。空描述会导致该物品在后续交互中无法被正确比较。

### 4.3 描述长度膨胀

初始模板描述长度约 75-100 字符，更新后平均膨胀到 250-350 字符。尽管 prompt 要求"under 50 words"，LLM 实际输出远超限制（50 words ≈ 300 字符，但部分描述达到 400+ 字符）。

### 4.4 覆盖率不均

- 82.8% 的物品被更新过，17.2% 从未更新
- 51.5% 的物品只有 1 次更新（2 个版本），说明大部分物品在训练中只被少量交互涉及
- 仅 0.5% 的物品达到 10 个版本，这些是训练中的"热门物品"

### 4.5 用户偏好信息的跨用户传递

物品描述更新后，所有用户在后续交互中都会读到最新版本。这意味着：

- **正面效果**：一个用户的偏好信息可以通过物品描述传递给其他用户（如 Item 691 的描述中逐步加入了"ideal for mathematically grounded users"等偏好标签）
- **负面效果**：偏移的描述也会影响所有后续用户，造成错误信息传播

---

## 5. 结论

AgentCF 的 item memory 更新机制存在显著的**描述偏移**问题。核心原因是 backward prompt 的设计：它要求 LLM 根据**当前交互用户的偏好**来修改物品描述，这使得描述逐渐偏向特定用户群体而非物品的客观特征。

两条改进路径：

1. **约束物品描述更新**：在 prompt 中更强调"不矛盾于物品固有特征"，或限制更新幅度（如只允许添加，不允许替换）
2. **分离客观描述与偏好标签**：将物品描述分为"固有特征"（不可修改）和"用户偏好标签"（可更新）两部分
