from agents.base_agent import BaseAgent

class Critic(BaseAgent):
    def run(self, state: dict):
        draft = state["current_draft"]
        print("🔍 Critic: Reviewing the latest draft...")
        
        prompt = f"""
        Review the following research report:
        {draft}
        
        If the report is comprehensive, has citations, and is well-formatted, respond ONLY with 'APPROVED'.
        Otherwise, provide a bulleted list of what is missing or needs fixing.
        """
        
        feedback = self.invoke_llm(prompt)
        
        if "APPROVED" in feedback.upper():
            return {"approved": True, "critique": ""}
        return {"approved": False, "critique": feedback}