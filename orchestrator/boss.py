import os
import json
from crewai import Task, Crew, Process
from agents.janitor import janitor, extract_raw_text
from agents.researcher import researcher
from agents.writer import writer
from errors import FileIngestionError, APIError, InvalidOutputError, AgentTimeoutError, PipelineError


def run_pipeline(input_filepath: str, output_dir: str = "data/clean", user_prompt: str = ""):
    """
    The full multi-agent pipeline.
    user_prompt: optional instructions from the user on how to organize/focus the output.
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n📂 Reading file: {input_filepath}")
    try:
        raw_text = extract_raw_text(input_filepath)
    except FileIngestionError as e:
        print(f"\n❌ FILE ERROR: {e}")
        return None

    print(f"✅ Extracted {len(raw_text)} characters of raw text.\n")

    # Build the user instruction block — injected into Janitor and Writer
    if user_prompt and user_prompt.strip():
        user_instruction = (
            f"\n\nSPECIAL INSTRUCTIONS FROM THE USER:\n"
            f"\"{user_prompt.strip()}\"\n"
            f"Follow these instructions carefully when organizing and presenting the output.\n"
        )
    else:
        user_instruction = ""

    # ------------------------------------------------------------------
    # Janitor task — clean + organize per user instructions
    # ------------------------------------------------------------------
    task_clean = Task(
        description=(
            f"You have been given the following raw data extracted from a file:\n\n"
            f"---\n{raw_text}\n---\n\n"
            "Please do the following:\n"
            "1. Identify any data quality issues (missing fields, bad formatting, duplicates).\n"
            "2. Clean and standardize the data.\n"
            "3. Organize the records according to any special instructions below.\n"
            "4. Return ONLY a valid JSON array of cleaned records. "
            "No explanation, no markdown, just raw JSON."
            f"{user_instruction}"
        ),
        expected_output="A valid JSON array of cleaned and organized records.",
        agent=janitor
    )

    # ------------------------------------------------------------------
    # Researcher task — analyze with user focus in mind
    # ------------------------------------------------------------------
    task_research = Task(
        description=(
            "You have received cleaned, structured data from the Data Janitor. "
            "Analyze it thoroughly and identify:\n"
            "1. Key patterns and trends\n"
            "2. Any anomalies or outliers\n"
            "3. Important statistics (totals, averages, distributions)\n"
            "4. Any correlations between fields\n\n"
            "Present your findings as a clear, numbered list of insights."
            f"{user_instruction}"
        ),
        expected_output="A numbered list of data insights and patterns.",
        agent=researcher,
        context=[task_clean]
    )

    # ------------------------------------------------------------------
    # Writer task — report tailored to user instructions
    # ------------------------------------------------------------------
    task_report = Task(
        description=(
            "You have received analytical findings from the Data Research Analyst. "
            "Write a professional business summary report with the following sections:\n\n"
            "1. **Executive Summary** — 2-3 sentences summarizing the data and purpose\n"
            "2. **Key Findings** — The most important insights in plain English\n"
            "3. **Recommendations** — 2-3 actionable next steps based on the findings\n\n"
            "Write for a non-technical business audience. Keep it concise and clear."
            f"{user_instruction}"
        ),
        expected_output="A professional business report in markdown format.",
        agent=writer,
        context=[task_research],
        output_file=os.path.join(output_dir, "report.md")
    )

    crew = Crew(
        agents=[janitor, researcher, writer],
        tasks=[task_clean, task_research, task_report],
        process=Process.sequential,
        verbose=True
    )

    print("🤖 Orchestrator starting the pipeline...\n")
    if user_prompt:
        print(f"📝 User instructions: {user_prompt}\n")
    print("Flow: Janitor → Researcher → Writer\n")
    print("-" * 50)

    try:
        result = crew.kickoff()
    except TimeoutError:
        raise AgentTimeoutError(
            "An agent timed out during the pipeline.\n"
            "Try reducing the input file size or increasing max_rpm in llm_config.py."
        )
    except Exception as e:
        error_msg = str(e).lower()
        if any(k in error_msg for k in ["404", "api", "quota", "rate limit", "authentication"]):
            raise APIError(
                f"Gemini API error during pipeline: {e}\n"
                f"Check your GOOGLE_API_KEY in .env and your API quota at console.cloud.google.com"
            )
        raise

    # Save and validate Janitor JSON output
    json_output_path = os.path.join(output_dir, "output.json")
    try:
        import re as _re
        raw_output = str(task_clean.output.raw).strip()
        _match = _re.search(r'(\[.*?\]|\{.*?\})', raw_output, _re.DOTALL)
        if _match:
            raw_output = _match.group(1).strip()
        else:
            raw_output = _re.sub(r'```[a-zA-Z]*', '', raw_output).strip('`').strip()
        clean_json = json.loads(raw_output)
        with open(json_output_path, "w") as f:
            json.dump(clean_json, f, indent=2)
        print(f"\n✅ Clean JSON saved to: {json_output_path}")
    except (json.JSONDecodeError, AttributeError):
        raise InvalidOutputError(
            "The Janitor agent did not return valid JSON.\n"
            "Try adding 'Return ONLY raw JSON, no markdown backticks' to the task prompt."
        )

    print(f"✅ Report saved to: {output_dir}/report.md")
    print("\n🎉 Pipeline complete!")
    return result
