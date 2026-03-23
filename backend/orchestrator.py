import asyncio
from backend.models import ResearchSession, AgentResult, AgentEvent
from backend.file_handler import parse_all_pdfs, parse_all_data_files
from backend.agents.literature import LiteratureAgent
from backend.agents.data import DataAgent
from backend.agents.hypothesis import HypothesisAgent
from backend.agents.critique import CritiqueAgent
from backend.agents.synthesis import SynthesisAgent
from backend.utils.report_export import save_report_markdown
from datetime import datetime


async def run_pipeline(session: ResearchSession, event_queue: asyncio.Queue):
    """Run the full multi-agent pipeline for a research session."""
    session.status = "running"

    # Initialize agent results
    for agent_name in ["literature", "data", "hypothesis", "critique", "synthesis"]:
        session.agent_results[agent_name] = AgentResult(agent_name=agent_name)

    try:
        # Parse uploaded files
        literature_text = parse_all_pdfs(session.literature_files)
        data_summary = parse_all_data_files(session.data_files)
        question = session.research_question

        # Phase 1: Run Literature, Data, and Hypothesis agents in parallel
        lit_agent = LiteratureAgent()
        data_agent = DataAgent()
        hyp_agent = HypothesisAgent()

        session.agent_results["literature"].status = "running"
        session.agent_results["literature"].started_at = datetime.now()
        session.agent_results["data"].status = "running"
        session.agent_results["data"].started_at = datetime.now()
        session.agent_results["hypothesis"].status = "running"
        session.agent_results["hypothesis"].started_at = datetime.now()

        lit_result, data_result, hyp_result = await asyncio.gather(
            lit_agent.run(literature_text, question, event_queue),
            data_agent.run(data_summary, question, event_queue),
            hyp_agent.run(literature_text, question, event_queue),
        )

        # Store Phase 1 results
        session.agent_results["literature"].output = lit_result
        session.agent_results["literature"].status = "complete"
        session.agent_results["literature"].completed_at = datetime.now()

        session.agent_results["data"].output = data_result
        session.agent_results["data"].status = "complete"
        session.agent_results["data"].completed_at = datetime.now()

        session.agent_results["hypothesis"].output = hyp_result
        session.agent_results["hypothesis"].status = "complete"
        session.agent_results["hypothesis"].completed_at = datetime.now()

        # Phase 2: Critique agent (needs all Phase 1 outputs)
        critique_agent = CritiqueAgent()
        session.agent_results["critique"].status = "running"
        session.agent_results["critique"].started_at = datetime.now()

        critique_result = await critique_agent.run(
            {"literature": lit_result, "data": data_result, "hypothesis": hyp_result},
            question,
            event_queue,
        )

        session.agent_results["critique"].output = critique_result
        session.agent_results["critique"].status = "complete"
        session.agent_results["critique"].completed_at = datetime.now()

        # Phase 3: Synthesis agent (needs everything)
        synthesis_agent = SynthesisAgent()
        session.agent_results["synthesis"].status = "running"
        session.agent_results["synthesis"].started_at = datetime.now()

        synthesis_result = await synthesis_agent.run(
            {
                "literature": lit_result,
                "data": data_result,
                "hypothesis": hyp_result,
                "critique": critique_result,
            },
            question,
            event_queue,
        )

        session.agent_results["synthesis"].output = synthesis_result
        session.agent_results["synthesis"].status = "complete"
        session.agent_results["synthesis"].completed_at = datetime.now()
        session.synthesis = synthesis_result

        # Save report
        save_report_markdown(session.session_id, synthesis_result)

        # Signal completion
        session.status = "complete"
        await event_queue.put(AgentEvent(
            type="report_ready", session_id=session.session_id
        ))

    except Exception as e:
        session.status = "error"
        await event_queue.put(AgentEvent(
            agent="pipeline", type="error", content=str(e)
        ))
