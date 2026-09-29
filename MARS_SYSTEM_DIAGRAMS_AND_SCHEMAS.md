# MARS: Formal Architecture Diagrams & Specification Code
**Eraser.io & Draw.io Diagram-as-Code Specifications**

**System:** MARS (Multi-Agent Reasoning System for Corporate Decision Advisory)  
**Date:** September 30, 2026  
**Document Type:** Technical Blueprint & UML Specifications  

---

## Quick Import Instructions

* **For Eraser.io (Diagram 1):**  
  1. Open [Eraser.io](https://app.eraser.io/).  
  2. Create a new document or canvas.  
  3. Click **Insert > Diagram as Code** (or paste directly into an Eraser code block).  
  4. Paste the Eraser.io code snippet from **Section 1**.

* **For Draw.io / diagrams.net (Diagrams 2, 3, and 4):**  
  1. Open [draw.io (diagrams.net)](https://app.diagrams.net/).  
  2. Create a blank diagram.  
  3. Go to top menu: **Arrange > Insert > Advanced > XML...** (or **Extras > Edit Diagram...**).  
  4. Paste the complete XML block from the respective section and click **Apply**.

---

## 1. UML Class Diagram (Eraser.io Code)

```eraser
title MARS System Architecture - UML Class Diagram

// --- STATE MANAGEMENT ---
State [icon: layers, color: blue] {
  messages: List[BaseMessage]
  query: str
  active_departments: Optional[List[str]]
  finance_output: Optional[Dict]
  rd_output: Optional[Dict]
  legal_output: Optional[Dict]
  operations_output: Optional[Dict]
  final_decision: Optional[str]
  metadata: Dict[str, Any]
}

// --- AGENT SUBSYSTEM ---
AgentBase [icon: cpu, color: purple] {
  name: str
  role: str
  execute(state: State): Dict
  build_case_evidence(cases, tools, conf): Dict
}

RouterAgent [icon: git-branch, color: purple] {
  classify_intent(state: State): Dict
}

FinanceAgent [icon: dollar-sign, color: purple] {
  assess_financial_impact(state: State): Dict
}

LegalAgent [icon: shield, color: purple] {
  audit_regulatory_compliance(state: State): Dict
}

RDAgent [icon: terminal, color: purple] {
  evaluate_technical_feasibility(state: State): Dict
}

OperationsAgent [icon: settings, color: purple] {
  analyze_supply_chain(state: State): Dict
}

AggregatorAgent [icon: refresh-cw, color: purple] {
  rank_departments(outputs: List): List
  synthesize_tradeoffs(state: State): Dict
}

// --- REASONING & GROUNDING SUBSYSTEM ---
SemanticRouter [icon: compass, color: green] {
  DEPARTMENT_ANCHOR_PROFILES: Dict
  threshold: float = 0.32
  margin_ratio: float = 0.70
  get_department_centroids(): Dict[str, ndarray]
  route_departments_semantically(query): Tuple[List[str], Dict]
}

ConfidenceEngine [icon: activity, color: green] {
  w_sim: float
  w_rec: float
  w_succ: float
  DEFAULT_RECENCY_LAMBDA: float = 0.05
  calculate_confidence(cases, weights): float
  compute_recency(cases, ref_quarter, decay): float
  parse_quarter_to_index(quarter_str): int
}

ConformalRiskController [icon: award, color: green] {
  alpha: float = 0.05
  decay_rate: float = 0.05
  quantile_cache: Dict[str, float]
  calibrate_from_historical_data(conf, y, quarters): float
  evaluate_decision_bound(point_conf, dept, alpha): ConformalDecisionBound
}

ConformalDecisionBound [icon: file-text, color: gray] {
  point_confidence: float
  confidence_interval: Tuple[float, float]
  coverage_guarantee: float
  quantile_cutoff: float
  risk_level: str
  decision_policy: str
  policy_rationale: str
}

WeightRegistry [icon: database, color: green] {
  registry_path: str
  profiles: Dict[str, List[float]]
  get_weights(domain, action_type): Tuple
  update_profile(name, weights): None
  optimize_weights_from_outcomes(cases): Tuple
}

CalibrationMetrics [icon: bar-chart-2, color: green] {
  compute_ece(conf, y, n_bins): float
  compute_brier_score(conf, y): float
  compute_nll(conf, y): float
  compute_calibration_curve(conf, y): Dict
}

OutcomeAnalyzer [icon: check-circle, color: green] {
  SUCCESS_KEYWORDS: List[str]
  FAILURE_KEYWORDS: List[str]
  NEGATED_PATTERNS: List[str]
  analyze_outcomes(cases): float
  classify_text_outcome(excerpt): str
}

// --- STORAGE & RETRIEVAL ---
CaseRetrievalService [icon: server, color: orange] {
  supabase_client: Client
  get_similar_cases(query, department, limit): List[Dict]
  execute_hybrid_search(query, alpha): List[Dict]
}

EmbedderService [icon: zap, color: orange] {
  model_name: str = "all-MiniLM-L6-v2"
  get_embedding(text): List[float]
  get_embeddings(texts): List[List[float]]
}

// --- INHERITANCE & RELATIONSHIPS ---
AgentBase <|-- RouterAgent
AgentBase <|-- FinanceAgent
AgentBase <|-- LegalAgent
AgentBase <|-- RDAgent
AgentBase <|-- OperationsAgent
AgentBase <|-- AggregatorAgent

RouterAgent > SemanticRouter : invokes vector gating
RouterAgent > State : mutates active_departments

FinanceAgent > CaseRetrievalService : queries pgvector RAG
LegalAgent > CaseRetrievalService : queries pgvector RAG
RDAgent > CaseRetrievalService : queries pgvector RAG
OperationsAgent > CaseRetrievalService : queries pgvector RAG

AgentBase > ConfidenceEngine : computes case_based_confidence
AgentBase > ConformalRiskController : obtains distribution-free bounds
ConformalRiskController > ConformalDecisionBound : generates
ConfidenceEngine > WeightRegistry : reads calibrated weights
ConfidenceEngine > OutcomeAnalyzer : evaluates precedent track record

AggregatorAgent > State : reads all active outputs
AggregatorAgent > ConformalDecisionBound : formats risk policy into prompt

SemanticRouter > EmbedderService : projects queries to 384d
CaseRetrievalService > EmbedderService : vectorizes search query
```

---

## 2. UML Use Case Diagram (Draw.io XML Code)

Copy the XML below and paste into Draw.io (**Arrange > Insert > Advanced > XML...**):

```xml
<mxfile host="app.diagrams.net" modified="2026-09-30T00:00:00.000Z" agent="MARS-Architect" version="21.0.0" type="device">
  <diagram id="mars-usecase-diag" name="MARS Use Case Diagram">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="900" background="#FFFFFF">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- Actors -->
        <mxCell id="act_exec" value="Corporate Executive&#xa;(CEO / CFO / General Counsel)" style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
          <mxGeometry x="50" y="240" width="40" height="80" as="geometry"/>
        </mxCell>

        <mxCell id="act_analyst" value="Strategic Risk Analyst&#xa;(Finance / Legal / Ops)" style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor=#d5e8d4;strokeColor=#82b366;" vertex="1" parent="1">
          <mxGeometry x="50" y="480" width="40" height="80" as="geometry"/>
        </mxCell>

        <mxCell id="act_mle" value="AI/ML Engineer&#xa;(Continuous Evaluator)" style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="1">
          <mxGeometry x="1070" y="340" width="40" height="80" as="geometry"/>
        </mxCell>

        <!-- System Boundary -->
        <mxCell id="sys_box" value="MARS Corporate Decision Advisory Platform" style="shape=rect;html=1;verticalAlign=top;fontStyle=1;whiteSpace=wrap;align=center;fillColor=#f8f9fa;strokeColor=#495057;strokeWidth=2;dashed=0;" vertex="1" parent="1">
          <mxGeometry x="170" y="40" width="840" height="800" as="geometry"/>
        </mxCell>

        <!-- Core Operational Use Cases -->
        <mxCell id="uc_query" value="Submit Complex Strategic Query&#xa;(e.g. M&amp;A, CapEx, Antitrust)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0066cc;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="220" y="100" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_route" value="Dynamic Embedding-Space&#xa;Sparse MoE Routing (&lt;10ms)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="540" y="100" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_rag" value="Retrieve Historical Precedents&#xa;(Hybrid pgvector + MMR)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0066cc;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="220" y="220" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_conf" value="Compute Multi-Factor&#xa;Calibrated Confidence" style="ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="540" y="220" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_conformal" value="Apply Temporally-Weighted&#xa;Conformal Risk Bounds (95% CI)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;strokeWidth=2;" vertex="1" parent="1">
          <mxGeometry x="540" y="340" width="230" height="70" as="geometry"/>
        </mxCell>

        <mxCell id="uc_synth" value="Synthesize Cross-Departmental&#xa;Trade-offs &amp; Action Plan" style="ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0066cc;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="220" y="340" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_abstain" value="Trigger Risk-Controlled&#xa;Human Review / Abstention" style="ellipse;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontStyle=1;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="220" y="460" width="220" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_audit" value="Inspect Explainability Trail&#xa;&amp; Citation Sources" style="ellipse;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0066cc;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="220" y="580" width="220" height="60" as="geometry"/>
        </mxCell>

        <!-- Engineering / Research Use Cases -->
        <mxCell id="uc_opt" value="Optimize Simplex Weights&#xa;(BCE Loss on Historical Outcomes)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="550" y="470" width="230" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_backtest" value="Execute Longitudinal Backtesting&#xa;(2023-2024 -> 2025-2026 Split)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="550" y="580" width="230" height="60" as="geometry"/>
        </mxCell>

        <mxCell id="uc_multicorp" value="Evaluate Cross-Industry Generalization&#xa;(MultiCorp-QA Benchmark)" style="ellipse;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=1.5;" vertex="1" parent="1">
          <mxGeometry x="550" y="690" width="240" height="65" as="geometry"/>
        </mxCell>

        <!-- Actor Associations -->
        <mxCell id="e_exec1" edge="1" source="act_exec" target="uc_query" parent="1" style="strokeColor=#0066cc;strokeWidth=1.5;"/>
        <mxCell id="e_exec2" edge="1" source="act_exec" target="uc_synth" parent="1" style="strokeColor=#0066cc;strokeWidth=1.5;"/>
        <mxCell id="e_analyst1" edge="1" source="act_analyst" target="uc_audit" parent="1" style="strokeColor=#82b366;strokeWidth=1.5;"/>
        <mxCell id="e_analyst2" edge="1" source="act_analyst" target="uc_abstain" parent="1" style="strokeColor=#b85450;strokeWidth=1.5;"/>
        
        <mxCell id="e_mle1" edge="1" source="act_mle" target="uc_opt" parent="1" style="strokeColor=#d79b00;strokeWidth=1.5;"/>
        <mxCell id="e_mle2" edge="1" source="act_mle" target="uc_backtest" parent="1" style="strokeColor=#d79b00;strokeWidth=1.5;"/>
        <mxCell id="e_mle3" edge="1" source="act_mle" target="uc_multicorp" parent="1" style="strokeColor=#d79b00;strokeWidth=1.5;"/>

        <!-- Includes & Extends Relationships -->
        <mxCell id="inc_route" value="&amp;lt;&amp;lt;include&amp;gt;&amp;gt;" edge="1" source="uc_query" target="uc_route" parent="1" style="dashed=1;endArrow=open;strokeColor=#7f8c8d;"/>
        <mxCell id="inc_rag" value="&amp;lt;&amp;lt;include&amp;gt;&amp;gt;" edge="1" source="uc_route" target="uc_rag" parent="1" style="dashed=1;endArrow=open;strokeColor=#7f8c8d;"/>
        <mxCell id="inc_conf" value="&amp;lt;&amp;lt;include&amp;gt;&amp;gt;" edge="1" source="uc_rag" target="uc_conf" parent="1" style="dashed=1;endArrow=open;strokeColor=#7f8c8d;"/>
        <mxCell id="inc_conformal" value="&amp;lt;&amp;lt;include&amp;gt;&amp;gt;" edge="1" source="uc_conf" target="uc_conformal" parent="1" style="dashed=1;endArrow=open;strokeColor=#7f8c8d;"/>
        <mxCell id="inc_synth" value="&amp;lt;&amp;lt;include&amp;gt;&amp;gt;" edge="1" source="uc_conformal" target="uc_synth" parent="1" style="dashed=1;endArrow=open;strokeColor=#7f8c8d;"/>
        <mxCell id="ext_abstain" value="&amp;lt;&amp;lt;extend&amp;gt;&amp;gt;&#xa;(lower bound &lt; 0.30)" edge="1" source="uc_abstain" target="uc_conformal" parent="1" style="dashed=1;endArrow=open;strokeColor=#b85450;fontColor=#b85450;"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## 3. UML Sequence Diagram (Draw.io XML Code)

Copy the XML below and paste into Draw.io (**Arrange > Insert > Advanced > XML...**):

```xml
<mxfile host="app.diagrams.net" modified="2026-09-30T00:00:00.000Z" agent="MARS-Architect" version="21.0.0" type="device">
  <diagram id="mars-sequence-diag" name="MARS End-to-End Sequence Diagram">
    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1350" pageHeight="950" background="#FFFFFF">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- Lifelines (Headers) -->
        <mxCell id="ll_user" value="User / Client&#xa;(Executive)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="110" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_user" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_user" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="95" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_router" value="Router Node&#xa;(semantic_router)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="220" y="40" width="130" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_router" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_router" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="285" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_active" value="Active Agent&#xa;(Finance / Legal)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="420" y="40" width="130" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_active" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_active" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_pruned" value="Pruned Agent&#xa;(R&amp;D / Ops)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="610" y="40" width="120" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_pruned" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_pruned" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="670" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_db" value="Database / RAG&#xa;(Supabase pgvector)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="790" y="40" width="130" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_db" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_db" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="855" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_conformal" value="Conformal Engine&#xa;(TW-CRC Controller)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="980" y="40" width="140" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_conformal" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_conformal" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1050" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="ll_aggregator" value="Aggregator Node&#xa;(Cross-Dept Synth)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="1180" y="40" width="130" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="line_aggregator" value="" style="endArrow=none;dashed=1;html=1;strokeWidth=1.5;" edge="1" source="ll_aggregator" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1245" y="850" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <!-- Messages & Interactions -->
        <mxCell id="msg1" value="1. POST /api/query (query_str)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="95" y="110" as="sourcePoint"/>
            <mxPoint x="285" y="110" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg2" value="2. Encode query &amp; compute dot-product vs centroids (&lt;10ms)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="285" y="140" as="sourcePoint"/>
            <mxPoint x="285" y="170" as="targetPoint"/>
            <Array as="points">
              <mxPoint x="340" y="140"/>
              <mxPoint x="340" y="170"/>
            </Array>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg3" value="3. Set State['active_departments'] = ['finance', 'legal']" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="285" y="200" as="sourcePoint"/>
            <mxPoint x="485" y="200" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <!-- Fast Exit for Pruned -->
        <mxCell id="msg4" value="4. Check active_departments (rd not in active)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="285" y="230" as="sourcePoint"/>
            <mxPoint x="670" y="230" as="targetPoint"/>
          </mxGeometry>
        </mxCell>
        <mxCell id="msg5" value="5. Instant Fast Exit: return {rd_output: None} (0.0001s, 0 DB, 0 LLM)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="670" y="260" as="sourcePoint"/>
            <mxPoint x="1245" y="260" as="targetPoint"/>
            <Array as="points"><mxPoint x="800" y="260"/></Array>
          </mxGeometry>
        </mxCell>

        <!-- Active Agent Flow -->
        <mxCell id="msg6" value="6. get_similar_cases(query, dept, limit=5)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="300" as="sourcePoint"/>
            <mxPoint x="855" y="300" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg7" value="7. Return retrieved historical precedents with quarters &amp; outcomes" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="855" y="340" as="sourcePoint"/>
            <mxPoint x="485" y="340" as="targetPoint"/>
            <mxPoint as="offset"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg8" value="8. Calculate confidence = w1*Sim + w2*Rec + w3*Succ" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="380" as="sourcePoint"/>
            <mxPoint x="485" y="410" as="targetPoint"/>
            <Array as="points">
              <mxPoint x="540" y="380"/>
              <mxPoint x="540" y="410"/>
            </Array>
          </mxGeometry>
        </mxCell>

        <!-- Conformal Call -->
        <mxCell id="msg9" value="9. evaluate_decision_bound(point_conf=0.85, alpha=0.05)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="440" as="sourcePoint"/>
            <mxPoint x="1050" y="440" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg10" value="10. Return ConformalDecisionBound([0.61, 1.00], PROCEED_AUTONOMOUS)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1050" y="480" as="sourcePoint"/>
            <mxPoint x="485" y="480" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg11" value="11. Execute LLM Reasoning with Case Evidence" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="520" as="sourcePoint"/>
            <mxPoint x="485" y="550" as="targetPoint"/>
            <Array as="points">
              <mxPoint x="540" y="520"/>
              <mxPoint x="540" y="550"/>
            </Array>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg12" value="12. Return {finance_output: ..., case_based_confidence: 0.85, conformal: ...}" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="485" y="580" as="sourcePoint"/>
            <mxPoint x="1245" y="580" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <!-- Aggregator Phase -->
        <mxCell id="msg13" value="13. Rank active departments by case_based_confidence" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1245" y="620" as="sourcePoint"/>
            <mxPoint x="1245" y="650" as="targetPoint"/>
            <Array as="points">
              <mxPoint x="1300" y="620"/>
              <mxPoint x="1300" y="650"/>
            </Array>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg14" value="14. Synthesize trade-offs (format Scoped Out vs Conformal 95% Bounds)" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1245" y="680" as="sourcePoint"/>
            <mxPoint x="1245" y="710" as="targetPoint"/>
            <Array as="points">
              <mxPoint x="1300" y="680"/>
              <mxPoint x="1300" y="710"/>
            </Array>
          </mxGeometry>
        </mxCell>

        <mxCell id="msg15" value="15. Return Final Synthesized Advisory + Conformal Bounds + Citations" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="1245" y="750" as="sourcePoint"/>
            <mxPoint x="95" y="750" as="targetPoint"/>
          </mxGeometry>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## 4. UML Package & Deployment Diagram (Draw.io XML Code)

Copy the XML below and paste into Draw.io (**Arrange > Insert > Advanced > XML...**):

```xml
<mxfile host="app.diagrams.net" modified="2026-09-30T00:00:00.000Z" agent="MARS-Architect" version="21.0.0" type="device">
  <diagram id="mars-package-deploy" name="MARS Package and Deployment Diagram">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="900" background="#FFFFFF">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- Package 1: Presentation / API Layer -->
        <mxCell id="pkg_api" value="Package: app.api &amp; app.core" style="shape=folder;fontStyle=1;tabWidth=150;tabHeight=30;tabPosition=left;html=1;boundedLbl=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
          <mxGeometry x="40" y="60" width="340" height="220" as="geometry"/>
        </mxCell>
        <mxCell id="c_fastapi" value="&amp;lt;&amp;lt;component&amp;gt;&amp;gt;&#xa;FastAPI Application&#xa;(main.py / routes)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;" vertex="1" parent="pkg_api">
          <mxGeometry x="30" y="50" width="130" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_config" value="&amp;lt;&amp;lt;component&amp;gt;&amp;gt;&#xa;Config &amp; Settings&#xa;(core/config.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;" vertex="1" parent="pkg_api">
          <mxGeometry x="180" y="50" width="130" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_state" value="&amp;lt;&amp;lt;component&amp;gt;&amp;gt;&#xa;Graph State Model&#xa;(state.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontStyle=1;" vertex="1" parent="pkg_api">
          <mxGeometry x="90" y="130" width="150" height="60" as="geometry"/>
        </mxCell>

        <!-- Package 2: Multi-Agent Workflow Layer -->
        <mxCell id="pkg_agents" value="Package: app.agents" style="shape=folder;fontStyle=1;tabWidth=140;tabHeight=30;tabPosition=left;html=1;boundedLbl=1;fillColor=#e1d5e7;strokeColor=#9673a6;" vertex="1" parent="1">
          <mxGeometry x="440" y="60" width="340" height="220" as="geometry"/>
        </mxCell>
        <mxCell id="c_router" value="Router Node&#xa;(router.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;" vertex="1" parent="pkg_agents">
          <mxGeometry x="20" y="50" width="130" height="50" as="geometry"/>
        </mxCell>
        <mxCell id="c_depts" value="Department Agents&#xa;(finance, legal, rd, ops)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;" vertex="1" parent="pkg_agents">
          <mxGeometry x="180" y="50" width="140" height="50" as="geometry"/>
        </mxCell>
        <mxCell id="c_agg" value="Aggregator Node&#xa;(reasoning/aggregator.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;" vertex="1" parent="pkg_agents">
          <mxGeometry x="20" y="130" width="140" height="50" as="geometry"/>
        </mxCell>
        <mxCell id="c_common" value="Common Evidence&#xa;(common.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;" vertex="1" parent="pkg_agents">
          <mxGeometry x="180" y="130" width="140" height="50" as="geometry"/>
        </mxCell>

        <!-- Package 3: Reasoning & Conformal Core -->
        <mxCell id="pkg_reasoning" value="Package: app.reasoning (Tier-1 Core)" style="shape=folder;fontStyle=1;tabWidth=220;tabHeight=30;tabPosition=left;html=1;boundedLbl=1;fillColor=#d5e8d4;strokeColor=#82b366;" vertex="1" parent="1">
          <mxGeometry x="40" y="340" width="740" height="220" as="geometry"/>
        </mxCell>
        <mxCell id="c_sem_router" value="Semantic Vector Router&#xa;(semantic_router.py)&#xa;Sub-10ms MoE Gating" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="30" y="50" width="160" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_conf_eng" value="Confidence Engine&#xa;(confidence.py)&#xa;Sim + Rec + Succ" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="210" y="50" width="150" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_conformal_pred" value="Conformal Predictor&#xa;(conformal_predictor.py)&#xa;TW-CRC 95% Risk Bounds" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="380" y="50" width="160" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_weight_reg" value="Weight Registry&#xa;(weight_registry.py)&#xa;Simplex Optimization" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="560" y="50" width="150" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="c_outcome_an" value="Outcome Analysis &amp; Negation&#xa;(outcome_analysis.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="110" y="140" width="220" height="50" as="geometry"/>
        </mxCell>
        <mxCell id="c_calib_met" value="Calibration Metrics (ECE, Brier)&#xa;(calibration_metrics.py)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;" vertex="1" parent="pkg_reasoning">
          <mxGeometry x="400" y="140" width="230" height="50" as="geometry"/>
        </mxCell>

        <!-- Deployment Nodes (Hardware & Services) -->
        <mxCell id="node_server" value="&amp;lt;&amp;lt;deployment node&amp;gt;&amp;gt;&#xa;MARS Application Server (FastAPI + Uvicorn)&#xa;Python 3.11 Runtime in .venv" style="shape=cube;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="840" y="60" width="320" height="230" as="geometry"/>
        </mxCell>
        <mxCell id="sub_langgraph" value="LangGraph StateMachine Runner" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#666666;" vertex="1" parent="node_server">
          <mxGeometry x="40" y="60" width="230" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="sub_torch" value="PyTorch + SentenceTransformers&#xa;(all-MiniLM-L6-v2 local cache)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#666666;" vertex="1" parent="node_server">
          <mxGeometry x="40" y="120" width="230" height="45" as="geometry"/>
        </mxCell>
        <mxCell id="sub_registry_file" value="calibrated_weights_registry.json" style="shape=note;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;" vertex="1" parent="node_server">
          <mxGeometry x="50" y="175" width="210" height="35" as="geometry"/>
        </mxCell>

        <!-- External Cloud Infrastructure -->
        <mxCell id="node_supabase" value="&amp;lt;&amp;lt;managed cloud&amp;gt;&amp;gt;&#xa;Supabase Cloud Database" style="shape=cube;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="840" y="340" width="320" height="180" as="geometry"/>
        </mxCell>
        <mxCell id="sub_pgvector" value="PostgreSQL 15 + pgvector&#xa;Table: decision_embeddings (1536d / 384d)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;" vertex="1" parent="node_supabase">
          <mxGeometry x="30" y="60" width="250" height="40" as="geometry"/>
        </mxCell>
        <mxCell id="sub_dataset_tables" value="Tables: decisions, outcomes, quantitative_signals&#xa;(2,080 historical SEC filings)" style="shape=rect;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;" vertex="1" parent="node_supabase">
          <mxGeometry x="30" y="115" width="250" height="45" as="geometry"/>
        </mxCell>

        <!-- Connections between Packages -->
        <mxCell id="dep1" edge="1" source="pkg_api" target="pkg_agents" parent="1" style="dashed=1;endArrow=open;strokeColor=#495057;strokeWidth=1.5;"/>
        <mxCell id="dep2" edge="1" source="pkg_agents" target="pkg_reasoning" parent="1" style="dashed=1;endArrow=open;strokeColor=#495057;strokeWidth=1.5;"/>
        <mxCell id="dep3" edge="1" source="pkg_agents" target="node_supabase" parent="1" style="dashed=1;endArrow=open;strokeColor=#27ae60;strokeWidth=2;"/>
        <mxCell id="dep4" edge="1" source="node_server" target="node_supabase" parent="1" style="strokeColor=#2980b9;strokeWidth=2;"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```
