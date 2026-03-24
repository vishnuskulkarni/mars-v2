import asyncio
import os
from backend.models import ResearchSession, AgentResult, AgentEvent, FeedbackEntry
from backend.file_handler import parse_all_pdfs, parse_all_data_files
from backend.agents.literature import LiteratureAgent
from backend.agents.data import DataAgent
from backend.agents.hypothesis import HypothesisAgent
from backend.agents.methods import MethodsAgent
from backend.agents.scout import ScoutAgent
from backend.agents.critique import CritiqueAgent
from backend.agents.synthesis import SynthesisAgent
from backend.agents.output import OutputAgent
from backend.utils.report_export import save_report_markdown
from backend.utils.plot_generator import generate_all_plots
from datetime import datetime


ALL_AGENTS = ["literature", "data", "hypothesis", "methods", "scout", "critique", "synthesis", "output"]
PHASE1_AGENTS = ["literature", "data", "hypothesis", "methods", "scout"]

# Downstream cascade: which agents need to re-run if a given agent is revised
DOWNSTREAM = {
    "literature": ["critique", "synthesis", "output"],
    "data": ["critique", "synthesis", "output"],
    "hypothesis": ["critique", "synthesis", "output"],
    "methods": ["critique", "synthesis", "output"],
    "scout": ["critique", "synthesis", "output"],
    "critique": ["synthesis", "output"],
    "synthesis": ["output"],
    "output": [],
}


def _extract_paper_titles(file_paths: list) -> str:
    """Extract filenames as paper title proxies."""
    titles = []
    for path in file_paths:
        name = os.path.splitext(os.path.basename(path))[0]
        titles.append(name.replace("_", " ").replace("-", " "))
    return "\n".join(titles) if titles else "No papers uploaded."


def _append_plot_references(agent_output: str, plots: list, session_id: str) -> str:
    """Append markdown image references to the data agent's output."""
    if not plots:
        return agent_output
    plot_md = "\n\n---\n### Generated Visualizations\n\n"
    for p in plots:
        plot_md += f"![{p['title']}](/api/plots/{session_id}/{p['filename']})\n\n"
    return agent_output + plot_md


async def _start_agent(session, name):
    session.agent_results[name].status = "running"
    session.agent_results[name].started_at = datetime.now()


async def _finish_agent(session, name, result):
    session.agent_results[name].output = result
    session.agent_results[name].status = "complete"
    session.agent_results[name].completed_at = datetime.now()


async def run_pipeline(session: ResearchSession, event_queue: asyncio.Queue):
    """Run the full 4-phase, 8-agent pipeline."""
    session.status = "running"

    for name in ALL_AGENTS:
        session.agent_results[name] = AgentResult(agent_name=name)

    try:
        # Parse uploaded files
        literature_text = parse_all_pdfs(session.literature_files)
        data_summary = parse_all_data_files(session.data_files)
        paper_titles = _extract_paper_titles(session.literature_files)
        question = session.research_question

        # Phase 1: Parallel (5 agents)
        lit_agent = LiteratureAgent()
        data_agent = DataAgent()
        hyp_agent = HypothesisAgent()
        methods_agent = MethodsAgent()
        scout_agent = ScoutAgent()

        for name in PHASE1_AGENTS:
            await _start_agent(session, name)

        lit_result, data_result, hyp_result, methods_result, scout_result = await asyncio.gather(
            lit_agent.run(literature_text, question, event_queue),
            data_agent.run(data_summary, question, event_queue),
            hyp_agent.run(literature_text, question, event_queue),
            methods_agent.run(data_summary, question, event_queue),
            scout_agent.run(paper_titles, question, event_queue),
        )

        await _finish_agent(session, "literature", lit_result)
        await _finish_agent(session, "data", data_result)
        await _finish_agent(session, "hypothesis", hyp_result)
        await _finish_agent(session, "methods", methods_result)
        await _finish_agent(session, "scout", scout_result)

        # Generate data visualizations
        if session.data_files:
            plots = generate_all_plots(session.data_files, data_result, session.session_id)
            data_result = _append_plot_references(data_result, plots, session.session_id)
            session.agent_results["data"].output = data_result

        # Phase 2: Critique
        critique_agent = CritiqueAgent()
        await _start_agent(session, "critique")
        critique_result = await critique_agent.run(
            {
                "literature": lit_result,
                "data": data_result,
                "hypothesis": hyp_result,
                "methods": methods_result,
                "scout": scout_result,
            },
            question, event_queue,
        )
        await _finish_agent(session, "critique", critique_result)

        # Phase 3: Synthesis
        synthesis_agent = SynthesisAgent()
        await _start_agent(session, "synthesis")
        synthesis_result = await synthesis_agent.run(
            {
                "literature": lit_result,
                "data": data_result,
                "hypothesis": hyp_result,
                "methods": methods_result,
                "scout": scout_result,
                "critique": critique_result,
            },
            question, event_queue,
        )
        await _finish_agent(session, "synthesis", synthesis_result)
        session.synthesis = synthesis_result

        # Phase 4: Output + Opportunity Map
        output_agent = OutputAgent()
        await _start_agent(session, "output")
        output_result = await output_agent.run(
            {
                "literature": lit_result,
                "data": data_result,
                "hypothesis": hyp_result,
                "methods": methods_result,
                "scout": scout_result,
                "critique": critique_result,
                "synthesis": synthesis_result,
            },
            question, event_queue,
        )
        await _finish_agent(session, "output", output_result)

        # Save report (use Output agent's result as the final report)
        save_report_markdown(session.session_id, output_result)

        session.status = "complete"
        await event_queue.put(AgentEvent(type="report_ready", session_id=session.session_id))

    except Exception as e:
        session.status = "error"
        await event_queue.put(AgentEvent(agent="pipeline", type="error", content=str(e)))


async def run_feedback(session: ResearchSession, agent_name: str, feedback: str, event_queue: asyncio.Queue):
    """Re-run an agent with feedback, then cascade downstream agents."""
    question = session.research_question
    previous_output = session.agent_results[agent_name].output or ""

    # Record feedback
    if agent_name not in session.feedback_history:
        session.feedback_history[agent_name] = []
    entry = FeedbackEntry(feedback=feedback, previous_output=previous_output)
    session.feedback_history[agent_name].append(entry)

    # Build revision prompt suffix
    revision_context = (
        f"\n\nHere is your previous analysis:\n{previous_output}\n\n"
        f"The researcher provided this feedback:\n{feedback}\n\n"
        f"Revise your analysis incorporating this feedback. "
        f"Clearly indicate what changed and why."
    )

    # Re-run the target agent
    agents_to_run = [agent_name] + DOWNSTREAM.get(agent_name, [])

    for name in agents_to_run:
        session.agent_results[name].status = "running"
        session.agent_results[name].started_at = datetime.now()

    # Instantiate agents
    agent_map = {
        "literature": LiteratureAgent,
        "data": DataAgent,
        "hypothesis": HypothesisAgent,
        "methods": MethodsAgent,
        "scout": ScoutAgent,
        "critique": CritiqueAgent,
        "synthesis": SynthesisAgent,
        "output": OutputAgent,
    }

    try:
        # Re-run the revised agent
        agent_cls = agent_map[agent_name]
        agent_instance = agent_cls()

        # Build context based on agent type
        if agent_name in PHASE1_AGENTS:
            # Phase 1 agents get their original context + revision prompt
            if agent_name == "literature":
                context = f"Literature provided:\n\n{parse_all_pdfs(session.literature_files)}" + revision_context
            elif agent_name == "data":
                context = f"Dataset summary:\n\n{parse_all_data_files(session.data_files)}" + revision_context
            elif agent_name == "hypothesis":
                context = f"Available evidence from literature:\n\n{parse_all_pdfs(session.literature_files)}" + revision_context
            elif agent_name == "methods":
                context = f"Dataset summary:\n\n{parse_all_data_files(session.data_files)}" + revision_context
            elif agent_name == "scout":
                context = f"Uploaded paper titles:\n{_extract_paper_titles(session.literature_files)}" + revision_context
            revised = await agent_instance.run(context, question, event_queue)
        else:
            # Downstream agents get all prior outputs + revision context
            outputs = {n: session.agent_results[n].output or "N/A" for n in ALL_AGENTS if session.agent_results.get(n)}
            if agent_name == "critique":
                agent_instance_typed = CritiqueAgent()
                # Append revision context to the normal context
                revised = await _run_with_revision(agent_instance_typed, outputs, question, event_queue, revision_context)
            elif agent_name == "synthesis":
                agent_instance_typed = SynthesisAgent()
                revised = await _run_with_revision(agent_instance_typed, outputs, question, event_queue, revision_context)
            elif agent_name == "output":
                agent_instance_typed = OutputAgent()
                revised = await _run_with_revision(agent_instance_typed, outputs, question, event_queue, revision_context)
            else:
                revised = previous_output

        session.agent_results[agent_name].output = revised
        session.agent_results[agent_name].status = "complete"
        session.agent_results[agent_name].completed_at = datetime.now()
        session.agent_results[agent_name].revision_count += 1
        entry.revised_output = revised

        # Cascade: re-run downstream agents normally (no revision context for them)
        downstream = DOWNSTREAM.get(agent_name, [])
        for ds_name in downstream:
            outputs = {n: session.agent_results[n].output or "N/A" for n in ALL_AGENTS if session.agent_results.get(n)}
            ds_agent = agent_map[ds_name]()
            ds_result = await ds_agent.run(outputs, question, event_queue)
            session.agent_results[ds_name].output = ds_result
            session.agent_results[ds_name].status = "complete"
            session.agent_results[ds_name].completed_at = datetime.now()

        # Update synthesis reference
        if session.agent_results.get("output") and session.agent_results["output"].output:
            save_report_markdown(session.session_id, session.agent_results["output"].output)

        session.status = "complete"
        await event_queue.put(AgentEvent(type="report_ready", session_id=session.session_id))

    except Exception as e:
        session.status = "error"
        await event_queue.put(AgentEvent(agent="pipeline", type="error", content=str(e)))


async def _run_with_revision(agent, outputs, question, event_queue, revision_context):
    """Helper to run a multi-input agent with revision context appended."""
    # Build normal context, then append revision
    if hasattr(agent, 'run'):
        # Temporarily modify the agent's system prompt to include revision instruction
        original_prompt = agent.system_prompt
        agent.system_prompt = original_prompt + revision_context
        result = await agent.run(outputs, question, event_queue)
        agent.system_prompt = original_prompt
        return result
    return ""
