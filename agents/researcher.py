from agents.base_agent import BaseAgent
from tools.base_tool import search_internet, summarize_context_quality

class Researcher(BaseAgent):
    def run(self, state: dict):
        query = state["query"]
        feedback = state.get("critique", "")
        # Use existing revision count or start at 0
        revision_count = state.get("revision_count", 0) + 1
        
        # 1. OBSERVABILITY: IEEE-specific logging
        print(f"\n🌐 [IEEE Research Fellow] Turn {revision_count}")
        
        # 2. ENHANCED ACADEMIC SEARCH
        academic_search_query = (
            f"{query} datasheet whitepaper MPa \"ASTM standard\" 2026 "
            "-site:zhihu.com -site:reddit.com -site:quora.com "
            "site:ieeexplore.ieee.org OR site:sciencedirect.com OR site:mdpi.com OR site:arxiv.org"
        )
        print(f"   🔍 Harvesting technical datasets for: '{query}'")
        
        if feedback:
            print(f"   💡 Addressing Peer Review Feedback...")

        search_data = search_internet(academic_search_query)
        
        # Log tool success/fail transparency
        search_data_str = str(search_data)
        no_context_markers = (
            "Search engine error:",
            "No results found.",
            "No external datasets found.",
        )
        if not search_data or any(search_data_str.startswith(m) for m in no_context_markers):
            print("   ⚠️  Data gap detected. Utilizing heuristic analytical projections.")
            search_data = "No external datasets found."
        else:
            metrics = summarize_context_quality(search_data_str)
            print(
                "   ✅ Synthesized "
                f"{metrics['total_chars']} characters "
                f"({metrics['usable_chars']} usable, {metrics['fallback_chars']} fallback)."
            )

        # 3. IEEE SYSTEM INSTRUCTIONS
        system_instructions = """
        You are a Technical Research Fellow at the IEEE. Your goal is to produce a rigorous, peer-review-ready technical report.

        STRICT TECHNICAL SPECIFICATIONS:
        1. **Academic Structure**: TITLE, ABSTRACT, I. INTRODUCTION, II. METHODOLOGY, III. ANALYSIS, IV. SOCIO-TECHNICAL IMPACT, V. CONCLUSION, REFERENCES.
        2. **Quantitative Focus**: Prioritize hard data—dates, mechanical specifications, and metrics. 
        3. **Analytical Tone**: Use a passive, objective voice.
        4. **Expansive Content**: Provide deep, dense technical analysis.
        5. **No Structural Leaks**: Never mention 'search results', 'llm', or tool names.
        """

        # 4. DATA-DRIVEN PROMPT
        prompt = f"""
        {system_instructions}
        
        RESEARCH TOPIC: {query}
        PEER REVIEW FEEDBACK: {feedback if feedback else "Initial submission. Ensure broad coverage."}
        CURRENT REVISION: {revision_count}
        
        SOURCE CONTEXT: 
        {search_data}
        
        TASK: Synthesize the formal IEEE technical report.
        """
        
        print("   📊 Synthesizing formal research paper...")
        report = self.invoke_llm(prompt)
        
        # --- CRITICAL CHANGE FOR AUDITOR ---
        # We return 'sources_text' as a list so the Auditor can cross-verify 
        # the claims in the report against the raw search_data.
        return {
            "current_draft": report, 
            "revision_count": revision_count,
            "sources_text": [search_data] # This feeds the 'Annotated' list in main.py
        }