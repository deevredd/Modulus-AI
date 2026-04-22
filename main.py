import sqlite3
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, interrupt

from state.state_definition import AgentState

# Import your agents and evaluator
from agents.researcher import Researcher
from agents.critic import Critic
from tests.evals.evaluator import run_technical_audit

# --- 2. PERSISTENCE LAYER ---
conn = sqlite3.connect("agent_memory.db", check_same_thread=False)
memory = SqliteSaver(conn)

# --- 3. AGENT INITIALIZATION ---
researcher = Researcher()
critic = Critic()

# --- 4. NEW: AUDITOR NODE ---
def audit_node(state: AgentState):
    """
    Automated Quality Gate: Rejects reports that are ungrounded or vague.
    """
    print("\n⚖️  Node: Auditor is verifying report integrity...")
    
    # Check if we have sources to verify against
    if not state.get("sources_text"):
        return {"critique": "Auditor failed: No source data found to verify.", "approved": False}

    current_test = {
        "query": state['query'],
        "critical_facts": "Ensuring technical metrics and claims are grounded in provided sources." 
    }
    
    # Run the DeepEval/Ragas audit
    results = run_technical_audit(
        agent_output=state['current_draft'],
        source_context=state['sources_text'],
        test_case=current_test
    )
    
    if not results['Pass']:
        print(f"⚠️  AUDIT FAILED (Score: {results['Faithfulness']}): Sending back for revision.")
        return {
            "critique": f"Low Faithfulness Score ({results['Faithfulness']}). Data points in the report do not match search results. Please re-verify metrics.",
            "approved": False,
            "revision_count": state.get("revision_count", 0) + 1
        }
    
    print(f"✅ AUDIT PASSED (Score: {results['Faithfulness']})")
    return {"approved": True} # This tells the graph the Auditor is satisfied

# --- 5. HUMAN APPROVAL NODE ---
def human_approval_node(state: AgentState):
    print("\n--- ⏸️  WAITING FOR HUMAN REVIEW ---")
    print(f"Auditor has cleared this draft. Turn {state.get('revision_count')}.")
    
    user_feedback = interrupt("Do you want to (A)pprove, (R)equest specific changes, or (E)xit?")
    
    if user_feedback.lower() == 'a':
        return {"approved": True}
    elif user_feedback.lower() == 'e':
        return {"approved": True, "exit_requested": True, "critique": "__USER_EXIT__"}
    else:
        return {"critique": f"HUMAN FEEDBACK: {user_feedback}", "approved": False}

# --- 6. BUILD THE GRAPH ---
builder = StateGraph(AgentState)

builder.add_node("researcher", researcher.run)
builder.add_node("critic", critic.run)
builder.add_node("auditor", audit_node)        # Added Auditor
builder.add_node("human_review", human_approval_node)

builder.set_entry_point("researcher")
builder.add_edge("researcher", "critic")
builder.add_edge("critic", "auditor")          # Critic sends to Auditor

def audit_router(state):
    # If Auditor failed (approved=False), go back to researcher
    if not state.get("approved"):
        return "revise"
    return "human"

builder.add_conditional_edges("auditor", audit_router, {"revise": "researcher", "human": "human_review"})

def final_router(state):
    # Only finish if human approves or we hit the revision cap
    if (
        state.get("approved")
        or state.get("revision_count", 0) >= 3
        or state.get("exit_requested")
    ):
        return "end"
    return "continue"

builder.add_conditional_edges("human_review", final_router, {"continue": "researcher", "end": END})

app = builder.compile(checkpointer=memory)

# --- 7. INTERACTIVE EXECUTION LOOP ---
def run_interactive():
    default_thread_id = "main_user_session"
    print("\n" + "="*50)
    print("🤖 2026 IEEE RESEARCH AGENT (WITH AUTO-AUDIT)")
    print("="*50)
    resume_choice = input("\nResume previous session? [Y/n]: ").strip().lower()
    if resume_choice in {"n", "no"}:
        thread_id = f"session_{int(time.time())}"
        print(f"🆕 Starting fresh session: {thread_id}")
    else:
        thread_id = default_thread_id
        print(f"📌 Using session: {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        state_snapshot = app.get_state(config)
        
        if state_snapshot.next:
            print("\n📬 RESUMING PREVIOUS TASK...")
            user_input = input("Your decision/feedback: ")
            inputs = Command(resume=user_input)
        else:
            user_query = input("\n🔍 What should I research today? ")
            if user_query.lower() in ["exit", "quit"]: break
            inputs = {
                "query": user_query,
                "revision_count": 0,
                "approved": False,
                "exit_requested": False,
                "sources_text": [],
            }

        for event in app.stream(inputs, config=config):
            for node, data in event.items():
                if "__interrupt__" in str(event): continue
                print(f"  └─ ⚙️  {node.capitalize()} is processing...")

        final_state = app.get_state(config)
        if final_state.values.get("exit_requested"):
            print("\n👋 Session ended by user.")
            break
        if not final_state.next and final_state.values.get("current_draft"):
            print("\n" + "✨" + "-"*48 + "✨")
            print(final_state.values.get("current_draft"))
            print("-"*50)

if __name__ == "__main__":
    run_interactive()