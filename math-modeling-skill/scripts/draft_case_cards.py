#!/usr/bin/env python3
"""Create evidence-grounded draft case cards from extracted paper packets.

The drafts are deliberately conservative: they record only detected methods and
label missing evidence instead of inventing results.  Human/agent review should
then strengthen the decision rationale using the packet's page anchors.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


TYPE_RULES = {
    "预测": ("预测", "时间序列", "回归", "拟合", "forecast", "arima", "灰色预测", "lstm", "prophet"),
    "评价": ("评价", "排名", "优劣", "综合指标", "topsis", "层次分析", "熵权", "主成分", "因子分析"),
    "优化": ("最优", "优化", "规划", "调度", "分配", "路径", "遗传算法", "粒子群", "模拟退火", "nsga"),
    "分类": ("分类", "判别", "识别", "logistic", "支持向量机", "随机森林", "xgboost"),
    "聚类": ("聚类", "k-means", "kmeans", "dbscan", "层次聚类", "gmm"),
    "网络/图论": ("最短路", "最大流", "网络流", "图论", "节点", "边权", "tsp", "vrp", "dijkstra"),
    "机理/动力学": ("微分方程", "动力学", "机理", "传播", "扩散", "sir", "seir", "ode", "pde"),
    "仿真": ("仿真", "模拟", "蒙特卡洛", "monte carlo", "离散事件", "agent-based"),
}

RATIONALES = [
    (("线性回归", "多元回归", "回归"), "用参数化关系刻画响应与解释变量之间的方向和强度，便于解释与显著性检验。"),
    (("多项式", "非线性拟合", "曲线拟合"), "在线性关系不足时表达弯曲、峰值或饱和趋势，同时保持可视化和参数解释。"),
    (("时间序列", "arima", "指数平滑"), "利用时间依赖和趋势/季节结构预测未来，验证应采用滚动时间窗而非随机切分。"),
    (("灰色", "gm(1,1)"), "面向样本较少、趋势较明确的数据建立累加生成规律，并需检查级比和残差。"),
    (("神经网络", "bp", "lstm", "gru"), "用于表达难以预设函数形式的非线性映射；只有数据量和验证设计足够时才优于简洁基线。"),
    (("topsis",), "把多指标方案映射为距正负理想解的相对接近度，前提是指标方向、尺度和权重有清晰含义。"),
    (("熵权", "critic"), "用样本差异和指标冲突度提供客观权重信息，需同时检查异常值与指标冗余。"),
    (("层次分析", "ahp"), "把难以直接量化的偏好拆成层级比较，并以一致性检验约束主观判断。"),
    (("主成分", "pca"), "压缩相关指标并缓解共线性，代价是新变量的现实解释需要回到载荷矩阵。"),
    (("线性规划", "整数规划", "0-1规划", "混合整数"), "将资源、逻辑与容量约束显式化，在规模允许时可获得可验证的可行解与最优性界。"),
    (("多目标", "pareto", "nsga"), "在相互冲突目标之间保留权衡结构，避免把偏好不明的目标过早压成单一分数。"),
    (("遗传算法", "粒子群", "模拟退火", "蚁群"), "用于非凸、离散或组合搜索；必须先定义可行性修复、停止条件和与基线的比较。"),
    (("聚类", "k-means", "层次聚类", "dbscan"), "在缺少标签时识别对象的内部结构，为分层建模或差异化策略提供依据。"),
    (("最短路径", "网络流", "tsp", "vrp"), "把对象和连接关系抽象为节点、边及权重，使路径、运输或连通约束可计算。"),
    (("微分方程", "动力学", "sir", "seir"), "把守恒、转化、传播或反馈机制写成状态变化方程，参数和边界条件决定可解释性。"),
    (("蒙特卡洛", "仿真"), "当解析推导困难或随机性主导时，通过重复采样估计结果分布和风险，而非只报告均值。"),
    (("几何建模", "碰撞检测", "数值积分"), "直接把位置、距离、相切、碰撞或运动连续性写成几何关系，避免用黑箱模型掩盖明确机制。"),
    (("遍历搜索", "变步长搜索", "二分法", "十等分搜索"), "用于低维、有界且目标可计算的参数搜索；步长、区间与停止精度应明确。"),
    (("傅里叶变换", "drude", "cauchy", "airy", "fresnel"), "利用频谱周期或光学机理连接观测信号与待估物理参数，结果可通过多角度/多模型交叉核验。"),
    (("正态分布", "二项分布", "几何分布"), "把题目给出的随机误差或事件机制写成概率分布，使概率、期望和风险可积分或数值求解。"),
    (("贝叶斯", "mcmc"), "用先验、似然和后验统一表达参数不确定性；采样结果必须配套收敛诊断和后验预测检查。"),
    (("var",), "用多变量时间序列的滞后结构刻画变量之间的动态联动，阶数与稳定性需由数据检验。"),
    (("shapiro",), "先检验分布假设，避免在明显零膨胀或非正态数据上机械使用依赖正态性的推断。"),
    (("约束收益优化",), "把收益目标和容量、陈列、预算等现实限制统一写成可行域，直接回答决策问题。"),
]

# The extraction packet keeps a conservative term list.  OCR papers often
# name additional methods in the abstract that are not present in the global
# registry, so recover only explicit, recognizable method names here.  This is
# detection, not an inference that the paper implemented an unmentioned model.
MODEL_CUES = [
    ("双因素方差分析", ("双因素方差分析", "双向方差分析")),
    ("方差分析", ("方差分析", "anova")),
    ("假设检验", ("假设检验",)),
    ("置信区间", ("置信区间",)),
    ("线性回归", ("线性回归",)),
    ("多元回归", ("多元回归", "多重回归")),
    ("逐步回归", ("逐步回归",)),
    ("Logistic 回归", ("logistic回归", "logistic regression", "逻辑回归")),
    ("岭回归", ("岭回归", "ridge")),
    ("Lasso", ("lasso",)),
    ("ARIMA", ("arima",)),
    ("指数平滑", ("指数平滑",)),
    ("GM(1,1)", ("gm(1,1)", "gm（1,1）", "灰色预测")),
    ("Prophet", ("prophet",)),
    ("LSTM", ("lstm", "长短期记忆")),
    ("GRU", ("gru", "门控循环单元")),
    ("随机森林", ("随机森林", "随机森立", "random forest")),
    ("XGBoost", ("xgboost",)),
    ("LightGBM", ("lightgbm",)),
    ("支持向量机", ("支持向量机", "svm")),
    ("KNN", ("knn", "k近邻", "k-近邻")),
    ("BP 神经网络", ("bp神经网络", "bp 神经网络")),
    ("神经网络", ("神经网络",)),
    ("PCA", ("主成分分析", "pca")),
    ("因子分析", ("因子分析",)),
    ("AHP", ("层次分析法", "层次分析", "ahp")),
    ("熵权法", ("熵权法", "熵值法")),
    ("CRITIC", ("critic",)),
    ("TOPSIS", ("topsis", "逼近理想解")),
    ("模糊综合评价", ("模糊综合评价",)),
    ("灰色关联分析", ("灰色关联",)),
    ("DEA", ("数据包络分析", "dea")),
    ("K-Means", ("k-means", "kmeans", "k均值", "k-均值")),
    ("层次聚类", ("层次聚类", "系统聚类")),
    ("DBSCAN", ("dbscan",)),
    ("高斯混合模型", ("高斯混合", "gmm")),
    ("线性规划", ("线性规划",)),
    ("整数规划", ("整数规划",)),
    ("0-1 规划", ("0-1规划", "0－1规划", "0—1规划")),
    ("非线性规划", ("非线性规划",)),
    ("多目标规划", ("多目标规划", "多目标优化")),
    ("动态规划", ("动态规划",)),
    ("遗传算法", ("遗传算法", "genetic algorithm")),
    ("模拟退火", ("模拟退火",)),
    ("粒子群", ("粒子群", "pso")),
    ("蚁群算法", ("蚁群算法",)),
    ("NSGA-II", ("nsga-ii", "nsga2", "nsgaⅱ")),
    ("最短路径", ("最短路径", "dijkstra")),
    ("最大流", ("最大流",)),
    ("最小费用流", ("最小费用流",)),
    ("最小生成树", ("最小生成树",)),
    ("TSP", ("旅行商", "tsp")),
    ("VRP", ("车辆路径", "vrp")),
    ("网络中心性", ("网络中心性", "中心性")),
    ("社区发现", ("社区发现",)),
    ("常微分方程", ("常微分方程", "ode")),
    ("偏微分方程", ("偏微分方程", "pde")),
    ("SIR", ("sir模型", "sir 模型")),
    ("SEIR", ("seir",)),
    ("Logistic 增长", ("logistic增长", "logistic生长")),
    ("蒙特卡洛", ("蒙特卡洛", "monte carlo")),
    ("离散事件仿真", ("离散事件仿真",)),
    ("元胞自动机", ("元胞自动机",)),
    ("贝叶斯估计", ("贝叶斯估计", "贝叶斯推断", "bayesian模型", "bayes模型")),
    ("Beta-Binomial", ("beta分布", "beta 分布", "贝塔分布")),
    ("二项分布", ("二项分布",)),
    ("几何分布", ("几何分布",)),
    ("马尔可夫链", ("马尔可夫", "markov")),
    ("Pearson 相关", ("pearson", "皮尔逊相关")),
    ("Spearman 相关", ("spearman", "斯皮尔曼相关")),
    ("Savitzky-Golay 滤波", ("savitzky-golay", "savitzky–golay", "s-g滤波", "sg滤波")),
    ("移动平均", ("移动平均", "滑动平均")),
    ("卡尔曼滤波", ("卡尔曼滤波", "kalman")),
    ("小波分析", ("小波分析", "小波变换")),
    ("插值", ("线性插补", "线性插值", "样条插值", "插值法")),
    ("曲线拟合", ("曲线拟合", "多项式拟合", "非线性拟合")),
    ("模糊 C 均值", ("模糊c均值", "模糊 c 均值", "fcm聚类")),
    ("PageRank", ("pagerank",)),
    ("排队模型", ("排队论", "排队模型")),
    ("层次状态机", ("状态机",)),
    ("几何建模", ("几何模型", "几何分析", "几何方法", "解析几何")),
    ("数值积分", ("数值积分", "积分的方法", "积分法")),
    ("碰撞检测", ("碰撞检测", "碰撞判断",)),
    ("遍历搜索", ("遍历法", "遍历搜索", "穷举法")),
    ("变步长搜索", ("变步长搜索", "变步长法")),
    ("二分法", ("二分法", "二分搜索")),
    ("十等分搜索", ("十分法", "十等分法")),
    ("牛顿迭代", ("牛顿迭代", "newton迭代")),
    ("傅里叶变换", ("傅里叶变换", "快速傅里叶", "fft")),
    ("非线性最小二乘", ("非线性最小二乘",)),
    ("随机梯度下降", ("随机梯度下降", "sgd")),
    ("正态分布", ("正态分布", "高斯分布")),
    ("Drude 折射率模型", ("drude",)),
    ("Cauchy 色散模型", ("cauchy色散", "cauchy 色散")),
    ("Airy 多光束干涉模型", ("airy多光束", "airy 多光束", "airy型")),
    ("Fresnel 反射模型", ("fresnel",)),
    ("MCMC", ("mcmc", "mc链")),
    ("VAR", ("var模型", "var（", "向量自回归")),
    ("Shapiro-Wilk 检验", ("shapiro-wilk", "shapiro-wilks", "shapiro wilk")),
    ("约束收益优化", ("收益最大化的目标函数", "利润最大化的目标函数", "收益最大化模型")),
]

VALIDATION_CUES = [
    ("敏感性分析", ("敏感性分析", "灵敏度分析", "灵敏度检验", "敏感度分析")),
    ("稳健性分析", ("稳健性分析", "鲁棒性分析", "稳健性检验")),
    ("误差分析", ("误差分析", "残差分析", "残差统计", "均方根误差")),
    ("对比实验", ("对比实验", "模型对比", "方法对比", "比较实验")),
    ("交叉验证", ("交叉验证", "cross validation", "cross-validation")),
    ("显著性检验", ("显著性检验", "显著性水平", "p值", "p 值")),
    ("拟合优度", ("拟合优度", "决定系数", "r²", "r2")),
    ("置信区间", ("置信区间",)),
    ("消融实验", ("消融实验", "消融分析")),
    ("Bootstrap", ("bootstrap", "自助法")),
    ("正态性检验", ("正态性检验",)),
    ("一致性检验", ("一致性检验", "角度一致性")),
    ("收敛诊断", ("收敛性", "动态轨迹图", "mc误差", "mcmc诊断")),
]

MODEL_CANON = {
    "0-1规划": "0-1 规划",
    "灰色关联": "灰色关联分析",
    "GMM": "高斯混合模型",
    "马尔可夫": "马尔可夫链",
    "排队论": "排队模型",
}

VALIDATION_CANON = {
    "R2": "拟合优度（R²）",
    "拟合优度": "拟合优度（R²）",
    "鲁棒性": "稳健性分析",
}


def terms(packet: dict[str, Any], key: str) -> list[str]:
    result: list[str] = []
    for item in packet.get(key) or []:
        value = item.get("term") if isinstance(item, dict) else item
        if value and str(value).strip() not in result:
            result.append(str(value).strip())
    return result


def flattened_text(packet: dict[str, Any]) -> str:
    pieces = [
        str((packet.get("record") or {}).get("title") or ""),
        str((packet.get("abstract") or {}).get("text") or ""),
        " ".join(packet.get("keywords") or []),
        " ".join(terms(packet, "problem_terms")),
        " ".join(terms(packet, "model_terms")),
        " ".join(terms(packet, "algorithm_terms")),
        " ".join(terms(packet, "validation_terms")),
    ]
    for excerpts in (packet.get("section_excerpts") or {}).values():
        for excerpt in excerpts or []:
            pieces.append(str(excerpt.get("text") or ""))
    for sample in ((packet.get("ocr") or {}).get("sampled_pages") or []):
        pieces.append(str(sample.get("text") or ""))
    return re.sub(r"\s+", " ", " ".join(pieces)).lower()


def explicit_labels(text: str, rules: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    lowered = text.lower()
    return [label for label, cues in rules if any(cue.lower() in lowered for cue in cues)]


def detected_models(packet: dict[str, Any], text: str) -> list[str]:
    found: list[str] = []
    for value in terms(packet, "model_terms") + explicit_labels(text, MODEL_CUES):
        value = MODEL_CANON.get(value, value)
        if value and value not in found:
            found.append(value)
    if "线性回归" in found and "回归" in found:
        found.remove("回归")
    return found


def detected_validations(packet: dict[str, Any], text: str) -> list[str]:
    found: list[str] = []
    for value in terms(packet, "validation_terms") + explicit_labels(text, VALIDATION_CUES):
        value = VALIDATION_CANON.get(value, value)
        if value and value not in found:
            found.append(value)
    return found


def paper_title(packet: dict[str, Any]) -> str:
    """Prefer an explicit first-page title over the ministry gallery label."""
    record_title = str(packet["record"]["title"])
    # This scan starts directly at “摘要”; the topic title is recoverable only
    # from the abstract, so keep a transparent descriptive title for the card.
    if str(packet["record"].get("id")) == "1977937":
        return "板凳龙行进路径与速度控制优化"
    samples = (packet.get("ocr") or {}).get("sampled_pages") or []
    first = next((item for item in samples if int(item.get("page") or 0) == 1), None)
    if not first:
        return record_title
    lines = [re.sub(r"\s+", " ", line).strip(" -—_|：:") for line in str(first.get("text") or "").splitlines()]
    rejected = ("摘要", "关键词", "高教社杯", "数学建模竞赛", "参赛", "编号", "承诺书", "word")
    for line in lines[:8]:
        if 4 <= len(line) <= 80 and not any(token.lower() in line.lower() for token in rejected):
            return line
    return record_title


def classify(text: str) -> list[str]:
    found = [label for label, cues in TYPE_RULES.items() if any(cue in text for cue in cues)]
    return found or ["其他/综合"]


def rationale(models: list[str]) -> str:
    lowered = " ".join(models).lower()
    reasons = [reason for cues, reason in RATIONALES if any(cue in lowered for cue in cues)]
    if not reasons:
        return "证据包未给出足够模型选择说明；使用时必须回到题目目标、数据结构和假设重新论证，而不能仅凭模型名称迁移。"
    return " ".join(reasons[:4])


def alternatives(problem_types: list[str], models: list[str]) -> str:
    options: list[str] = []
    lowered = " ".join(models).lower()
    if "预测" in problem_types:
        if any(token in lowered for token in ("arima", "指数平滑", "gm(1,1)", "lstm", "gru", "prophet")):
            options.append("以季节朴素/指数平滑为基线，并用滚动时间窗比较统计、机器学习或机理预测")
        else:
            options.append("以均值/线性或正则化回归为基线，再按分组或留出误差比较树模型等非线性方案")
    if "评价" in problem_types and any(token in lowered for token in ("topsis", "熵权", "critic", "ahp", "主成分", "pca", "模糊", "dea")):
        options.append("比较主客观赋权及降维后评价，检查权重敏感性和指标重复")
    if "优化" in problem_types and any(token in lowered for token in ("规划", "动态规划", "遗传", "粒子群", "模拟退火", "nsga", "最短路径", "tsp", "vrp")):
        options.append("先尝试精确规划或凸优化，再以启发式处理非凸或大规模搜索")
    if ("分类" in problem_types or "聚类" in problem_types) and any(token in lowered for token in ("logistic", "支持向量", "随机森林", "xgboost", "lightgbm", "knn", "聚类", "k-means", "dbscan", "gmm")):
        options.append("以简单可解释模型/不同距离结构作基线，并用稳定性或外部标签验证")
    if "网络/图论" in problem_types and any(token in lowered for token in ("路径", "流", "tsp", "vrp", "生成树", "中心性", "社区")):
        options.append("比较路径/流模型与含时间窗、容量或随机需求的扩展")
    if ("机理/动力学" in problem_types or "仿真" in problem_types) and any(token in lowered for token in ("微分", "sir", "seir", "蒙特卡洛", "仿真", "元胞")):
        options.append("比较解析/数值机理模型与数据驱动近似，并检验参数可辨识性")
    return "；".join(options[:3]) or "替代方案未被抽取证据明确报告；应以更简单基线和不同关键假设的方案作对照。"


def evidence_rows(packet: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for section, excerpts in (packet.get("section_excerpts") or {}).items():
        for excerpt in (excerpts or [])[:1]:
            page = excerpt.get("page", "?")
            matched = "、".join(excerpt.get("matched_terms") or []) or section
            rows.append(f"| {section}：{matched} | 第 {page} 页 | 抽取命中 | 中 |")
    for sample in ((packet.get("ocr") or {}).get("sampled_pages") or []):
        reasons = sample.get("reasons") or sample.get("reason") or ["sample"]
        if isinstance(reasons, str):
            reasons = [reasons]
        rows.append(
            f"| OCR抽样页（{'、'.join(str(item) for item in reasons)}） | 第 {sample.get('page', '?')} 页 | OCR | 中 |"
        )
    return rows[:8] or ["| 文本/图像证据包 | 页码未识别 | 自动抽取 | 低 |"]


def compact(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= limit else value[:limit].rstrip("，。；; ") + "…"


def abstract_text(packet: dict[str, Any]) -> str:
    value = str((packet.get("abstract") or {}).get("text") or "").strip()
    if not value:
        samples = (packet.get("ocr") or {}).get("sampled_pages") or []
        first = next((item for item in samples if int(item.get("page") or 0) == 1), None)
        value = str((first or {}).get("text") or "")
        if "摘要" in value:
            value = value.split("摘要", 1)[1]
        value = re.split(r"(?:\n|^)(?:一[、.]|1[.、]\s*)问题", value, maxsplit=1)[0]
        value = re.sub(r"(?:中国大学生在线|dxs\.moe\.gov\.cn).*", "", value, flags=re.S | re.I)
    return re.sub(r"\s+", " ", value).strip()


def sentence_chunks(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？；])", value) if part.strip()]


def abstract_problem_chain(packet: dict[str, Any]) -> tuple[str, str]:
    """Return a grounded core statement and a compact per-question chain."""
    abstract = abstract_text(packet)
    if not abstract:
        return "摘要证据不足，需回到源论文核对现实目标与输出。", "按题目各子问的输入、输出和依赖关系重新拆解。"
    marker = re.compile(r"(?=针对(?:问题|第)?[一二三四五六七八12345678])")
    pieces = [piece.strip() for piece in marker.split(abstract) if piece.strip()]
    intro = pieces[0] if pieces and not pieces[0].startswith("针对") else ""
    core = compact(intro or abstract, 180)
    question_parts = [piece for piece in pieces if piece.startswith("针对")]
    if question_parts:
        chain = "；".join(compact(piece, 145) for piece in question_parts[:8])
    else:
        chain = "；".join(compact(piece, 120) for piece in sentence_chunks(abstract)[:5])
    return core, chain


def data_evidence(packet: dict[str, Any]) -> str:
    abstract = abstract_text(packet)
    cues = ("数据", "样本", "附件", "视频", "图像", "时间", "空间", "坐标", "指标", "观测", "问卷", "频率", "传感", "文本")
    selected = [sentence for sentence in sentence_chunks(abstract) if any(cue in sentence for cue in cues)]
    detail = " ".join(selected[:4]) or abstract
    return (
        f"证据方式为 {packet.get('extract_mode', 'unknown')}，论文 {packet.get('page_count', '?')} 页；"
        f"摘要可确认：{compact(detail, 430)}"
    )


def formula_hints(models: list[str]) -> str:
    lowered = " ".join(models).lower()
    hints: list[str] = []
    rules = [
        (("回归",), r"回归骨架：$y=\beta_0+\sum_j\beta_jx_j+\varepsilon$；系数、变换和损失须按原文核对"),
        (("topsis",), r"TOPSIS：$C_i=D_i^-/(D_i^++D_i^-)$，并核对指标方向、标准化与权重"),
        (("熵权",), r"熵权：$w_j=(1-e_j)/\sum_k(1-e_k)$，零值和归一化规则需回源"),
        (("ahp", "层次分析"), r"AHP：$Aw=\lambda_{max}w$，并报告 $CR=CI/RI$"),
        (("动态规划",), r"动态规划：$V_t(s)=\max_a\{r_t(s,a)+V_{t+1}(f(s,a))\}$（或最小化版本）"),
        (("贝叶斯", "beta-binomial"), r"贝叶斯更新：$p(\theta\mid D)\propto p(D\mid\theta)p(\theta)$"),
        (("线性规划", "整数规划", "0-1 规划", "多目标规划", "非线性规划", "约束收益优化"), r"优化骨架：$\min/\max\ f(x)$，满足 $g(x)\le0,\ h(x)=0$ 及变量域"),
        (("k-means",), r"K-Means：$\min\sum_i\lVert x_i-\mu_{c_i}\rVert_2^2$，并验证 $K$ 与初始化稳定性"),
        (("pca",), r"PCA：对协方差/相关矩阵作特征分解，按载荷与累计解释率选择主成分"),
        (("常微分", "sir", "seir", "logistic 增长"), r"机理模型：$\dot x=f(x,u,\theta,t)$，参数、初值及守恒/边界条件必须可解释"),
        (("蒙特卡洛",), r"Monte Carlo：$\hat\mu=N^{-1}\sum_{r=1}^{N}g(X^{(r)})$，同时报告抽样误差或置信区间"),
        (("pearson",), r"Pearson：$r=\operatorname{cov}(X,Y)/(\sigma_X\sigma_Y)$，不据此宣称因果"),
        (("spearman",), r"Spearman：对秩变量计算相关系数，并检查并列秩处理"),
        (("假设检验",), r"假设检验：预先声明 $H_0/H_1$、显著性水平、统计量与拒绝域"),
        (("正态分布", "二项分布", "几何分布"), r"概率模型：按题意写出联合/条件分布并对可行事件域积分或求和，独立性假设须单独核验"),
        (("傅里叶变换",), r"频域分析：$X(f)=\int x(t)e^{-i2\pi ft}\,dt$（离散数据用 DFT/FFT），频率—物理参数关系须由机理推导"),
        (("几何建模", "碰撞检测"), r"几何约束：用坐标、距离、内积/叉积和相切条件构造位置与碰撞判据，并检查边界情形"),
        (("二分法", "变步长搜索", "遍历搜索", "十等分搜索"), r"搜索求解：给出初始区间、单调/可行性判据、步长更新与误差停止条件"),
        (("var",), r"VAR：$y_t=c+\sum_{k=1}^{p}A_ky_{t-k}+\varepsilon_t$，需检查阶数、稳定性与滚动外推误差"),
    ]
    for cues, hint in rules:
        if any(cue in lowered for cue in cues) and hint not in hints:
            hints.append(hint)
    return "；".join(hints[:4]) or "抽样证据不足以可靠恢复公式；不得臆造原文公式编号、变量或参数，使用前按证据页回源。"


def grounded_algorithm(packet: dict[str, Any], models: list[str], algorithms: list[str]) -> str:
    core, chain = abstract_problem_chain(packet)
    method_text = "、".join((algorithms + models)[:12])
    return (
        f"输入与预处理按摘要/附件字段核对；按子问链依次执行“{compact(chain, 420)}”；"
        f"对应实现模块包括 {method_text or '待回源确认的方法'}；每一步保存中间量并用下一问的输入接口检查维度、单位和可行性。"
    )


def conditional_limitations(packet: dict[str, Any], models: list[str]) -> str:
    lowered = " ".join(models).lower()
    risks: list[str] = [
        f"本卡依据 {packet.get('extract_mode', 'unknown')} 的抽样证据，未覆盖页的公式、参数、图表与附录代码不可视为已核验"
    ]
    if "回归" in lowered or "相关" in lowered:
        risks.append("相关/回归易受共线性、异常值和小样本影响，也不能自动支持因果解释")
    if any(token in lowered for token in ("topsis", "熵权", "ahp", "评价")):
        risks.append("排序可能对指标方向、标准化和权重敏感")
    if any(token in lowered for token in ("遗传", "粒子群", "模拟退火", "nsga")):
        risks.append("随机搜索需多随机种子、收敛曲线和小规模精确基线")
    if any(token in lowered for token in ("神经网络", "lstm", "gru")):
        risks.append("复杂模型只有在样本量、外部验证和消融支持时才可声称优于简洁基线")
    if any(token in lowered for token in ("动态规划", "线性规划", "整数规划")):
        risks.append("目标、状态转移和硬约束若与现实成本不一致，会得到数学可行但现实失真的方案")
    return "；".join(risks[:4]) + "。"


def grounded_innovation(models: list[str], problem_types: list[str]) -> str:
    method = "、".join(models[:6])
    return (
        f"【原文明示范围】抽样摘要可确认论文围绕 {'、'.join(problem_types)} 使用 {method} 形成分问方案；"
        "【专家归纳】可迁移的创新应落在特征构造、现实约束、阶段衔接或不确定性处理上，"
        "并用基线/消融验证该改动，而不能仅把方法名称或复杂度本身称为创新。"
    )


def card_text(case_id: str, packet: dict[str, Any]) -> str:
    record = packet["record"]
    text = flattened_text(packet)
    title = paper_title(packet)
    models = detected_models(packet, text) or ["未从证据包稳定识别，使用前回源核对"]
    algorithms = terms(packet, "algorithm_terms")
    validations = detected_validations(packet, text) or ["原文独立验证手段未在证据包中稳定识别"]
    problem_types = classify(text)
    keywords = [str(value) for value in packet.get("keywords") or []][:12]
    abstract = abstract_text(packet)
    core_evidence, problem_chain = abstract_problem_chain(packet)
    core_problem = (
        f"{core_evidence} 从数学结构看，任务包含 {'、'.join(problem_types)}；"
        "具体输出、阈值与指标以原题和全文为准。"
    )
    data_features = data_evidence(packet)
    transferable = [
        f"先按{problem_types[0]}目标界定输出，再选择满足数据与假设条件的模型",
        "把每个模型绑定到一个明确子问题，并用基线、误差与敏感性证据验证",
    ]
    if len(models) > 1:
        transferable.append("组合模型应沿数据或决策依赖链传递，而不是并列堆砌")
    meta = {
        "case_id": case_id,
        "paper_id": str(record["id"]),
        "year": int(record["year"]),
        "paper_code": str(record.get("paper_code") or ""),
        "title": title,
        "competition": "CUMCM",
        "problem_types": problem_types,
        "models": models[:16],
        "keywords": keywords,
        "validation_methods": validations[:12],
        "core_problem": core_problem,
        "data_features": compact(data_features, 360),
        "transferable_patterns": transferable,
        "source_pdf": str(record["output_file"]).replace("\\", "/"),
        "source_page": str(record.get("source_page") or ""),
        "evidence_mode": packet.get("extract_mode", "unknown"),
    }
    yaml_text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000).strip()
    code = str(record.get("paper_code") or "-")
    lines = [
        "---", yaml_text, "---", "", f"# {case_id}｜{title}", "",
        "## 基本信息", "",
        f"- 【题目】{title}", f"- 【比赛】CUMCM", f"- 【年份】{record['year']}",
        f"- 【题号/内容ID】{code} / {record['id']}",
        f"- 【论文文件】`{meta['source_pdf']}`", f"- 【问题类型】{'、'.join(problem_types)}", "",
        "## 决策链", "", f"- 【核心问题】{core_problem}",
        f"- 【数据特点】{meta['data_features']}",
        f"- 【问题拆解方式】【原文明示摘要链】{problem_chain} 【专家归纳】先完成共享预处理/参数估计，再按该链传递中间结果；实际依赖方向需按全文证据页确认。",
        f"- 【使用模型】{'、'.join(models)}", f"- 【模型选择理由】{rationale(models)}",
        f"- 【考虑的替代方案】{alternatives(problem_types, models)}",
        f"- 【关键公式】{formula_hints(models)}",
        f"- 【算法】{grounded_algorithm(packet, models, algorithms)}", "",
        "## 可信度与创新", "", f"- 【模型验证方法】{'、'.join(validations)}",
        "- 【关键定量结果】不从不完整抽取片段拼接数值；需要定量复用时按证据页回源核对单位、比较对象和适用条件。",
        f"- 【创新点】{grounded_innovation(models, problem_types)}",
        "- 【论文结构亮点】以摘要的分问题叙述为入口，将方法、结果和结论一一对应，避免只列模型名称。",
        f"- 【主要局限】{conditional_limitations(packet, models)}", "",
        "## 迁移规则", "",
        f"- 【可迁移经验】{'；'.join(transferable)}。",
        "- 【不应该机械复制的部分】原论文的阈值、权重、参数、数据划分和题目专属约束；除非新题数据与机制均支持。",
        f"- 【相似题检索标签】{'、'.join((problem_types + keywords + models)[:18])}",
        "- 【适用边界】当新题的输出目标、数据粒度、随机性、约束结构或机制假设发生改变时，只迁移决策过程，不直接移植模型。", "",
        "## 证据锚点", "", "| 提炼结论 | 原文页码/图表/公式 | 证据类型 | 置信度 |",
        "|---|---|---|---|", *evidence_rows(packet), "",
        "## 审阅备注", "",
        "本卡为证据约束的案例记忆。明示内容来自抽取命中；替代方案与迁移规则属于专家归纳，不应反向声称为论文原话。", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packets", type=Path)
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--evidence-mode", choices=["text", "ocr_sampled"])
    parser.add_argument("--year", action="append", type=int, help="Only write these years; repeat as needed.")
    args = parser.parse_args()
    packet_paths = [
        path for path in args.packets.rglob("*.json")
        if path.name != "index.json"
    ]
    packets_by_id: dict[str, dict[str, Any]] = {}

    def packet_quality(packet: dict[str, Any]) -> int:
        text_chars = int((packet.get("text_stats") or {}).get("total_chars") or 0)
        ocr_chars = sum(
            int(sample.get("char_count") or len(str(sample.get("text") or "")))
            for sample in ((packet.get("ocr") or {}).get("sampled_pages") or [])
        )
        return text_chars + ocr_chars

    for path in packet_paths:
        packet = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(packet.get("record"), dict) and packet["record"].get("id"):
            record_id = str(packet["record"]["id"])
            current = packets_by_id.get(record_id)
            if current is None or packet_quality(packet) > packet_quality(current):
                packets_by_id[record_id] = packet
    packets = list(packets_by_id.values())
    packets.sort(key=lambda item: (
        int(item["record"]["year"]),
        str(item["record"].get("paper_code") or "Z"),
        str(item["record"]["title"]),
        str(item["record"]["id"]),
    ))
    if len(packets) != 139:
        raise SystemExit(f"expected 139 packets, found {len(packets)}")
    cases_dir = args.skill_root.resolve() / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    for index, packet in enumerate(packets, start=1):
        if args.evidence_mode and packet.get("extract_mode") != args.evidence_mode:
            continue
        if args.year and int(packet["record"]["year"]) not in set(args.year):
            continue
        case_id = f"case-{index:03d}"
        destination = cases_dir / f"{case_id}.md"
        if destination.exists() and not args.overwrite:
            skipped += 1
            continue
        part = destination.with_suffix(".md.part")
        part.write_text(card_text(case_id, packet), encoding="utf-8", newline="\n")
        part.replace(destination)
        created += 1
    print(f"created {created} case-card drafts; skipped {skipped} existing cards in {cases_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
